
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# --------------------------------------------------
# 1. Paths and folders
# --------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "raw" / "03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx"
OUT = ROOT / "reports" / "task6_overtime_leave"
CHARTS = OUT / "charts"

OUT.mkdir(parents=True, exist_ok=True)
CHARTS.mkdir(parents=True, exist_ok=True)

if not FILE.exists():
    raise FileNotFoundError(f"Dataset not found: {FILE}")

# --------------------------------------------------
# 2. Load source data
# --------------------------------------------------
payroll = pd.read_excel(FILE, sheet_name="fact_payroll")
attendance = pd.read_excel(FILE, sheet_name="fact_attendance_monthly")
leave = pd.read_excel(FILE, sheet_name="fact_leave")
employees = pd.read_excel(FILE, sheet_name="dim_employee")
departments = pd.read_excel(FILE, sheet_name="dim_department")

print("Dataset loaded successfully.")

# --------------------------------------------------
# 3. Department name mapping
# --------------------------------------------------
dept_name_col = next(
    (c for c in ["department_name", "name", "department"]
     if c in departments.columns),
    None
)

if dept_name_col and "department_id" in departments.columns:
    dept_map = dict(
        zip(departments["department_id"], departments[dept_name_col])
    )
else:
    dept_map = {}

def add_department_name(df):
    df = df.copy()
    if "department_id" in df.columns:
        df["department_name"] = (
            df["department_id"].map(dept_map)
            .fillna(df["department_id"].astype(str))
        )
    return df

def make_numeric(df, columns):
    df = df.copy()
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df

# --------------------------------------------------
# 4. Prepare payroll
# --------------------------------------------------
payroll = add_department_name(payroll)
payroll = make_numeric(
    payroll,
    [
        "overtime_hours_paid", "overtime_pay",
        "employer_cost", "lop_days", "gross_pay"
    ]
)

payroll["period_end_date"] = pd.to_datetime(
    payroll["period_end_date"], errors="coerce"
)
payroll["month"] = payroll["period_end_date"].dt.to_period("M").astype(str)

# --------------------------------------------------
# 5. Prepare attendance
# --------------------------------------------------
attendance = add_department_name(attendance)
attendance = make_numeric(
    attendance,
    [
        "scheduled_days", "present_days", "half_days_unpaid",
        "unpaid_absence_days", "late_arrivals",
        "overtime_hours", "paid_leave_days"
    ]
)

attendance["period_end_date"] = pd.to_datetime(
    attendance["period_end_date"], errors="coerce"
)
attendance["month"] = (
    attendance["period_end_date"].dt.to_period("M").astype(str)
)

# --------------------------------------------------
# 6. Prepare leave
# --------------------------------------------------
leave["days"] = pd.to_numeric(
    leave["days"], errors="coerce"
).fillna(0)

leave["status"] = leave["status"].fillna("Unknown").astype(str)
leave["leave_type_code"] = (
    leave["leave_type_code"].fillna("Unknown").astype(str)
)
leave["start_date"] = pd.to_datetime(
    leave["start_date"], errors="coerce"
)
leave["end_date"] = pd.to_datetime(
    leave["end_date"], errors="coerce"
)

# --------------------------------------------------
# 7. Monthly overtime and LOP metrics
# --------------------------------------------------
monthly = payroll.groupby("month", dropna=False).agg(
    employees=("employee_key", "nunique"),
    overtime_hours_paid=("overtime_hours_paid", "sum"),
    overtime_pay=("overtime_pay", "sum"),
    employer_cost=("employer_cost", "sum"),
    lop_days=("lop_days", "sum")
).reset_index()

monthly["overtime_share_pct"] = (
    monthly["overtime_pay"]
    .div(monthly["employer_cost"].where(monthly["employer_cost"] != 0))
    * 100
).fillna(0)

monthly.to_csv(OUT / "monthly_overtime_lop.csv", index=False)

# Department payroll report: publish only groups of 5+ employees
dept_payroll = payroll.groupby(
    ["month", "department_id", "department_name"], dropna=False
).agg(
    employees=("employee_key", "nunique"),
    overtime_hours_paid=("overtime_hours_paid", "sum"),
    overtime_pay=("overtime_pay", "sum"),
    employer_cost=("employer_cost", "sum"),
    lop_days=("lop_days", "sum")
).reset_index()

dept_payroll["overtime_share_pct"] = (
    dept_payroll["overtime_pay"]
    .div(dept_payroll["employer_cost"].where(
        dept_payroll["employer_cost"] != 0
    ))
    * 100
).fillna(0)

