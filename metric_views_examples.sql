-- PulseIQ PQ-04: reusable metric views
-- Raw source tables are never modified.
-- Known duplicated payroll records are excluded from trusted payroll metrics.
-- Small groups are masked where a minimum group size is defined.

CREATE OR REPLACE VIEW m01_headcount AS
SELECT month_start_date, department_id,
       CASE WHEN headcount_end >= 5 THEN headcount_end END AS headcount,
       headcount_end AS group_size
FROM raw.fact_headcount_monthly;

CREATE OR REPLACE VIEW m02_hires AS
SELECT month_start_date, department_id,
       CASE WHEN headcount_end >= 5 THEN hires END AS hires,
       headcount_end AS group_size
FROM raw.fact_headcount_monthly;

CREATE OR REPLACE VIEW m03_exits AS
SELECT month_start_date, department_id,
       CASE WHEN headcount_end >= 5 THEN exits END AS exits,
       headcount_end AS group_size
FROM raw.fact_headcount_monthly;

CREATE OR REPLACE VIEW m04_monthly_attrition AS
SELECT month_start_date, department_id,
       CASE WHEN headcount_start >= 10
            THEN ROUND(100.0 * exits / NULLIF(headcount_start, 0), 2)
       END AS attrition_pct,
       headcount_start AS group_size
FROM raw.fact_headcount_monthly;

CREATE OR REPLACE VIEW m05_rolling_12m_attrition AS
SELECT month_start_date, department_id,
       CASE WHEN AVG(headcount_end) OVER (
                    PARTITION BY department_id ORDER BY month_start_date
                    ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
                 ) >= 10
            THEN ROUND(
                100.0 * SUM(exits) OVER (
                    PARTITION BY department_id ORDER BY month_start_date
                    ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
                ) /
                NULLIF(AVG(headcount_end) OVER (
                    PARTITION BY department_id ORDER BY month_start_date
                    ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
                ), 0), 2)
       END AS attrition_pct,
       AVG(headcount_end) OVER (
           PARTITION BY department_id ORDER BY month_start_date
           ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
       ) AS average_headcount
FROM raw.fact_headcount_monthly;

CREATE OR REPLACE VIEW m06_voluntary_attrition AS
SELECT month_start_date, department_id,
       CASE WHEN AVG(headcount_end) OVER (
                    PARTITION BY department_id ORDER BY month_start_date
                    ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
                 ) >= 10
            THEN ROUND(
                100.0 * SUM(voluntary_exits) OVER (
                    PARTITION BY department_id ORDER BY month_start_date
                    ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
                ) /
                NULLIF(AVG(headcount_end) OVER (
                    PARTITION BY department_id ORDER BY month_start_date
                    ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
                ), 0), 2)
       END AS voluntary_attrition_pct
FROM raw.fact_headcount_monthly;

CREATE OR REPLACE VIEW m07_gross_pay AS
SELECT period_end_date, department_id,
       COUNT(DISTINCT employee_id) AS employees_paid,
       CASE WHEN COUNT(DISTINCT employee_id) >= 5
            THEN ROUND(SUM(gross_pay), 2) END AS gross_pay
FROM (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY run_id, employee_id, date_key
        ORDER BY CASE WHEN payroll_item_id LIKE 'PI-X%' THEN 1 ELSE 0 END,
                 payroll_item_id
    ) AS duplicate_rank
    FROM raw.fact_payroll
) p
WHERE duplicate_rank = 1
GROUP BY period_end_date, department_id;

CREATE OR REPLACE VIEW m08_net_pay AS
SELECT period_end_date, department_id,
       COUNT(DISTINCT employee_id) AS employees_paid,
       CASE WHEN COUNT(DISTINCT employee_id) >= 5
            THEN ROUND(SUM(net_pay), 2) END AS net_pay
FROM (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY run_id, employee_id, date_key
        ORDER BY CASE WHEN payroll_item_id LIKE 'PI-X%' THEN 1 ELSE 0 END,
                 payroll_item_id
    ) AS duplicate_rank
    FROM raw.fact_payroll
) p
WHERE duplicate_rank = 1
GROUP BY period_end_date, department_id;

