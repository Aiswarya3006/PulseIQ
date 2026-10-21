# PulseIQ Task 3 - Data Quality Gatekeeper



## 1. Latest Data Quality Results



\- Total checks: 14

\- FAIL: 4

\- PASS: 3

\- WARNING: 7



Evidence file: `docs/dq_results_evidence.csv`



## 2. Known Issues Coverage



| Issue ID | Check ID | Evidence | Status |

|---|---|---|---|

| DQ-01 Attendance after exit | DQ-C05 | 81 warning rows | Matched - planted records verified |

| DQ-02 Duplicate payroll rows | DQ-C03 | 2 failure rows | Matched - planted records verified |

| DQ-03 Orphan employee references | DQ-C04 | 2 failure rows | Matched - planted records verified |

| DQ-04 Payroll-ledger mismatch | DQ-C01 | PR-2026-06; difference 18,450 | Matched |

| DQ-05 Overpaid invoice | DQ-C07 | INV-00385 detected | Matched |

| DQ-06 Completed before started | DQ-C09 | Invalid task dates detected | Matched - all planted records verified |

| DQ-07 Done without completion date | DQ-C09 | Missing completion dates detected | Matched - all planted records verified |

| DQ-08 Invalid leave dates | DQ-C10 | LR-000025 and LR-002286 | Matched |

| DQ-09 Stale AI prediction | DQ-C11 | Five planted IDs detected | Matched |

| DQ-10 Expense total mismatch | DQ-C08 | EXP-00371; difference 500 | Matched |

| DQ-11 SCD interval overlap | DQ-C12 | Employee key 100000 | Matched |



## 3. Severity Decisions



### Critical checks



Payroll-ledger mismatches, duplicate payroll rows, orphan employee references, and overlapping employee history require investigation before affected results can be trusted. An unbalanced ledger should also block financial reporting.



### Warning checks



Attendance after exit, unpaid absence review, invoice arithmetic, expense arithmetic, task dates, leave dates, and stale AI predictions are reported as warnings for investigation.



### Passing checks



DQ-C02, DQ-C13, and DQ-C14 returned PASS in the latest run. DQ-C13 requires further validation because its result depends on an ETL log setup/test record.



## 4. Limitations and Follow-up



1. Verified planted records: DQ-01 (4 attendance rows), DQ-02 (2 duplicate payroll rows), DQ-03 (2 orphan references), DQ-06 (12 invalid task dates), and DQ-07 (8 missing completion dates). DQ-C05 and DQ-C09 display only sample IDs in result details.

2\. Review DQ-C06 because its 1,532 warning rows may include expected cases.

3\. A test record in `etl_run_log` is not proof of a successful production pipeline run.

4\. Test all 14 checks with deliberately bad rows in isolated copies before claiming every check is tested.

5\. Preserve the original source data and planted issues during validation.



## 5. Conclusion



The current run executes 14 data quality checks and records results in `dq_results`. The report identifies failures and warnings requiring investigation. Remaining validation items must be completed before declaring the gatekeeper fully tested.



