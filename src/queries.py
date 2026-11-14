"""The 20 predefined analytical SQL queries used by the dashboard.

Each query is written against three table tokens:

    {cs}  -> customer_sales
    {br}  -> branches
    {ps}  -> payment_splits

For a Super Admin the tokens become the plain table names. For an Admin
they become sub-queries filtered to the admin's branch, so the *same* query
automatically returns branch-only data - role-based access is enforced in
SQL, not by filtering in Python afterwards.

``sql/04_analysis_queries.sql`` is generated from this file
(``python scripts/export_queries.py``) so both always stay in sync.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Query:
    category: str
    question: str
    sql: str


QUERIES: list[Query] = [
    # ------------------------------------------------------------ Basic
    Query("Basic", "Retrieve all records from the customer_sales table.",
          "SELECT * FROM {cs} cs ORDER BY cs.sale_id;"),
    Query("Basic", "Retrieve all records from the branches table.",
          "SELECT * FROM {br} b ORDER BY b.branch_id;"),
    Query("Basic", "Retrieve all records from the payment_splits table.",
          "SELECT * FROM {ps} ps ORDER BY ps.payment_id;"),
    Query("Basic", "Display all sales with status = 'Open'.",
          "SELECT * FROM {cs} cs WHERE cs.status = 'Open' ORDER BY cs.date;"),
    Query("Basic", "Retrieve all sales belonging to the Chennai branch.",
          """SELECT cs.*
FROM {cs} cs
JOIN {br} b ON b.branch_id = cs.branch_id
WHERE b.branch_name = 'Chennai'
ORDER BY cs.date;"""),

    # ------------------------------------------------------------ Aggregation
    Query("Aggregation", "Calculate the total gross sales across all branches.",
          "SELECT SUM(cs.gross_sales) AS total_gross_sales FROM {cs} cs;"),
    Query("Aggregation", "Calculate the total received amount across all sales.",
          "SELECT SUM(cs.received_amount) AS total_received_amount FROM {cs} cs;"),
    Query("Aggregation", "Calculate the total pending amount across all sales.",
          "SELECT SUM(cs.pending_amount) AS total_pending_amount FROM {cs} cs;"),
    Query("Aggregation", "Count the total number of sales per branch.",
          """SELECT b.branch_name, COUNT(cs.sale_id) AS total_sales
FROM {br} b
LEFT JOIN {cs} cs ON cs.branch_id = b.branch_id
GROUP BY b.branch_id, b.branch_name
ORDER BY total_sales DESC;"""),
    Query("Aggregation", "Find the average gross sales amount.",
          "SELECT ROUND(AVG(cs.gross_sales), 2) AS average_gross_sales FROM {cs} cs;"),

    # ------------------------------------------------------------ Join-based
    Query("Join", "Retrieve sales details along with the branch name.",
          """SELECT cs.sale_id, cs.date, b.branch_name, cs.name, cs.mobile_number,
       cs.product_name, cs.gross_sales, cs.received_amount,
       cs.pending_amount, cs.status
FROM {cs} cs
JOIN {br} b ON b.branch_id = cs.branch_id
ORDER BY cs.sale_id;"""),
    Query("Join", "Retrieve sales details along with total payment received (using payment_splits).",
          """SELECT cs.sale_id, cs.name, cs.product_name, cs.gross_sales,
       COALESCE(SUM(ps.amount_paid), 0) AS total_paid_from_splits,
       COUNT(ps.payment_id)            AS no_of_payments,
       cs.pending_amount, cs.status
FROM {cs} cs
LEFT JOIN {ps} ps ON ps.sale_id = cs.sale_id
GROUP BY cs.sale_id, cs.name, cs.product_name, cs.gross_sales,
         cs.pending_amount, cs.status
ORDER BY cs.sale_id;"""),
    Query("Join", "Show branch-wise total gross sales (using JOIN & GROUP BY).",
          """SELECT b.branch_name,
       COUNT(cs.sale_id)                   AS total_sales,
       COALESCE(SUM(cs.gross_sales), 0)    AS total_gross_sales
