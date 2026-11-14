-- =====================================================================
-- Sales Intelligence Hub - Database Schema
-- Target: MySQL 8.0.16+ (also tested on MariaDB 10.11)
-- =====================================================================

DROP DATABASE IF EXISTS sales_management_system;
CREATE DATABASE sales_management_system
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE sales_management_system;

-- ---------------------------------------------------------------------
-- 1. branches : one row per business branch
-- ---------------------------------------------------------------------
CREATE TABLE branches (
    branch_id          INT AUTO_INCREMENT PRIMARY KEY,
    branch_name        VARCHAR(100) NOT NULL,
    branch_admin_name  VARCHAR(100) NOT NULL,
    CONSTRAINT uq_branch_name UNIQUE (branch_name)
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- 2. customer_sales : main financial table
--    received_amount  -> maintained ONLY by triggers on payment_splits
--    pending_amount   -> generated column (gross_sales - received_amount)
-- ---------------------------------------------------------------------
CREATE TABLE customer_sales (
    sale_id          INT AUTO_INCREMENT PRIMARY KEY,
    branch_id        INT NOT NULL,
    date             DATE NOT NULL,
    name             VARCHAR(100) NOT NULL,
    mobile_number    VARCHAR(15)  NOT NULL,
    product_name     VARCHAR(30)  NOT NULL,
    gross_sales      DECIMAL(12,2) NOT NULL,
    received_amount  DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    pending_amount   DECIMAL(12,2)
                     GENERATED ALWAYS AS (gross_sales - received_amount) STORED,
    status           ENUM('Open','Close') NOT NULL DEFAULT 'Open',

    CONSTRAINT fk_sales_branch
        FOREIGN KEY (branch_id) REFERENCES branches (branch_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT uq_sales_mobile    UNIQUE (mobile_number),
    CONSTRAINT chk_product        CHECK (product_name IN ('DS','DA','BA','FSD')),
    CONSTRAINT chk_gross_positive CHECK (gross_sales > 0),
    CONSTRAINT chk_received_range CHECK (received_amount >= 0 AND received_amount <= gross_sales),
    CONSTRAINT chk_mobile_digits  CHECK (mobile_number REGEXP '^[0-9]{10,15}$')
) ENGINE = InnoDB;

-- Indexes for the most common filters / joins in the dashboard
CREATE INDEX idx_sales_branch_date ON customer_sales (branch_id, date);
CREATE INDEX idx_sales_status      ON customer_sales (status);
CREATE INDEX idx_sales_date        ON customer_sales (date);

-- ---------------------------------------------------------------------
-- 3. users : login accounts (Super Admin / Admin)
--    password stores a salted PBKDF2-SHA256 hash, never plain text.
--    Super Admin is not tied to a branch, so branch_id is nullable,
--    but every Admin must have one. (MySQL does not allow a CHECK on a
--    column used by a cascading foreign key, so the app enforces this.)
-- ---------------------------------------------------------------------
CREATE TABLE users (
    user_id    INT AUTO_INCREMENT PRIMARY KEY,
    username   VARCHAR(100) NOT NULL,
    password   VARCHAR(255) NOT NULL,
    branch_id  INT NULL,
    role       ENUM('Super Admin','Admin') NOT NULL DEFAULT 'Admin',
    email      VARCHAR(255) NOT NULL,

    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT uq_users_email    UNIQUE (email),
    CONSTRAINT fk_users_branch
        FOREIGN KEY (branch_id) REFERENCES branches (branch_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE = InnoDB;

-- ---------------------------------------------------------------------
-- 4. payment_splits : one sale can be paid in many instalments
-- ---------------------------------------------------------------------
CREATE TABLE payment_splits (
    payment_id      INT AUTO_INCREMENT PRIMARY KEY,
    sale_id         INT NOT NULL,
    payment_date    DATE NOT NULL,
    amount_paid     DECIMAL(12,2) NOT NULL,
    payment_method  VARCHAR(50) NOT NULL,

    CONSTRAINT fk_payment_sale
        FOREIGN KEY (sale_id) REFERENCES customer_sales (sale_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT chk_amount_positive CHECK (amount_paid > 0),
    CONSTRAINT chk_payment_method  CHECK (payment_method IN ('Cash','UPI','Card'))
) ENGINE = InnoDB;

CREATE INDEX idx_payment_sale   ON payment_splits (sale_id);
CREATE INDEX idx_payment_method ON payment_splits (payment_method);
