# Report 1 — Phase 2: Payroll, Leave and Finance Analytics

## 1. Tasks Completed

| Task | Work Planned | Current Status | Pull Request Link |
|---|---|---|---|
| Task 5 — Payroll Dashboard | Analyse monthly payroll costs and check reconciliation results | Completed — all 18 monthly checks passed | Not yet recorded |
| Task 6 — Overtime and Leave Analytics | Analyse overtime, leave, loss of pay (LOP) and data quality | Reports generated; validation still needs to be completed | Not yet recorded |
| Task 7 — Ledger Analytics | Check journal entries and compare monthly ledger values | Journal entries balanced; June difference needs further investigation | Not yet recorded |
| Task 8 — Invoice and Cash Flow Dashboard | Review invoices, collections, outstanding amounts and cash projections | Main checks passed; a ₹100 mismatch needs investigation | Not yet recorded |

## 2. Summary of My Work

- **Task 5:** I prepared the payroll dashboard and checked the monthly reconciliation results. All 18 months matched the expected values.
- **Task 6:** I analysed 7,343 attendance records and 3,441 leave requests. I also identified 93 data-quality flags that need further review.
- **Task 7:** I checked 2,524 journal entries and confirmed that the debit and credit amounts balanced. However, I found a difference of ₹18,450 in the June 2026 salary-related expense reconciliation.
- **Task 8:** I checked invoice collections, outstanding receivables and bank balances. The closing receivables and bank balance matched the expected values, but a ₹100 difference was found between invoice payments and the recorded amount paid.

## 3. What I Learned

1. I learned how to calculate payroll costs and compare the results with expected values.
2. I understood how to identify data-quality issues such as duplicate records, missing employee references and invalid leave dates.
3. I learned that balancing journal entries and reconciling monthly ledger amounts are two different checks.
4. I gained a better understanding of invoice payments, outstanding receivables and overdue balances.
5. I learned the importance of checking results carefully, keeping the original data unchanged and reporting any differences honestly.

## 4. How This Work Can Be Used

- The payroll dashboard helps review monthly employer costs and reconciliation results.
- The overtime and leave reports help identify attendance patterns, leave usage and records that need checking.
- The ledger reports help review journal entries and investigate differences in financial records.
- The invoice and cash flow dashboard helps monitor collections, overdue invoices, outstanding balances and estimated future cash flow.
- The related Excel workbooks, CSV files and charts are saved in the `reports/` directory.

## 5. Issues That Need Further Review

- **Task 6:** The identified data-quality flags need to be checked against the available data contracts and known issues. The reported totals are based on the available source data and have not been treated as corrected figures.
- **Task 7:** The ₹18,450 difference in the June 2026 salary-related ledger expense still needs investigation.
- **Task 8:** The invoice payment total is ₹100 lower than the total recorded in the invoice `amount_paid` field. The original data has not been changed to hide this difference.
- The cash flow figures are estimates based on the available records and should not be treated as guaranteed future cash flow.
- Pull-request links have not yet been added to this report.

## 6. Dashboard Screenshots

- **Task 5 — Payroll Dashboard:** All 18 monthly payroll reconciliation checks passed with zero difference. Screenshot: `reports/screenshots/task5_payroll_summary.png`

- **Task 6 — Overtime and Leave Analytics:** The reports show overtime, LOP and leave patterns, along with data-quality issues that need further review. Screenshot: `reports/screenshots/task6_monthly_overtime_share.png`

- **Task 7 — Ledger Analytics:** All 2,524 journal entries balanced successfully. The June 2026 salary-related difference remains unresolved. Screenshot: `reports/screenshots/task7_monthly_salary_expense.png`

- **Task 8 — Invoice and Cash Flow Dashboard:** Closing receivables and bank balances matched the expected values. A ₹100 invoice-payment difference still needs investigation. Screenshot: `reports/screenshots/task8_cash_in_vs_cash_out.png`

## 7. Overall Review

During this phase, I worked on payroll, attendance and leave, ledger, invoice and cash flow analytics. I generated the required reports, dashboards and supporting files and performed the available reconciliation checks.

Task 5 passed all monthly reconciliation checks. Tasks 6, 7 and 8 have produced useful results, but some data-quality checks and reconciliation differences still need attention. I have documented these issues instead of changing the source data without verification.

The screenshot evidence has been saved in `reports/screenshots/`. Before considering this phase fully complete, I still need to finish the pending validations and add the relevant pull-request links.