-- One row per day across the reporting period. Weeks start on Monday.
SELECT
    d::DATE                                    AS date,
    year(d)                                    AS year,
    date_trunc('month', d)::DATE               AS month_start,
    strftime(d, '%b %Y')                       AS month_label,
    date_trunc('week', d)::DATE                AS week_start,
    dayofweek(d) IN (0, 6)                     AS is_weekend
FROM range(DATE '2025-01-01', DATE '2026-10-01', INTERVAL 1 DAY) t(d);