FROM {br} b
JOIN {cs} cs ON cs.branch_id = b.branch_id
GROUP BY b.branch_id, b.branch_name
ORDER BY total_gross_sales DESC;"""),
    Query("Join", "Display sales along with payment method used.",
          """SELECT cs.sale_id, cs.name, cs.product_name, ps.payment_id,
       ps.payment_date, ps.amount_paid, ps.payment_method
FROM {cs} cs
JOIN {ps} ps ON ps.sale_id = cs.sale_id
ORDER BY cs.sale_id, ps.payment_date;"""),
    Query("Join", "Retrieve sales along with branch admin name.",
          """SELECT cs.sale_id, cs.date, cs.name, cs.product_name, cs.gross_sales,
       b.branch_name, b.branch_admin_name
FROM {cs} cs
JOIN {br} b ON b.branch_id = cs.branch_id
ORDER BY cs.sale_id;"""),

    # ------------------------------------------------------------ Financial
    Query("Financial", "Find sales where the pending amount is greater than 5000.",
          """SELECT cs.sale_id, cs.date, cs.name, cs.mobile_number, cs.product_name,
       cs.gross_sales, cs.received_amount, cs.pending_amount
FROM {cs} cs
WHERE cs.pending_amount > 5000
ORDER BY cs.pending_amount DESC;"""),
    Query("Financial", "Retrieve top 3 highest gross sales.",
          """SELECT cs.sale_id, cs.date, cs.name, cs.product_name, cs.gross_sales
FROM {cs} cs
ORDER BY cs.gross_sales DESC, cs.date ASC
LIMIT 3;"""),
    Query("Financial", "Find the branch with highest total gross sales.",
          """SELECT b.branch_name, SUM(cs.gross_sales) AS total_gross_sales
FROM {cs} cs
JOIN {br} b ON b.branch_id = cs.branch_id
GROUP BY b.branch_id, b.branch_name
ORDER BY total_gross_sales DESC
LIMIT 1;"""),
    Query("Financial", "Retrieve monthly sales summary (group by month & year).",
          """SELECT YEAR(cs.date)               AS year,
       MONTH(cs.date)              AS month,
       DATE_FORMAT(MIN(cs.date), '%b %Y') AS month_name,
       COUNT(*)                    AS total_sales,
       SUM(cs.gross_sales)         AS gross_sales,
       SUM(cs.received_amount)     AS received_amount,
       SUM(cs.pending_amount)      AS pending_amount
FROM {cs} cs
GROUP BY YEAR(cs.date), MONTH(cs.date)
ORDER BY year, month;"""),
    Query("Financial", "Calculate payment method-wise total collection (Cash / UPI / Card).",
          """SELECT ps.payment_method,
       COUNT(*)            AS no_of_payments,
       SUM(ps.amount_paid) AS total_collection
FROM {ps} ps
GROUP BY ps.payment_method
ORDER BY total_collection DESC;"""),
]


def scoped_tables(branch_id: int | None) -> dict[str, str]:
    """Return table-token replacements for the given access scope."""
    if branch_id is None:  # Super Admin: everything
        return {"cs": "customer_sales", "br": "branches", "ps": "payment_splits"}
    return {
        "cs": "(SELECT * FROM customer_sales WHERE branch_id = %(bid)s)",
        "br": "(SELECT * FROM branches WHERE branch_id = %(bid)s)",
        "ps": "(SELECT p.* FROM payment_splits p "
              "JOIN customer_sales s ON s.sale_id = p.sale_id "
              "WHERE s.branch_id = %(bid)s)",
    }


def render(query: Query, branch_id: int | None) -> tuple[str, dict]:
    """Return (sql, params) ready for cursor.execute for this user scope."""
    sql = query.sql.format(**scoped_tables(branch_id))
    # Named (dict) parameters: the driver only substitutes %(bid)s, so
    # literal '%' (e.g. in DATE_FORMAT) needs no escaping.
    return sql, {"bid": branch_id}


def plain_sql(query: Query) -> str:
    """Human-readable SQL (no driver escaping) for display / export."""
    return query.sql.format(**scoped_tables(None))
