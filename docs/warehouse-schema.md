# PulseIQ Analytics Warehouse Schema

## Overview

The warehouse uses PostgreSQL under the `dw` schema. It contains 29 tables for dimensions, facts, reference data, data quality, and metrics.

## Dimension Tables

- `dim_date`: One row per calendar date.
- `dim_department`: One row per department.
- `dim_role`: One row per role.
- `dim_employee`: One row per employee version, if version history is available.
- `dim_leave_type`: One row per leave type.
- `dim_account`: One row per account.
- `dim_client`: One row per client.
- `dim_sprint`: One row per sprint.
- `dim_team`: One row per team.
- `dim_vendor`: One row per vendor.
- `dim_location`: One row per work location.

## Fact Tables and Grain

- `fact_payroll`: One row per payroll item.
- `fact_leave`: One row per leave request.
- `fact_ledger`: One row per ledger line.
- `fact_task`: One row per task.
- `fact_expense`: One row per expense.
- `fact_forecast`: One row per forecast record.
- `fact_invoice`: One row per invoice.
- `fact_invoice_payment`: One row per invoice payment record.
- `fact_anomaly`: One row per anomaly detection result.
- `fact_attendance_monthly`: One row per attendance fact record at its stored grain.
- `fact_headcount_monthly`: One row per month and department.
- `budget_payroll_dept_month`: One row per month and department payroll budget.
- `kpi_targets`: One row per month and department KPI target.

## Validation Requirements

1. `PR-2025-04` employer cost must equal `53,363,392.08`.
2. Employees paid in `PR-2026-09` must equal `444`.
3. Compare at least one department-month result with `reference_summary_dept_month`.
4. Test an employee transfer and verify the department before and after the effective date.
5. Run the loading process twice and verify that row counts do not increase due to duplicate records.

Note: Confirm table grains, keys, and effective-date columns against the actual source data before final submission.