CREATE OR REPLACE VIEW m09_employer_cost AS
SELECT period_end_date, department_id,
       COUNT(DISTINCT employee_id) AS employees_paid,
       CASE WHEN COUNT(DISTINCT employee_id) >= 5
            THEN ROUND(SUM(employer_cost), 2) END AS employer_cost
FROM (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY run_id, employee_id, date_key
        ORDER BY CASE WHEN payroll_item_id LIKE 'PI-X%' THEN 1 ELSE 0 END,
                 payroll_item_id
    ) AS duplicate_rank
    FROM raw.fact_payroll
) p
WHERE duplicate_rank = 1
GROUP BY period_end_date, department_id;

CREATE OR REPLACE VIEW m10_cost_per_head AS
SELECT period_end_date, department_id,
       COUNT(DISTINCT employee_id) AS employees_paid,
       CASE WHEN COUNT(DISTINCT employee_id) >= 5
            THEN ROUND(SUM(employer_cost) /
                       NULLIF(COUNT(DISTINCT employee_id), 0), 2)
       END AS cost_per_head
FROM (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY run_id, employee_id, date_key
        ORDER BY CASE WHEN payroll_item_id LIKE 'PI-X%' THEN 1 ELSE 0 END,
                 payroll_item_id
    ) AS duplicate_rank
    FROM raw.fact_payroll
) p
WHERE duplicate_rank = 1
GROUP BY period_end_date, department_id;

CREATE OR REPLACE VIEW m11_overtime_share AS
SELECT period_end_date, department_id,
       CASE WHEN COUNT(DISTINCT employee_id) >= 5
            THEN ROUND(100.0 * SUM(overtime_pay) /
                       NULLIF(SUM(employer_cost), 0), 2)
       END AS overtime_share_pct,
       COUNT(DISTINCT employee_id) AS group_size
FROM (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY run_id, employee_id, date_key
        ORDER BY CASE WHEN payroll_item_id LIKE 'PI-X%' THEN 1 ELSE 0 END,
                 payroll_item_id
    ) AS duplicate_rank
    FROM raw.fact_payroll
) p
WHERE duplicate_rank = 1
GROUP BY period_end_date, department_id;

CREATE OR REPLACE VIEW m12_variable_pay_share AS
SELECT period_end_date, department_id,
       CASE WHEN COUNT(DISTINCT employee_id) >= 5
            THEN ROUND(100.0 * SUM(variable_pay) /
                       NULLIF(SUM(gross_pay), 0), 2)
       END AS variable_pay_share_pct,
       COUNT(DISTINCT employee_id) AS group_size
FROM (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY run_id, employee_id, date_key
        ORDER BY CASE WHEN payroll_item_id LIKE 'PI-X%' THEN 1 ELSE 0 END,
                 payroll_item_id
    ) AS duplicate_rank
    FROM raw.fact_payroll
) p
WHERE duplicate_rank = 1
GROUP BY period_end_date, department_id;

CREATE OR REPLACE VIEW m13_attendance_rate AS
SELECT period_end_date, department_id,
       CASE WHEN COUNT(DISTINCT employee_id) >= 5
            THEN ROUND(
                100.0 * SUM(present_days + 0.5 * half_days_unpaid) /
                NULLIF(SUM(scheduled_days), 0), 2)
       END AS attendance_rate_pct,
       COUNT(DISTINCT employee_id) AS group_size
FROM raw.fact_attendance_monthly
GROUP BY period_end_date, department_id;
-- M14: Late arrival rate
CREATE OR REPLACE VIEW m14_late_arrival_rate AS
SELECT period_end_date, department_id,
       CASE WHEN COUNT(DISTINCT employee_id) >= 5
            THEN ROUND(100.0 * SUM(late_arrivals) /
                       NULLIF(SUM(present_days), 0), 2)
       END AS late_arrival_rate_pct,
       COUNT(DISTINCT employee_id) AS group_size
FROM raw.fact_attendance_monthly
GROUP BY period_end_date, department_id;

-- M15: Leave without pay days (aggregated for privacy)
CREATE OR REPLACE VIEW m15_lop_days AS
SELECT period_end_date, department_id,
       COUNT(DISTINCT employee_id) AS group_size,
       CASE WHEN COUNT(DISTINCT employee_id) >= 5
            THEN ROUND(SUM(lop_days), 2)
       END AS lop_days
