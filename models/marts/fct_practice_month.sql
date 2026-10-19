-- Billed and collected revenue by practice area and month of issue.
SELECT
    m.practice_area,
    date_trunc('month', i.issued_date)  AS month,
    COUNT(DISTINCT i.matter_id)         AS active_billed_matters,
    SUM(i.amount_billed)                AS billed,
    SUM(i.amount_paid)                  AS collected
FROM stg_invoices i
JOIN stg_matters m USING (matter_id)
GROUP BY 1, 2
ORDER BY 2, 1;
