-- The attorney is reached through Matters, so there is only one path from attorney to time.
SELECT
    entry_id,
    matter_id,
    date::DATE                                           AS date,
    hours,
    billable,
    rate,
    CASE WHEN billable THEN hours ELSE 0 END             AS billable_hours,
    ROUND(CASE WHEN billable THEN hours * rate ELSE 0 END, 2) AS standard_value,
    needs_review
FROM stg_time_entries;
