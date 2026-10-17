-- id: active_subscriptions
-- description: Active subscriptions at the start of a month
-- kind: scalar
-- format: int
-- unit: subscriptions
-- param: start_month date [0-9]{4}-[0-9]{2}-01
SELECT SUM(active_start) AS active_subscriptions
FROM {{table:cs.churn_monthly}}
WHERE `month` = :start_month
