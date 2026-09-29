"""Phase 1: profile the raw Online Retail file. Reads only; changes nothing.

Run from the project root:  python src/inspect_data.py
Prints a report and saves it to outputs/inspection_report.txt.
"""
from pathlib import Path

import pandas as pd

RAW_PATH = Path("data/Online Retail.xlsx")
REPORT_PATH = Path("outputs/inspection_report.txt")

lines = []


def report(*parts):
    text = " ".join(str(p) for p in parts)
    print(text)
    lines.append(text)


# Read InvoiceNo and StockCode as text so "C536379" and "85123A" aren't coerced.
df = pd.read_excel(RAW_PATH, dtype={"InvoiceNo": str, "StockCode": str})

report("=== Shape and types ===")
report("rows:", len(df), "| columns:", df.shape[1])
report(df.dtypes.to_string())

report("\n=== Nulls per column ===")
report(df.isna().sum().to_string())
blank_desc = df["Description"].notna() & (df["Description"].astype(str).str.strip() == "")
report("blank (whitespace-only) descriptions:", int(blank_desc.sum()))

report("\n=== Date range ===")
report("min:", df["InvoiceDate"].min(), "| max:", df["InvoiceDate"].max())
report("rows per month:")
report(df["InvoiceDate"].dt.to_period("M").value_counts().sort_index().to_string())

report("\n=== Invoice numbers ===")
inv = df["InvoiceNo"].str.strip()
starts_c = inv.str.startswith("C")
report("distinct invoices:", inv.nunique())
report("rows with InvoiceNo starting 'C':", int(starts_c.sum()),
       "| distinct C invoices:", inv[starts_c].nunique())
non_digit = ~inv.str.fullmatch(r"C?\d+")
report("rows whose InvoiceNo is not digits or C+digits:", int(non_digit.sum()))
if non_digit.any():
    report(inv[non_digit].value_counts().head(10).to_string())

report("\n=== Quantity and UnitPrice ===")
report(df[["Quantity", "UnitPrice"]].describe().to_string())
qty_np = df["Quantity"] <= 0
price_np = df["UnitPrice"] <= 0
report("Quantity <= 0:", int(qty_np.sum()), "| of which C invoices:", int((qty_np & starts_c).sum()))
report("C invoices with Quantity > 0:", int((starts_c & ~qty_np).sum()))
report("UnitPrice == 0:", int((df["UnitPrice"] == 0).sum()),
       "| UnitPrice < 0:", int((df["UnitPrice"] < 0).sum()))
report("Rows with UnitPrice < 0:")
report(df[df["UnitPrice"] < 0].to_string())
report("Nonpositive quantity on non-C invoices, by whether CustomerID is null:")
report((qty_np & ~starts_c).groupby(df["CustomerID"].isna()).sum().to_string())
report("Sample descriptions on non-C invoices with Quantity <= 0:")
report(df.loc[qty_np & ~starts_c, "Description"].value_counts(dropna=False).head(15).to_string())

report("\n=== CustomerID ===")
missing_cust = df["CustomerID"].isna()
report("missing CustomerID rows:", int(missing_cust.sum()),
       f"({missing_cust.mean():.1%})")
report("distinct CustomerIDs:", df["CustomerID"].nunique())

report("\n=== StockCode ===")
code = df["StockCode"].str.strip()
report("distinct stock codes:", code.nunique())
# Most merchandise codes are 5 digits plus an optional letter suffix.
unusual = ~code.str.fullmatch(r"\d{5}[A-Za-z]{0,2}")
report("rows with codes NOT matching 5 digits + optional letters:", int(unusual.sum()))
summary = (df[unusual]
           .assign(StockCode=code[unusual], amount=df["Quantity"] * df["UnitPrice"])
           .groupby("StockCode")
           .agg(rows=("StockCode", "size"),
                example_description=("Description", "first"),
                sum_amount=("amount", "sum"))
           .sort_values("rows", ascending=False))
report(summary.to_string())

report("\n=== Duplicates ===")
dup = df.duplicated(keep="first")
report("exact duplicate rows (all columns, excluding first occurrence):", int(dup.sum()))

report("\n=== Country ===")
report("distinct countries:", df["Country"].nunique())
report(df["Country"].value_counts().to_string())

REPORT_PATH.write_text("\n".join(lines))
print(f"\nSaved report to {REPORT_PATH}")
