-- =====================================================================
-- Sales Intelligence Hub - 20 Analytical SQL Queries
-- (generated from src/queries.py by scripts/export_queries.py)
-- =====================================================================

USE sales_management_system;

-- ---------------------------------------------------------------------
-- Basic Queries
-- ---------------------------------------------------------------------

-- Q1. Retrieve all records from the customer_sales table.
SELECT * FROM customer_sales cs ORDER BY cs.sale_id;

-- Q2. Retrieve all records from the branches table.
SELECT * FROM branches b ORDER BY b.branch_id;

-- Q3. Retrieve all records from the payment_splits table.
SELECT * FROM payment_splits ps ORDER BY ps.payment_id;

-- Q4. Display all sales with status = 'Open'.
SELECT * FROM customer_sales cs WHERE cs.status = 'Open' ORDER BY cs.date;

-- Q5. Retrieve all sales belonging to the Chennai branch.
SELECT cs.*
FROM customer_sales cs
JOIN branches b ON b.branch_id = cs.branch_id
WHERE b.branch_name = 'Chennai'
ORDER BY cs.date;

-- ---------------------------------------------------------------------
-- Aggregation Queries
-- ---------------------------------------------------------------------

-- Q6. Calculate the total gross sales across all branches.
SELECT SUM(cs.gross_sales) AS total_gross_sales FROM customer_sales cs;

-- Q7. Calculate the total received amount across all sales.
SELECT SUM(cs.received_amount) AS total_received_amount FROM customer_sales cs;

-- Q8. Calculate the total pending amount across all sales.
SELECT SUM(cs.pending_amount) AS total_pending_amount FROM customer_sales cs;

-- Q9. Count the total number of sales per branch.
SELECT b.branch_name, COUNT(cs.sale_id) AS total_sales
FROM branches b
LEFT JOIN customer_sales cs ON cs.branch_id = b.branch_id
GROUP BY b.branch_id, b.branch_name
ORDER BY total_sales DESC;

-- Q10. Find the average gross sales amount.
SELECT ROUND(AVG(cs.gross_sales), 2) AS average_gross_sales FROM customer_sales cs;

-- ---------------------------------------------------------------------
-- Join-Based Queries
-- ---------------------------------------------------------------------

-- Q11. Retrieve sales details along with the branch name.
SELECT cs.sale_id, cs.date, b.branch_name, cs.name, cs.mobile_number,
       cs.product_name, cs.gross_sales, cs.received_amount,
       cs.pending_amount, cs.status
FROM customer_sales cs
JOIN branches b ON b.branch_id = cs.branch_id
ORDER BY cs.sale_id;

-- Q12. Retrieve sales details along with total payment received (using payment_splits).
SELECT cs.sale_id, cs.name, cs.product_name, cs.gross_sales,
       COALESCE(SUM(ps.amount_paid), 0) AS total_paid_from_splits,
       COUNT(ps.payment_id)            AS no_of_payments,
       cs.pending_amount, cs.status
FROM customer_sales cs
LEFT JOIN payment_splits ps ON ps.sale_id = cs.sale_id
GROUP BY cs.sale_id, cs.name, cs.product_name, cs.gross_sales,
         cs.pending_amount, cs.status
ORDER BY cs.sale_id;

-- Q13. Show branch-wise total gross sales (using JOIN & GROUP BY).
SELECT b.branch_name,
       COUNT(cs.sale_id)                   AS total_sales,
       COALESCE(SUM(cs.gross_sales), 0)    AS total_gross_sales
FROM branches b
JOIN customer_sales cs ON cs.branch_id = b.branch_id
GROUP BY b.branch_id, b.branch_name
ORDER BY total_gross_sales DESC;

-- Q14. Display sales along with payment method used.
SELECT cs.sale_id, cs.name, cs.product_name, ps.payment_id,
       ps.payment_date, ps.amount_paid, ps.payment_method
FROM customer_sales cs
JOIN payment_splits ps ON ps.sale_id = cs.sale_id
ORDER BY cs.sale_id, ps.payment_date;

-- Q15. Retrieve sales along with branch admin name.
SELECT cs.sale_id, cs.date, cs.name, cs.product_name, cs.gross_sales,
       b.branch_name, b.branch_admin_name
FROM customer_sales cs
JOIN branches b ON b.branch_id = cs.branch_id
ORDER BY cs.sale_id;

-- ---------------------------------------------------------------------
-- Financial Tracking Queries
-- ---------------------------------------------------------------------

-- Q16. Find sales where the pending amount is greater than 5000.
SELECT cs.sale_id, cs.date, cs.name, cs.mobile_number, cs.product_name,
       cs.gross_sales, cs.received_amount, cs.pending_amount
FROM customer_sales cs
WHERE cs.pending_amount > 5000
ORDER BY cs.pending_amount DESC;

-- Q17. Retrieve top 3 highest gross sales.
SELECT cs.sale_id, cs.date, cs.name, cs.product_name, cs.gross_sales
FROM customer_sales cs
ORDER BY cs.gross_sales DESC, cs.date ASC
LIMIT 3;

-- Q18. Find the branch with highest total gross sales.
SELECT b.branch_name, SUM(cs.gross_sales) AS total_gross_sales
FROM customer_sales cs
JOIN branches b ON b.branch_id = cs.branch_id
GROUP BY b.branch_id, b.branch_name
ORDER BY total_gross_sales DESC
LIMIT 1;

-- Q19. Retrieve monthly sales summary (group by month & year).
SELECT YEAR(cs.date)               AS year,
       MONTH(cs.date)              AS month,
       DATE_FORMAT(MIN(cs.date), '%b %Y') AS month_name,
       COUNT(*)                    AS total_sales,
       SUM(cs.gross_sales)         AS gross_sales,
       SUM(cs.received_amount)     AS received_amount,
       SUM(cs.pending_amount)      AS pending_amount
FROM customer_sales cs
GROUP BY YEAR(cs.date), MONTH(cs.date)
ORDER BY year, month;

-- Q20. Calculate payment method-wise total collection (Cash / UPI / Card).
SELECT ps.payment_method,
       COUNT(*)            AS no_of_payments,
       SUM(ps.amount_paid) AS total_collection
FROM payment_splits ps
GROUP BY ps.payment_method
ORDER BY total_collection DESC;
