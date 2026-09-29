# Findings: Online Retail sales and data quality

**Scope.** UCI Online Retail, 541,909 line items, 1 Dec 2010 – 9 Dec 2011. Every figure
below comes from the files in `outputs/`, produced by `src/run_queries.py`. Amounts are
quantity × unit price in pounds sterling. **Gross sales** means valid sale lines only
(no cancellations, quantity > 0, price > 0, no postage, fees or adjustments). It's not net revenue.

## 1. Monthly sales
- Gross sales totalled **£10,271,433** across **19,773 orders**, an average order value of **£519.47**.
- From December 2010 to August 2011, monthly gross sales ranged from **£508,886 (Feb 2011)**
  to **£777,932 (Dec 2010)**.
- **September–November 2011 were the only months above £1M**: £1,030,475, £1,106,670 and
  **£1,457,746 (Nov 2011, the highest month, 2,751 orders)**. Together they were 35.0% of gross sales.
- December 2011 covers only 9 days (£615,493 gross), so it isn't comparable to other months.
- With only 13 months of data, this can't show whether the autumn rise is seasonal or growth.

## 2. Products and countries (sales after recorded product cancellations)
- **REGENCY CAKESTAND 3 TIER (22423)** is the top product at **£164,762**. That's well
  ahead of #2 PARTY BUNTING (£98,303), #3 WHITE HANGING HEART T-LIGHT HOLDER (£97,895) and
  #4 JUMBO BAG RED RETROSPOT (£92,356). The top 10 products are 8.2% of sales
  after cancellations, so sales are spread across many products.
- The #9 product, PICNIC BASKET WICKER SMALL (22502), is inflated. £38,970 of it is one
  sale that was reversed through a manual adjustment, which these rules don't net out.
- **The United Kingdom is 84.77%** of sales after cancellations (£8,301,718). The next
  largest are the Netherlands (2.89%, from only 93 orders), EIRE (2.65%), Germany (2.05%)
  and France (1.86%).

## 3. Data quality
- **Cancellations:** 9,288 line items (1.71%) on 3,836 invoices. Product cancellations total
  **£478,724**, which is 4.7% of gross sales. **Two bulk orders account for £245,653 (51.3%) of that:**
  80,995 units of 23843 (invoice 581483) and 74,215 units of 23166 (invoice 541431). Each was
  cancelled by the customer who placed it, within 12 and 16 minutes respectively.
- **Missing CustomerID:** 135,080 rows (24.93%), worth £1,510,366 (14.7%) of gross sales.
  The dataset's UCI page says it has no missing values, but it does.
- **Other invalid values:**
  - 1,336 non-cancellation rows have quantity ≤ 0. All of them have no customer and look like stock write-offs.
  - 2,515 rows have a zero unit price.
  - 2 rows are bad-debt adjustments with a negative price.
  - 1,454 rows have a blank description.
  - 2,946 rows are non-product codes, such as postage, fees and adjustments.
- **Exact duplicate rows:** 5,268 (0.97%).

## 4. How the cleaning rules change results
- The raw sum of all line amounts, £9,747,748, is **£523,685 lower** than gross sales. That's
  because cancellations and fees are negative. Taking the raw sum would understate sales.
- Excluding non-product codes removes **£395,251** from 2,343 remaining rows. Postage makes up
  much of this: shipping charges total £291,402 and are reported separately.
- Subtracting product cancellations lowers gross sales from £10,271,433 to **£9,792,709**.
  - The biggest effect is on rankings. Without netting, the two cancelled bulk orders would put
    their products near the top.
  - It also affects single months: January 2011 falls from £671,933 to £580,407, and
    December 2011 from £615,493 to £441,367.
- Excluding exact duplicates would lower gross sales by only **£24,214 (0.24%)**, so that
  choice barely matters.

## Caveats
Cancellations are dated when they were recorded, and some may reverse sales from before the data window. Reversals booked as manual adjustments aren't netted out. Discounts, refunds outside the file, VAT and costs aren't captured.
