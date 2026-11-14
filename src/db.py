"""Python <-> MySQL connection helpers.

Connection settings come from environment variables (or a local ``.env``
file - see ``.env.example``):

    DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
"""

from __future__ import annotations

import os
from contextlib import contextmanager

import mysql.connector
import pandas as pd

try:  # optional: load a local .env file if python-dotenv is installed
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


def db_config(include_database: bool = True) -> dict:
    cfg = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
    }
    if include_database:
        cfg["database"] = os.getenv("DB_NAME", "sales_management_system")
    return cfg


@contextmanager
def get_connection(include_database: bool = True):
    """Yield a MySQL connection and always close it afterwards."""
    conn = mysql.connector.connect(**db_config(include_database))
    try:
        yield conn
    finally:
        conn.close()


def run_query(sql: str, params=None) -> pd.DataFrame:
    """Run a SELECT and return the result as a DataFrame."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        columns = [c[0] for c in cur.description] if cur.description else []
        rows = cur.fetchall()
        cur.close()
    df = pd.DataFrame(rows, columns=columns)
    # DECIMAL columns arrive as decimal.Decimal; convert them for charts/maths
    for col in df.columns:
        if len(df) and df[col].map(lambda v: v.__class__.__name__ == "Decimal").any():
            df[col] = pd.to_numeric(df[col])
    return df


def fetch_one(sql: str, params=None) -> dict | None:
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params or ())
        row = cur.fetchone()
        cur.close()
    return row


def execute(sql: str, params=None) -> int:
    """Run an INSERT/UPDATE/DELETE inside a transaction; return lastrowid."""
    with get_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(sql, params or ())
            conn.commit()
            return cur.lastrowid
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()


def test_connection() -> str:
    """Return the server version - handy for a quick connectivity check."""
    row = fetch_one("SELECT VERSION() AS version")
    return row["version"] if row else "unknown"


if __name__ == "__main__":
    print("Connected to MySQL server version:", test_connection())