dept_payroll.loc[dept_payroll["employees"] >= 5].to_csv(
    OUT / "department_overtime_lop.csv", index=False
)

# --------------------------------------------------
# 8. Monthly attendance impact
# --------------------------------------------------
att_monthly = attendance.groupby("month", dropna=False).agg(
    employees=("employee_key", "nunique"),
    scheduled_days=("scheduled_days", "sum"),
    present_days=("present_days", "sum"),
    half_days_unpaid=("half_days_unpaid", "sum"),
    unpaid_absence_days=("unpaid_absence_days", "sum"),
    late_arrivals=("late_arrivals", "sum"),
    overtime_hours=("overtime_hours", "sum")
).reset_index()

att_monthly["attendance_rate"] = (
    (
        att_monthly["present_days"]
        + 0.5 * att_monthly["half_days_unpaid"]
    ).div(
        att_monthly["scheduled_days"].where(
            att_monthly["scheduled_days"] != 0
        )
    )
)

att_monthly.to_csv(
    OUT / "monthly_attendance_impact.csv", index=False
)

att_dept = attendance.groupby(
    ["month", "department_id", "department_name"], dropna=False
).agg(
    employees=("employee_key", "nunique"),
    scheduled_days=("scheduled_days", "sum"),
    present_days=("present_days", "sum"),
    half_days_unpaid=("half_days_unpaid", "sum"),
    unpaid_absence_days=("unpaid_absence_days", "sum"),
    late_arrivals=("late_arrivals", "sum"),
    overtime_hours=("overtime_hours", "sum")
).reset_index()

att_dept["attendance_rate"] = (
    (
        att_dept["present_days"]
        + 0.5 * att_dept["half_days_unpaid"]
    ).div(
        att_dept["scheduled_days"].where(
            att_dept["scheduled_days"] != 0
        )
    )
)

att_dept.loc[att_dept["employees"] >= 5].to_csv(
    OUT / "department_attendance_impact.csv", index=False
)

# --------------------------------------------------
# 9. Leave summaries
# --------------------------------------------------
leave_summary = leave.groupby(
    ["leave_type_code", "status"], dropna=False
).agg(
    requests=("leave_request_id", "nunique"),
    employees=("employee_key", "nunique"),
    leave_days=("days", "sum")
).reset_index()

leave_summary.loc[leave_summary["employees"] >= 5].to_csv(
    OUT / "leave_type_status_summary.csv", index=False
)

leave_status = leave.groupby("status", dropna=False).agg(
    requests=("leave_request_id", "nunique"),
    employees=("employee_key", "nunique"),
    leave_days=("days", "sum")
).reset_index()

leave_status.to_csv(
    OUT / "leave_status_quality_check.csv", index=False
)

# --------------------------------------------------
# 10. Data-quality flags
# --------------------------------------------------
quality_issues = []

def add_issue(issue, record_id, details):
    quality_issues.append({
        "issue": issue,
        "record_id": record_id,
        "details": details
    })

# DQ-02: duplicate employee/run payroll combinations
duplicate_mask = payroll.duplicated(
    subset=["employee_id", "run_id"], keep=False
)

for _, row in payroll.loc[duplicate_mask].iterrows():
    add_issue(
        "DUPLICATE_PAYROLL_CANDIDATE",
        row["payroll_item_id"],
        f"Employee={row['employee_id']}; run={row['run_id']}"
    )

# DQ-03: payroll employee IDs missing from the employee dimension
master_ids = set(employees["employee_id"].dropna().astype(str))
orphan_mask = ~payroll["employee_id"].astype(str).isin(master_ids)

for _, row in payroll.loc[orphan_mask].iterrows():
    add_issue(
        "ORPHAN_PAYROLL_EMPLOYEE",
        row["payroll_item_id"],
        f"Employee {row['employee_id']} not found in dim_employee"
    )

# DQ-01: compare attendance month-end with the latest employee version.
# Use one dimension record per employee to avoid multiplying fact rows.
employee_dates = employees.copy()
employee_dates["valid_from"] = pd.to_datetime(
    employee_dates["valid_from"], errors="coerce"
)
employee_dates["exit_date"] = pd.to_datetime(
    employee_dates["exit_date"], errors="coerce"
)
employee_dates = employee_dates.sort_values("valid_from")
employee_dates = employee_dates.drop_duplicates(
    subset=["employee_id"], keep="last"
)

