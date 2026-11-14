# 📊 Sales Intelligence Hub

A branch-based **Sales Management & Financial Tracking System** built with **MySQL**, **Python** and **Streamlit**.

It stores branch-wise sales, supports split (instalment) payments, and uses **database triggers** and a **generated column** so that received and pending amounts are always calculated by the database. No one updates them by hand. A role-based Streamlit dashboard gives Super Admins a view across all branches and gives each branch Admin a view of their own branch.

**Domain:** Sales Analytics & Financial Tracking  
**Skills:** Python · MySQL database design · SQL queries & aggregations · Triggers & generated columns · Streamlit · Payment tracking logic · Relational database management

---

## Table of contents
1. [Features](#features)
2. [Project structure](#project-structure)
3. [Database design](#database-design)
4. [Automation logic (triggers)](#automation-logic-triggers)
5. [Setup & run](#setup--run)
6. [Demo logins](#demo-logins)
7. [Streamlit dashboard](#streamlit-dashboard)
8. [SQL analytical queries](#sql-analytical-queries)
9. [Business insights (sample data)](#business-insights-sample-data)
10. [Design decisions](#design-decisions)

---

## Features

- **Normalized MySQL schema** with 4 related tables, plus primary keys, foreign keys, UNIQUE, ENUM and CHECK constraints, and indexes
- **Generated column**: `pending_amount = gross_sales - received_amount` (STORED)
- **Triggers on `payment_splits`** recalculate `received_amount` and auto-close a sale once it is fully paid
- **Guard triggers**: they block overpayments and any manual update of `received_amount`
- **Secure login**: salted PBKDF2-SHA256 password hashes, session-based auth and logout
- **Role-based access control**: the Super Admin sees and creates data for all branches; an Admin sees and creates data only for their own branch (enforced in SQL)
- **Dashboard**: KPIs, branch comparison, sales trend & growth, payment-method analysis, branch performance summary and auto-generated insights
- **Forms** to add sales and payment splits, with validation
- **Reports**: a filterable sales report (branch, status, product, date, search) with CSV export, pending payments with ageing, and a payment-method summary
- **All 20 predefined SQL queries** can be run from the UI

## Project structure

```
sales-intelligence-hub/
├── app.py                        # Streamlit dashboard (entry point)
├── src/
│   ├── db.py                     # Python ↔ MySQL connection helpers
│   ├── auth.py                   # Password hashing + login validation
│   └── queries.py                # 20 predefined analytical queries (role-scoped)
├── sql/
│   ├── 01_schema.sql             # Database, tables, keys, constraints, generated column
│   ├── 02_triggers.sql           # Payment triggers + guard triggers
│   ├── 03_sample_data.sql        # Demo data: 6 branches, 7 users, 150 sales, 300 payments
│   └── 04_analysis_queries.sql   # The 20 SQL questions with answers
├── scripts/
│   ├── setup_db.py               # Runs 01 → 03 from Python (one command)
│   ├── generate_sample_data.py   # Regenerates 03_sample_data.sql
│   └── export_queries.py         # Regenerates 04_analysis_queries.sql from src/queries.py
├── .streamlit/config.toml        # Theme
├── .env.example                  # DB connection settings template
└── requirements.txt
```

## Database design

Database: **`sales_management_system`**

```
branches (1) ──< (many) customer_sales (1) ──< (many) payment_splits
    │
    └──< (many) users
```

### `branches`
| Column | Type | Notes |
|---|---|---|
| branch_id | INT PK AUTO_INCREMENT | |
| branch_name | VARCHAR(100) | UNIQUE (e.g. Chennai, Delhi) |
| branch_admin_name | VARCHAR(100) | |

### `customer_sales` (main financial table)
| Column | Type | Notes |
|---|---|---|
| sale_id | INT PK AUTO_INCREMENT | |
| branch_id | INT FK → branches | |
| date | DATE | Sale date |
| name | VARCHAR(100) | Customer name |
| mobile_number | VARCHAR(15) | **UNIQUE**, 10–15 digits (CHECK) |
| product_name | VARCHAR(30) | CHECK in (DS, DA, BA, FSD) |
| gross_sales | DECIMAL(12,2) | CHECK > 0 |
| received_amount | DECIMAL(12,2) | **Maintained only by triggers** |
| pending_amount | DECIMAL(12,2) | **Generated**: `gross_sales - received_amount` |
| status | ENUM('Open','Close') | Set to `Close` by the trigger when fully paid |

### `users`
| Column | Type | Notes |
|---|---|---|
| user_id | INT PK AUTO_INCREMENT | |
| username | VARCHAR(100) | UNIQUE |
| password | VARCHAR(255) | Salted PBKDF2-SHA256 hash (never plain text) |
| branch_id | INT FK → branches | NULL for the Super Admin |
| role | ENUM('Super Admin','Admin') | |
| email | VARCHAR(255) | **UNIQUE** |

### `payment_splits`
| Column | Type | Notes |
|---|---|---|
| payment_id | INT PK AUTO_INCREMENT | |
| sale_id | INT FK → customer_sales | Many payments per sale |
| payment_date | DATE | |
| amount_paid | DECIMAL(12,2) | CHECK > 0 |
| payment_method | VARCHAR(50) | CHECK in (Cash, UPI, Card) |

**Normalization:** the schema is in 3NF. Branch details live only in `branches`. Each sale stores only `branch_id`, and each payment stores only `sale_id`. `received_amount` is a controlled aggregate kept in sync by triggers. It is denormalized on purpose so that reporting stays fast, which the project brief requires.

## Automation logic (triggers)

Defined in [`sql/02_triggers.sql`](sql/02_triggers.sql):

| Trigger | Event | What it does |
|---|---|---|
| `trg_payment_before_insert` | BEFORE INSERT on payment_splits | Rejects a payment for a missing sale, or one larger than the pending amount |
| **`trg_payment_after_insert`** | **AFTER INSERT on payment_splits** | `SUM(amount_paid)` for the sale → sets `received_amount` → `pending_amount` updates automatically → `status = 'Close'` when fully paid |
| `trg_payment_after_update` | AFTER UPDATE on payment_splits | Recalculates totals if a payment is corrected |
| `trg_payment_after_delete` | AFTER DELETE on payment_splits | Recalculates totals if a payment is removed |
| `trg_sales_block_manual_received` | BEFORE UPDATE on customer_sales | Blocks any manual change to `received_amount`. Only the payment triggers (which set a session flag) can change it |

Example:
```sql
INSERT INTO payment_splits (sale_id, payment_date, amount_paid, payment_method)
VALUES (151, '2026-11-07', 15000, 'UPI');
-- customer_sales #151 → received_amount 15000, pending_amount 25000, status 'Open'

UPDATE customer_sales SET received_amount = 0 WHERE sale_id = 1;
-- ERROR 1644: received_amount is managed by payment_splits triggers ...
```

## Setup & run

**Prerequisites:** Python 3.10+ and MySQL 8.0.16+ (MariaDB 10.11 also works).

```bash
# 1. Clone and install
git clone https://github.com/<your-username>/sales-intelligence-hub.git
cd sales-intelligence-hub
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure the DB connection
cp .env.example .env              # then edit DB_USER / DB_PASSWORD

# 3. Create the database, triggers and sample data (drops & recreates the DB)
python scripts/setup_db.py
#   or with the MySQL CLI:
#   mysql -u root -p < sql/01_schema.sql
#   mysql -u root -p < sql/02_triggers.sql
#   mysql -u root -p < sql/03_sample_data.sql

# 4. (optional) Check the connection
python -m src.db

# 5. Launch the dashboard
streamlit run app.py
```

Open http://localhost:8501 and log in with one of the demo accounts below.

## Demo logins

| Role | Username | Password | Scope |
|---|---|---|---|
| Super Admin | `superadmin` | `Super@123` | All branches |
| Admin | `chennai_admin` | `Chennai@123` | Chennai |
| Admin | `bangalore_admin` | `Bangalore@123` | Bangalore |
| Admin | `hyderabad_admin` | `Hyderabad@123` | Hyderabad |
| Admin | `delhi_admin` | `Delhi@123` | Delhi |
| Admin | `mumbai_admin` | `Mumbai@123` | Mumbai |
| Admin | `pune_admin` | `Pune@123` | Pune |

> These are demo credentials for evaluation only. Change them before using the app with real data.

## Streamlit dashboard

| Page | Super Admin | Admin |
|---|---|---|
| 📈 **Dashboard** | KPIs (total sales, gross, received, pending, pending %, open/closed), branch-wise comparison, payment-method donut, monthly trend and MoM growth, branch performance summary, key insights. Includes a branch filter | Same, limited to their own branch (with a product breakdown) |
| ➕ **Add sale** | Any branch | Own branch only (branch field locked) |
| 💳 **Add payment** | Any open sale | Open sales of own branch only. Shows the sale's payment history and caps the amount at the pending balance |
| 📋 **Sales report** | Filter by branch, status, product, date range, search; CSV export | Same, own branch |
| ⏳ **Pending payments** | Dues with ageing buckets, Open vs Close status | Own branch |
| 💰 **Payment summary** | Cash / UPI / Card totals, share, monthly collections by method | Own branch |
| 🧮 **SQL queries** | All 20 predefined queries, with the SQL shown | The same queries, automatically scoped to their branch |

**How access control works:** the logged-in user is held in `st.session_state`. Every page checks it, and nothing loads before login. Admin scoping happens **inside SQL**: every query is filtered by `branch_id`, and the 20 predefined queries swap their table names for branch-filtered sub-queries (see `src/queries.py`). Because of this, an Admin can never pull another branch's rows.

## SQL analytical queries

All **20** questions are answered in [`sql/04_analysis_queries.sql`](sql/04_analysis_queries.sql) (the brief requires at least 15). You can also run them from the **SQL queries** page.

| # | Category | Question |
|---|---|---|
| 1–5 | Basic | All sales · all branches · all payments · Open sales · Chennai sales |
| 6–10 | Aggregation | Total gross · total received · total pending · sales count per branch · average gross |
| 11–15 | Join | Sales + branch name · sales + total paid from splits · branch-wise gross · sales + payment method · sales + branch admin |
| 16–20 | Financial | Pending > 5000 · top 3 gross · top branch · monthly summary · method-wise collection |

## Business insights (sample data)

All figures below come from the demo dataset (150 sales, Jan–Oct 2026):

- **Overall revenue:** ₹73.2 L gross, of which ₹55.1 L has been received (75.3%) and **₹18.1 L is pending (24.7%)**.
- **Top branch:** Chennai, with ₹16.55 L gross from 34 sales. Bangalore is second with ₹15.34 L.
- **Collection risk:** Delhi has the lowest collection rate (61.9%) and the highest pending amount (₹4.89 L), so it should be the first branch for follow-ups. Mumbai collects best (84.0%).
- **Payment channels:** UPI accounts for 51% of collections, Card for 30% and Cash for 19%.
- **Products:** DS (Data Science) earns the most revenue (₹26.4 L), followed by FSD (₹22.8 L).
- **Trend:** monthly sales grew from ₹4.5 L in January to a peak of ₹11.4 L in September.
- **Dues:** 69 sales have more than ₹5,000 pending.

## Design decisions

- **`mobile_number` is UNIQUE**, as the brief requires, so each customer can have only one sale record. The app shows a friendly message when someone tries to add a duplicate.
- **Super Admin `branch_id` is NULL** because the Super Admin is not tied to one branch. Admins always have a branch. (MySQL doesn't allow a CHECK constraint on a column used by a cascading foreign key, so the app enforces this rule.)
- **Status is automatic:** the trigger sets `Close` when `received_amount = gross_sales`, and `Open` otherwise.
- **Passwords** are hashed with PBKDF2-SHA256 from the Python standard library, with 200k iterations and a per-user salt.
- **Sample data** is generated by a script with a fixed seed, so it is reproducible. Payments are inserted *after* sales, so the triggers produce every financial figure.

---

*Built as part of the GUVI Data Science capstone: Sales Intelligence Hub.*
