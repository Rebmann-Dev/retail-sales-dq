# Retail Sales & Data Quality Dashboard

A small, reproducible analysis of a UK online retailer's transactions (Dec 2010 – Dec 2011).
Python/pandas loads and flags the data, SQLite and SQL compute every metric, and a
Streamlit dashboard shows the results alongside a data-quality summary.

**Questions answered**
1. How do monthly sales change over time?
2. Which products and countries contribute the most sales?
3. How many cancellations and invalid or missing values are there?
4. How do the cleaning rules change the reported results?

Findings are in [FINDINGS.md](FINDINGS.md).
## Dashboard

<img width="1146" height="776" alt="Screenshot 2026-09-29 at 4 52 34 PM" src="https://github.com/user-attachments/assets/8748330b-a73e-4e2b-a76e-2bcd34e16e4d" />
<img width="1143" height="764" alt="Screenshot 2026-09-29 at 4 53 19 PM" src="https://github.com/user-attachments/assets/0ede4b2f-8d7a-453a-8945-81add4ff527a" />
<img width="1150" height="774" alt="Screenshot 2026-09-29 at 4 53 39 PM" src="https://github.com/user-attachments/assets/7fdd8919-17ca-4087-b22b-a4faf8961c6e" />

## Data source

UCI Machine Learning Repository, **Online Retail** (Chen, D., 2015).
https://archive.ics.uci.edu/dataset/352/online+retail · DOI 10.24432/C5BW33 ·
licensed CC BY 4.0. The file is not included in this repo. Download it, unzip, and
place `Online Retail.xlsx` in `data/`.

Per UCI: invoice numbers starting with "C" are cancellations, and unit prices are in
pounds sterling. UCI lists the dataset as having no missing values, but the file
contains 135,080 blank CustomerIDs and 1,454 blank descriptions (see below).

## Setup and how to run

Run all commands from the project root.

```bash
pip install -r requirements.txt
python src/inspect_data.py   # optional: profile the raw file -> outputs/inspection_report.txt
python src/clean.py          # flag every row, write outputs/retail.db (~30 s)
python src/run_queries.py    # create SQL views, run queries -> outputs/*.csv
streamlit run app.py         # dashboard
pytest -v                    # tests (use synthetic data; no download needed)
```

Tested on macOS with Python 3.13.12, Streamlit 1.64.0 and pytest 9.1.1. A full rerun of
the pipeline there gave output CSVs identical to the original run.

## Project structure

```
data/                   raw Excel file (not committed)
sql/views.sql           defines the analysis subsets as SQL views
sql/queries.sql         one named SQL query per metric/chart
src/inspect_data.py     raw-data profile (read-only)
src/clean.py            load Excel, add flag columns, write all rows to SQLite
src/run_queries.py      run the views and queries, save CSVs
src/dashboard_data.py   load query results for the dashboard (no Streamlit code)
app.py                  Streamlit dashboard
tests/                  pytest tests for cleaning rules and SQL metrics
outputs/                generated: retail.db, query CSVs, inspection report
```

## How the pipeline works

1. **Flag, never delete.** `clean.py` writes all 541,909 raw rows to the `line_items`
   table and adds one 0/1 column per rule. It asserts that the rows in equal the rows out.
2. **Exclusions are SQL.** `sql/views.sql` defines which rows count, as `WHERE`
   clauses. You can see every exclusion by reading one file.
3. **Metrics are SQL.** Every number in the dashboard and memo comes from a named query
   in `sql/queries.sql`. pandas only fetches results and saves them as CSVs.

## Cleaning rules

The rules were chosen after profiling the raw file (`outputs/inspection_report.txt`).

| Flag | Rule | Rows | Treatment |
|---|---|---|---|
| `is_cancellation` | Invoice starts with "C" | 9,288 | Excluded from gross sales; reported separately |
| `qty_nonpositive` | Quantity ≤ 0 | 10,624 | Excluded. All 9,288 cancellations are in this group; the other 1,336 are stock write-offs with no customer ("damages", "check", …) |
| `price_nonpositive` | Unit price ≤ 0 | 2,517 | Excluded (2,515 zero-price rows; 2 "Adjust bad debt" rows at −£11,062.06) |
| `is_non_product` | Postage (POST, DOT, C2), manual adjustments (M, m), discount (D), samples (S), bank charges, Amazon fees, CRUK commission, bad debt (B), gift vouchers (`gift_0001_*`) | 2,946 | Excluded from product sales. Shipping is reported separately |
| `missing_customer_id` | CustomerID blank | 135,080 | **Kept** in sales, because the sale still happened. Excluded only from the customer count |
| `missing_description` | Description blank | 1,454 | All of these also have price ≤ 0, so they're already excluded |
| `is_duplicate` | Identical to an earlier row in every column | 5,268 | **Kept.** With no line numbers, a double entry can't be told apart from a repeat purchase. The effect of excluding them is shown as a sensitivity step |

## Metric definitions

- **Line item**: one row. **Order**: one distinct invoice number. These are counted separately.
- **Valid sale line**: not a cancellation, quantity > 0, unit price > 0, and not a non-product code.
- **Gross sales**: Σ quantity × unit price over valid sale lines. **This is not net revenue.**
- **Sales after recorded product cancellations**: gross sales plus the (negative)
  amounts on cancellation lines for product codes. It's used to rank products and countries.
  It's not net revenue either (see limitations).
- **Average order value**: gross sales ÷ distinct orders among valid sale lines.
- **Product ranking**: grouped by stock code and labelled with each code's most frequent description.

## Results (from `outputs/`)

| Metric | Value |
|---|---|
| Gross sales | £10,271,433.06 |
| Recorded product cancellations | £478,724.18 |
| Sales after recorded product cancellations | £9,792,708.88 |
| Valid sale lines / orders | 527,761 / 19,773 |
| Average order value (gross) | £519.47 |
| Identified customers | 4,334 |
| Shipping charges (excluded from sales) | £291,401.65 |

See [FINDINGS.md](FINDINGS.md) for the interpretation.

## Tests

`pytest -v` runs 10 tests:
- 6 check each cleaning flag, including edge values of 0 and negative numbers,
  and that no rows are dropped.
- 4 build a 7-row SQLite database by hand and check the real views and queries
  against totals worked out by hand. The test data is written out in
  `tests/test_metrics.py`.

## Limitations

- **Cancellations aren't matched to their original sales.** A cancellation is dated when it
  was recorded, and it may reverse a sale from before December 2010.
- **Reversals booked as manual adjustments aren't netted out.** A £38,970 sale of
  stock code 22502 (invoice 556444) was reversed with a "Manual" adjustment line rather than
  a product cancellation. This puts the product in the top 10, and the dashboard footnotes it.
- **This isn't net revenue.** The file doesn't record discounts outside the data, refunds, VAT, or costs.
- **December 2011 is partial** (1–9 Dec only).
- **The data covers 13 months**, so seasonality can't be separated from year-over-year growth.
- **One quarter of rows have no CustomerID.** Customer-level analysis (for example,
  retention) would leave out £1.51M of gross sales, so it isn't attempted here.
- **Country is taken as recorded.** The values include "Unspecified" and "European Community".
