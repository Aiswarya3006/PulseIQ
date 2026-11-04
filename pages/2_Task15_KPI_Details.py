from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(
    page_title="PulseIQ | KPI Details",
    page_icon="📈",
    layout="wide"
)

st.title("PulseIQ | KPI Detail Explorer")
st.caption("Task 15 — Metric-level details and historical trends")

DB_PATH = Path(__file__).resolve().parent.parent / "pulseiq.duckdb"

if not DB_PATH.exists():
    st.error(f"Database not found: {DB_PATH}")
    st.stop()

METRICS = {
    "M01": ("Workforce headcount", "m01_headcount", "month_start_date", "headcount", "count", "Department"),
    "M04": ("Monthly attrition", "m04_monthly_attrition", "month_start_date", "attrition_pct", "percent", "Department"),
    "M09": ("Employer cost", "m09_employer_cost", "period_end_date", "employer_cost", "INR", "Department"),
    "M11": ("Overtime share", "m11_overtime_share", "period_end_date", "overtime_share_pct", "percent", "Department"),
    "M13": ("Attendance rate", "m13_attendance_rate", "period_end_date", "attendance_rate_pct", "percent", "Department"),
    "M16": ("Revenue", "m16_revenue", "month_start_date", "revenue", "INR", "Account"),
    "M17": ("Net profit", "m17_net_profit", "month_start_date", "net_profit", "INR", "Company"),
    "M18": ("Operating margin", "m18_operating_margin", "month_start_date", "operating_margin_pct", "percent", "Company"),
}

metric_id = st.query_params.get("metric", "M01")
if metric_id not in METRICS:
    metric_id = "M01"

metric_options = list(METRICS.keys())
metric_id = st.selectbox(
    "Choose KPI",
    metric_options,
    index=metric_options.index(metric_id),
    format_func=lambda key: f"{key} — {METRICS[key][0]}"
)

name, view, date_col, value_col, unit, grouping = METRICS[metric_id]

@st.cache_data
def load_metric(database_path, modified_time, view_name):
    con = duckdb.connect(database_path, read_only=True)
    try:
        return con.execute(
            f"SELECT * FROM {view_name} ORDER BY 1"
        ).fetchdf()
    finally:
        con.close()

df = load_metric(str(DB_PATH), DB_PATH.stat().st_mtime, view)
df[date_col] = pd.to_datetime(df[date_col])
df["report_month"] = df[date_col].dt.to_period("M").dt.to_timestamp()

months = sorted(df["report_month"].dropna().unique())
if not months:
    st.warning("No data is available for this KPI.")
    st.stop()

month_labels = [pd.Timestamp(m).strftime("%B %Y") for m in months]
selected_label = st.selectbox(
    "Reporting month",
    month_labels,
    index=len(months) - 1
)
selected_month = pd.Timestamp(months[month_labels.index(selected_label)])

current = df[df["report_month"] == selected_month].copy()

st.divider()
st.subheader(f"{metric_id} — {name}")
st.caption(f"Source metric view: {view}")

if unit == "INR":
    total = pd.to_numeric(current[value_col], errors="coerce").sum()
    display_value = f"₹{total:,.2f}"
elif unit == "count":
    total = pd.to_numeric(current[value_col], errors="coerce").sum()
    display_value = f"{total:,.0f}"
else:
    values = pd.to_numeric(current[value_col], errors="coerce").dropna()
    total = float(values.median()) if not values.empty else None
    display_value = f"{total:.2f}%" if total is not None else "N/A"

st.metric("Selected month KPI", display_value)

# Monthly historical trend
if grouping == "Department":
    trend = (
        df.groupby("report_month")[value_col]
        .median()
        .reset_index()
    )
    trend_note = "Median of reportable department values."
elif grouping == "Account":
    trend = (
        df.groupby("report_month")[value_col]
        .sum()
        .reset_index()
    )
    trend_note = "Sum across account rows."
else:
    trend = (
        df.groupby("report_month")[value_col]
        .sum()
        .reset_index()
    )
    trend_note = "Company-level metric view."

fig = px.line(
    trend,
    x="report_month",
    y=value_col,
    markers=True,
    title=f"{name} — Monthly trend"
)
fig.update_layout(
    xaxis_title="Month",
    yaxis_title=unit,
    height=400
)
st.plotly_chart(fig, width="stretch")
st.caption(trend_note)

# Selected month source rows
st.subheader(f"{selected_label} — Source detail")
st.dataframe(
    current.drop(columns=["report_month"]),
    width="stretch",
    hide_index=True
)

# Department target comparison
target_map = {
    "M04": ("attrition_monthly_target_pct", "Lower is better"),
    "M11": ("overtime_share_target_pct", "Lower is better"),
    "M13": ("attendance_rate_target", "Higher is better"),
}

if metric_id in target_map:
    target_col, direction = target_map[metric_id]
    con = duckdb.connect(str(DB_PATH), read_only=True)
    targets = con.execute(
        """
        SELECT *
        FROM raw.kpi_targets
        WHERE month = ?
        ORDER BY department_id
        """,
        [selected_month.date()]
    ).fetchdf()
    con.close()

    if not targets.empty and "department_id" in current.columns:
        comparison = current.merge(
            targets[["department_id", target_col]],
            on="department_id",
            how="left"
        )
        comparison[value_col] = pd.to_numeric(
            comparison[value_col], errors="coerce"
        )
        comparison[target_col] = pd.to_numeric(
            comparison[target_col], errors="coerce"
        )
        if metric_id == "M13":
            comparison[target_col] = comparison[target_col] * 100

        comparison = comparison.dropna(
            subset=[value_col, target_col]
        )

        if direction == "Higher is better":
            comparison["Target status"] = comparison.apply(
                lambda row: "Met" if row[value_col] >= row[target_col] else "Below target",
                axis=1
            )
        else:
            comparison["Target status"] = comparison.apply(
                lambda row: "Met" if row[value_col] <= row[target_col] else "Above target",
                axis=1
            )

        st.subheader("Department target comparison")
        st.dataframe(
            comparison[
                ["department_id", value_col, target_col, "Target status"]
            ],
            width="stretch",
            hide_index=True
        )

st.caption(
    "Source values are read from the approved metric views. "
    "Suppressed or null values are not treated as zero."
)
