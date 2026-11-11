# PulseIQ Analytics Warehouse — Database ERD

## 1. Overview

The PulseIQ analytics warehouse is implemented in PostgreSQL using the `dw` schema. It contains 29 tables covering dimensions, facts, reference data, data quality, and metric definitions.

## 2. Dimension Tables

- `dim_date` — Calendar and date information
- `dim_department` — Department details
- `dim_employee` — Employee dimension records, uniquely identified by `employee_key`
- `dim_role` — Employee role details
- `dim_leave_type` — Leave category details
- `dim_location` — Work location information
- `dim_account` — Account information
- `dim_client` — Client information
- `dim_sprint` — Sprint information
- `dim_team` — Team information
- `dim_vendor` — Vendor information

## 3. Fact Tables

- `fact_attendance_monthly` — Monthly attendance records
- `fact_payroll` — Payroll records
- `fact_leave` — Employee leave requests
- `fact_headcount_monthly` — Monthly headcount records
- `fact_task` — Task records
- `fact_ledger` — Ledger entries
- `fact_invoice` — Invoice records
- `fact_invoice_payment` — Invoice payment records
- `fact_expense` — Expense records
- `fact_forecast` — Forecast records
- `fact_anomaly` — Anomaly scoring results
- `fact_attrition_risk` — Attrition risk records

## 4. Additional Tables

The warehouse also includes budget and KPI tables, data contracts, data dictionary entries, data-quality check definitions, and metric definitions.

## 5. Database Implementation Status

| Item | Verified result |
|---|---:|
| Tables in `dw` | 29 |
| Primary-key constraints | 26 |
| Foreign-key constraints | 17 |
| Check constraints | 29 |
| Indexes | 36 |
| Payroll rows | 7,338 |

## 6. Data Validation

Payroll reference totals for `PR-2025-04` and `PR-2026-09` matched the expected reference values during verification.

One known relationship issue remains: payment record `INV-00385` does not have a matching invoice in `fact_invoice`. The corresponding foreign key was not created. Investigate the source record before making any correction.

## 7. Notes

- Dimension tables provide descriptive attributes.
- Fact tables store business events and measurements.
- Primary keys and foreign keys enforce data integrity where validated.
- Indexes support common joins and queries.
- This document provides a high-level warehouse overview; it does not list every column or constraint.
