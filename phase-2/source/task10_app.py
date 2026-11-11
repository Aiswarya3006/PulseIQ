from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "pulseiq.duckdb"

st.set_page_config(
    page_title="PulseIQ | Budget & KPI Dashboard",
    page_icon="Ã°Å¸â€œÅ ",
    layout="wide",
)

st.title("PulseIQ - Budget vs Actual & KPI Dashboard")
st.caption(
    "Task 10 | Monthly payroll budget, actual cost, variance and KPI targets"
)

if not DB_PATH.exists():
    st.error(f"DuckDB database not found: {DB_PATH}")
    st.stop()


@st.cache_data
def load_data():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        budget = con.execute("""
            SELECT
                CAST(date_trunc('month', CAST(month AS DATE)) AS DATE)
                    AS month_start,
                department_id,
                SUM(budget_payroll_cost) AS budget
            FROM raw.budget_payroll_dept_month
            GROUP BY 1, 2
        """).fetchdf()

        actual = con.execute("""
            SELECT
                CAST(date_trunc('month', period_end_date) AS DATE)
                    AS month_start,
                department_id,
                SUM(employer_cost) AS actual,
                MAX(employees_paid) AS employees_paid
            FROM main.m09_employer_cost
            GROUP BY 1, 2
        """).fetchdf()

        targets = con.execute("""
            SELECT
                CAST(date_trunc('month', CAST(month AS DATE)) AS DATE)
                    AS month_start,
                department_id,
                attendance_rate_target,
                overtime_share_target_pct,
                attrition_monthly_target_pct,
                task_completion_target_pct
            FROM raw.kpi_targets
        """).fetchdf()

        attendance = con.execute("""
            SELECT
                CAST(date_trunc('month', period_end_date) AS DATE)
                    AS month_start,
                department_id,
                AVG(attendance_rate_pct) AS attendance_actual,
                MAX(group_size) AS attendance_group_size
            FROM main.m13_attendance_rate
            GROUP BY 1, 2
        """).fetchdf()

        overtime = con.execute("""
            SELECT
                CAST(date_trunc('month', period_end_date) AS DATE)
                    AS month_start,
                department_id,
                AVG(overtime_share_pct) AS overtime_actual,
                MAX(group_size) AS overtime_group_size
            FROM main.m11_overtime_share
            GROUP BY 1, 2
        """).fetchdf()

        attrition = con.execute("""
            SELECT
                CAST(date_trunc('month', month_start_date) AS DATE)
                    AS month_start,
                department_id,
                AVG(attrition_pct) AS attrition_actual,
                MAX(group_size) AS attrition_group_size
            FROM main.m04_monthly_attrition
            GROUP BY 1, 2
        """).fetchdf()

        # Match the existing M22 definition:
        # Done / non-cancelled tasks * 100, with at least 5 eligible tasks.
        # Attribute each sprint to its end month.
        completion = con.execute("""
            WITH sprint_team AS (
                SELECT
                    CAST(date_trunc('month', s.end_date) AS DATE)
                        AS month_start,
                    t.department_id,
                    f.sprint_id,
                    f.team_id,
                    COUNT(*) FILTER (WHERE f.status != 'Cancelled')
                        AS eligible_tasks,
                    COUNT(*) FILTER (
                        WHERE f.status = 'Done'
                    ) AS done_tasks
                FROM raw.fact_task f
                JOIN raw.dim_sprint s USING (sprint_id)
                JOIN raw.dim_team t USING (team_id)
                WHERE f.status != 'Cancelled'
                GROUP BY 1, 2, 3, 4
            )
            SELECT
                month_start,
                department_id,
                CASE
                    WHEN SUM(eligible_tasks) >= 5
                    THEN 100.0 * SUM(done_tasks)
                         / NULLIF(SUM(eligible_tasks), 0)
                    ELSE NULL
                END AS task_completion_actual,
                SUM(eligible_tasks) AS task_eligible_count
            FROM sprint_team
            GROUP BY 1, 2
        """).fetchdf()

        departments = con.execute("""
            SELECT department_id, department_name
            FROM raw.dim_department
        """).fetchdf()

        return (
            budget, actual, targets, attendance, overtime,
            attrition, completion, departments
        )
    finally:
        con.close()


