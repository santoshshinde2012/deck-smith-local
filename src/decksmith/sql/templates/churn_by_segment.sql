-- id: churn_by_segment
-- description: Weighted monthly churn by customer segment over a period; not cumulative cohort churn
-- kind: series
-- format: pct1
-- unit: ratio
-- param: start_month date [0-9]{4}-[0-9]{2}-01
-- param: end_month date [0-9]{4}-[0-9]{2}-01
SELECT segment,
       try_divide(SUM(churned), SUM(active_start)) AS churn_rate
FROM {{table:cs.churn_monthly}}
WHERE `month` >= :start_month AND `month` < :end_month
GROUP BY segment
ORDER BY segment
