from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st


# --------------------------------------------------
# Configuration
# --------------------------------------------------
DB_PATH = Path(__file__).resolve().parent / "pulseiq.duckdb"

st.set_page_config(
    page_title="PulseIQ Workforce Dashboard",
    page_icon="📊",
    layout="wide",
)

st.title("PulseIQ Workforce Dashboard")
st.caption("Workforce metrics, attendance, overtime and leave trends")


# --------------------------------------------------
# Load data from DuckDB
# --------------------------------------------------
@st.cache_data
def load_data():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    connection = duckdb.connect(str(DB_PATH), read_only=True)

    try:
        tables = connection.execute("SHOW ALL TABLES").fetchdf()
        data = {}

        for _, item in tables.iterrows():
            schema = str(item["schema"])
            name = str(item["name"])

            # Load metric views, leave, attendance and calendar source tables.
            if (
                name.startswith("m")
                or (
                    schema == "raw"
                    and name in {
                        "fact_leave",
                        "fact_attendance_monthly",
                        "dim_date",
                        "dim_employee",
                        "fact_headcount_monthly",
                        "fact_attrition_risk",
                    }
                )
                or name == "metric_catalog"
            ):
                key = f"{schema}.{name}"
                query = f'SELECT * FROM "{schema}"."{name}"'
                data[key] = connection.execute(query).fetchdf()

        return data

    finally:
        connection.close()


try:
    data = load_data()
except Exception as error:
    st.error(f"Unable to load PulseIQ database: {error}")
    st.stop()


# --------------------------------------------------
# Helpers
# --------------------------------------------------
def get_table(name):
    """Find a loaded table or view by its name."""
    for key, frame in data.items():
        if key.split(".")[-1].lower() == name.lower():
            return frame.copy()
    return pd.DataFrame()


def get_date_column(frame):
    if frame.empty:
        return None

    candidates = [
        "period_end_date",
        "month_end_date",
        "month_start_date",
        "period_start_date",
        "date",
        "start_date",
    ]

    for column in candidates:
        if column in frame.columns:
            return column

    for column in frame.columns:
        if "date" in column.lower() and "key" not in column.lower():
            converted = pd.to_datetime(frame[column], errors="coerce")
            if converted.notna().any():
                return column

    return None


def get_metric_column(frame, view_name):
    """Select a metric column without accidentally charting group_size."""
    preferred = {
        "m13_attendance_rate": "attendance_rate_pct",
        "m14_late_arrival_rate": "late_arrival_rate_pct",
        "m11_overtime_share": "overtime_share_pct",
        "m15_lop_days": "lop_days",
    }

    if view_name in preferred and preferred[view_name] in frame.columns:
        return preferred[view_name]

    excluded_words = (
        "group_size",
        "department_id",
        "employee_id",
        "employee_key",
        "date_key",
        "_key",
        "_id",
    )

    numeric_columns = frame.select_dtypes(include="number").columns.tolist()
    candidates = [
        column for column in numeric_columns
        if not any(word in column.lower() for word in excluded_words)
    ]

    return candidates[0] if candidates else None


def apply_filters(frame, start_date, end_date, department):
    result = frame.copy()
    date_column = get_date_column(result)

    if date_column:
        result[date_column] = pd.to_datetime(
            result[date_column], errors="coerce"
        )
        result = result[
            result[date_column].dt.date.between(start_date, end_date)
        ]

    if (
        department != "All departments"
        and "department_id" in result.columns
    ):
        result = result[
            result["department_id"].astype(str) == department
        ]

    return result


def draw_metric_chart(view_name, title, start_date, end_date, department):
    frame = get_table(view_name)
    if frame.empty:
        return

    frame = apply_filters(frame, start_date, end_date, department)
    date_column = get_date_column(frame)
    metric_column = get_metric_column(frame, view_name)

    if date_column is None or metric_column is None or frame.empty:
        return

    frame[date_column] = pd.to_datetime(frame[date_column], errors="coerce")
    frame = frame.dropna(subset=[date_column, metric_column])
    if frame.empty:
        return

    if metric_column.endswith("_pct") and "group_size" in frame.columns:
        frame["_weighted_value"] = (
            frame[metric_column] * frame["group_size"]
        )
        grouped = frame.groupby(date_column).agg(
            weighted_total=("_weighted_value", "sum"),
            group_total=("group_size", "sum"),
        )
        grouped["value"] = (
            grouped["weighted_total"]
            / grouped["group_total"].replace(0, float("nan"))
        )
        chart_data = grouped.reset_index()[[date_column, "value"]]
    else:
        aggregation = (
            "mean" if metric_column.endswith("_pct") else "sum"
        )
        chart_data = (
            frame.groupby(date_column, as_index=False)[metric_column]
            .agg(aggregation)
            .rename(columns={metric_column: "value"})
        )

    chart_data = chart_data.sort_values(date_column)
    fig = px.line(
        chart_data,
        x=date_column,
        y="value",
        markers=True,
        title=title,
        labels={date_column: "Month", "value": metric_column},
    )
    st.plotly_chart(fig, width="stretch")


