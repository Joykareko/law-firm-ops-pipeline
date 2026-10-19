-- Utilization, realization and collections per attorney per month.
--   Utilization  = billable hours / capacity (140 billable hours per month target)
--   Realization  = amount billed / standard value of billable time
--   Collection   = amount collected / amount billed
WITH time_m AS (
    SELECT
        t.attorney,
        date_trunc('month', t.date)                             AS month,
        SUM(CASE WHEN t.billable THEN t.hours ELSE 0 END)       AS billable_hours,
        SUM(t.hours)                                            AS total_hours,
        SUM(CASE WHEN t.billable THEN t.hours * t.rate ELSE 0 END) AS standard_value
    FROM stg_time_entries t
    GROUP BY 1, 2
),
inv_m AS (
    -- An invoice issued early in month M covers work done in month M - 1
    SELECT
        m.attorney,
        date_trunc('month', i.issued_date) - INTERVAL 1 MONTH   AS month,
        SUM(i.amount_billed)                                    AS billed,
        SUM(i.amount_paid)                                      AS collected
    FROM stg_invoices i
    JOIN stg_matters m USING (matter_id)
    GROUP BY 1, 2
)
SELECT
    t.attorney,
    t.month,
    t.billable_hours,
    t.total_hours,
    t.standard_value,
    COALESCE(i.billed, 0)                                       AS billed,
    COALESCE(i.collected, 0)                                    AS collected,
    t.billable_hours / 140.0                                    AS utilization,
    CASE WHEN t.standard_value > 0 THEN COALESCE(i.billed, 0) / t.standard_value END AS realization,
    CASE WHEN i.billed > 0 THEN i.collected / i.billed END      AS collection_rate
FROM time_m t
LEFT JOIN inv_m i ON i.attorney = t.attorney AND i.month = t.month
ORDER BY t.month, t.attorney;
