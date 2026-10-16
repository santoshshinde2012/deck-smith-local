-- id: nrr_quarter
-- description: Net revenue retention for a period (retained MRR / starting MRR), as a ratio
-- kind: scalar
-- format: pct1
-- unit: ratio
-- param: start_month date [0-9]{4}-[0-9]{2}-01
-- param: end_month date [0-9]{4}-[0-9]{2}-01
SELECT try_divide(SUM(mrr_retained), SUM(mrr_start)) AS nrr
FROM {{table:cs.revenue_monthly}}
WHERE `month` >= :start_month AND `month` < :end_month
