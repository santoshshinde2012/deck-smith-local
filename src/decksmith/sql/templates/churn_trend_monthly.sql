-- id: churn_trend_monthly
-- description: Monthly churn rate over a period, one point per month
-- kind: series
-- format: pct1
-- unit: ratio
-- param: start_month date [0-9]{4}-[0-9]{2}-01
-- param: end_month date [0-9]{4}-[0-9]{2}-01
SELECT date_format(`month`, 'yyyy-MM') AS period,
       try_divide(SUM(churned), SUM(active_start)) AS churn_rate
FROM {{table:cs.churn_monthly}}
WHERE `month` >= :start_month AND `month` < :end_month
GROUP BY date_format(`month`, 'yyyy-MM')
ORDER BY period
