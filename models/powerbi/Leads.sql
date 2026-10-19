SELECT
    contact_id,
    source                                          AS channel,
    createdate::DATE                                AS created_date,
    consultation_date::DATE                         AS consultation_date,
    retained_date::DATE                             AS retained_date,
    consultation_date IS NOT NULL                   AS is_consulted,
    retained_date IS NOT NULL                       AS is_retained,
    date_diff('day', createdate, retained_date)     AS days_to_retain
FROM stg_contacts;
