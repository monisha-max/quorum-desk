-- Ledger features Quorum asks of BigQuery.
-- The prototype computes the same fields in quorum/warehouse.py
-- so a hearing does not wait on a loaded dataset.

SELECT
  alert_id,
  COUNT(*) AS payment_count,
  SUM(amount) AS total_amount,
  COUNTIF(currency = 'SGD' AND amount >= 8000 AND amount < 10000) AS splits_just_under_sgd_10000
FROM `harbourline.mart.payments`
GROUP BY alert_id;
