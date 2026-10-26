
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st


# --------------------------------------------------
# Configuration
# --------------------------------------------------
DB_PATH = Path(__file__).parent / "pulseiq.duckdb"

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

            if (
                name.startswith("m")
                or (
                    schema == "raw"
                    and name in {
                        "fact_leave",
                        "fact_attendance_monthly",
                        "dim_date",
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
    """Select a metric column without charting group_size."""
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

    if department != "All departments" and "department_id" in result.columns:
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

    frame[date_column] = pd.to_datetime(
        frame[date_column], errors="coerce"
    )
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
        aggregation = "mean" if metric_column.endswith("_pct") else "sum"
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


def as_bool(series):
    """Convert common database boolean representations to True/False."""
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .isin(["true", "1", "yes", "y"])
    )


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
    "Department",
    department_options,
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
    (view, title)
    for view, title in overview_views
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
        "See Metric View Availability below for available views."
    )


# --------------------------------------------------
# Attendance and punctuality
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
# Overtime and leave
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

        if (
            selected_department != "All departments"
            and "department_id" in approved_leave.columns
        ):
            approved_leave = approved_leave[
                approved_leave["department_id"].astype(str)
                == selected_department
            ]

        leave_summary = (
            approved_leave.groupby("leave_type_code", as_index=False)
            .agg(leave_days=("days", "sum"))
            .sort_values("leave_days", ascending=False)
        )

        if leave_summary.empty:
            st.info("No approved leave requests in the selected date range.")
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
            st.dataframe(leave_summary, width="stretch", hide_index=True)


# --------------------------------------------------
# Task 6: Monthly attendance and calendar analysis
# --------------------------------------------------
st.header("Task 6: Attendance & Calendar Analysis")

attendance_df = get_table("fact_attendance_monthly")
calendar_df = get_table("dim_date")
leave_task_df = get_table("fact_leave")

if attendance_df.empty:
    st.warning(
        "Task 6 requires raw.fact_attendance_monthly. "
        "Check that the table exists in pulseiq.duckdb."
    )
else:
    required_attendance = {
        "period_end_date",
        "department_id",
        "scheduled_days",
        "present_days",
    }
    missing_columns = required_attendance - set(attendance_df.columns)

    if missing_columns:
        st.warning(
            "Task 6 cannot calculate attendance. Missing columns: "
            + ", ".join(sorted(missing_columns))
        )
    else:
        task_att = attendance_df.copy()
        task_att["period_end_date"] = pd.to_datetime(
            task_att["period_end_date"], errors="coerce"
        )
        task_att = task_att.dropna(subset=["period_end_date"])

        task_att = task_att[
            task_att["period_end_date"].dt.date.between(
                start_date, end_date
            )
        ].copy()

        if selected_department != "All departments":
            task_att = task_att[
                task_att["department_id"].astype(str)
                == selected_department
            ]

        for column in [
            "scheduled_days",
            "present_days",
            "late_arrivals",
            "overtime_hours",
        ]:
            if column in task_att.columns:
                task_att[column] = pd.to_numeric(
                    task_att[column], errors="coerce"
                ).fillna(0)

        if task_att.empty:
            st.info("No attendance records match the selected filters.")
        else:
            # Weighted monthly rate: total present days / total scheduled days.
            monthly_aggregations = {
                "scheduled_days": ("scheduled_days", "sum"),
                "present_days": ("present_days", "sum"),
            }

            if "late_arrivals" in task_att.columns:
                monthly_aggregations["late_arrivals"] = (
                    "late_arrivals", "sum"
                )

            if "overtime_hours" in task_att.columns:
                monthly_aggregations["overtime_hours"] = (
                    "overtime_hours", "sum"
                )

            monthly_att = (
                task_att.groupby("period_end_date", as_index=False)
                .agg(**monthly_aggregations)
                .sort_values("period_end_date")
            )

            monthly_att["attendance_rate_pct"] = (
                100 * monthly_att["present_days"]
                / monthly_att["scheduled_days"].replace(0, float("nan"))
            )

            # Monthly attendance rate.
            st.subheader("Monthly Attendance Rate")

            fig_att = px.line(
                monthly_att,
                x="period_end_date",
                y="attendance_rate_pct",
                markers=True,
                title="Weighted Attendance Rate by Month",
                labels={
                    "period_end_date": "Month",
                    "attendance_rate_pct": "Attendance Rate (%)",
                },
            )
            st.plotly_chart(fig_att, width="stretch")

            # Late arrivals.
            if "late_arrivals" in monthly_att.columns:
                st.subheader("Late Arrivals by Month")

                fig_late = px.bar(
                    monthly_att,
                    x="period_end_date",
                    y="late_arrivals",
                    title="Total Late Arrivals by Month",
                    labels={
                        "period_end_date": "Month",
                        "late_arrivals": "Late Arrivals",
                    },
                )
                st.plotly_chart(fig_late, width="stretch")

            # Overtime hours.
            if "overtime_hours" in monthly_att.columns:
                st.subheader("Overtime Hours by Month")

                fig_ot = px.bar(
                    monthly_att,
                    x="period_end_date",
                    y="overtime_hours",
                    title="Total Recorded Overtime Hours by Month",
                    labels={
                        "period_end_date": "Month",
                        "overtime_hours": "Overtime Hours",
                    },
                )
                st.plotly_chart(fig_ot, width="stretch")

            # Department comparison.
            st.subheader("Attendance by Department")

            dept_monthly = (
                task_att.groupby(
                    ["period_end_date", "department_id"], as_index=False
                )
                .agg(
                    scheduled_days=("scheduled_days", "sum"),
                    present_days=("present_days", "sum"),
                )
            )

            dept_monthly["attendance_rate_pct"] = (
                100 * dept_monthly["present_days"]
                / dept_monthly["scheduled_days"].replace(0, float("nan"))
            )

            fig_dept = px.line(
                dept_monthly,
                x="period_end_date",
                y="attendance_rate_pct",
                color="department_id",
                markers=True,
                title="Weighted Monthly Attendance by Department",
                labels={
                    "period_end_date": "Month",
                    "attendance_rate_pct": "Attendance Rate (%)",
                    "department_id": "Department",
                },
            )
            st.plotly_chart(fig_dept, width="stretch")

            # --------------------------------------------------
            # Holiday and long-weekend calendar context
            # --------------------------------------------------
            st.subheader("Holiday and Long-Weekend Context")

            calendar_monthly = pd.DataFrame(
                columns=["month", "holiday_days", "long_weekend_days"]
            )

            if not calendar_df.empty and "date" in calendar_df.columns:
                cal = calendar_df.copy()
                cal["date"] = pd.to_datetime(
                    cal["date"], errors="coerce"
                )
                cal = cal.dropna(subset=["date"]).sort_values("date")

                if "is_holiday" in cal.columns:
                    cal["_holiday"] = as_bool(cal["is_holiday"])
                else:
                    cal["_holiday"] = False

                if "is_weekend" in cal.columns:
                    cal["_weekend"] = as_bool(cal["is_weekend"])
                else:
                    cal["_weekend"] = cal["date"].dt.dayofweek >= 5

                if "is_working_day" in cal.columns:
                    cal["_working"] = as_bool(cal["is_working_day"])
                else:
                    cal["_working"] = ~(
                        cal["_holiday"] | cal["_weekend"]
                    )

                cal["_long_weekend"] = False

                # Identify non-working runs of at least three days
                # that contain a holiday.
                nonwork = cal.loc[~cal["_working"]].copy()

                if not nonwork.empty:
                    nonwork["_run"] = (
                        nonwork["date"].diff().dt.days.ne(1)
                    ).cumsum()

                    for _, run in nonwork.groupby("_run"):
                        if len(run) >= 3 and run["_holiday"].any():
                            cal.loc[
                                cal["date"].isin(run["date"]),
                                "_long_weekend",
                            ] = True

                cal = cal[
                    cal["date"].dt.date.between(start_date, end_date)
                ].copy()

                cal["month"] = cal["date"].dt.to_period("M").astype(str)

                calendar_monthly = (
                    cal.groupby("month", as_index=False)
                    .agg(
                        holiday_days=("_holiday", "sum"),
                        long_weekend_days=("_long_weekend", "sum"),
                    )
                )

                if not calendar_monthly.empty:
                    st.dataframe(
                        calendar_monthly,
                        width="stretch",
                        hide_index=True,
                    )

                    fig_calendar = px.bar(
                        calendar_monthly,
                        x="month",
                        y=["holiday_days", "long_weekend_days"],
                        barmode="group",
                        title="Holiday and Long-Weekend Days by Month",
                        labels={
                            "month": "Month",
                            "value": "Calendar Days",
                            "variable": "Calendar Context",
                        },
                    )
                    st.plotly_chart(fig_calendar, width="stretch")
            else:
                st.info(
                    "raw.dim_date was not found or has no date column. "
                    "Calendar context is unavailable."
                )

            # --------------------------------------------------
            # Monthly approved leave patterns
            # --------------------------------------------------
            st.subheader("Monthly Leave Patterns")

            if leave_task_df.empty:
                st.info("raw.fact_leave was not found.")
            elif not {
                "start_date", "leave_type_code", "days", "status"
            }.issubset(leave_task_df.columns):
                st.warning(
                    "Monthly leave analysis requires start_date, "
                    "leave_type_code, days and status columns."
                )
            else:
                task_leave = leave_task_df.copy()
                task_leave["start_date"] = pd.to_datetime(
                    task_leave["start_date"], errors="coerce"
                )
                task_leave["days"] = pd.to_numeric(
                    task_leave["days"], errors="coerce"
                ).fillna(0)

                task_leave = task_leave[
                    task_leave["status"].astype(str).str.strip().str.lower()
                    == "approved"
                ].copy()

                task_leave = task_leave.dropna(subset=["start_date"])
                task_leave = task_leave[
                    task_leave["start_date"].dt.date.between(
                        start_date, end_date
                    )
                ].copy()

                # Add a department mapping if the leave table has no
                # department_id but employee IDs are available.
                if (
                    selected_department != "All departments"
                    and "department_id" not in task_leave.columns
                    and "employee_id" in task_leave.columns
                    and "employee_id" in attendance_df.columns
                ):
                    emp_dept = attendance_df[
                        ["employee_id", "department_id"]
                    ].dropna().copy()

                    emp_dept["employee_id"] = emp_dept[
                        "employee_id"
                    ].astype(str)
                    emp_dept["department_id"] = emp_dept[
                        "department_id"
                    ].astype(str)

                    emp_dept = (
                        emp_dept.groupby(["employee_id", "department_id"])
                        .size()
                        .reset_index(name="records")
                        .sort_values("records", ascending=False)
                        .drop_duplicates("employee_id")
                    )

                    task_leave["employee_id"] = task_leave[
                        "employee_id"
                    ].astype(str)

                    task_leave = task_leave.merge(
                        emp_dept[["employee_id", "department_id"]],
                        on="employee_id",
                        how="left",
                    )

                if (
                    selected_department != "All departments"
                    and "department_id" in task_leave.columns
                ):
                    task_leave = task_leave[
                        task_leave["department_id"].astype(str)
                        == selected_department
                    ]
                elif (
                    selected_department != "All departments"
                    and "department_id" not in task_leave.columns
                ):
                    st.warning(
                        "Department filtering is unavailable for leave "
                        "because employee-to-department mapping is missing."
                    )

                task_leave["month"] = (
                    task_leave["start_date"].dt.to_period("M").astype(str)
                )

                leave_monthly = (
                    task_leave.groupby(
                        ["month", "leave_type_code"], as_index=False
                    )
                    .agg(approved_leave_days=("days", "sum"))
                )

                if leave_monthly.empty:
                    st.info("No approved leave records match these filters.")
                else:
                    fig_leave_monthly = px.bar(
                        leave_monthly,
                        x="month",
                        y="approved_leave_days",
                        color="leave_type_code",
                        barmode="stack",
                        title="Approved Leave Days by Month and Leave Type",
                        labels={
                            "month": "Month",
                            "approved_leave_days": "Approved Leave Days",
                            "leave_type_code": "Leave Type",
                        },
                    )
                    st.plotly_chart(
                        fig_leave_monthly, width="stretch"
                    )
                    st.dataframe(
                        leave_monthly,
                        width="stretch",
                        hide_index=True,
                    )

            # --------------------------------------------------
            # Three unusual months
            # --------------------------------------------------
            st.subheader("Three Unusual Attendance Months")
            st.caption(
                "These are data-based flags. Possible causes are "
                "hypotheses to investigate, not confirmed explanations."
            )

            valid_months = monthly_att.dropna(
                subset=["attendance_rate_pct"]
            )

            unusual = valid_months.nsmallest(
                min(3, len(valid_months)), "attendance_rate_pct"
            ).copy()

            calendar_lookup = {}

            if not calendar_monthly.empty:
                calendar_lookup = calendar_monthly.set_index(
                    "month"
                ).to_dict("index")

            if unusual.empty:
                st.info("There are not enough valid monthly records.")
            else:
                median_att = monthly_att["attendance_rate_pct"].median()

                median_late = (
                    monthly_att["late_arrivals"].median()
                    if "late_arrivals" in monthly_att.columns
                    else None
                )

                median_ot = (
                    monthly_att["overtime_hours"].median()
                    if "overtime_hours" in monthly_att.columns
                    else None
                )

                unusual_rows = []

                for _, row in unusual.iterrows():
                    month_label = row["period_end_date"].strftime("%Y-%m")
                    possible_causes = []

                    if row["attendance_rate_pct"] < median_att:
                        possible_causes.append(
                            "Attendance below selected-period median"
                        )

                    if (
                        median_late is not None
                        and row["late_arrivals"] > median_late
                    ):
                        possible_causes.append(
                            "Late arrivals above selected-period median"
                        )

                    if (
                        median_ot is not None
                        and row["overtime_hours"] > median_ot
                    ):
                        possible_causes.append(
                            "Overtime above selected-period median"
                        )

                    cal_info = calendar_lookup.get(month_label, {})

                    if cal_info.get("holiday_days", 0) > 0:
                        possible_causes.append(
                            "Holiday timing may be relevant"
                        )

                    if cal_info.get("long_weekend_days", 0) > 0:
                        possible_causes.append(
                            "Long-weekend timing may be relevant"
                        )

                    if not possible_causes:
                        possible_causes.append(
                            "Investigate staffing, schedules and "
                            "department-level changes"
                        )

                    unusual_rows.append({
                        "Month": month_label,
                        "Attendance Rate (%)": round(
                            row["attendance_rate_pct"], 2
                        ),
                        "Scheduled Days": int(row["scheduled_days"]),
                        "Present Days": int(row["present_days"]),
                        "Possible Cause (Hypothesis)": "; ".join(
                            possible_causes
                        ),
                    })

                st.dataframe(
                    pd.DataFrame(unusual_rows),
                    width="stretch",
                    hide_index=True,
                )

            # --------------------------------------------------
            # Three numerical insights
            # --------------------------------------------------
            st.subheader("Three Numerical Insights")

            lowest = valid_months.loc[
                valid_months["attendance_rate_pct"].idxmin()
            ]

            st.write(
                f"1. Lowest attendance was "
                f"{lowest['attendance_rate_pct']:.2f}% in "
                f"{lowest['period_end_date']:%Y-%m}, based on "
                f"{int(lowest['scheduled_days']):,} scheduled days."
            )

            if "late_arrivals" in monthly_att.columns:
                peak_late = monthly_att.loc[
                    monthly_att["late_arrivals"].idxmax()
                ]
                st.write(
                    f"2. Highest recorded late-arrival count was "
                    f"{int(peak_late['late_arrivals']):,} in "
                    f"{peak_late['period_end_date']:%Y-%m}."
                )
            else:
                st.write(
                    "2. Late-arrival totals are unavailable because "
                    "the source has no late_arrivals column."
                )

            if "overtime_hours" in monthly_att.columns:
                peak_ot = monthly_att.loc[
                    monthly_att["overtime_hours"].idxmax()
                ]
                st.write(
                    f"3. Highest recorded overtime was "
                    f"{peak_ot['overtime_hours']:,.1f} hours in "
                    f"{peak_ot['period_end_date']:%Y-%m}."
                )
            else:
                st.write(
                    "3. Overtime totals are unavailable because "
                    "the source has no overtime_hours column."
                )

            st.subheader("Monthly Attendance Data")
            st.dataframe(
                monthly_att.round(2),
                width="stretch",
                hide_index=True,
            )


# --------------------------------------------------
# Workforce breakdown
# --------------------------------------------------
st.header("Workforce Breakdown")

location_df = get_table("m29_headcount_by_location_tier")

if not location_df.empty:
    st.subheader("Headcount by Location Tier")
    st.dataframe(location_df, width="stretch", hide_index=True)

    numeric = get_metric_column(
        location_df, "m29_headcount_by_location_tier"
    )
    dimensions = [
        column for column in location_df.columns
        if column != numeric
        and not pd.api.types.is_numeric_dtype(location_df[column])
    ]

    if numeric and dimensions:
        fig_location = px.bar(
            location_df,
            x=dimensions[0],
            y=numeric,
            title="Headcount by Location Tier",
        )
        st.plotly_chart(fig_location, width="stretch")


work_mode_df = get_table("m30_headcount_by_work_mode")

if not work_mode_df.empty:
    st.subheader("Headcount by Work Mode")
    st.dataframe(work_mode_df, width="stretch", hide_index=True)

    numeric = get_metric_column(
        work_mode_df, "m30_headcount_by_work_mode"
    )
    dimensions = [
        column for column in work_mode_df.columns
        if column != numeric
        and not pd.api.types.is_numeric_dtype(work_mode_df[column])
    ]

    if numeric and dimensions:
        fig_mode = px.bar(
            work_mode_df,
            x=dimensions[0],
            y=numeric,
            title="Headcount by Work Mode",
        )
        st.plotly_chart(fig_mode, width="stretch")


# --------------------------------------------------
# Other available dated metric views
# --------------------------------------------------
st.header("Additional Metric Trends")

known_views = {
    "m01_headcount_monthly",
    "m02_hires",
    "m03_exits",
    "m04_attrition_rate",
    "m11_overtime_share",
    "m13_attendance_rate",
    "m14_late_arrival_rate",
    "m15_lop_days",
    "m29_headcount_by_location_tier",
    "m30_headcount_by_work_mode",
    "metric_catalog",
    "fact_leave",
    "fact_attendance_monthly",
    "dim_date",
}

for key, frame in data.items():
    view_name = key.split(".")[-1]

    if view_name in known_views or frame.empty:
        continue

    if get_date_column(frame) is not None:
        st.subheader(view_name.replace("_", " ").title())
        draw_metric_chart(
            view_name,
            view_name.replace("_", " ").title(),
            start_date,
            end_date,
            selected_department,
        )


# --------------------------------------------------
# Metric view availability
# --------------------------------------------------
st.header("Metric View Availability")

availability_rows = []

for key, frame in sorted(data.items()):
    availability_rows.append({
        "View / Table": key,
        "Rows": len(frame),
        "Columns": ", ".join(map(str, frame.columns)),
        "Status": "Available" if not frame.empty else "Empty",
    })

if availability_rows:
    st.dataframe(
        pd.DataFrame(availability_rows),
        width="stretch",
        hide_index=True,
    )
else:
    st.warning("No metric views or required raw tables were loaded.")

st.caption(
    "Note: Department filtering applies to views containing "
    "department_id. Approved leave uses leave start date. Task 6 "
    "attendance is calculated as total present days divided by "
    "total scheduled days."
)
