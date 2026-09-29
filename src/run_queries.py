"""Phase 3: create the SQL views and run every named query in sql/queries.sql.

All metrics are computed by SQLite. pandas is used only to fetch each
result and save it as a CSV in outputs/.

Run from the project root (after clean.py):  python src/run_queries.py
"""
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path("outputs/retail.db")
SQL_DIR = Path("sql")
OUT_DIR = Path("outputs")


def load_queries(path=SQL_DIR / "queries.sql"):
    """Split queries.sql into {name: sql} using the '-- name: x' markers."""
    queries, name, buf = {}, None, []
    for line in Path(path).read_text().splitlines():
        if line.startswith("-- name:"):
            if name:
                queries[name] = "\n".join(buf).strip()
            name, buf = line.split(":", 1)[1].strip(), []
        elif name:
            buf.append(line)
    if name:
        queries[name] = "\n".join(buf).strip()
    return queries


def create_views(con, path=SQL_DIR / "views.sql"):
    con.executescript(Path(path).read_text())


def run_all(con):
    return {name: pd.read_sql_query(sql, con) for name, sql in load_queries().items()}


def main():
    with sqlite3.connect(DB_PATH) as con:
        create_views(con)
        results = run_all(con)
    for name, df in results.items():
        df.to_csv(OUT_DIR / f"{name}.csv", index=False)
        print(f"\n=== {name} ===")
        print(df.to_string(index=False))

    # Consistency check: step 4 of the cleaning table must equal gross sales.
    step4 = results["cleaning_steps"].set_index("step").loc[4, "sum_line_amount"]
    gross = results["headline"].loc[0, "gross_sales"]
    assert abs(step4 - gross) < 0.01, (step4, gross)
    print("\nCheck passed: cleaning step 4 equals headline gross sales.")


if __name__ == "__main__":
    main()
