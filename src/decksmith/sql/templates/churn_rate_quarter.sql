-- id: churn_rate_quarter
-- description: Weighted monthly churn over a period (sum of monthly churned / sum of monthly active starts); not cumulative cohort churn
-- kind: scalar
-- format: pct1
-- unit: ratio
-- param: start_month date [0-9]{4}-[0-9]{2}-01
-- param: end_month date [0-9]{4}-[0-9]{2}-01
SELECT try_divide(SUM(churned), SUM(active_start)) AS churn_rate
FROM {{table:cs.churn_monthly}}
WHERE `month` >= :start_month AND `month` < :end_month
