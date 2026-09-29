-- Each query starts with a "-- name: <name>" line. run_queries.py runs them
-- in order and saves each result to outputs/<name>.csv.
-- Terms: a "line item" is one row; an "order" is one distinct invoice_no.

-- name: headline
SELECT
    (SELECT COUNT(*) FROM line_items)                                AS raw_line_items,
    (SELECT COUNT(DISTINCT invoice_no) FROM line_items)              AS raw_invoices,
    (SELECT COUNT(*) FROM v_valid_sales)                             AS valid_sale_lines,
    (SELECT COUNT(DISTINCT invoice_no) FROM v_valid_sales)           AS valid_orders,
    (SELECT ROUND(SUM(line_amount), 2) FROM v_valid_sales)           AS gross_sales,
    (SELECT ROUND(SUM(line_amount) / COUNT(DISTINCT invoice_no), 2)
       FROM v_valid_sales)                                           AS avg_order_value,
    (SELECT COUNT(DISTINCT customer_id) FROM v_valid_sales)          AS distinct_customers,
    (SELECT ROUND(SUM(line_amount), 2) FROM v_valid_sales
      WHERE missing_customer_id = 1)                                 AS gross_sales_missing_customer,
    (SELECT COUNT(*) FROM v_product_cancellations)                   AS product_cancellation_lines,
    (SELECT ROUND(-SUM(line_amount), 2) FROM v_product_cancellations) AS product_cancellation_value,
    (SELECT ROUND(SUM(line_amount), 2) FROM v_sales_after_cancellations) AS sales_after_cancellations,
    (SELECT ROUND(SUM(line_amount), 2) FROM line_items
      WHERE is_shipping = 1 AND is_cancellation = 0
        AND qty_nonpositive = 0 AND price_nonpositive = 0)           AS shipping_charges,
    (SELECT MIN(invoice_date) FROM line_items)                       AS first_date,
    (SELECT MAX(invoice_date) FROM line_items)                       AS last_date;

-- name: monthly
-- Cancellations are placed in the month the cancellation was recorded.
WITH sales AS (
    SELECT strftime('%Y-%m', invoice_date) AS month,
           SUM(line_amount)               AS gross_sales,
           COUNT(*)                       AS sale_lines,
           COUNT(DISTINCT invoice_no)     AS orders
    FROM v_valid_sales
    GROUP BY month
),
cancels AS (
    SELECT strftime('%Y-%m', invoice_date) AS month,
           SUM(line_amount)               AS cancel_amount   -- negative
    FROM v_product_cancellations
    GROUP BY month
)
SELECT s.month,
       ROUND(s.gross_sales, 2)                                 AS gross_sales,
       ROUND(-COALESCE(c.cancel_amount, 0), 2)                 AS product_cancellation_value,
       ROUND(s.gross_sales + COALESCE(c.cancel_amount, 0), 2)  AS sales_after_cancellations,
       s.orders,
       s.sale_lines,
       CASE WHEN s.month = (SELECT strftime('%Y-%m', MAX(invoice_date)) FROM line_items)
            THEN 1 ELSE 0 END                                  AS is_partial_month
FROM sales s
LEFT JOIN cancels c ON c.month = s.month
ORDER BY s.month;

-- name: top_products
-- Grouped by stock_code; shown with the code's most frequent description.
WITH by_code AS (
    SELECT stock_code,
           SUM(line_amount)                                           AS sales_after_cancellations,
           SUM(CASE WHEN is_cancellation = 0 THEN line_amount END)    AS gross_sales,
           SUM(quantity)                                              AS net_quantity
    FROM v_sales_after_cancellations
    GROUP BY stock_code
),
desc_counts AS (
    SELECT stock_code, description,
           ROW_NUMBER() OVER (PARTITION BY stock_code
                              ORDER BY COUNT(*) DESC, description) AS rn
    FROM v_valid_sales
    WHERE description IS NOT NULL
    GROUP BY stock_code, description
)
SELECT b.stock_code,
       d.description,
       ROUND(b.sales_after_cancellations, 2) AS sales_after_cancellations,
       ROUND(COALESCE(b.gross_sales, 0), 2)  AS gross_sales,
       b.net_quantity
