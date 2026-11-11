from pathlib import Path

import duckdb
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st


# ---------------------------------------------------------
# 1. PAGE CONFIGURATION
# ---------------------------------------------------------

st.set_page_config(
    page_title="PulseIQ | Task 13 Department Impact",
    page_icon="📊",
    layout="wide"
)

st.title("PulseIQ | Cross-Department Impact Analysis")
st.caption(
    "Task 13 - Department-level payroll, overtime, attendance, "
    "leave and attrition analysis"
)
DB_PATH = Path(__file__).resolve().parent / "pulseiq.duckdb"

VAULT_CSV = (
    DB_PATH.parents[2]
    / "04_Validation_Vault"
    / "unlock_PQ-13_reference_summary_dept_month.csv"
)


# ---------------------------------------------------------
# 2. LOAD COMBINED DEPARTMENT-MONTH DATA
# ---------------------------------------------------------

if not DB_PATH.exists():
    st.error(f"DuckDB database not found: {DB_PATH}")
    st.stop()


@st.cache_data
def load_data(database_path: str, modified_time: float) -> pd.DataFrame:
    con = duckdb.connect(database_path, read_only=True)
    try:
        data = con.execute("""
            SELECT *
            FROM main.v_task13_department_month_impact
            ORDER BY department_id, month_start
        """).fetchdf()
    finally:
        con.close()

    data["month_start"] = pd.to_datetime(data["month_start"])

    numeric_columns = [
        "headcount_start",
        "headcount_end",
        "average_headcount",
        "hires",
        "exits",
        "voluntary_exits",
        "attrition_rate_monthly_pct",
        "gross_pay",
        "employer_cost",
        "overtime_cost",
        "overtime_hours",
        "scheduled_days",
        "present_days",
        "late_arrivals",
        "attendance_rate_pct",
        "leave_days",
        "leave_days_per_head",
    ]

    for column in numeric_columns:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")

    return data


df = load_data(str(DB_PATH), DB_PATH.stat().st_mtime)

if df.empty:
    st.warning("No department-month data is available.")
    st.stop()

required_columns = [
    "department_id",
    "department_name",
    "month_start",
    "employer_cost",
    "overtime_cost",
    "overtime_hours",
    "attrition_rate_monthly_pct",
    "attendance_rate_pct",
    "leave_days",
    "leave_days_per_head",
]

missing_columns = [
    column for column in required_columns
    if column not in df.columns
]

if missing_columns:
    st.error(
        f"Required columns are missing from the Task 13 view: "
        f"{missing_columns}"
    )
    st.stop()


# ---------------------------------------------------------
# 3. FILTERS
# ---------------------------------------------------------

st.sidebar.header("Dashboard Filters")

# D00 is excluded from the dashboard because it is a very small group.
display_df = df[df["department_id"] != "D00"].copy()

departments = sorted(
    display_df["department_name"].dropna().unique()
)

if not departments:
    st.warning("No reportable departments are available.")
    st.stop()

default_department = (
    "Customer Support"
    if "Customer Support" in departments
    else departments[0]
)

selected_department = st.sidebar.selectbox(
    "Select Department",
    departments,
    index=departments.index(default_department)
)

min_date = display_df["month_start"].min().date()
max_date = display_df["month_start"].max().date()

