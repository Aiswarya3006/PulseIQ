# PulseIQ – Task 11: Profit & Loss and Expense Analytics

## 1. Objective

Build a financial analytics dashboard to analyze:
- Revenue
- Expenses
- Net Profit
- Profit Margin
- Monthly financial performance
- Expense categories
- Top 10 vendors by spending

## 2. Data Sources

The dashboard uses the following tables from DuckDB:

| Table | Purpose |
|---|---|
| `fact_ledger` | Revenue, expenses and P&L calculations |
| `dim_account` | Account classification and account hierarchy |
| `fact_expense` | Expense category and vendor analysis |
| `dim_vendor` | Vendor details |
| `dim_department` | Department filtering |

## 3. Account Classification

- Revenue is calculated using credit minus debit for credit-normal accounts.
- Expenses are calculated using debit minus credit for debit-normal accounts.
- Group accounts are excluded to avoid double counting.
- Only Profit & Loss detail accounts are included.

## 4. Dashboard Features

1. Profit & Loss summary.
2. Monthly Revenue, Expenses and Profit Margin charts.
3. Monthly P&L table with month selection.
4. Expense by Category analysis.
5. Top 10 Vendors by Spend.
6. README headline tie-out.
7. Three financial findings.
8. Supporting data for possible margin changes.
9. Filtered expense details.
10. CSV evidence downloads.

## 5. Dashboard Results

Full-period dashboard results (1 April 2025 – 30 September 2026):

| Metric | Dashboard Value |
|---|---:|
| Revenue | ₹1,260,930,052.00 |
| Expenses | ₹1,036,264,914.42 |
| Net Profit | ₹224,665,137.58 |
| Profit Margin | 17.82% |

**Note:** These are dashboard-calculated figures, not independently verified README headline figures. Use the original README/workbook figures for the final tie-out.

## 6. Key Findings

- Revenue increased by ₹9,526,395.00 between April 2025 and September 2026.
- Profit margin improved by 9.71 percentage points over the same period.
- Skyline Realty Holdings was the highest-spend vendor, with ₹16,879,440.00 excluding GST.

## 7. Possible Causes of Margin Changes

| Possible Cause | Supporting Data |
|---|---|
| Expenses increase faster than revenue | Monthly ledger expenses |
| Revenue mix changes | Monthly revenue by account |
| High or one-time vendor spending | Monthly vendor and invoice-level expense trends |

## 8. Evidence and Deliverables

The following evidence should be saved:

- Task 11 dashboard screenshot.
- Monthly P&L screenshot.
- Expense category screenshot.
- Top 10 vendor screenshot.
- README headline tie-out table.
- Monthly P&L CSV.
- Expense category CSV.
- Top 10 vendor CSV.

## 9. Technology Used

- Python
- Streamlit
- DuckDB
- Pandas
- Plotly

## 10. Application File

`task11_app.py`

Run the dashboard using:

```powershell
streamlit run task11_app.py
```