FROM by_code b
LEFT JOIN desc_counts d ON d.stock_code = b.stock_code AND d.rn = 1
ORDER BY b.sales_after_cancellations DESC
LIMIT 10;

-- name: top_countries
WITH by_country AS (
    SELECT country,
           SUM(line_amount)                                          AS sales_after_cancellations,
           SUM(CASE WHEN is_cancellation = 0 THEN line_amount END)   AS gross_sales,
           COUNT(DISTINCT CASE WHEN is_cancellation = 0 THEN invoice_no END) AS orders
    FROM v_sales_after_cancellations
    GROUP BY country
)
SELECT country,
       ROUND(sales_after_cancellations, 2) AS sales_after_cancellations,
       ROUND(gross_sales, 2)               AS gross_sales,
       orders,
       ROUND(100.0 * sales_after_cancellations
             / (SELECT SUM(sales_after_cancellations) FROM by_country), 2) AS pct_of_total
FROM by_country
ORDER BY sales_after_cancellations DESC
LIMIT 10;

-- name: dq_flag_counts
-- Flags overlap, so these counts are NOT additive.
SELECT 'is_cancellation' AS flag, SUM(is_cancellation) AS rows_flagged,
       ROUND(100.0 * SUM(is_cancellation) / COUNT(*), 2) AS pct_of_raw FROM line_items
UNION ALL SELECT 'missing_customer_id', SUM(missing_customer_id),
       ROUND(100.0 * SUM(missing_customer_id) / COUNT(*), 2) FROM line_items
UNION ALL SELECT 'missing_description', SUM(missing_description),
       ROUND(100.0 * SUM(missing_description) / COUNT(*), 2) FROM line_items
UNION ALL SELECT 'qty_nonpositive', SUM(qty_nonpositive),
       ROUND(100.0 * SUM(qty_nonpositive) / COUNT(*), 2) FROM line_items
UNION ALL SELECT 'price_nonpositive', SUM(price_nonpositive),
       ROUND(100.0 * SUM(price_nonpositive) / COUNT(*), 2) FROM line_items
UNION ALL SELECT 'is_non_product', SUM(is_non_product),
       ROUND(100.0 * SUM(is_non_product) / COUNT(*), 2) FROM line_items
UNION ALL SELECT 'is_duplicate', SUM(is_duplicate),
       ROUND(100.0 * SUM(is_duplicate) / COUNT(*), 2) FROM line_items;

-- name: cleaning_steps
-- Sequential exclusions: each step keeps the previous step's filters and
-- adds one more. Step 4 equals gross sales. Step 5 is a sensitivity check
-- only (duplicates stay in the headline numbers).
SELECT 0 AS step, 'All raw line items' AS rule,
       COUNT(*) AS rows_remaining, ROUND(SUM(line_amount), 2) AS sum_line_amount
FROM line_items
UNION ALL
SELECT 1, 'Exclude cancellations (invoice starts with C)',
       COUNT(*), ROUND(SUM(line_amount), 2)
FROM line_items WHERE is_cancellation = 0
UNION ALL
SELECT 2, 'Exclude remaining quantity <= 0',
       COUNT(*), ROUND(SUM(line_amount), 2)
FROM line_items WHERE is_cancellation = 0 AND qty_nonpositive = 0
UNION ALL
SELECT 3, 'Exclude unit price <= 0',
       COUNT(*), ROUND(SUM(line_amount), 2)
FROM line_items WHERE is_cancellation = 0 AND qty_nonpositive = 0
                  AND price_nonpositive = 0
UNION ALL
SELECT 4, 'Exclude non-product codes (= gross sales)',
       COUNT(*), ROUND(SUM(line_amount), 2)
FROM line_items WHERE is_cancellation = 0 AND qty_nonpositive = 0
                  AND price_nonpositive = 0 AND is_non_product = 0
UNION ALL
SELECT 5, 'Sensitivity: also exclude exact duplicates',
       COUNT(*), ROUND(SUM(line_amount), 2)
FROM line_items WHERE is_cancellation = 0 AND qty_nonpositive = 0
                  AND price_nonpositive = 0 AND is_non_product = 0
                  AND is_duplicate = 0
ORDER BY step;
