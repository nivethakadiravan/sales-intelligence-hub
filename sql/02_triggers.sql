-- =====================================================================
-- Sales Intelligence Hub - Triggers
-- received_amount in customer_sales is NEVER updated by hand.
-- It is recalculated from payment_splits by the triggers below, and
-- pending_amount (a generated column) follows automatically.
-- =====================================================================

USE sales_management_system;

DROP TRIGGER IF EXISTS trg_payment_before_insert;
DROP TRIGGER IF EXISTS trg_payment_after_insert;
DROP TRIGGER IF EXISTS trg_payment_after_update;
DROP TRIGGER IF EXISTS trg_payment_after_delete;
DROP TRIGGER IF EXISTS trg_sales_block_manual_received;

DELIMITER $$

-- ---------------------------------------------------------------------
-- Guard: reject a payment that would exceed the sale's pending amount
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_payment_before_insert
BEFORE INSERT ON payment_splits
FOR EACH ROW
BEGIN
    DECLARE v_pending DECIMAL(12,2);

    SELECT pending_amount INTO v_pending
    FROM customer_sales
    WHERE sale_id = NEW.sale_id;

    IF v_pending IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Sale does not exist';
    END IF;

    IF NEW.amount_paid > v_pending THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Payment exceeds pending amount for this sale';
    END IF;
END$$

-- ---------------------------------------------------------------------
-- Main trigger (required): AFTER INSERT on payment_splits
--   1. Calculate total amount_paid for the sale
--   2. Update received_amount in customer_sales
--   3. pending_amount adjusts automatically (generated column)
--   4. Status becomes 'Close' once the sale is fully paid
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_payment_after_insert
AFTER INSERT ON payment_splits
FOR EACH ROW
BEGIN
    DECLARE v_total DECIMAL(12,2);

    SELECT COALESCE(SUM(amount_paid), 0) INTO v_total
    FROM payment_splits
    WHERE sale_id = NEW.sale_id;

    SET @allow_received_update = 1;
    UPDATE customer_sales
    SET received_amount = v_total,
        status = IF(v_total >= gross_sales, 'Close', 'Open')
    WHERE sale_id = NEW.sale_id;
    SET @allow_received_update = 0;
END$$

-- ---------------------------------------------------------------------
-- Keep totals correct if a payment is corrected...
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_payment_after_update
AFTER UPDATE ON payment_splits
FOR EACH ROW
BEGIN
    SET @allow_received_update = 1;

    -- old sale (in case the payment was moved to another sale)
    UPDATE customer_sales cs
    SET cs.received_amount = (SELECT COALESCE(SUM(p.amount_paid), 0)
                              FROM payment_splits p
                              WHERE p.sale_id = OLD.sale_id),
        cs.status = IF(cs.received_amount >= cs.gross_sales, 'Close', 'Open')
    WHERE cs.sale_id = OLD.sale_id;

    -- new sale
    UPDATE customer_sales cs
    SET cs.received_amount = (SELECT COALESCE(SUM(p.amount_paid), 0)
                              FROM payment_splits p
                              WHERE p.sale_id = NEW.sale_id),
        cs.status = IF(cs.received_amount >= cs.gross_sales, 'Close', 'Open')
    WHERE cs.sale_id = NEW.sale_id;

    SET @allow_received_update = 0;
END$$

-- ---------------------------------------------------------------------
-- ...or deleted.
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_payment_after_delete
AFTER DELETE ON payment_splits
FOR EACH ROW
BEGIN
    SET @allow_received_update = 1;
    UPDATE customer_sales cs
    SET cs.received_amount = (SELECT COALESCE(SUM(p.amount_paid), 0)
                              FROM payment_splits p
                              WHERE p.sale_id = OLD.sale_id),
        cs.status = IF(cs.received_amount >= cs.gross_sales, 'Close', 'Open')
    WHERE cs.sale_id = OLD.sale_id;
    SET @allow_received_update = 0;
END$$

-- ---------------------------------------------------------------------
-- Guard: block any manual UPDATE of received_amount.
-- Only the payment_splits triggers above (which set the session flag)
-- are allowed to change it.
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_sales_block_manual_received
BEFORE UPDATE ON customer_sales
FOR EACH ROW
BEGIN
    IF NEW.received_amount <> OLD.received_amount
       AND COALESCE(@allow_received_update, 0) <> 1 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'received_amount is managed by payment_splits triggers and cannot be updated manually';
    END IF;
END$$

DELIMITER ;
