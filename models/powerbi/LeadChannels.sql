-- One row per lead source. channel_type separates channels the firm pays for from free ones.
SELECT DISTINCT
    source AS channel,
    CASE
        WHEN source IN ('Google Ads', 'Facebook Ads', 'Legal Directory') THEN 'Paid'
        WHEN source = 'Website Organic' THEN 'Organic'
        WHEN source = 'Referral' THEN 'Referral'
        ELSE 'Other'
    END AS channel_type
FROM stg_contacts
ORDER BY 1;
