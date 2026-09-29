"""Tests for the flag rules in src/clean.py, using tiny hand-made data."""
import pandas as pd

from clean import add_flags


def make_raw(rows):
    """Build a DataFrame shaped like the raw Excel file."""
    cols = ["InvoiceNo", "StockCode", "Description", "Quantity",
            "InvoiceDate", "UnitPrice", "CustomerID", "Country"]
    return pd.DataFrame(rows, columns=cols)


def row(invoice="1001", code="85123A", desc="HEART", qty=1, price=2.5,
        customer=12345.0, date="2011-01-05 10:00"):
    return [invoice, code, desc, qty, pd.Timestamp(date), price, customer, "United Kingdom"]


def test_cancellation_flag_uses_c_prefix():
    df = add_flags(make_raw([row(invoice="C536379", qty=-1), row(invoice="536380")]))
    assert df["is_cancellation"].tolist() == [True, False]


def test_nonpositive_quantity_and_price_at_zero_and_negative():
    df = add_flags(make_raw([
        row(qty=0), row(qty=-3), row(qty=1),
        row(price=0.0), row(price=-11062.06), row(price=0.01),
    ]))
    assert df["qty_nonpositive"].tolist() == [True, True, False, False, False, False]
    assert df["price_nonpositive"].tolist() == [False, False, False, True, True, False]


def test_non_product_codes():
    codes = ["POST", "M", "m", "AMAZONFEE", "gift_0001_20", "DCGS0003", "85123A"]
    df = add_flags(make_raw([row(code=c) for c in codes]))
    assert df["is_non_product"].tolist() == [True, True, True, True, True, False, False]
    assert df["is_shipping"].tolist() == [True, False, False, False, False, False, False]


def test_missing_customer_and_blank_description():
    df = add_flags(make_raw([row(customer=None), row(desc="   "), row(desc=None), row()]))
    assert df["missing_customer_id"].tolist() == [True, False, False, False]
    assert df["missing_description"].tolist() == [False, True, True, False]


def test_duplicates_flag_only_the_repeat():
    df = add_flags(make_raw([row(), row(), row(qty=2)]))
    assert df["is_duplicate"].tolist() == [False, True, False]


def test_no_rows_dropped_and_line_amount():
    raw = make_raw([row(qty=3, price=2.0), row(invoice="C1", qty=-1), row(price=0.0)])
    df = add_flags(raw)
    assert len(df) == len(raw)
    assert df["line_amount"].tolist() == [6.0, -2.5, 0.0]
