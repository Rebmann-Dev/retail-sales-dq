"""Retail Sales & Data Quality Dashboard (Streamlit).

Run from the project root, after the pipeline:
    python src/clean.py
    python src/run_queries.py
    streamlit run app.py
"""
import sys
from pathlib import Path

import altair as alt
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from dashboard_data import load_results, monthly_long  # noqa: E402

BLUE = "#2a78d6"    # sales after recorded product cancellations
ORANGE = "#eb6834"  # gross sales
MONEY = ",.0f"

st.set_page_config(page_title="Retail Sales & Data Quality", layout="wide")


@st.cache_data
def get_results():
    return load_results()


r = get_results()
h = r["headline"].iloc[0]

st.title("Retail Sales & Data Quality Dashboard")
st.caption(
    f"UCI Online Retail dataset · {h.first_date[:10]} to {h.last_date[:10]} · "
    "amounts in £ as recorded (UnitPrice × Quantity). December 2011 covers 1–9 Dec only."
)

# ---- KPI row -------------------------------------------------------------
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Gross sales", f"£{h.gross_sales:,.0f}")
c2.metric("After recorded product cancellations", f"£{h.sales_after_cancellations:,.0f}")
c3.metric("Orders (distinct invoices)", f"{h.valid_orders:,}")
c4.metric("Avg order value (gross)", f"£{h.avg_order_value:,.2f}")
c5.metric("Identified customers", f"{h.distinct_customers:,}")

with st.expander("Metric definitions"):
    st.markdown(
        """
- **Line item**: one row of the source file. **Order**: one distinct invoice number.
- **Valid sale line**: not a cancellation (invoice not starting with "C"), quantity > 0,
  unit price > 0, and not a non-product code (postage, fees, manual adjustments,
  discounts, samples, bad-debt adjustments, gift vouchers).
- **Gross sales**: sum of quantity × unit price over valid sale lines. Not net revenue.
- **Sales after recorded product cancellations**: gross sales plus the (negative)
  amounts on cancellation lines for product codes. Cancellations are dated by when
  they were recorded and may reverse sales from before the data window.
- **Average order value**: gross sales ÷ orders.
- Rows with no CustomerID are **included** in sales; they are excluded only from the
  customer count.
- Shipping charges (POST, DOT, C2) are excluded from sales and reported separately:
  """ + f"£{h.shipping_charges:,.0f}."
    )

# ---- Chart 1: monthly ----------------------------------------------------
st.subheader("1. Monthly sales")
ml = monthly_long(r["monthly"])
monthly_chart = (
    alt.Chart(ml)
    .mark_line(point=alt.OverlayMarkDef(size=60), strokeWidth=2)
    .encode(
        x=alt.X("month_label:O", title=None, sort=None, axis=alt.Axis(labelAngle=-45)),
        y=alt.Y("amount:Q", title="£", axis=alt.Axis(format="~s")),
        color=alt.Color("measure:N", title=None, legend=alt.Legend(orient="top", labelLimit=0),
                        scale=alt.Scale(domain=["Gross sales",
                                                "Sales after recorded product cancellations"],
                                        range=[ORANGE, BLUE])),
        tooltip=[alt.Tooltip("month_label:O", title="Month"),
                 alt.Tooltip("measure:N", title="Measure"),
                 alt.Tooltip("amount:Q", title="£", format=MONEY),
                 alt.Tooltip("orders:Q", title="Orders", format=",")],
    )
    .properties(height=320)
)
st.altair_chart(monthly_chart, width="stretch")
st.caption("The last month is partial (1–9 Dec 2011). Its large gap between the two lines "
           "is mostly one cancelled 80,995-unit order (invoice 581483 / C581484).")

left, right = st.columns(2)

