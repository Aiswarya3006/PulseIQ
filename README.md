# PulseIQ — Data Analytics Project

## Project Overview
PulseIQ is a data analytics project focused on ETL processing, data warehouse validation, data quality monitoring, business metric development, and dashboard reporting.

## Phase 1 Objectives
- Validate ETL processing and automated tests.
- Review warehouse tables and data relationships.
- Execute data quality checks and document findings.
- Review analytical metric views and the metric catalog.
- Present business metrics through a dashboard.

## Tasks and Evidence

| Task | Work Completed | Evidence |
|---|---|---|
| Task 1 — ETL Pipeline | Ran automated ETL tests and checked row-count balance, run logs, and summary output. | `reports/task1_etl_tests.png` |
| Task 2 — Warehouse Validation | Reviewed the ER diagram, payroll reconciliation, and orphan-reference checks. | `reports/task2_er_diagram.png`, `reports/task2_orphan_check.png`, `reports/task2_payroll_reconciliation.png` |
| Task 3 — Data Quality | Executed data quality checks and documented failures and warnings for review. | `reports/Task3_Screenshot1_DQ_Results.png`, `docs/dq_missed_issues.md` |
| Task 4 — Metric Layer | Reviewed metric views and performed hand checks. | `reports/task4_metric_views.png`, `reports/task4_hand_checks.png`, `docs/metric-dictionary.md` |
| Task 5 — Dashboard | Captured dashboard evidence. | `reports/task5_dashboard.png` |

## Validation Summary
- Automated ETL tests: 4 passed.
- Warehouse verification: 29 PostgreSQL tables; 7,338 payroll rows and 18 distinct payroll runs reported.
- Payroll orphan checks: zero employee-key or department orphans in the checked PostgreSQL payroll data.
- Contract validation: 29,775 rows checked with zero validation errors; extra columns were flagged for review.
- Data quality: 14 checks executed — 3 PASS, 4 FAIL, and 7 WARNING.
- Metric views `m01` through `m30` were reported present; the metric catalog contained 28 rows.

Data-quality failures and warnings are documented for further review. The forecast MAPE view returned no rows because the available forecast and actual headcount periods did not overlap.

## Repository Structure
- `docs/` — Project documentation, metric dictionary, validation reports, and data-quality findings.
- `reports/` — Screenshots, ETL logs, contract validation outputs, and supporting evidence.
- `app.py` — Dashboard application, if present in this repository.
- SQL and Python files — Data processing, validation, and metric-related implementation.

## Running the Project
1. Clone or download this repository.
2. Create and activate the project's Python virtual environment.
3. Install dependencies using the project's existing dependency file, if provided.
4. Follow the repository's scripts and documentation to configure the required databases and run the application.

Use the actual configuration and run commands documented in the repository; do not commit credentials or secrets.

## Project Links
- GitHub Repository: https://github.com/Aiswarya3006/PulseIQ
- Phase 1 Git Tag: `phase-1`

## Next Steps
- Review data-quality warnings against business rules.
- Investigate documented validation failures.
- Validate forecast metrics when suitable actual data becomes available.
- Practice defining, building, displaying, and manually verifying a new metric within 45 minutes.