try:
    (
        budget, actual, targets, attendance, overtime,
        attrition, completion, departments
    ) = load_data()
except Exception as exc:
    st.error(f"Could not load dashboard data: {exc}")
    st.stop()


def normalize_dates(frame):
    frame = frame.copy()
    frame["month_start"] = pd.to_datetime(frame["month_start"])
    return frame


frames = [
    budget, actual, targets, attendance, overtime, attrition, completion
]
budget, actual, targets, attendance, overtime, attrition, completion = [
    normalize_dates(frame) for frame in frames
]

df = budget.merge(
    actual, on=["month_start", "department_id"], how="left"
)
df = df.merge(
    targets, on=["month_start", "department_id"], how="left"
)
for metric_df in [attendance, overtime, attrition, completion]:
    df = df.merge(
        metric_df, on=["month_start", "department_id"], how="left"
    )

df = df.merge(departments, on="department_id", how="left")
df["department_name"] = df["department_name"].fillna(df["department_id"])

# Keep missing actuals missing; never replace them with zero.
df["variance"] = df["actual"] - df["budget"]
df["variance_pct"] = (
    df["variance"] / df["budget"].where(df["budget"] != 0)
) * 100

st.sidebar.header("Dashboard Filters")

min_month = df["month_start"].min().date()
max_month = df["month_start"].max().date()
month_range = st.sidebar.date_input(
    "Month range",
    value=(min_month, max_month),
    min_value=min_month,
    max_value=max_month,
)

department_options = sorted(df["department_name"].dropna().unique())
selected_departments = st.sidebar.multiselect(
    "Departments",
    department_options,
    default=list(department_options),
)

if isinstance(month_range, (tuple, list)) and len(month_range) == 2:
    start_month, end_month = month_range
else:
    start_month = end_month = month_range

filtered = df[
    df["month_start"].dt.date.between(start_month, end_month)
    & df["department_name"].isin(selected_departments)
].copy()

if filtered.empty:
    st.warning("No data for the selected filters.")
    st.stop()

# Payroll groups with fewer than five employees are suppressed.
# Missing employee counts are not treated as zero.
filtered.loc[
    filtered["employees_paid"].notna()
    & (filtered["employees_paid"] < 5),
    "actual"
] = float("nan")

filtered["variance"] = filtered["actual"] - filtered["budget"]
filtered["variance_pct"] = (
    filtered["variance"] / filtered["budget"].where(filtered["budget"] != 0)
) * 100

