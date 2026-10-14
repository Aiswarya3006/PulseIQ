
# PulseIQ Database ER Diagram

## Dimension Tables
- dim_department
- dim_employee
- dim_role
- dim_date
- dim_leave_type

## Fact Tables
- fact_attendance
- fact_payroll
- fact_leave
- fact_headcount_monthly

## Table Relationships
- dim_department → dim_employee
- dim_employee → fact_attendance
- dim_employee → fact_payroll
- dim_employee → fact_leave
- dim_leave_type → fact_leave
- dim_department → fact_headcount_monthly
