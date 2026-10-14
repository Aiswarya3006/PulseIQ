# Overtime and Leave Cost Impact — Insights

## Objective
Analyse overtime, loss-of-pay (LOP), and leave patterns to understand their impact on workforce attendance and payroll cost.

## Key Findings
- The attendance dataset contains 7,343 rows.
- The leave dataset contains 3,441 requests.
- The payroll analysis covers April 2025 to September 2026.
- Recorded overtime pay totals INR 3,024,619.28.
- Recorded employer cost totals INR 861,997,359.88.
- Payroll LOP totals 1,599 days.
- Leave records contain 7,999 days across all statuses; approved leave accounts for 7,276 days.

## Data Quality and Limitations
- 93 data-quality flags were identified.
- Four duplicate payroll candidates, two orphan payroll employee candidates, 85 attendance-after-exit candidates, and two invalid leave date ranges were flagged.
- The two invalid leave records have an end date earlier than the start date.
- The 85 attendance-after-exit flags require interpretation against employee exit dates and the monthly attendance period.
- Synthetic PI-X payroll records require confirmation against the dataset's data-contract rules before final sign-off.

## Recommendation
Review the flagged records against the data contract and source data before using the results for operational decisions. Preserve the original source data and document any unresolved exceptions.

## Evidence
Charts and supporting CSV outputs are stored in `reports/task6_overtime_leave/`. The monthly overtime-share chart is available at `reports/screenshots/task6_monthly_overtime_share.png`.