# --------------------------------------------------
# Date and department filters
# --------------------------------------------------
all_dates = []
for frame in data.values():
    date_column = get_date_column(frame)
    if date_column:
        values = pd.to_datetime(
            frame[date_column], errors="coerce"
        ).dropna()
        if not values.empty:
            all_dates.extend(values.tolist())

if all_dates:
    min_date = min(all_dates).date()
    max_date = max(all_dates).date()
else:
    min_date = pd.Timestamp("2025-01-01").date()
    max_date = pd.Timestamp.today().date()

st.sidebar.header("Dashboard Filters")
date_range = st.sidebar.date_input(
    "Date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start_date, end_date = date_range
elif isinstance(date_range, (tuple, list)) and len(date_range) == 1:
    start_date = end_date = date_range[0]
else:
    start_date = end_date = date_range

departments = set()
for frame in data.values():
    if "department_id" in frame.columns:
        departments.update(
            frame["department_id"].dropna().astype(str).unique().tolist()
        )

department_options = ["All departments"] + sorted(departments)
selected_department = st.sidebar.selectbox(
    "Department", department_options
)


# --------------------------------------------------
# Workforce overview and metric views
# --------------------------------------------------
st.header("Workforce Overview")
overview_views = [
    ("m01_headcount_monthly", "Headcount Trend"),
    ("m02_hires", "Hires Trend"),
    ("m03_exits", "Exits Trend"),
    ("m04_attrition_rate", "Attrition Trend"),
]
available_overview = [
    (view, title) for view, title in overview_views
    if not get_table(view).empty
]

if available_overview:
    for view, title in available_overview:
        draw_metric_chart(
            view, title, start_date, end_date, selected_department
        )
else:
    st.info(
        "Overview metric views were not found under the expected names. "
        "See Metric View Availability below for the views that are available."
    )


# --------------------------------------------------
# Existing attendance and punctuality charts
# --------------------------------------------------
st.header("Attendance & Punctuality")
draw_metric_chart(
    "m13_attendance_rate",
    "Attendance Rate Trend",
    start_date,
    end_date,
    selected_department,
)
draw_metric_chart(
    "m14_late_arrival_rate",
    "Late Arrival Rate Trend",
    start_date,
    end_date,
    selected_department,
)


# --------------------------------------------------
# Existing overtime and LOP charts
# --------------------------------------------------
st.header("Overtime & Leave Trends")
draw_metric_chart(
    "m11_overtime_share",
    "Overtime Share Trend",
    start_date,
    end_date,
    selected_department,
)
draw_metric_chart(
    "m15_lop_days",
    "Loss of Pay (LOP) Days Trend",
    start_date,
    end_date,
    selected_department,
)


# --------------------------------------------------
# Leave days by type
# --------------------------------------------------
st.subheader("Leave Days by Type")
leave_df = get_table("fact_leave")

if leave_df.empty:
    st.warning("raw.fact_leave was not found in the database.")
else:
    required_columns = {"leave_type_code", "days", "status"}
    if not required_columns.issubset(leave_df.columns):
        st.warning(
            "Leave table is missing required columns: "
            "leave_type_code, days, status."
        )
    else:
        approved_leave = leave_df[
            leave_df["status"].astype(str).str.strip().str.lower()
            == "approved"
        ].copy()

        if "start_date" in approved_leave.columns:
            approved_leave["start_date"] = pd.to_datetime(
                approved_leave["start_date"], errors="coerce"
            )
            approved_leave = approved_leave[
                approved_leave["start_date"].dt.date.between(
                    start_date, end_date
                )
            ]

        # Apply department filter by mapping leave requests to attendance
        # employee + month records, when source keys are available.
        if selected_department != "All departments":
            attendance_source = get_table("fact_attendance_monthly")
            if (
                not attendance_source.empty
                and "employee_id" in approved_leave.columns
                and "employee_id" in attendance_source.columns
                and "start_date" in approved_leave.columns
            ):
                attendance_source["period_end_date"] = pd.to_datetime(
                    attendance_source["period_end_date"], errors="coerce"
                )
                attendance_source["month"] = (
                    attendance_source["period_end_date"]
                    .dt.to_period("M").dt.to_timestamp()
                )
                approved_leave["month"] = (
                    approved_leave["start_date"]
                    .dt.to_period("M").dt.to_timestamp()
                )
                dept_map = attendance_source[
                    ["employee_id", "month", "department_id"]
                ].drop_duplicates()
                approved_leave = approved_leave.merge(
                    dept_map,
                    on=["employee_id", "month"],
                    how="left",
                )
                approved_leave = approved_leave[
                    approved_leave["department_id"].astype(str)
                    == selected_department
                ]
            else:
                st.info(
                    "Department filtering could not be applied to leave "
                    "because employee/month mapping columns were unavailable."
                )

        leave_summary = (
            approved_leave.groupby("leave_type_code", as_index=False)
            .agg(
                leave_days=("days", "sum"),
                requests=("leave_type_code", "size"),
            )
            .sort_values("leave_days", ascending=False)
        )

        if leave_summary.empty:
            st.info("No approved leave requests match the selected filters.")
        else:
            fig_leave = px.bar(
                leave_summary,
                x="leave_type_code",
                y="leave_days",
                text="leave_days",
                title="Approved Leave Days by Type",
                labels={
                    "leave_type_code": "Leave Type",
                    "leave_days": "Approved Leave Days",
                },
            )
            st.plotly_chart(fig_leave, width="stretch")
            st.dataframe(
                leave_summary, width="stretch", hide_index=True
            )
# --------------------------------------------------
# Task 6: Attendance and leave analysis
# --------------------------------------------------
st.header("Task 6 — Attendance & Leave Analysis")

raw_att = get_table("fact_attendance_monthly")
calendar_df = get_table("dim_date")

if raw_att.empty:
    st.error("raw.fact_attendance_monthly was not loaded.")
else:
    raw_att["period_end_date"] = pd.to_datetime(
        raw_att["period_end_date"], errors="coerce"
    )
    raw_att = raw_att.dropna(subset=["period_end_date"]).copy()
    raw_att["month"] = (
        raw_att["period_end_date"].dt.to_period("M").dt.to_timestamp()
    )

    for col in [
        "present_days", "scheduled_days", "late_arrivals", "overtime_hours"
    ]:
        raw_att[col] = pd.to_numeric(
            raw_att[col], errors="coerce"
        ).fillna(0)

    task_att = raw_att[
        raw_att["period_end_date"].dt.date.between(start_date, end_date)
    ].copy()

    if selected_department != "All departments":
        task_att = task_att[
            task_att["department_id"].astype(str) == selected_department
        ]

    if task_att.empty:
        st.info("No attendance records for these filters.")
    else:
        monthly_att = (
            task_att.groupby("month", as_index=False)
            .agg(
                present_days=("present_days", "sum"),
                scheduled_days=("scheduled_days", "sum"),
                late_arrivals=("late_arrivals", "sum"),
                overtime_hours=("overtime_hours", "sum"),
            )
        )
        monthly_att["attendance_rate_pct"] = (
            100 * monthly_att["present_days"]
            / monthly_att["scheduled_days"].replace(0, float("nan"))
        )

        calendar_month = pd.DataFrame(
            columns=["month", "holiday_dates", "long_weekend_days"]
        )
        if not calendar_df.empty and "date" in calendar_df.columns:
            calendar_df["date"] = pd.to_datetime(
                calendar_df["date"], errors="coerce"
            )
            calendar_df = calendar_df.dropna(subset=["date"]).copy()

            for flag in ["is_holiday", "is_weekend", "is_working_day"]:
                if flag in calendar_df.columns:
                    calendar_df[flag] = (
                        calendar_df[flag].astype(str).str.strip().str.upper()
                        == "Y"
                    )

            calendar_df["month"] = (
                calendar_df["date"].dt.to_period("M").dt.to_timestamp()
            )

            if "is_holiday" in calendar_df.columns:
                calendar_month = (
                    calendar_df.groupby("month", as_index=False)
                    .agg(holiday_dates=("is_holiday", "sum"))
                )

            if "is_working_day" in calendar_df.columns:
                calendar_df = calendar_df.sort_values("date")
                calendar_df["_non_working"] = ~calendar_df["is_working_day"]
                calendar_df["_run_id"] = (
                    calendar_df["_non_working"]
                    .ne(calendar_df["_non_working"].shift()).cumsum()
                )
                run_size = calendar_df.groupby("_run_id")[
                    "_non_working"
                ].transform("sum")
                calendar_df["long_weekend_day"] = (
                    calendar_df["_non_working"] & (run_size >= 3)
                )
                long_weekends = (
                    calendar_df.groupby("month", as_index=False)
                    .agg(long_weekend_days=("long_weekend_day", "sum"))
                )

                if calendar_month.empty:
                    calendar_month = long_weekends
                else:
                    calendar_month = calendar_month.merge(
                        long_weekends, on="month", how="outer"
                    )

        if not calendar_month.empty:
            monthly_att = monthly_att.merge(
                calendar_month, on="month", how="left"
            )

        for col in ["holiday_dates", "long_weekend_days"]:
            if col not in monthly_att.columns:
                monthly_att[col] = 0
            monthly_att[col] = monthly_att[col].fillna(0).astype(int)

        st.subheader("Monthly attendance rate")
        fig_rate = px.line(
            monthly_att.sort_values("month"),
            x="month",
            y="attendance_rate_pct",
            markers=True,
            custom_data=[
                "holiday_dates", "long_weekend_days",
                "scheduled_days", "present_days",
            ],
            labels={
                "month": "Month",
                "attendance_rate_pct": "Attendance rate (%)",
            },
            title="Weighted rate: total present days ÷ total scheduled days",
        )
        fig_rate.update_traces(
            hovertemplate=(
                "%{x|%b %Y}<br>Attendance: %{y:.2f}%"
                "<br>Holiday dates: %{customdata[0]}"
                "<br>Long-weekend days: %{customdata[1]}"
                "<br>Scheduled days: %{customdata[2]:,.0f}"
                "<br>Present days: %{customdata[3]:,.0f}<extra></extra>"
            )
        )
        st.plotly_chart(fig_rate, width="stretch")

        st.subheader("Department attendance rate by month")
        dept_month = (
            task_att.groupby(["month", "department_id"], as_index=False)
            .agg(
                present_days=("present_days", "sum"),
                scheduled_days=("scheduled_days", "sum"),
            )
        )
        dept_month["attendance_rate_pct"] = (
            100 * dept_month["present_days"]
            / dept_month["scheduled_days"].replace(0, float("nan"))
        )
        fig_dept = px.line(
            dept_month.sort_values("month"),
            x="month",
            y="attendance_rate_pct",
            color="department_id",
            markers=True,
            title="Attendance rate by department",
            labels={
                "month": "Month",
                "attendance_rate_pct": "Attendance rate (%)",
                "department_id": "Department",
            },
        )
        st.plotly_chart(fig_dept, width="stretch")

        st.subheader("Late arrivals and overtime hours")
        left, right = st.columns(2)
        with left:
            fig_late = px.bar(
                monthly_att,
                x="month",
                y="late_arrivals",
                title="Late arrivals by month",
                labels={"late_arrivals": "Late arrivals", "month": "Month"},
            )
            st.plotly_chart(fig_late, width="stretch")
        with right:
            fig_ot = px.bar(
                monthly_att,
                x="month",
                y="overtime_hours",
                title="Recorded overtime hours by month",
                labels={"overtime_hours": "Overtime hours", "month": "Month"},
            )
            st.plotly_chart(fig_ot, width="stretch")

        st.subheader("Holiday and long-weekend context")
        if calendar_month.empty:
            st.warning("Calendar holiday/weekend flags were not available.")
        else:
            calendar_display = calendar_month.copy()
            calendar_display["month"] = calendar_display["month"].dt.strftime(
                "%b %Y"
            )
            st.dataframe(
                calendar_display,
                width="stretch",
                hide_index=True,
            )
            st.caption(
                "Long-weekend days are part of runs of at least three "
                "consecutive non-working calendar days. Calendar context "
                "does not prove that holidays caused an attendance dip."
            )

        st.subheader("Three unusual months and likely explanations")
        unusual = monthly_att.sort_values("attendance_rate_pct").head(3).copy()
        baseline_late = monthly_att["late_arrivals"].median()
        baseline_ot = monthly_att["overtime_hours"].median()
        baseline_holidays = monthly_att["holiday_dates"].median()
        baseline_long_weekends = monthly_att["long_weekend_days"].median()

        if unusual.empty:
            st.info("Not enough monthly data to identify unusual months.")
        else:
            for rank, (_, row) in enumerate(
                unusual.sort_values("month").iterrows(), start=1
            ):
                reasons = []
                if row["holiday_dates"] > baseline_holidays:
                    reasons.append(
                        f"{int(row['holiday_dates'])} holiday date(s), above the "
                        f"selected-period median of {baseline_holidays:.0f}"
                    )
                if row["long_weekend_days"] > baseline_long_weekends:
                    reasons.append(
                        f"{int(row['long_weekend_days'])} long-weekend day(s), above "
                        f"the median of {baseline_long_weekends:.0f}"
                    )
                if row["late_arrivals"] > baseline_late:
                    reasons.append(
                        f"{int(row['late_arrivals']):,} late arrivals, above the "
                        f"median of {baseline_late:,.0f}"
                    )
                if row["overtime_hours"] > baseline_ot:
                    reasons.append(
                        f"{row['overtime_hours']:,.1f} overtime hours, above the "
                        f"median of {baseline_ot:,.1f}"
                    )
                if not reasons:
                    reasons.append(
                        "calendar, late-arrival and overtime indicators do not show "
                        "a clear above-median signal; review leave records and source data"
                    )
                st.markdown(
                    f"**{rank}. {row['month']:%b %Y} — "
                    f"{row['attendance_rate_pct']:.2f}% attendance**"
                )
                st.write("; ".join(reasons))
                st.caption(
                    "These are potential explanations to investigate, "
                    "not proof of causation."
                )

        st.subheader("Three numerical insights")
        lowest = monthly_att.loc[
            monthly_att["attendance_rate_pct"].idxmin()
        ]
        highest_late = monthly_att.loc[
            monthly_att["late_arrivals"].idxmax()
        ]
        highest_ot = monthly_att.loc[
            monthly_att["overtime_hours"].idxmax()
        ]

        st.write(
            f"1. Lowest monthly attendance was "
            f"{lowest['attendance_rate_pct']:.2f}% in "
            f"{lowest['month']:%b %Y}."
        )
        st.write(
            f"2. Highest late-arrival count was "
            f"{int(highest_late['late_arrivals']):,} in "
            f"{highest_late['month']:%b %Y}."
        )
        st.write(
            f"3. Highest recorded overtime was "
            f"{highest_ot['overtime_hours']:,.1f} hours in "
            f"{highest_ot['month']:%b %Y}."
        )

        st.subheader("Monthly attendance data")
        display_att = monthly_att.copy()
        display_att["month"] = display_att["month"].dt.strftime("%b %Y")
        st.dataframe(
            display_att.round(2),
            width="stretch",
            hide_index=True,
        )

# ============================================================
# TASK 7: ATTRITION ANALYTICS
# ============================================================

st.header("Task 7: Attrition Analytics")
st.caption(
    "Actual attrition is shown separately from predicted risk. "
    "Predictions are support signals, not certain outcomes."
)

T7_MIN_GROUP_SIZE = 5


def t7_get(*keys):
    """Return the first available dataframe from the existing data dictionary."""
    for key in keys:
        value = data.get(key)
        if isinstance(value, pd.DataFrame):
            return value.copy()
    return pd.DataFrame()


def t7_date_filter(df, date_column, start_date, end_date):
    if df.empty or date_column not in df.columns:
        return df.copy()

    result = df.copy()
    result[date_column] = pd.to_datetime(
        result[date_column], errors="coerce"
    )
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)

    return result[
        result[date_column].between(start, end + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))
    ].copy()


