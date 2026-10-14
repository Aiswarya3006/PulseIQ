
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "raw" / "03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx"
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)

# Load payroll data and exclude identified synthetic test records
payroll = pd.read_excel(WORKBOOK, sheet_name="fact_payroll")
payroll = payroll[
    ~payroll["payroll_item_id"].astype(str).str.startswith("PI-X")
].copy()

payroll["month"] = (
    pd.to_datetime(payroll["period_end_date"])
    .dt.to_period("M")
    .dt.to_timestamp()
)

# 1. Monthly employer cost trend and month-on-month change
monthly = payroll.groupby("month", as_index=False).agg(
    employer_cost=("employer_cost", "sum"),
    employees_paid=("headcount_flag", "sum"),
)
monthly = monthly.sort_values("month")
monthly["previous_month_cost"] = monthly["employer_cost"].shift(1)
monthly["mom_change"] = (
    monthly["employer_cost"] - monthly["previous_month_cost"]
)
monthly["mom_change_pct"] = (
    monthly["mom_change"] / monthly["previous_month_cost"] * 100
)
monthly.to_csv(REPORTS / "task5_monthly_trend.csv", index=False)

# 2. Department-wise employer cost
dept = payroll.groupby("department_id", as_index=False).agg(
    employer_cost=("employer_cost", "sum"),
    employees_paid=("headcount_flag", "sum"),
)
dept["cost_per_head"] = (
    dept["employer_cost"] / dept["employees_paid"].replace(0, pd.NA)
)
dept = dept.sort_values("employer_cost", ascending=False)
dept.to_csv(REPORTS / "task5_department_metrics.csv", index=False)

# 3. Role-wise employer cost
role = payroll.groupby("role_id", as_index=False).agg(
    employer_cost=("employer_cost", "sum"),
    employees_paid=("headcount_flag", "sum"),
)
role["cost_per_head"] = (
    role["employer_cost"] / role["employees_paid"].replace(0, pd.NA)
)
role = role.sort_values("employer_cost", ascending=False)
role.to_csv(REPORTS / "task5_role_metrics.csv", index=False)

# 4. Monthly department cost for dashboard filtering
monthly_dept = payroll.groupby(
    ["month", "department_id"], as_index=False
).agg(
    employer_cost=("employer_cost", "sum"),
    employees_paid=("headcount_flag", "sum"),
)
monthly_dept.to_csv(REPORTS / "task5_monthly_department_metrics.csv", index=False)

# 5. Key findings based on calculated values
highest_month = monthly.loc[monthly["employer_cost"].idxmax()]
lowest_month = monthly.loc[monthly["employer_cost"].idxmin()]
highest_dept = dept.iloc[0]

summary = [
    "TASK 5 - PAYROLL DASHBOARD METRICS",
    f"Months included: {len(monthly)}",
    f"Total employer cost: {payroll['employer_cost'].sum():,.2f}",
    f"Highest-cost month: {highest_month['month']:%Y-%m} "
    f"({highest_month['employer_cost']:,.2f})",
    f"Lowest-cost month: {lowest_month['month']:%Y-%m} "
    f"({lowest_month['employer_cost']:,.2f})",
    f"Highest-cost department: {highest_dept['department_id']} "
    f"({highest_dept['employer_cost']:,.2f})",
    "",
    "Note: PI-X synthetic records are excluded pending data-contract confirmation.",
    "Validate small-group privacy rules before publishing department/role breakdowns.",
]
(REPORTS / "task5_dashboard_findings.txt").write_text(
    "\n".join(summary), encoding="utf-8"
)

print("\n".join(summary))
print("\nCreated dashboard metric files:")
for filename in [
    "task5_monthly_trend.csv",
    "task5_department_metrics.csv",
    "task5_role_metrics.csv",
    "task5_monthly_department_metrics.csv",
    "task5_dashboard_findings.txt",
]:
    print(REPORTS / filename)
