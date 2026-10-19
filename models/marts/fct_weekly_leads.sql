-- Weekly leads per channel with an anomaly flag.
-- A week is flagged when a channel that normally brings at least 8 leads a week
-- drops below 25% of its trailing 8 week average. At these volumes ordinary
-- week to week noise almost never falls that far, so a flag usually means
-- something broke (a form, a tracking tag, an ad account) rather than bad luck.
-- The final, partial week is excluded so it does not raise a false alarm.
WITH weekly AS (
    -- Build a full week by channel grid so a week with zero leads still appears
    SELECT w.week, ch.channel, COUNT(c.contact_id) AS leads
    FROM (
        SELECT DISTINCT date_trunc('week', createdate) AS week FROM stg_contacts
        WHERE date_trunc('week', createdate) + INTERVAL 6 DAY <= (SELECT MAX(createdate) FROM stg_contacts)
    ) w
    CROSS JOIN (SELECT DISTINCT source AS channel FROM stg_contacts) ch
    LEFT JOIN stg_contacts c
        ON date_trunc('week', c.createdate) = w.week AND c.source = ch.channel
    GROUP BY 1, 2
),
stats AS (
    SELECT
        *,
        AVG(leads)    OVER w AS trailing_avg,
        STDDEV(leads) OVER w AS trailing_std
    FROM weekly
    WINDOW w AS (PARTITION BY channel ORDER BY week ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING)
)
SELECT
    week,
    channel,
    leads,
    trailing_avg,
    trailing_std,
    (leads - trailing_avg) / NULLIF(trailing_std, 0)            AS z_score,
    COALESCE(trailing_avg >= 8 AND leads < 0.25 * trailing_avg, FALSE) AS is_anomaly
FROM stats
ORDER BY week, channel;