def t7_department_filter(df, department):
    if df.empty or department == "All departments":
        return df.copy()

    if "department_id" not in df.columns:
        return df.copy()

    return df[
        df["department_id"].astype(str) == str(department)
    ].copy()


# Load metric views and source tables already available in load_data().
t7_exits = t7_get("main.m03_exits", "m03_exits")
t7_monthly_attrition = t7_get(
    "main.m04_monthly_attrition", "m04_monthly_attrition"
)
t7_rolling_attrition = t7_get(
    "main.m05_rolling_12m_attrition", "m05_rolling_12m_attrition"
)
t7_voluntary_attrition = t7_get(
    "main.m06_voluntary_attrition", "m06_voluntary_attrition"
)
t7_headcount = t7_get(
    "raw.fact_headcount_monthly", "fact_headcount_monthly"
)
t7_employees = t7_get("raw.dim_employee", "dim_employee")
t7_risk = t7_get("raw.fact_attrition_risk", "fact_attrition_risk")


# Ensure date fields are usable.
for _df, _cols in [
    (t7_exits, ["month_start_date"]),
    (t7_monthly_attrition, ["month_start_date"]),
    (t7_rolling_attrition, ["month_start_date"]),
    (t7_voluntary_attrition, ["month_start_date"]),
    (t7_headcount, ["month_start_date"]),
    (t7_employees, ["hire_date", "exit_date"]),
    (t7_risk, ["as_of_date"]),
]:
    for _col in _cols:
        if _col in _df.columns:
            _df[_col] = pd.to_datetime(_df[_col], errors="coerce")


