
# PulseIQ Metric Dictionary

## M01 — Headcount
- Definition: Number of employees active on the selected reporting date.
- Source: Employee and headcount data.
- Validation: Exclude employees outside their active employment period.

## M02 — Payroll Cost
- Definition: Total payroll cost for the selected reporting period.
- Source: fact_payroll and budget_payroll_dept_month.
- Validation: Check for negative payroll amounts and valid periods.

## M03 — Attendance Rate
- Definition: Present attendance divided by expected attendance.
- Source: fact_attendance_monthly.
- Validation: Avoid division by zero and document missing attendance.

## M04 — Attrition Risk
- Definition: Count or percentage of employees flagged as at risk.
- Source: fact_attrition_risk.
- Validation: Confirm risk scores are within their documented range.

## M05 — Anomaly Count
- Definition: Number of anomaly records flagged for review.
- Source: fact_anomaly.
- Validation: flagged must be Y or N; anomaly_score must be between 0 and 1.