FROM raw.fact_payroll
WHERE payroll_item_id NOT IN ('PI-X0001', 'PI-X0002')
GROUP BY period_end_date, department_id;

-- M16: Revenue by account and month
CREATE OR REPLACE VIEW m16_revenue AS
SELECT DATE_TRUNC('month', entry_date)::DATE AS month_start_date,
       account_code,
       ROUND(-SUM(signed_amount_debit_positive), 2) AS revenue
FROM raw.fact_ledger
WHERE account_code IN (4001, 4002, 4003, 4004)
GROUP BY 1, 2;

-- M17: Net profit by month (revenue less expense)
CREATE OR REPLACE VIEW m17_net_profit AS
SELECT DATE_TRUNC('month', entry_date)::DATE AS month_start_date,
       ROUND(-SUM(signed_amount_debit_positive), 2) AS net_profit
FROM raw.fact_ledger
WHERE account_code BETWEEN 4000 AND 5999
GROUP BY 1;

-- M18: Operating margin
CREATE OR REPLACE VIEW m18_operating_margin AS
WITH monthly AS (
    SELECT DATE_TRUNC('month', entry_date)::DATE AS month_start_date,
           SUM(CASE WHEN account_code IN (4001,4002,4003,4004)
                    THEN -signed_amount_debit_positive ELSE 0 END) AS revenue,
           SUM(CASE WHEN account_code BETWEEN 4000 AND 5999
                    THEN -signed_amount_debit_positive ELSE 0 END) AS net_profit
    FROM raw.fact_ledger
    GROUP BY 1
)
SELECT month_start_date,
       ROUND(100.0 * net_profit / NULLIF(revenue, 0), 2) AS operating_margin_pct
FROM monthly;

-- M19: Payroll as percentage of revenue
CREATE OR REPLACE VIEW m19_payroll_pct_revenue AS
WITH payroll AS (
    SELECT DATE_TRUNC('month', entry_date)::DATE AS month_start_date,
           SUM(signed_amount_debit_positive) AS payroll_cost
    FROM raw.fact_ledger
    WHERE account_code BETWEEN 5001 AND 5005
    GROUP BY 1
),
revenue AS (
    SELECT DATE_TRUNC('month', entry_date)::DATE AS month_start_date,
           -SUM(signed_amount_debit_positive) AS revenue
    FROM raw.fact_ledger
    WHERE account_code IN (4001,4002,4003,4004)
    GROUP BY 1
)
SELECT p.month_start_date, ROUND(100.0 * p.payroll_cost /
       NULLIF(r.revenue, 0), 2) AS payroll_pct_revenue
FROM payroll p JOIN revenue r USING (month_start_date);

-- M20: DSO using month-end outstanding receivables / last 90-day billed revenue
CREATE OR REPLACE VIEW m20_dso AS
WITH months AS (
    SELECT DISTINCT DATE_TRUNC('month', invoice_date)::DATE AS month_start_date
    FROM raw.fact_invoice
),
calc AS (
    SELECT m.month_start_date,
           (SELECT SUM(i.balance_due)
            FROM raw.fact_invoice i
            WHERE i.invoice_date < m.month_start_date + INTERVAL '1 month'
              AND i.status NOT IN ('DRAFT', 'CANCELLED')) AS receivables,
           (SELECT SUM(i.total_amount)
            FROM raw.fact_invoice i
            WHERE i.invoice_date >= m.month_start_date - INTERVAL '2 months'
              AND i.invoice_date < m.month_start_date + INTERVAL '1 month'
              AND i.status NOT IN ('DRAFT', 'CANCELLED')) AS billed_90d
    FROM months m
)
SELECT month_start_date,
       ROUND(90.0 * receivables / NULLIF(billed_90d, 0), 2) AS dso_days
FROM calc;

-- M21: Overdue receivables by client and report date
CREATE OR REPLACE VIEW m21_overdue_receivables AS
SELECT client_id, MAX(due_date) AS report_date,
       SUM(balance_due) AS overdue_receivables
FROM raw.fact_invoice
WHERE days_past_due_at_cutoff > 0
  AND status NOT IN ('DRAFT', 'CANCELLED', 'PAID')
GROUP BY client_id;