# Independent Task 7 filters, so existing dashboard filters remain unchanged.
t7_date_candidates = []
for _df, _col in [
    (t7_exits, "month_start_date"),
    (t7_monthly_attrition, "month_start_date"),
    (t7_employees, "exit_date"),
    (t7_risk, "as_of_date"),
]:
    if not _df.empty and _col in _df.columns:
        t7_date_candidates.extend(_df[_col].dropna().tolist())

if t7_date_candidates:
    t7_min_date = min(pd.Timestamp(x).date() for x in t7_date_candidates)
    t7_max_date = max(pd.Timestamp(x).date() for x in t7_date_candidates)
else:
    t7_min_date = pd.Timestamp("2020-01-01").date()
    t7_max_date = pd.Timestamp.today().date()

with st.expander("Task 7 filters", expanded=True):
    t7_filter_col1, t7_filter_col2 = st.columns(2)

    with t7_filter_col1:
        t7_selected_dates = st.date_input(
            "Attrition date range",
            value=(t7_min_date, t7_max_date),
            min_value=t7_min_date,
            max_value=max(t7_max_date, t7_min_date),
            key="task7_date_range",
        )

    with t7_filter_col2:
        t7_dept_values = set()
        for _df in [
            t7_exits,
            t7_monthly_attrition,
            t7_headcount,
            t7_risk,
        ]:
            if not _df.empty and "department_id" in _df.columns:
                t7_dept_values.update(
                    _df["department_id"].dropna().astype(str).tolist()
                )

        t7_dept_options = ["All departments"] + sorted(t7_dept_values)
        t7_selected_department = st.selectbox(
            "Department",
            t7_dept_options,
            key="task7_department",
        )