# ---- Chart 2: top products -----------------------------------------------
with left:
    st.subheader("2. Top 10 products")
    tp = r["top_products"].copy()
    tp["label"] = tp["description"].fillna("") + " (" + tp["stock_code"] + ")"
    tp.loc[tp["stock_code"] == "22502", "label"] += " *"
    st.altair_chart(
        alt.Chart(tp).mark_bar(color=BLUE, cornerRadiusEnd=4)
        .encode(
            x=alt.X("sales_after_cancellations:Q", title="£ after recorded product cancellations",
                    axis=alt.Axis(format="~s")),
            y=alt.Y("label:N", sort="-x", title=None, axis=alt.Axis(labelLimit=320)),
            tooltip=[alt.Tooltip("label:N", title="Product"),
                     alt.Tooltip("sales_after_cancellations:Q", title="£ after cancellations",
                                 format=MONEY),
                     alt.Tooltip("gross_sales:Q", title="£ gross", format=MONEY),
                     alt.Tooltip("net_quantity:Q", title="Net units", format=",")],
        ).properties(height=340),
        width="stretch",
    )
    st.caption("Grouped by stock code. * £38,970 of this product's total is one sale "
               "(invoice 556444) reversed by a 'Manual' adjustment line, which this "
               "rule cannot net out; without it the product would not be in the top 10.")

# ---- Chart 3: top countries ----------------------------------------------
with right:
    st.subheader("3. Top 10 countries")
    tc = r["top_countries"].copy()
    hide_uk = st.checkbox("Hide United Kingdom (to compare the rest)")
    if hide_uk:
        tc = tc[tc["country"] != "United Kingdom"]
    st.altair_chart(
        alt.Chart(tc).mark_bar(color=BLUE, cornerRadiusEnd=4)
        .encode(
            x=alt.X("sales_after_cancellations:Q", title="£ after recorded product cancellations",
                    axis=alt.Axis(format="~s")),
            y=alt.Y("country:N", sort="-x", title=None),
            tooltip=[alt.Tooltip("country:N", title="Country"),
                     alt.Tooltip("sales_after_cancellations:Q", title="£ after cancellations",
                                 format=MONEY),
                     alt.Tooltip("pct_of_total:Q", title="% of all countries", format=".2f"),
                     alt.Tooltip("gross_sales:Q", title="£ gross", format=MONEY),
                     alt.Tooltip("orders:Q", title="Orders", format=",")],
        ).properties(height=340),
        width="stretch",
    )
    st.caption("Share is of the total across all 38 country values, which include "
               "'Unspecified' and 'European Community'.")

# ---- Chart 4: cleaning impact --------------------------------------------
st.subheader("4. How each cleaning rule changes the totals")
cs = r["cleaning_steps"].copy()
cs["label"] = cs["step"].astype(str) + ". " + cs["rule"]
st.altair_chart(
    alt.Chart(cs).mark_bar(color=BLUE, cornerRadiusEnd=4)
    .encode(
        x=alt.X("sum_line_amount:Q", title="Sum of quantity × unit price (£)",
                axis=alt.Axis(format="~s")),
        y=alt.Y("label:N", sort=None, title=None, axis=alt.Axis(labelLimit=360)),
        tooltip=[alt.Tooltip("rule:N", title="Rule"),
                 alt.Tooltip("rows_remaining:Q", title="Rows remaining", format=","),
                 alt.Tooltip("sum_line_amount:Q", title="£", format=MONEY)],
    ).properties(height=240),
    width="stretch",
)
st.caption("Each step keeps the filters above it. Removing cancellations raises the sum "
           "because cancellation amounts are negative. Step 4 is gross sales; step 5 is "
           "a sensitivity check only.")

# ---- Data-quality summary ------------------------------------------------
st.subheader("Data-quality summary")
d1, d2 = st.columns(2)
with d1:
    st.markdown(f"**Raw file:** {h.raw_line_items:,} line items, {h.raw_invoices:,} invoices. "
                "No rows are deleted; each rule below is a flag.")
    st.markdown("**Rows per flag** (flags overlap, so counts are not additive)")
    st.dataframe(r["dq_flag_counts"], hide_index=True, width="stretch",
                 column_config={"rows_flagged": st.column_config.NumberColumn(format="localized")})
with d2:
    st.markdown("**Sequential exclusions**")
    st.dataframe(cs[["step", "rule", "rows_remaining", "sum_line_amount"]],
                 hide_index=True, width="stretch",
                 column_config={"rows_remaining": st.column_config.NumberColumn(format="localized"),
                                "sum_line_amount": st.column_config.NumberColumn(format="localized")})
    st.markdown(
        f"- Product cancellation lines: {h.product_cancellation_lines:,}, "
        f"worth £{h.product_cancellation_value:,.0f}\n"
        f"- Gross sales on rows with no CustomerID: £{h.gross_sales_missing_customer:,.0f} "
        f"({h.gross_sales_missing_customer / h.gross_sales:.1%} of gross sales)"
    )