-- M22: Task completion rate by team and sprint
CREATE OR REPLACE VIEW m22_task_completion_rate AS
SELECT team_id, sprint_id, COUNT(*) AS eligible_tasks,
       CASE WHEN COUNT(*) >= 5
            THEN ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'Done') /
                       NULLIF(COUNT(*) FILTER (WHERE status <> 'Cancelled'), 0), 2)
       END AS task_completion_pct
FROM raw.fact_task
WHERE status <> 'Cancelled'
GROUP BY team_id, sprint_id;

-- M23: On-time delivery rate by team and sprint
CREATE OR REPLACE VIEW m23_on_time_delivery_rate AS
SELECT team_id, sprint_id,
       COUNT(*) FILTER (WHERE status = 'Done') AS completed_tasks,
       CASE WHEN COUNT(*) FILTER (WHERE status = 'Done') >= 5
            THEN ROUND(100.0 * COUNT(*) FILTER (
                           WHERE status = 'Done' AND completed_on_time = 'Y') /
                       NULLIF(COUNT(*) FILTER (WHERE status = 'Done'), 0), 2)
       END AS on_time_delivery_pct
FROM raw.fact_task
GROUP BY team_id, sprint_id;

-- M24: Velocity
CREATE OR REPLACE VIEW m24_velocity AS
SELECT team_id, sprint_id,
       SUM(story_points) FILTER (WHERE status = 'Done') AS velocity_points
FROM raw.fact_task
GROUP BY team_id, sprint_id;

-- M25: Average cycle time
CREATE OR REPLACE VIEW m25_average_cycle_time AS
SELECT team_id, sprint_id,
       COUNT(*) FILTER (WHERE status = 'Done' AND started_date IS NOT NULL
                         AND completed_date IS NOT NULL
                         AND completed_date >= started_date) AS valid_completed_tasks,
       CASE WHEN COUNT(*) FILTER (WHERE status = 'Done'
                         AND started_date IS NOT NULL
                         AND completed_date IS NOT NULL
                         AND completed_date >= started_date) >= 5
            THEN ROUND(AVG(DATE_DIFF('day', started_date, completed_date))
                       FILTER (WHERE status = 'Done' AND started_date IS NOT NULL
                         AND completed_date IS NOT NULL
                         AND completed_date >= started_date), 2)
       END AS avg_cycle_time_days
FROM raw.fact_task
GROUP BY team_id, sprint_id;

-- M26: Anomaly flag rate by source and month
CREATE OR REPLACE VIEW m26_anomaly_flag_rate AS
SELECT source_dataset, DATE_TRUNC('month', period)::DATE AS month_start_date,
       COUNT(*) AS anomaly_rows,
       ROUND(100.0 * COUNT(*) FILTER (WHERE flagged = 'Y') /
             NULLIF(COUNT(*), 0), 2) AS anomaly_flag_pct
FROM raw.fact_anomaly
GROUP BY source_dataset, DATE_TRUNC('month', period)::DATE;

-- M27: High-risk share by department, minimum group size 10
CREATE OR REPLACE VIEW m27_high_risk_share AS
SELECT department_id, COUNT(*) AS group_size,
       CASE WHEN COUNT(*) >= 10
            THEN ROUND(100.0 * COUNT(*) FILTER (WHERE risk_band = 'High') /
                       NULLIF(COUNT(*), 0), 2)
       END AS high_risk_share_pct
FROM raw.fact_attrition_risk
GROUP BY department_id;

-- M28: Forecast MAPE, only where actual values exist
CREATE OR REPLACE VIEW m28_forecast_mape AS
SELECT f.department_id, f.forecast_month AS month_start_date,
       ROUND(AVG(100.0 * ABS(a.headcount_end - f.forecast_value) /
                 NULLIF(a.headcount_end, 0)), 2) AS forecast_mape_pct
FROM raw.fact_forecast f
JOIN raw.fact_headcount_monthly a
  ON a.department_id = f.department_id
 AND a.month_start_date = f.forecast_month
WHERE f.metric = 'headcount_end'
GROUP BY f.department_id, f.forecast_month;

-- Metric catalog for discoverability
CREATE OR REPLACE VIEW metric_catalog AS
SELECT metric_id, metric_name, business_definition, formula,
       source_table, grain, time_period, owner_team, unit,
       good_direction, caveat, minimum_group_size
FROM raw.metric_dictionary;