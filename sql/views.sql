-- Views that define the analysis subsets. The base table `line_items`
-- keeps every raw row; each exclusion is a visible WHERE clause here.

-- Valid sale lines: the basis of "gross sales".
DROP VIEW IF EXISTS v_valid_sales;
CREATE VIEW v_valid_sales AS
SELECT *
FROM line_items
WHERE is_cancellation = 0
  AND qty_nonpositive = 0
  AND price_nonpositive = 0
  AND is_non_product = 0;

-- Cancellation lines for real products (fees/postage/manual codes excluded).
-- line_amount is negative on these rows.
DROP VIEW IF EXISTS v_product_cancellations;
CREATE VIEW v_product_cancellations AS
SELECT *
FROM line_items
WHERE is_cancellation = 1
  AND is_non_product = 0;

-- Both of the above stacked, so SUM(line_amount) gives
-- "sales after recorded product cancellations".
DROP VIEW IF EXISTS v_sales_after_cancellations;
CREATE VIEW v_sales_after_cancellations AS
SELECT * FROM v_valid_sales
UNION ALL
SELECT * FROM v_product_cancellations;