selected_dates = st.sidebar.date_input(
    "Select Month Range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

if not isinstance(selected_dates, (tuple, list)) or len(selected_dates) != 2:
    st.info("Please select both a start date and an end date.")
    st.stop()

start_date, end_date = selected_dates

if start_date > end_date:
    st.error("Start date must be before end date.")
    st.stop()

filtered = display_df[
    (display_df["month_start"].dt.date >= start_date)
    & (display_df["month_start"].dt.date <= end_date)
].copy()

if filtered.empty:
    st.warning("No records found for the selected filters.")
    st.stop()

department_data = (
    filtered[filtered["department_name"] == selected_department]
    .sort_values("month_start")
    .copy()
)


# ---------------------------------------------------------
# 4. DEPARTMENT-LEVEL SUMMARY
# ---------------------------------------------------------

department_summary = (
    filtered.groupby(
        ["department_id", "department_name"],
        as_index=False
    )
    .agg(
        months=("month_start", "nunique"),
        headcount_end=("headcount_end", "mean"),
        gross_pay=("gross_pay", "sum"),
        employer_cost=("employer_cost", "sum"),
        overtime_cost=("overtime_cost", "sum"),
        overtime_hours=("overtime_hours", "sum"),
        late_arrivals=("late_arrivals", "sum"),
        leave_days=("leave_days", "sum"),
        avg_leave_days_per_head=("leave_days_per_head", "mean"),
        avg_attrition_pct=("attrition_rate_monthly_pct", "mean"),
        avg_attendance_pct=("attendance_rate_pct", "mean"),
    )
)

department_summary["avg_attrition_pct"] = (
    department_summary["avg_attrition_pct"].round(2)
)

department_summary["avg_attendance_pct"] = (
    department_summary["avg_attendance_pct"].round(2)
)

department_summary["avg_leave_days_per_head"] = (
    department_summary["avg_leave_days_per_head"].round(2)
)

department_summary = department_summary.sort_values(
    "employer_cost",
    ascending=False
)


# ---------------------------------------------------------
# 5. KEY PERFORMANCE INDICATORS
# ---------------------------------------------------------

st.subheader("1. Selected Department Performance Overview")

total_employer_cost = department_data["employer_cost"].sum()
total_overtime_cost = department_data["overtime_cost"].sum()
total_overtime_hours = department_data["overtime_hours"].sum()
total_leave_days = department_data["leave_days"].sum()

avg_attrition = (
    department_data["attrition_rate_monthly_pct"].mean()
)

if (
    "present_days" in department_data.columns
    and "scheduled_days" in department_data.columns
    and department_data["scheduled_days"].sum() > 0
):
    avg_attendance = (
        department_data["present_days"].sum()
        / department_data["scheduled_days"].sum()
        * 100
    )
else:
    avg_attendance = (
        department_data["attendance_rate_pct"].mean()
    )

avg_leave_per_head = (
    department_data["leave_days_per_head"].mean()
)

col1, col2, col3 = st.columns(3)

col1.metric(
    "Total Employer Cost",
    f"₹{total_employer_cost:,.0f}"
)

col2.metric(
    "Overtime Cost",
    f"₹{total_overtime_cost:,.0f}"
)

col3.metric(
    "Overtime Hours",
    f"{total_overtime_hours:,.1f}"
)

col4, col5, col6 = st.columns(3)

col4.metric(
    "Allocated Leave Days",
    f"{total_leave_days:,.1f}"
)

col5.metric(
    "Average Monthly Attrition",
    f"{avg_attrition:.2f}%"
)

col6.metric(
    "Attendance Rate",
    f"{avg_attendance:.2f}%"
)

st.caption(
    f"Average monthly leave days per head: "
    f"{avg_leave_per_head:.2f}"
)


# ---------------------------------------------------------
# 6. CROSS-DEPARTMENT IMPACT CHART
# ---------------------------------------------------------

st.subheader(
    "2. Cross-Department Cost, Overtime and Attrition"
)

st.caption(
    "This chart compares departments over the selected date range. "
    "Cost metrics use the left axis; average monthly attrition uses "
    "the right axis."
)

fig_cross = make_subplots(
    specs=[[{"secondary_y": True}]]
)

fig_cross.add_trace(
    go.Bar(
        x=department_summary["department_name"],
        y=department_summary["employer_cost"],
        name="Employer Cost",
        hovertemplate=(
            "%{x}<br>Employer Cost: ₹%{y:,.0f}<extra></extra>"
        ),
    ),
    secondary_y=False,
)

fig_cross.add_trace(
    go.Bar(
        x=department_summary["department_name"],
        y=department_summary["overtime_cost"],
        name="Overtime Cost",
        hovertemplate=(
            "%{x}<br>Overtime Cost: ₹%{y:,.0f}<extra></extra>"
        ),
    ),
    secondary_y=False,
)

fig_cross.add_trace(
    go.Scatter(
        x=department_summary["department_name"],
        y=department_summary["avg_attrition_pct"],
        name="Average Monthly Attrition",
        mode="lines+markers",
        hovertemplate=(
            "%{x}<br>Average Attrition: %{y:.2f}%<extra></extra>"
        ),
    ),
    secondary_y=True,
)

fig_cross.update_layout(
    title=(
        "Department Comparison: Employer Cost, "
        "Overtime Cost and Attrition"
    ),
    xaxis_title="Department",
    barmode="group",
    hovermode="x unified",
    legend_title="Metrics",
    height=570,
    xaxis_tickangle=-35,
)

fig_cross.update_yaxes(
    title_text="Cost (₹)",
    secondary_y=False,
)

fig_cross.update_yaxes(
    title_text="Average Monthly Attrition (%)",
    secondary_y=True,
)

st.plotly_chart(
    fig_cross,
    use_container_width=True
)


# ---------------------------------------------------------
# 7. SELECTED DEPARTMENT MONTHLY TRENDS
# ---------------------------------------------------------

st.subheader("3. Selected Department Monthly Trends")

fig_monthly = make_subplots(
    specs=[[{"secondary_y": True}]]
)

fig_monthly.add_trace(
    go.Scatter(
        x=department_data["month_start"],
        y=department_data["employer_cost"],
        name="Employer Cost",
        mode="lines+markers",
    ),
    secondary_y=False,
)

fig_monthly.add_trace(
    go.Scatter(
        x=department_data["month_start"],
        y=department_data["overtime_cost"],
        name="Overtime Cost",
        mode="lines+markers",
    ),
    secondary_y=False,
)

fig_monthly.add_trace(
    go.Scatter(
        x=department_data["month_start"],
        y=department_data["attrition_rate_monthly_pct"],
        name="Monthly Attrition",
        mode="lines+markers",
    ),
    secondary_y=True,
)

fig_monthly.update_layout(
    title=(
        f"{selected_department}: Monthly Cost, "
        "Overtime and Attrition"
    ),
    xaxis_title="Month",
    hovermode="x unified",
    legend_title="Metrics",
    height=450,
)

fig_monthly.update_yaxes(
    title_text="Cost (₹)",
    secondary_y=False
)

fig_monthly.update_yaxes(
    title_text="Monthly Attrition (%)",
    secondary_y=True
)

st.plotly_chart(
    fig_monthly,
    use_container_width=True
)


# ---------------------------------------------------------
# 8. DEPARTMENT COMPARISON TABLE
# ---------------------------------------------------------

st.subheader("4. Department Comparison Table")

st.dataframe(
    department_summary.round(2),
    use_container_width=True,
    hide_index=True,
)


# ---------------------------------------------------------
# 9. ATTENDANCE AND LEAVE DETAILS
# ---------------------------------------------------------

st.subheader("5. Attendance and Leave Details")

left, right = st.columns(2)

with left:
    fig_attendance = go.Figure()

    fig_attendance.add_trace(
        go.Scatter(
            x=department_data["month_start"],
            y=department_data["attendance_rate_pct"],
            name="Attendance Rate",
            mode="lines+markers",
        )
    )

    fig_attendance.update_layout(
        title=f"{selected_department}: Monthly Attendance Rate",
        xaxis_title="Month",
        yaxis_title="Attendance (%)",
        height=350,
    )

    st.plotly_chart(
        fig_attendance,
        use_container_width=True
    )

with right:
    leave_display = department_data[
        [
            "month_start",
            "leave_days",
            "leave_days_per_head"
        ]
    ].copy()

    leave_display = leave_display.rename(
        columns={
            "month_start": "Month",
            "leave_days": "Allocated Leave Days",
            "leave_days_per_head": "Leave Days per Head",
        }
    )

    st.markdown("**Monthly Leave Summary**")

    st.dataframe(
        leave_display.round(2),
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------
# 10. BUSINESS INSIGHTS
# ---------------------------------------------------------

st.subheader("6. Business Insights")

if not department_summary.empty:

    highest_cost = department_summary.loc[
        department_summary["employer_cost"].idxmax()
    ]

    highest_overtime = department_summary.loc[
        department_summary["overtime_cost"].idxmax()
    ]

    highest_attrition = department_summary.loc[
        department_summary["avg_attrition_pct"].idxmax()
    ]

    highest_leave_per_head = department_summary.loc[
        department_summary["avg_leave_days_per_head"].idxmax()
    ]

    st.write(
        f"**Highest employer cost:** "
        f"{highest_cost['department_name']} "
        f"with ₹{highest_cost['employer_cost']:,.0f}."
    )

    st.write(
        f"**Highest overtime cost:** "
        f"{highest_overtime['department_name']} "
        f"with ₹{highest_overtime['overtime_cost']:,.0f}."
    )

    st.write(
        f"**Highest average monthly attrition:** "
        f"{highest_attrition['department_name']} "
        f"at {highest_attrition['avg_attrition_pct']:.2f}%."
    )

    st.write(
        f"**Highest average leave days per head:** "
        f"{highest_leave_per_head['department_name']} "
        f"at {highest_leave_per_head['avg_leave_days_per_head']:.2f}."
    )


# ---------------------------------------------------------
# 11. JOIN ORDER AND GRAIN EXPLANATION
# ---------------------------------------------------------

st.subheader("7. Data Model: Join Order and Aggregation")

st.markdown("""
The combined view uses **department + month** as its reporting grain.

1. **Payroll:** Aggregate payroll rows to department and month first.
   Calculate gross pay, employer cost, overtime pay and overtime hours.

2. **Attendance:** Aggregate attendance rows to department and month first.
   Calculate scheduled days, present days and late arrivals.

3. **Leave:** Keep approved leave requests, split requests that cross month
   boundaries, map employees to their department for each segment, allocate
   recorded leave days using working-day weights, and aggregate to department
   and month.

4. **Headcount:** Use the monthly headcount fact as the base department-month
   set, then LEFT JOIN the payroll, attendance and leave aggregates using
   department ID and month.

**Why aggregate before joining?** Joining raw payroll, attendance and leave
records directly can create many-to-many row multiplication. Pre-aggregating
each source to the same department-month grain prevents that fan-out and
keeps the totals from being unintentionally duplicated.

**Metric definitions**

- Attendance rate = total present days / total scheduled days × 100.
- Leave days per head = allocated leave days / average monthly headcount.
- Overtime cost uses payroll overtime pay; overtime hours use paid overtime
  hours from payroll.
- Cross-month leave is allocated using working-day weights. This is an
  allocation assumption, not a change to the original recorded leave total.
""")


# ---------------------------------------------------------
# 12. CORRELATION VS CAUSATION
# ---------------------------------------------------------

st.subheader("8. Correlation vs Causation")

st.markdown("""
- Higher overtime and higher attrition occurring together may indicate a
  relationship worth investigating.
- This does **not** prove that overtime causes employees to leave.
- Other factors may influence both, including workload, staffing shortages,
  management, seasonality, compensation and job roles.
- Further analysis is needed before making causal claims.
""")


# ---------------------------------------------------------
# 13. REFERENCE SUMMARY COMPARISON
# ---------------------------------------------------------

st.subheader("9. Validation Vault Reference Comparison")

if not VAULT_CSV.exists():

    st.warning(
        "The Task 13 reference CSV was not found. "
        f"Expected location: {VAULT_CSV}"
    )

    st.info(
        "Keep unlock_PQ-13_reference_summary_dept_month.csv inside "
        "PulseIQ/04_Validation_Vault so this comparison can load it."
    )

else:

    try:
        reference = pd.read_csv(VAULT_CSV)

        reference["month"] = pd.to_datetime(
            reference["month"]
        )

        reference["department_id"] = (
            reference["department_id"].astype(str)
        )

        own = df.copy()

        own["department_id"] = (
            own["department_id"].astype(str)
        )

        comparison = reference.merge(
            own,
            left_on=["department_id", "month"],
            right_on=["department_id", "month_start"],
            how="outer",
            indicator=True,
        )

        both = comparison[
            comparison["_merge"] == "both"
        ].copy()

        match_col1, match_col2, match_col3 = st.columns(3)

        match_col1.metric(
            "Reference Rows",
            f"{len(reference):,}"
        )

        match_col2.metric(
            "Matched Department-Months",
            f"{len(both):,}"
        )

        match_col3.metric(
            "Unmatched Keys",
            f"{int((comparison['_merge'] != 'both').sum()):,}"
        )

        metric_pairs = [
            (
                "Employer Cost",
                "employer_cost_x",
                "employer_cost_y",
                0.02,
                1.0
            ),
            (
                "Gross Pay",
                "gross_pay_x",
                "gross_pay_y",
                0.02,
                1.0
            ),
            (
                "Overtime Pay",
                "overtime_pay",
                "overtime_cost",
                0.01,
                1.0
            ),
            (
                "Overtime Hours",
                "overtime_hours_x",
                "overtime_hours_y",
                0.01,
                1.0
            ),
            (
                "Late Arrivals",
                "late_arrivals_x",
                "late_arrivals_y",
                0.01,
                1.0
            ),
            (
                "Headcount End",
                "headcount_end_x",
                "headcount_end_y",
                0.01,
                1.0
            ),
            (
                "Hires",
                "hires_x",
                "hires_y",
                0.01,
                1.0
            ),
            (
                "Exits",
                "exits_x",
                "exits_y",
                0.01,
                1.0
            ),
            (
                "Monthly Attrition (%)",
                "attrition_rate_monthly_pct_x",
                "attrition_rate_monthly_pct_y",
                0.11,
                1.0
            ),
            (
                "Attendance Rate",
                "attendance_rate",
                "attendance_rate_pct",
                0.0011,
                100.0
            ),
        ]

        difference_rows = []
        detail_rows = []

        for (
            label,
            ref_col,
            own_col,
            tolerance,
            own_multiplier
        ) in metric_pairs:

            if (
                ref_col not in both.columns
                or own_col not in both.columns
            ):
                continue

            ref_values = pd.to_numeric(
                both[ref_col],
                errors="coerce"
            )

            own_values = (
                pd.to_numeric(
                    both[own_col],
                    errors="coerce"
                )
                / own_multiplier
            )

            delta = (ref_values - own_values).abs()

            mismatch = delta > tolerance

            difference_rows.append(
                {
                    "Metric": label,
                    "Mismatched Rows": int(mismatch.sum()),
                    "Tolerance": tolerance,
                }
            )

            if mismatch.any():

                bad = both.loc[
                    mismatch,
                    ["department_id", "month"]
                ].copy()

                bad["Metric"] = label

                bad["Reference Value"] = (
                    ref_values.loc[mismatch].values
                )

                bad["Our Value"] = (
                    own_values.loc[mismatch].values
                )

                bad["Absolute Difference"] = (
                    delta.loc[mismatch].values
                )

                detail_rows.append(bad)

        difference_summary = pd.DataFrame(
            difference_rows
        )

        st.markdown("**Metric-by-metric comparison**")

        st.dataframe(
            difference_summary,
            use_container_width=True,
            hide_index=True,
        )

        if detail_rows:

            difference_details = pd.concat(
                detail_rows,
                ignore_index=True
            )

            difference_details["month"] = pd.to_datetime(
                difference_details["month"]
            ).dt.strftime("%Y-%m")

            difference_details = difference_details.rename(
                columns={
                    "department_id": "Department ID",
                    "month": "Month",
                }
            )

            st.markdown(
                "**Rows that differ from the reference**"
            )

            st.dataframe(
                difference_details.round(3),
                use_container_width=True,
                hide_index=True,
            )

            st.download_button(
                "Download Reference Difference Details CSV",
                data=difference_details.to_csv(
                    index=False
                ).encode("utf-8"),
                file_name=(
                    "task13_reference_difference_details.csv"
                ),
                mime="text/csv",
            )

        else:

            difference_details = pd.DataFrame()

            st.success(
                "All compared metrics are within the configured tolerances."
            )

        st.caption(
            "Reference comparisons are diagnostic. Differences are shown "
            "rather than silently changing the source data."
        )

    except Exception as exc:

        st.error(
            f"Could not complete the reference comparison: {exc}"
        )


# ---------------------------------------------------------
# 14. EVIDENCE DOWNLOADS
# ---------------------------------------------------------

st.subheader("10. Task 13 Evidence Downloads")

st.download_button(
    "Download Department Comparison CSV",
    data=department_summary.to_csv(
        index=False
    ).encode("utf-8"),
    file_name="task13_department_comparison.csv",
    mime="text/csv",
)

st.download_button(
    "Download Department-Month Impact CSV",
    data=filtered.to_csv(
        index=False
    ).encode("utf-8"),
    file_name="task13_department_month_impact.csv",
    mime="text/csv",
)

st.caption(
    "PulseIQ | Task 13 | Cross-Department Impact Analysis"
)