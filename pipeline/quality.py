"""
Data quality checks that run after cleaning and before anything reaches a dashboard.

Each check returns PASS, WARN or FAIL. A FAIL stops the pipeline, so leadership
never sees numbers built on broken data.
"""
from __future__ import annotations

import duckdb
import pandas as pd


def run_checks(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    checks = [
        ("Every matter has a unique ID",
         "SELECT COUNT(*) - COUNT(DISTINCT matter_id) FROM stg_matters", "FAIL"),
        ("Matters link to a CRM contact",
         """SELECT COUNT(*) FROM stg_matters m
            LEFT JOIN stg_contacts c ON m.client_email = c.email WHERE c.email IS NULL""", "WARN"),
        ("Time entries link to a known matter",
         """SELECT COUNT(*) FROM stg_time_entries t
            LEFT JOIN stg_matters m USING (matter_id) WHERE m.matter_id IS NULL""", "FAIL"),
        ("No time entries dated in the future",
         "SELECT COUNT(*) FROM stg_time_entries WHERE date > DATE '2026-09-30'", "FAIL"),
        ("Every practice area mapped",
         "SELECT COUNT(*) FROM stg_matters WHERE practice_area IS NULL", "FAIL"),
        ("Invoices never exceed billed amount after cleaning",
         "SELECT COUNT(*) FROM stg_invoices WHERE amount_paid > amount_billed", "FAIL"),
        ("Entries flagged for human review",
         "SELECT COUNT(*) FROM stg_time_entries WHERE needs_review", "WARN"),
    ]
    rows = []
    for name, sql, severity in checks:
        failing = con.execute(sql).fetchone()[0]
        rows.append({"check": name, "failing_rows": failing,
                     "status": "PASS" if failing == 0 else severity})
    return pd.DataFrame(rows)
