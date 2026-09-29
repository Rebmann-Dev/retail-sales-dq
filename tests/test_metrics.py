"""Tests for the SQL metrics: build a tiny database, create the real views,
run the real named queries from sql/queries.sql, compare to hand-computed values.

Fixture (amounts are quantity x unit price):
  1001  10001  2 x 5.00 = 10  (Jan)   valid
  1001  10002  1 x 3.00 =  3  (Jan)   valid  -> order 1001 has 2 lines
  1002  10001  4 x 5.00 = 20  (Feb)   valid
  1002  POST 1 x 15 = 15  (Feb)   shipping, excluded from sales
  C1003 10001 -2 x 5.00 = -10 (Feb)   product cancellation
  1004  10002  1 x 0.00 =  0  (Jan)   price 0, excluded
  1005  10001 -3 x 0.00 =  0  (Jan)   quantity < 0, no customer, excluded
Gross sales = 10 + 3 + 20 = 33 over 3 lines and 2 orders.
(Product codes avoid real non-product codes such as "B" = bad debt.)
"""
import sqlite3
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from clean import add_flags, write_sqlite
from run_queries import create_views, load_queries

ROWS = [
    ["1001", "10001", "ITEM A", 2, "2011-01-10 09:00", 5.0, 1.0],
    ["1001", "10002", "ITEM B", 1, "2011-01-10 09:00", 3.0, 1.0],
    ["1002", "10001", "ITEM A", 4, "2011-02-03 09:00", 5.0, 2.0],
    ["1002", "POST", "POSTAGE", 1, "2011-02-03 09:00", 15.0, 2.0],
    ["C1003", "10001", "ITEM A", -2, "2011-02-04 09:00", 5.0, 2.0],
    ["1004", "10002", "ITEM B", 1, "2011-01-11 09:00", 0.0, 3.0],
    ["1005", "10001", None, -3, "2011-01-12 09:00", 0.0, None],
]


def run_query(name):
    raw = pd.DataFrame(ROWS, columns=["InvoiceNo", "StockCode", "Description", "Quantity",
                                      "InvoiceDate", "UnitPrice", "CustomerID"])
    raw["InvoiceDate"] = pd.to_datetime(raw["InvoiceDate"])
    raw["Country"] = "United Kingdom"
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.db"
        write_sqlite(add_flags(raw), db)
        con = sqlite3.connect(db)
        try:
            create_views(con)
            return pd.read_sql_query(load_queries()[name], con)
        finally:
            con.close()


def test_headline_metrics():
    h = run_query("headline").iloc[0]
    assert h["raw_line_items"] == 7
    assert h["gross_sales"] == pytest.approx(33.0)
    assert h["valid_sale_lines"] == 3
    assert h["valid_orders"] == 2              # orders < line items
    assert h["avg_order_value"] == pytest.approx(16.5)
    assert h["product_cancellation_value"] == pytest.approx(10.0)
    assert h["sales_after_cancellations"] == pytest.approx(23.0)
    assert h["shipping_charges"] == pytest.approx(15.0)


def test_cancellations_and_postage_not_in_gross_sales():
    m = run_query("monthly").set_index("month")
    assert m.loc["2011-01", "gross_sales"] == pytest.approx(13.0)
    assert m.loc["2011-02", "gross_sales"] == pytest.approx(20.0)   # not 20+15-10
    assert m.loc["2011-02", "sales_after_cancellations"] == pytest.approx(10.0)
    assert m.loc["2011-01", "orders"] == 1
    assert m["is_partial_month"].tolist() == [0, 1]                  # last month flagged


def test_top_products_net_out_cancellations():
    tp = run_query("top_products")
    assert tp["stock_code"].tolist() == ["10001", "10002"]
    a = tp.iloc[0]
    assert a["gross_sales"] == pytest.approx(30.0)
    assert a["sales_after_cancellations"] == pytest.approx(20.0)
    assert a["net_quantity"] == 4


def test_cleaning_steps_are_sequential_and_end_at_gross_sales():
    cs = run_query("cleaning_steps").set_index("step")
    assert cs["rows_remaining"].tolist() == [7, 6, 5, 4, 3, 3]
    assert cs.loc[0, "sum_line_amount"] == pytest.approx(38.0)
    assert cs.loc[1, "sum_line_amount"] == pytest.approx(48.0)   # removing -10 raises it
    assert cs.loc[4, "sum_line_amount"] == pytest.approx(33.0)   # equals gross sales
