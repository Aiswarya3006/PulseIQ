
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "raw" / "03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx"
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)

# Load source data and reference totals
payroll = pd.read_excel(WORKBOOK, sheet_name="fact_payroll")
answer = pd.read_excel(WORKBOOK, sheet_name="reconciliation_answer_key")
budget = pd.read_excel(WORKBOOK, sheet_name="budget_payroll_dept_month")

# Exclude identified synthetic test records; retain source workbook unchanged
payroll = payroll[
    ~payroll["payroll_item_id"].astype(str).str.startswith("PI-X")
].copy()

payroll["month"] = (
    pd.to_datetime(payroll["period_end_date"])
    .dt.to_period("M")
    .dt.to_timestamp()
)
answer["month"] = (
    pd.to_datetime(answer["month"])
    .dt.to_period("M")
    .dt.to_timestamp()
)
budget["month"] = (
    pd.to_datetime(budget["month"])
    .dt.to_period("M")
    .dt.to_timestamp()
)

# Monthly reconciliation
monthly = payroll.groupby("month", as_index=False).agg(
    employer_cost=("employer_cost", "sum"),
    employees_paid=("headcount_flag", "sum"),
)
monthly = monthly.merge(
    answer[["month", "payroll_employer_cost"]],
    on="month",
    how="outer",
)
monthly["difference"] = (
    monthly["employer_cost"] - monthly["payroll_employer_cost"]
)
monthly["status"] = monthly["difference"].abs().lt(0.01).map(
    {True: "PASS", False: "CHECK"}
)
monthly.to_csv(REPORTS / "task5_monthly_reconciliation.csv", index=False)

# Department and month actual cost vs budget
department = payroll.groupby(
    ["month", "department_id"], as_index=False
).agg(
    actual_employer_cost=("employer_cost", "sum"),
    employees_paid=("headcount_flag", "sum"),
)
comparison = department.merge(
    budget,
    on=["month", "department_id"],
    how="outer",
)
comparison["variance"] = (
    comparison["actual_employer_cost"] - comparison["budget_payroll_cost"]
)
comparison["variance_pct"] = (
    comparison["variance"] / comparison["budget_payroll_cost"] * 100
)
comparison.to_csv(
    REPORTS / "task5_department_budget_comparison.csv", index=False
)

# Summary
all_match = (
    len(monthly) == 18
    and monthly["difference"].abs().lt(0.01).all()
)
summary = [
    "Task 5 - Payroll Cost Dashboard preparation",
    f"Months reconciled: {len(monthly)}",
    f"All 18 months match: {all_match}",
    f"Total employer cost: {payroll['employer_cost'].sum():,.2f}",
    f"Total headcount flags: {payroll['headcount_flag'].sum():,.0f}",
    f"Monthly reconciliation failures: {(monthly['status'] != 'PASS').sum()}",
    "",
    "Synthetic PI-X records excluded from this analysis.",
    "Validate the data-contract rule for synthetic records before final submission.",
]
(REPORTS / "task5_summary.txt").write_text(
    "\n".join(summary), encoding="utf-8"
)

print("\n".join(summary))
print("\nCreated reports:")
print(REPORTS / "task5_monthly_reconciliation.csv")
print(REPORTS / "task5_department_budget_comparison.csv")
print(REPORTS / "task5_summary.txt")