exit_map = employee_dates.set_index("employee_id")["exit_date"]
attendance_exit = attendance.copy()
attendance_exit["exit_date"] = attendance_exit["employee_id"].map(exit_map)

after_exit = (
    attendance_exit["exit_date"].notna()
    & (
        attendance_exit["period_end_date"]
        > attendance_exit["exit_date"]
    )
)

for _, row in attendance_exit.loc[after_exit].iterrows():
    add_issue(
        "ATTENDANCE_AFTER_EXIT_CANDIDATE",
        row["attendance_fact_id"],
        f"Employee={row['employee_id']}; month={row['month']}"
    )

# DQ-08: leave end date before start date
invalid_leave = (
    leave["start_date"].notna()
    & leave["end_date"].notna()
    & (leave["end_date"] < leave["start_date"])
)

for _, row in leave.loc[invalid_leave].iterrows():
    add_issue(
        "LEAVE_END_BEFORE_START",
        row["leave_request_id"],
        f"{row['start_date'].date()} to {row['end_date'].date()}"
    )

quality_report = pd.DataFrame(
    quality_issues,
    columns=["issue", "record_id", "details"]
)

quality_report.to_csv(
    OUT / "task6_data_quality_flags.csv", index=False
)

# --------------------------------------------------
# 11. Charts
# --------------------------------------------------
if not monthly.empty:
    plt.figure(figsize=(11, 5))
    plt.plot(
        monthly["month"], monthly["overtime_share_pct"], marker="o"
    )
    plt.title("Monthly Overtime Pay as % of Employer Cost")
    plt.xlabel("Month")
    plt.ylabel("Overtime share (%)")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(CHARTS / "monthly_overtime_share.png", dpi=150)
    plt.close()

    plt.figure(figsize=(11, 5))
    plt.bar(monthly["month"], monthly["lop_days"])
    plt.title("Monthly Loss of Pay (LOP) Days")
    plt.xlabel("Month")
    plt.ylabel("LOP days")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(CHARTS / "monthly_lop_days.png", dpi=150)
    plt.close()

if not leave_summary.empty:
    leave_chart = leave_summary.groupby(
        "leave_type_code"
    )["leave_days"].sum()

    if not leave_chart.empty:
        plt.figure(figsize=(9, 5))
        leave_chart.plot(kind="bar")
        plt.title("Leave Days by Leave Type")
        plt.xlabel("Leave type")
        plt.ylabel("Leave days")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.savefig(CHARTS / "leave_days_by_type.png", dpi=150)
        plt.close()

# --------------------------------------------------
# 12. Summary
# --------------------------------------------------
summary = [
    "TASK 6 - OVERTIME & LEAVE IMPACT",
    f"Payroll rows processed: {len(payroll)}",
    f"Attendance rows processed: {len(attendance)}",
    f"Leave requests processed: {len(leave)}",
    f"Payroll date range: {payroll['month'].min()} to {payroll['month'].max()}",
    f"Total overtime pay (raw): {payroll['overtime_pay'].sum():,.2f}",
    f"Total employer cost (raw): {payroll['employer_cost'].sum():,.2f}",
    f"Total payroll LOP days (raw): {payroll['lop_days'].sum():,.2f}",
    f"Total leave days (all statuses): {leave['days'].sum():,.2f}",
    f"Approved leave days: {leave.loc[leave['status'] == 'Approved', 'days'].sum():,.2f}",
    f"Quality flags created: {len(quality_report)}",
    "",
    "CAVEATS:",
    "- These are raw totals, not corrected/validated totals.",
    "- Duplicate and orphan payroll rows are flagged, not automatically removed.",
    "- Attendance-after-exit records are flagged for review.",
    "- Invalid leave date records are flagged; source values are preserved.",
    "- Payroll overtime_hours_paid and attendance overtime_hours are separate measures.",
    "- Department reports suppress groups with fewer than 5 employees.",
    "- Review dq_known_issues and the data contracts before final reporting."
]

(OUT / "task6_summary.txt").write_text(
    "\n".join(summary), encoding="utf-8"
)

print("\nTask 6 processing completed.")
print(f"Output folder: {OUT}")
print(f"Quality flags: {OUT / 'task6_data_quality_flags.csv'}")
print("\nQuality issues by type:")

if quality_report.empty:
    print("No flags generated by the current checks.")
else:
    print(quality_report.groupby("issue").size().to_string())

print("\n" + "\n".join(summary))
