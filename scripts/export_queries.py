"""Write sql/04_analysis_queries.sql from src/queries.py.

Run:  python scripts/export_queries.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.queries import QUERIES, plain_sql  # noqa: E402

HEADINGS = {
    "Basic": "Basic Queries",
    "Aggregation": "Aggregation Queries",
    "Join": "Join-Based Queries",
    "Financial": "Financial Tracking Queries",
}


def main() -> None:
    out = [
        "-- =====================================================================",
        "-- Sales Intelligence Hub - 20 Analytical SQL Queries",
        "-- (generated from src/queries.py by scripts/export_queries.py)",
        "-- =====================================================================",
        "",
        "USE sales_management_system;",
    ]
    current = None
    for i, q in enumerate(QUERIES, start=1):
        if q.category != current:
            current = q.category
            out += ["", "-- ---------------------------------------------------------------------",
                    f"-- {HEADINGS[current]}",
                    "-- ---------------------------------------------------------------------"]
        out += ["", f"-- Q{i}. {q.question}", plain_sql(q)]
    out.append("")
    path = ROOT / "sql" / "04_analysis_queries.sql"
    path.write_text("\n".join(out), encoding="utf-8")
    print(f"Wrote {path.relative_to(ROOT)} ({len(QUERIES)} queries)")


if __name__ == "__main__":
    main()