total_budget = filtered["budget"].sum(min_count=1)
total_actual = filtered["actual"].sum(min_count=1)
total_variance = (
    total_actual - total_budget
    if pd.notna(total_actual) and pd.notna(total_budget)
    else float("nan")
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Budget", f"INR {total_budget:,.0f}" if pd.notna(total_budget) else "N/A")
c2.metric("Actual payroll", f"INR {total_actual:,.0f}" if pd.notna(total_actual) else "N/A")
c3.metric(
    "Variance",
    f"INR {total_variance:,.0f}" if pd.notna(total_variance) else "N/A",
)
c4.metric(
    "Variance %",
    f"{100 * total_variance / total_budget:.2f}%"
    if pd.notna(total_variance) and total_budget
    else "N/A",
)

st.subheader("Monthly Budget vs Actual")
monthly = filtered.groupby("month_start", as_index=False).agg(
    budget=("budget", "sum"),
    actual=("actual", lambda x: x.sum(min_count=1)),
)
monthly_long = monthly.melt(
    id_vars="month_start",
    value_vars=["budget", "actual"],
    var_name="series",
    value_name="payroll_cost",
)
fig = px.line(
    monthly_long,
    x="month_start",
    y="payroll_cost",
    color="series",
    markers=True,
    title="Monthly payroll cost (INR)",
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Department Budget Variance")
ranking = filtered.groupby(
    ["department_id", "department_name"], as_index=False
).agg(
    budget=("budget", "sum"),
    actual=("actual", lambda x: x.sum(min_count=1)),
)
ranking["variance"] = ranking["actual"] - ranking["budget"]
ranking["variance_pct"] = (
    ranking["variance"] / ranking["budget"].where(ranking["budget"] != 0)
) * 100
ranking = ranking.sort_values("variance", ascending=False, na_position="last")
st.dataframe(
    ranking.style.format({
        "budget": "INR {:,.0f}",
        "actual": "INR {:,.0f}",
        "variance": "INR {:,.0f}",
        "variance_pct": "{:.2f}%",
    }, na_rep="N/A"),
    use_container_width=True,
    hide_index=True,
)

chart_ranking = ranking.dropna(subset=["variance"])
if not chart_ranking.empty:
    st.plotly_chart(
        px.bar(
            chart_ranking,
            x="department_name",
            y="variance",
            color="variance",
            title="Department variance: positive = overspend",
            labels={"department_name": "Department", "variance": "Variance (INR)"},
        ),
        use_container_width=True,
    )

st.subheader("KPI Target Status")
kpi_rows = []
for _, row in filtered.iterrows():
    checks = [
        ("Attendance", row.get("attendance_actual"),
         row.get("attendance_rate_target", float("nan")) * 100,
         "higher"),
        ("Overtime share", row.get("overtime_actual"),
         row.get("overtime_share_target_pct"), "lower"),
        ("Attrition", row.get("attrition_actual"),
         row.get("attrition_monthly_target_pct"), "lower"),
        ("Task completion", row.get("task_completion_actual"),
         row.get("task_completion_target_pct"), "higher"),
    ]
    for metric, value, target, direction in checks:
        if pd.isna(value) or pd.isna(target):
            status = "Unavailable"
        elif (value >= target if direction == "higher" else value <= target):
            status = "Meets target"
        else:
            status = "Needs attention"
        kpi_rows.append({
            "Month": row["month_start"].strftime("%Y-%m"),
            "Department": row["department_name"],
            "KPI": metric,
            "Actual (%)": value,
            "Target (%)": target,
            "Status": status,
        })

kpi_df = pd.DataFrame(kpi_rows)
st.dataframe(
    kpi_df.style.format(
        {"Actual (%)": "{:.2f}", "Target (%)": "{:.2f}"},
        na_rep="N/A",
    ),
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "Attendance target is converted from ratio to percent. KPI status uses "
    "the configured target and metric direction; unavailable values are not "
    "treated as zero. Task completion is attributed to sprint end month."
)

st.subheader("Hand Verification - Three Department-Months")
verification = filtered.sort_values(
    ["month_start", "department_id"]
).dropna(subset=["budget", "actual"]).head(3).copy()

if verification.empty:
    st.info("No department-month rows have both budget and actual for verification.")
else:
    verification["variance_check"] = (
        verification["actual"] - verification["budget"]
    )
    verification["variance_pct_check"] = (
        verification["variance_check"] / verification["budget"]
    ) * 100
    st.dataframe(
        verification[[
            "month_start", "department_id", "budget", "actual",
            "variance_check", "variance_pct_check"
        ]].style.format({
            "budget": "INR {:,.2f}",
            "actual": "INR {:,.2f}",
            "variance_check": "INR {:,.2f}",
            "variance_pct_check": "{:.2f}%",
        }),
        use_container_width=True,
        hide_index=True,
    )
    st.caption("Variance = actual - budget; variance % = variance / budget x 100.")

st.subheader("Recommendations - Highest Overspend")
top_overspend = ranking.dropna(subset=["variance"])
top_overspend = top_overspend[top_overspend["variance"] > 0].head(2)

if top_overspend.empty:
    st.write("No positive overspend found in the selected period.")
else:
    for _, row in top_overspend.iterrows():
        st.markdown(
            f"**{row['department_name']}** - variance "
            f"INR {row['variance']:,.0f} "
            f"({row['variance_pct']:.2f}% of budget). "
            "Review monthly payroll drivers, overtime, headcount changes, "
            "and one-off payments before adjusting the forecast."
        )

st.warning(
    "Budget caveat: the supplied budget may not reflect a hiring freeze "
    "or subsequent workforce changes. Treat variance as a planning signal, "
    "not proof of overspending misconduct. Confirm budget assumptions with Finance."
)

st.caption(
    "Data quality: missing actuals remain N/A. Department payroll groups "
    "with fewer than five employees are suppressed."
)

st.download_button(
    "Download filtered budget and KPI data (CSV)",
    data=filtered.to_csv(index=False).encode("utf-8"),
    file_name="pulseiq_task10_budget_kpi.csv",
    mime="text/csv",
)


