"""One-command database setup from Python.

Runs, in order:
    sql/01_schema.sql        - database, tables, keys, constraints, generated column
    sql/02_triggers.sql      - payment triggers
    sql/03_sample_data.sql   - demo branches, users, sales and payments

Run:  python scripts/setup_db.py
(WARNING: drops and recreates the sales_management_system database.)

Equivalent with the MySQL CLI:
    mysql -u root -p < sql/01_schema.sql
    mysql -u root -p < sql/02_triggers.sql
    mysql -u root -p < sql/03_sample_data.sql
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db import get_connection  # noqa: E402

SQL_FILES = ["01_schema.sql", "02_triggers.sql", "03_sample_data.sql"]


def split_statements(script: str) -> list[str]:
    """Split a .sql script into statements, honouring DELIMITER changes."""
    statements, buf, delimiter = [], [], ";"
    for line in script.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("DELIMITER "):
            delimiter = stripped.split(None, 1)[1]
            continue
        if not buf and (not stripped or stripped.startswith("--")):
            continue
        buf.append(line)
        if stripped.endswith(delimiter):
            stmt = "\n".join(buf).rstrip()[: -len(delimiter)].strip()
            if stmt:
                statements.append(stmt)
            buf = []
    if "".join(buf).strip():
        statements.append("\n".join(buf).strip())
    return statements


def main() -> None:
    with get_connection(include_database=False) as conn:
        cur = conn.cursor()
        for name in SQL_FILES:
            stmts = split_statements((ROOT / "sql" / name).read_text(encoding="utf-8"))
            for stmt in stmts:
                cur.execute(stmt)
            conn.commit()
            print(f"OK  {name:<22} ({len(stmts)} statements)")
        cur.execute("SELECT COUNT(*) FROM sales_management_system.customer_sales")
        print(f"Done - {cur.fetchone()[0]} sales loaded.")
        cur.close()


if __name__ == "__main__":
    main()
