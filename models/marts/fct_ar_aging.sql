-- Outstanding receivables as of the reporting date, bucketed by age.
WITH open_items AS (
    SELECT
        i.invoice_id,
        m.practice_area,
        m.attorney,
        i.issued_date,
        i.amount_billed - i.amount_paid                         AS outstanding,
        date_diff('day', i.issued_date, DATE '2026-09-30')      AS days_outstanding
    FROM stg_invoices i
    JOIN stg_matters m USING (matter_id)
    WHERE i.amount_billed - i.amount_paid > 0.01
)
SELECT
    *,
    CASE
        WHEN days_outstanding <= 30 THEN '0-30 days'
        WHEN days_outstanding <= 60 THEN '31-60 days'
        WHEN days_outstanding <= 90 THEN '61-90 days'
        ELSE 'Over 90 days'
    END AS aging_bucket
FROM open_items;
