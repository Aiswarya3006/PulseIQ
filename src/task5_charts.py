
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "raw" / "03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx"
REPORTS = ROOT / "reports"
CHARTS = REPORTS / "task5_charts"
CHARTS.mkdir(parents=True, exist_ok=True)

payroll = pd.read_excel(WORKBOOK, sheet_name="fact_payroll")
payroll = payroll[
    ~payroll["payroll_item_id"].astype(str).str.startswith("PI-X")
].copy()

payroll["month"] = (
    pd.to_datetime(payroll["period_end_date"])
    .dt.to_period("M")
    .dt.to_timestamp()
)

# Chart 1: Monthly employer cost trend
monthly = payroll.groupby("month")["employer_cost"].sum().sort_index()

plt.figure(figsize=(12, 6))
plt.plot(monthly.index, monthly.values, marker="o")
plt.title("Monthly Employer Payroll Cost")
plt.xlabel("Month")
plt.ylabel("Employer Cost")
plt.xticks(rotation=45)
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(CHARTS / "monthly_employer_cost.png", dpi=150)
plt.close()

# Chart 2: Department cost (publish only if each department has 5+ employees)
dept = payroll.groupby("department_id").agg(
    employer_cost=("employer_cost", "sum"),
    people=("employee_id", "nunique"),
).reset_index()

dept_safe = dept[dept["people"] >= 5].sort_values("employer_cost")

plt.figure(figsize=(10, 6))
if not dept_safe.empty:
    plt.barh(dept_safe["department_id"], dept_safe["employer_cost"])
    plt.title("Department Payroll Cost (Groups of 5+ Employees)")
    plt.xlabel("Employer Cost")
    plt.ylabel("Department")
else:
    plt.text(0.5, 0.5, "No departments meet the 5-person threshold",
             ha="center", va="center")
    plt.axis("off")
plt.tight_layout()
plt.savefig(CHARTS / "department_payroll_cost.png", dpi=150)
plt.close()

# Chart 3: Role cost (publish only if each role has 5+ employees)
role = payroll.groupby("role_id").agg(
    employer_cost=("employer_cost", "sum"),
    people=("employee_id", "nunique"),
).reset_index()

role_safe = role[role["people"] >= 5].sort_values("employer_cost")

plt.figure(figsize=(10, 7))
if not role_safe.empty:
    plt.barh(role_safe["role_id"], role_safe["employer_cost"])
    plt.title("Role Payroll Cost (Groups of 5+ Employees)")
    plt.xlabel("Employer Cost")
    plt.ylabel("Role")
else:
    plt.text(0.5, 0.5, "No roles meet the 5-person threshold",
             ha="center", va="center")
    plt.axis("off")
plt.tight_layout()
plt.savefig(CHARTS / "role_payroll_cost.png", dpi=150)
plt.close()

print("Charts created successfully:")
for file in CHARTS.glob("*.png"):
    print(file)
