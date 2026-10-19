-- Receivables are measured as of the reporting date, 30 Sep 2026.
-- Each invoice is issued early in a month and bills the work done in the previous month,
-- so work_month_start lets realization compare billing with the time it actually covers.
SELECT
    invoice_id,
    matter_id,
    issued_date::DATE                                       AS issued_date,
    (date_trunc('month', issued_date) - INTERVAL 1 MONTH)::DATE AS work_month_start,
    paid_date::DATE                                         AS paid_date,
    amount_billed,
    amount_paid,
    ROUND(amount_billed - amount_paid, 2)                   AS outstanding,
    date_diff('day', issued_date, DATE '2026-09-30')        AS days_since_issue,
    CASE
        WHEN amount_billed - amount_paid <= 0.01 THEN 'Paid'
        WHEN date_diff('day', issued_date, DATE '2026-09-30') <= 30 THEN '0-30 days'
        WHEN date_diff('day', issued_date, DATE '2026-09-30') <= 60 THEN '31-60 days'
        WHEN date_diff('day', issued_date, DATE '2026-09-30') <= 90 THEN '61-90 days'
        ELSE 'Over 90 days'
    END                                                     AS aging_bucket,
    CASE
        WHEN amount_billed - amount_paid <= 0.01 THEN 0
        WHEN date_diff('day', issued_date, DATE '2026-09-30') <= 30 THEN 1
        WHEN date_diff('day', issued_date, DATE '2026-09-30') <= 60 THEN 2
        WHEN date_diff('day', issued_date, DATE '2026-09-30') <= 90 THEN 3
        ELSE 4
    END                                                     AS aging_order,
    needs_review
FROM stg_invoices;
