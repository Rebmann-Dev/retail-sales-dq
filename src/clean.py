"""Phase 2: load the raw Excel file, add data-quality flags, write to SQLite.

Rule: no row is ever dropped here. Every raw row goes into the `line_items`
table with flag columns; exclusions happen later, visibly, in SQL views.

Run from the project root:  python src/clean.py
"""
import sqlite3
from pathlib import Path

import pandas as pd

RAW_PATH = Path("data/Online Retail.xlsx")
DB_PATH = Path("outputs/retail.db")

# Stock codes that are not merchandise, chosen after inspecting the raw data
# (see outputs/inspection_report.txt). Matching is exact and case-sensitive.
NON_PRODUCT_CODES = {
    "POST",          # postage
    "DOT",           # dotcom postage
    "C2",            # carriage
    "M", "m",        # manual adjustment
    "D",             # discount
    "S",             # samples
    "BANK CHARGES",
    "AMAZONFEE",
    "CRUK",          # CRUK commission
    "B",             # adjust bad debt
}
GIFT_VOUCHER_PREFIX = "gift_0001_"

# Codes counted as shipping, reported separately from product sales.
SHIPPING_CODES = {"POST", "DOT", "C2"}

RAW_COLUMNS = ["InvoiceNo", "StockCode", "Description", "Quantity",
               "InvoiceDate", "UnitPrice", "CustomerID", "Country"]


def load_raw(path=RAW_PATH):
    """Read the Excel file, keeping invoice numbers and stock codes as text."""
    return pd.read_excel(path, dtype={"InvoiceNo": str, "StockCode": str})


def add_flags(raw):
    """Return a new DataFrame with the same rows as `raw`, renamed columns,
    a line amount, and one boolean column per data-quality rule."""
    # Duplicates are judged on the original columns, before anything is added.
    is_duplicate = raw.duplicated(subset=RAW_COLUMNS, keep="first")

    df = pd.DataFrame({
        "row_id": range(len(raw)),  # position in the original file
        "invoice_no": raw["InvoiceNo"].astype(str).str.strip(),
        "stock_code": raw["StockCode"].astype(str).str.strip(),
        "description": raw["Description"],
        "quantity": raw["Quantity"],
        "invoice_date": pd.to_datetime(raw["InvoiceDate"]),
        "unit_price": raw["UnitPrice"],
        "customer_id": raw["CustomerID"].astype("Int64"),  # nullable integer
        "country": raw["Country"],
    })

    df["line_amount"] = df["quantity"] * df["unit_price"]

    desc = df["description"]
    df["is_cancellation"] = df["invoice_no"].str.startswith("C")
    df["missing_customer_id"] = df["customer_id"].isna()
    df["missing_description"] = desc.isna() | (desc.astype(str).str.strip() == "")
    df["qty_nonpositive"] = df["quantity"] <= 0
    df["price_nonpositive"] = df["unit_price"] <= 0
    df["is_non_product"] = (df["stock_code"].isin(NON_PRODUCT_CODES)
                            | df["stock_code"].str.startswith(GIFT_VOUCHER_PREFIX))
    df["is_shipping"] = df["stock_code"].isin(SHIPPING_CODES)
    df["is_duplicate"] = is_duplicate.to_numpy()

    return df


def write_sqlite(df, db_path=DB_PATH):
    """Write all rows to the `line_items` table, replacing any previous run."""
    out = df.copy()
    # Store dates as ISO text so SQLite's strftime() can group by month.
    out["invoice_date"] = out["invoice_date"].dt.strftime("%Y-%m-%d %H:%M:%S")
    flag_cols = [c for c in out.columns if c.startswith(("is_", "missing_", "qty_", "price_"))]
    out[flag_cols] = out[flag_cols].astype(int)  # SQLite has no boolean type

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as con:
        out.to_sql("line_items", con, if_exists="replace", index=False)
    return len(out)


def main():
    raw = load_raw()
    flagged = add_flags(raw)
    # The core guarantee of this step: row count in == row count out.
    assert len(flagged) == len(raw), "cleaning must not drop rows"
    written = write_sqlite(flagged)
    print(f"raw rows read: {len(raw)} | rows written to {DB_PATH}: {written}")


if __name__ == "__main__":
    main()
