SELECT
    attorney,
    MEDIAN(rate)        AS standard_rate,
    140                 AS monthly_capacity_hours
FROM stg_time_entries
GROUP BY 1
ORDER BY 1;
