-- Weekly leads with the anomaly flag, computed in SQL because rolling windows are simpler here than in DAX.
SELECT week::DATE AS week_start, channel, leads, ROUND(trailing_avg, 1) AS trailing_avg, is_anomaly
FROM fct_weekly_leads;
