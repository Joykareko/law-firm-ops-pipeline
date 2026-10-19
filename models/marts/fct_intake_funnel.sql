-- Lead to consultation to retained client, by channel and month, with cost per retained client.
WITH funnel AS (
    SELECT
        date_trunc('month', createdate)                     AS month,
        source                                              AS channel,
        COUNT(*)                                            AS leads,
        COUNT(consultation_date)                            AS consultations,
        COUNT(retained_date)                                AS retained,
        AVG(date_diff('day', createdate, retained_date))    AS avg_days_to_retain
    FROM stg_contacts
    GROUP BY 1, 2
),
spend AS (
    SELECT CAST(month || '-01' AS DATE) AS month, channel, spend_usd
    FROM stg_marketing_spend
)
SELECT
    f.month,
    f.channel,
    f.leads,
    f.consultations,
    f.retained,
    f.avg_days_to_retain,
    COALESCE(s.spend_usd, 0)                                AS spend_usd,
    CASE WHEN f.retained > 0 THEN COALESCE(s.spend_usd, 0) / f.retained END AS cost_per_retained_client
FROM funnel f
LEFT JOIN spend s ON s.month = f.month AND s.channel = f.channel
ORDER BY f.month, f.channel;
