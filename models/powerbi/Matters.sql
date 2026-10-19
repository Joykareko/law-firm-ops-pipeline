SELECT
    matter_id,
    client_email,
    practice_area,
    attorney,
    open_date::DATE                                                     AS open_date,
    close_date::DATE                                                    AS close_date,
    status,
    date_diff('day', open_date, COALESCE(close_date, DATE '2026-09-30')) AS days_open
FROM stg_matters;
