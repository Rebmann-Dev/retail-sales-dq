"""Data access for the dashboard. No Streamlit here, so it can be tested alone.

Every number comes from the named SQL queries in sql/queries.sql, run
against outputs/retail.db. This module only reshapes results for display.
"""
import sqlite3
from pathlib import Path

import pandas as pd

from run_queries import load_queries

DB_PATH = Path("outputs/retail.db")


def load_results(db_path=DB_PATH):
    """Run every named query read-only and return {name: DataFrame}.
    Requires clean.py and run_queries.py to have been run first."""
    if not Path(db_path).exists():
        raise FileNotFoundError(
            f"{db_path} not found. Run: python src/clean.py && python src/run_queries.py")
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return {name: pd.read_sql_query(sql, con) for name, sql in load_queries().items()}
    finally:
        con.close()


def add_month_labels(monthly):
    """Label the last month as partial, e.g. '2011-12 (partial)'."""
    out = monthly.copy()
    out["month_label"] = out["month"].where(out["is_partial_month"] == 0,
                                            out["month"] + " (partial)")
    return out


def monthly_long(monthly):
    """Reshape to one row per month per measure, for a two-line chart."""
    labelled = add_month_labels(monthly)
    long = labelled.melt(id_vars=["month_label", "orders"],
                         value_vars=["gross_sales", "sales_after_cancellations"],
                         var_name="measure", value_name="amount")
    long["measure"] = long["measure"].map({
        "gross_sales": "Gross sales",
        "sales_after_cancellations": "Sales after recorded product cancellations",
    })
    return long