if isinstance(t7_selected_dates, (tuple, list)) and len(t7_selected_dates) == 2:
    t7_start_date, t7_end_date = t7_selected_dates
else:
    t7_start_date = t7_min_date
    t7_end_date = t7_max_date

if t7_start_date > t7_end_date:
    st.warning("Choose a valid date range.")
else:
    # ---------------- ACTUAL ATTRITION ----------------
    st.subheader("Actual Attrition")

    t7_exits_f = t7_date_filter(
        t7_exits, "month_start_date", t7_start_date, t7_end_date
    )
    t7_attrition_f = t7_date_filter(
        t7_monthly_attrition,
        "month_start_date",
        t7_start_date,
        t7_end_date,
    )
    t7_rolling_f = t7_date_filter(
        t7_rolling_attrition,
        "month_start_date",
        t7_start_date,
        t7_end_date,
    )
    t7_voluntary_f = t7_date_filter(
        t7_voluntary_attrition,
        "month_start_date",
        t7_start_date,
        t7_end_date,
    )
    t7_headcount_f = t7_date_filter(
        t7_headcount, "month_start_date", t7_start_date, t7_end_date
    )

    t7_exits_f = t7_department_filter(
        t7_exits_f, t7_selected_department
    )
    t7_attrition_f = t7_department_filter(
        t7_attrition_f, t7_selected_department
    )
    t7_rolling_f = t7_department_filter(
        t7_rolling_f, t7_selected_department
    )
    t7_voluntary_f = t7_department_filter(
        t7_voluntary_f, t7_selected_department
    )
    t7_headcount_f = t7_department_filter(
        t7_headcount_f, t7_selected_department
    )

    t7_tab_actual, t7_tab_predicted = st.tabs(
        ["Actual Attrition", "Predicted, not certain"]
    )

    with t7_tab_actual:
        # Monthly exits
        if not t7_exits_f.empty and {
            "month_start_date", "exits"
        }.issubset(t7_exits_f.columns):
            t7_monthly_exits = (
                t7_exits_f.groupby("month_start_date", as_index=False)["exits"]
                .sum()
                .sort_values("month_start_date")
            )
            st.markdown("#### Monthly Exits")
            fig = px.line(
                t7_monthly_exits,
                x="month_start_date",
                y="exits",
                markers=True,
                title="Employees Exiting by Month",
            )
            st.plotly_chart(fig, width='stretch')

            st.markdown("#### Exits by Department")
            if "department_id" in t7_exits_f.columns:
                t7_dept_exits = (
                    t7_exits_f.groupby("department_id", as_index=False)["exits"]
                    .sum()
                    .sort_values("exits", ascending=False)
                )
                fig = px.bar(
                    t7_dept_exits,
                    x="department_id",
                    y="exits",
                    title="Total Exits by Department",
                    labels={
                        "department_id": "Department",
                        "exits": "Exits",
                    },
                )
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("Department-wise exit data is unavailable.")
        else:
            st.info("Monthly exit metric data is unavailable for this selection.")

        # Monthly attrition rate
        st.markdown("#### Monthly Attrition Rate")
        if not t7_attrition_f.empty and {
            "month_start_date", "attrition_pct"
        }.issubset(t7_attrition_f.columns):
            t7_rate = (
                t7_attrition_f.groupby("month_start_date", as_index=False)
                ["attrition_pct"].mean()
                .sort_values("month_start_date")
            )
            fig = px.line(
                t7_rate,
                x="month_start_date",
                y="attrition_pct",
                markers=True,
                title="Monthly Attrition Rate",
                labels={"attrition_pct": "Attrition (%)"},
            )
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("Monthly attrition-rate data is unavailable.")

        # Voluntary vs other exits
        st.markdown("#### Voluntary vs Other Exits")
        if not t7_headcount_f.empty and {
            "exits", "voluntary_exits"
        }.issubset(t7_headcount_f.columns):
            t7_voluntary_counts = pd.to_numeric(
                t7_headcount_f["voluntary_exits"], errors="coerce"
            ).fillna(0).sum()
            t7_total_exits = pd.to_numeric(
                t7_headcount_f["exits"], errors="coerce"
            ).fillna(0).sum()
            t7_other_exits = max(t7_total_exits - t7_voluntary_counts, 0)

            t7_exit_split = pd.DataFrame({
                "Exit Type": ["Voluntary", "Other exits"],
                "Employees": [t7_voluntary_counts, t7_other_exits],
            })
            fig = px.bar(
                t7_exit_split,
                x="Exit Type",
                y="Employees",
                title="Exit Type Breakdown",
            )
            st.plotly_chart(fig, width='stretch')
            st.caption(
                "Other exits are calculated as total exits minus voluntary exits."
            )
        else:
            st.info(
                "Voluntary and total exit counts are unavailable in the selected data."
            )

        # Tenure at exit
        st.markdown("#### Tenure at Exit")
        if not t7_employees.empty and {
            "hire_date", "exit_date"
        }.issubset(t7_employees.columns):
            t7_tenure = t7_employees.copy()
            t7_tenure["hire_date"] = pd.to_datetime(
                t7_tenure["hire_date"], errors="coerce"
            )
            t7_tenure["exit_date"] = pd.to_datetime(
                t7_tenure["exit_date"], errors="coerce"
            )
            t7_tenure = t7_tenure[
                t7_tenure["exit_date"].notna()
                & t7_tenure["hire_date"].notna()
                & t7_tenure["exit_date"].between(
                    pd.Timestamp(t7_start_date),
                    pd.Timestamp(t7_end_date) + pd.Timedelta(days=1)
                    - pd.Timedelta(seconds=1),
                )
            ].copy()
            t7_tenure = t7_department_filter(
                t7_tenure, t7_selected_department
            )
            t7_tenure["tenure_years"] = (
                (t7_tenure["exit_date"] - t7_tenure["hire_date"]).dt.days
                / 365.25
            )
            t7_tenure = t7_tenure[
                t7_tenure["tenure_years"].ge(0)
            ]

            if not t7_tenure.empty:
                if "employee_id" in t7_tenure.columns:
                    t7_tenure = t7_tenure.drop_duplicates(
                        subset=["employee_id"]
                    ).copy()

                t7_median_tenure = t7_tenure["tenure_years"].median()
                t7_mean_tenure = t7_tenure["tenure_years"].mean()

                c1, c2, c3 = st.columns(3)
                c1.metric("Unique employees exited", len(t7_tenure))
                c2.metric("Median tenure", f"{t7_median_tenure:.2f} years")
                c3.metric("Average tenure", f"{t7_mean_tenure:.2f} years")

                fig = px.histogram(
                    t7_tenure,
                    x="tenure_years",
                    nbins=20,
                    title="Tenure Distribution at Exit",
                    labels={"tenure_years": "Tenure (years)"},
                )
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No valid exit-tenure records for this date range.")
        else:
            st.info("Employee hire/exit dates are unavailable for tenure analysis.")

    # ---------------- PREDICTED RISK ----------------
    with t7_tab_predicted:
        st.warning(
            "Predicted, not certain: risk scores are estimates, not confirmed "
            "future exits. They must not be used alone to make HR decisions."
        )

        t7_risk_f = t7_date_filter(
            t7_risk, "as_of_date", t7_start_date, t7_end_date
        )
        t7_risk_f = t7_department_filter(
            t7_risk_f, t7_selected_department
        )

        if not t7_risk_f.empty and {
            "department_id", "risk_score_12m"
        }.issubset(t7_risk_f.columns):
            t7_risk_f["risk_score_12m"] = pd.to_numeric(
                t7_risk_f["risk_score_12m"], errors="coerce"
            )
            t7_risk_f = t7_risk_f.dropna(subset=["risk_score_12m"])

            # Only aggregate group-level risk; never display employee-level rows.
            t7_group_risk = (
                t7_risk_f.groupby("department_id")
                .agg(
                    group_size=("risk_score_12m", "size"),
                    average_risk_score=("risk_score_12m", "mean"),
                )
                .reset_index()
            )
            t7_group_risk = t7_group_risk[
                t7_group_risk["group_size"] >= T7_MIN_GROUP_SIZE
            ]

            if not t7_group_risk.empty:
                st.markdown("#### Average Predicted Risk by Department")
                fig = px.bar(
                    t7_group_risk.sort_values(
                        "average_risk_score", ascending=False
                    ),
                    x="department_id",
                    y="average_risk_score",
                    title="Department-Level Average Risk Score",
                    labels={
                        "department_id": "Department",
                        "average_risk_score": "Average risk score",
                    },
                )
                st.plotly_chart(fig, width='stretch')
                st.dataframe(
                    t7_group_risk.rename(columns={
                        "department_id": "Department",
                        "group_size": "Group size",
                        "average_risk_score": "Average risk score",
                    }).round(3),
                    hide_index=True,
                    width='stretch',
                )
            else:
                st.info(
                    "No department meets the minimum group size of 5 for "
                    "the selected filters. Risk results are suppressed."
                )

            if "risk_band" in t7_risk_f.columns:
                t7_band_counts = (
                    t7_risk_f.groupby(["department_id", "risk_band"])
                    .size()
                    .reset_index(name="count")
                )
                t7_band_counts = t7_band_counts[
                    t7_band_counts["count"] >= T7_MIN_GROUP_SIZE
                ]

                st.markdown("#### Risk Bands (Groups of at Least 5)")
                if not t7_band_counts.empty:
                    fig = px.bar(
                        t7_band_counts,
                        x="department_id",
                        y="count",
                        color="risk_band",
                        barmode="stack",
                        title="Risk Band Counts by Department",
                        labels={
                            "department_id": "Department",
                            "count": "Records",
                            "risk_band": "Risk band",
                        },
                    )
                    st.plotly_chart(fig, width='stretch')
                else:
                    st.info(
                        "Risk-band counts are suppressed because no displayed "
                        "group has at least 5 records."
                    )

            if "model_note" in t7_risk_f.columns:
                t7_model_notes = (
                    t7_risk_f["model_note"].dropna().astype(str).unique().tolist()
                )
                if t7_model_notes:
                    st.caption("Model note: " + " | ".join(t7_model_notes[:2]))
        else:
            st.info("No predicted-risk records are available for this selection.")

        st.markdown("#### What This Prediction Does and Does Not Mean")
        st.markdown(
            "- **Does:** provides an estimated risk signal for review at group level.\n"
            "- **Does not:** prove that an employee will leave or explain the future with certainty.\n"
            "- **Use carefully:** do not make employment decisions from this score alone.\n"
            "- **Privacy:** individual names, employee IDs and individual risk rows are not displayed.\n"
            "- **Small groups:** departments and risk bands with fewer than 5 records are suppressed."
        )

    # ---------------- THREE KEY FINDINGS ----------------
    st.subheader("Three Numerical Findings")

    t7_finding1 = "Not available"
    t7_finding2 = "Not available"
    t7_finding3 = "Not available"

    if not t7_exits_f.empty and "exits" in t7_exits_f.columns:
        t7_total = pd.to_numeric(
            t7_exits_f["exits"], errors="coerce"
        ).fillna(0).sum()
        t7_finding1 = f"{t7_total:,.0f} total exits in the selected period."

    if (
        not t7_employees.empty
        and {"hire_date", "exit_date"}.issubset(t7_employees.columns)
    ):
        t7_finding_employees = t7_employees.copy()
        t7_finding_employees["hire_date"] = pd.to_datetime(
            t7_finding_employees["hire_date"], errors="coerce"
        )
        t7_finding_employees["exit_date"] = pd.to_datetime(
            t7_finding_employees["exit_date"], errors="coerce"
        )
        t7_finding_employees = t7_finding_employees[
            t7_finding_employees["exit_date"].between(
                pd.Timestamp(t7_start_date),
                pd.Timestamp(t7_end_date) + pd.Timedelta(days=1)
                - pd.Timedelta(seconds=1),
            )
            & t7_finding_employees["hire_date"].notna()
        ].copy()
        t7_finding_employees = t7_department_filter(
            t7_finding_employees, t7_selected_department
        )
        t7_finding_employees["tenure_years"] = (
            (t7_finding_employees["exit_date"]
             - t7_finding_employees["hire_date"]).dt.days / 365.25
        )
        t7_finding_employees = t7_finding_employees[
            t7_finding_employees["tenure_years"].ge(0)
        ]
        if "employee_id" in t7_finding_employees.columns:
            t7_finding_employees = t7_finding_employees.drop_duplicates(
                subset=["employee_id"]
            )
        if not t7_finding_employees.empty:
            t7_finding2 = (
                f"Median tenure at exit was "
                f"{t7_finding_employees['tenure_years'].median():.2f} years."
            )

    if (
        not t7_exits_f.empty
        and {"department_id", "exits"}.issubset(t7_exits_f.columns)
    ):
        t7_top_department = (
            t7_exits_f.groupby("department_id")["exits"]
            .sum()
            .sort_values(ascending=False)
        )
        if not t7_top_department.empty:
            t7_finding3 = (
                f"Department {t7_top_department.index[0]} had the highest "
                f"number of exits: {t7_top_department.iloc[0]:,.0f}."
            )

    st.markdown(f"1. {t7_finding1}")
    st.markdown(f"2. {t7_finding2}")
    st.markdown(f"3. {t7_finding3}")

    st.caption(
        "Findings change with the selected date range and department. "
        "Predicted risk is shown separately from actual exits."
    )

# ============================================================
# END TASK 7
# ============================================================


