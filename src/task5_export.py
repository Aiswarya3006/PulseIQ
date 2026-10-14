
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
OUTPUT = REPORTS / "Task5_Payroll_Dashboard.xlsx"

files = {
    "Monthly_Reconciliation": "task5_monthly_reconciliation.csv",
    "Department_Budget": "task5_department_budget_comparison.csv",
    "Monthly_Trend": "task5_monthly_trend.csv",
    "Department_Metrics": "task5_department_metrics.csv",
    "Role_Metrics": "task5_role_metrics.csv",
    "Monthly_Dept_Metrics": "task5_monthly_department_metrics.csv",
}

with pd.ExcelWriter(OUTPUT, engine="openpyxl") as writer:
    for sheet_name, filename in files.items():
        path = REPORTS / filename
        if path.exists():
            df = pd.read_csv(path)
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        else:
            print(f"Warning: Missing file - {filename}")

    summary_path = REPORTS / "task5_summary.txt"
    if summary_path.exists():
        summary = summary_path.read_text(encoding="utf-8")
        pd.DataFrame({"Task 5 Summary": summary.splitlines()}).to_excel(
            writer, sheet_name="Summary", index=False
        )

print(f"Excel export created: {OUTPUT}")
print("Open the workbook and check all sheets before submission.")
