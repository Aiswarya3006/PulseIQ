\# PulseIQ â€” Payroll ETL Pipeline



\## 1. Project Overview

PulseIQ is a data engineering project that extracts payroll data from Excel, validates records, separates clean and rejected data, and exports the results into CSV and Parquet formats.



\## 2. Objectives

\- Build an automated payroll ETL pipeline.

\- Validate data quality using Pandas and Pandera.

\- Identify invalid and duplicate records.

\- Store clean and rejected records separately.

\- Support repeatable execution using Docker.



\## 3. Technology Stack

\- Python 3.9

\- Pandas

\- Pandera

\- PyArrow

\- Pytest

\- PostgreSQL

\- Docker



\## 4. Project Structure

\- `raw/` â€” Source datasets

\- `src/` â€” ETL and database scripts

\- `clean/` â€” Clean CSV and Parquet outputs

\- `rejected/` â€” Rejected records with reasons

\- `tests/` â€” Automated tests

\- `docs/` â€” Database schema, ERD, and metric dictionary

\- `logs/` â€” ETL logs

\- `Dockerfile` â€” Docker image configuration

\- `docker-compose.yml` â€” Docker service configuration



\## 5. ETL Workflow

1\. Read payroll data from the Excel workbook.

2\. Check required columns.

3\. Validate employee keys and payroll amounts.

4\. Identify duplicate employee and payroll-run combinations.

5\. Apply Pandera schema validation.

6\. Separate valid and rejected records.

7\. Export clean records to CSV and Parquet.

8\. Save rejected records with rejection reasons.

9\. Log the ETL execution results.



\## 6. Data Quality Results

\- Input records: 7,344

\- Clean records: 7,340

\- Rejected records: 4

\- Automated tests: 8 passed

\- Docker ETL execution: Successful



\## 7. Run the Project Locally

Run these commands from the project root directory:



```powershell

.\\.venv\\Scripts\\python.exe .\\src\\main.py

.\\.venv\\Scripts\\python.exe -m pytest .\\tests\\test\_payroll\_etl.py -v

```



\## 8. Run with Docker



```powershell

docker compose build

docker compose run --rm etl

```



\## 9. Output Files

\- `clean/payroll\_clean.csv`

\- `clean/payroll\_clean.parquet`

\- `rejected/payroll\_rejected.csv`



\## 10. Database

PostgreSQL staging loader scripts are available in the `src/` directory. Database loading should be checked for duplicate prevention before rerunning the loaders.



\## 11. Conclusion

The payroll ETL pipeline successfully processed 7,344 records, producing 7,340 clean records and 4 rejected records. The existing automated test suite passed all 8 tests, and the pipeline ran successfully in Docker.



Note: Database integration and end-to-end reconciliation should be verified separately before claiming full production readiness.

## Handoff package

### Phase 1 — ETL and documentation
- [Automated ETL tests](tests/test_payroll_etl.py)
- [Database schema](docs/schema.sql)
- [Database ERD](docs/database_erd.md)
- [Metric dictionary](docs/metric_dictionary.csv)

### Phase 2 — Analytics and dashboards
- [Phase 2 review](reports/phase-2-review.md)
- [Report 1](reports/report-1.md)
- [Task 5 payroll dashboard](reports/Task5_Payroll_Dashboard.xlsx)
- [Task 6 overtime and leave insights](reports/insightsovertime.md)
- [Task 7 ledger analytics](reports/task7_ledger_analytics/Task7_Ledger_Analytics.xlsx)
- [Task 8 cash flow dashboard](reports/task8_invoice/Task8_Invoice_Cashflow_Dashboard.xlsx)
- [Task 8 analysis summary](reports/task8_invoice/Task8_Invoice_Analysis_Summary.md)
- [Cash flow insights](reports/insights-cashflow.md)

### Dashboard evidence
- [Task 5 screenshot](reports/screenshots/task5_payroll_summary.png)
- [Task 6 screenshot](reports/screenshots/task6_monthly_overtime_share.png)
- [Task 7 screenshot](reports/screenshots/task7_monthly_salary_expense.png)
- [Task 8 screenshot](reports/screenshots/task8_cash_in_vs_cash_out.png)

### Pending verification
- Verify Phase 1 Tasks 1–4 against the project guide.
- Verify database integration and end-to-end reconciliation.
- Review outstanding data-quality and reconciliation issues.
