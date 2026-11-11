# Task 2 — Warehouse Validation Report

## Warehouse Overview
- Database: pulseiq_wh
- Schema: dw
- Base tables: 29
- Payroll fact rows: 7,338
- Distinct payroll runs: 18

## Referential Integrity
- Payroll employee-key orphan records: 0
- Payroll department orphan records: 0

## Payroll Reconciliation
- PR-2025-04: 386 distinct employees; employer cost: 53,363,392.08
- PR-2026-09: 444 distinct employees; employer cost: 55,519,621.87
- Both totals match the provided reference values.

## Employee History
- 82 payroll rows have a period-end date later than the linked employee dimension row's valid_to.
- Source CSV inspection confirmed these cases originate in the source data.
- These are documented as source-data/business-rule exceptions; no source or warehouse records were modified.

## Repeat-Safe Loading
- The existing load_postgres.py stops if the dw schema already contains tables.
- Repeat-safe upsert behavior remains unverified and is not claimed as complete.

## Repeat-Safe Upsert Test
- A separate test database, pulseiq_upsert_test, was used.
- A sample row was inserted, then loaded again with the same primary key and updated values.
- Result: one row remained; risk_score changed from 0.35 to 0.80 and model_version changed from v1 to v2.
- The isolated UPSERT test passed using PostgreSQL ON CONFLICT DO UPDATE.
- The production warehouse loader still uses initial-load-only logic; production upsert is not yet implemented.

## Attrition Risk Validation
- Rows in fact_attrition_risk: 425
- Non-null employee keys: 425
- Distinct employee keys: 425
- Duplicate employee keys: 0
- employee_key is unique in the current dataset; no primary-key constraint was added.

## Evidence
- PostgreSQL table, payroll row, and payroll-run counts were verified.
- Referential integrity and payroll reconciliation queries were run.
- Source employee history was compared with dim_employee.csv.
