
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------
st.set_page_config(
    page_title="PulseIQ | Executive Health Scorecard",
    page_icon="📊",
    layout="wide"
)

DB_PATH = Path(__file__).resolve().parent / "pulseiq.duckdb"

st.title("PulseIQ | Executive Company-Health Scorecard")
st.caption("Task 15 | Monthly executive KPI scorecard")


# --------------------------------------------------
# DATABASE CHECK
# --------------------------------------------------
if not DB_PATH.exists():
    st.error(f"Database not found: {DB_PATH}")
    st.stop()


# --------------------------------------------------
# LOAD APPROVED METRIC VIEWS
# --------------------------------------------------
@st.cache_data
def load_data(database_path, modified_time):
    con = duckdb.connect(database_path, read_only=True)

    try:
        queries = {
            "headcount": "SELECT * FROM m01_headcount",
            "attrition": "SELECT * FROM m04_monthly_attrition",
            "cost": "SELECT * FROM m09_employer_cost",
            "overtime": "SELECT * FROM m11_overtime_share",
            "attendance": "SELECT * FROM m13_attendance_rate",
            "revenue": "SELECT * FROM m16_revenue",
            "profit": "SELECT * FROM m17_net_profit",
            "margin": "SELECT * FROM m18_operating_margin",
            "targets": "SELECT * FROM raw.kpi_targets"
        }

        return {
            name: con.execute(query).fetchdf()
            for name, query in queries.items()
        }

    finally:
        con.close()


data = load_data(
    str(DB_PATH),
    DB_PATH.stat().st_mtime
)


# --------------------------------------------------
# MONTH SELECTOR
# --------------------------------------------------
months = sorted(
    pd.to_datetime(
        data["profit"]["month_start_date"]
    ).dropna().unique()
)

if not months:
    st.error("No monthly metric data found.")
    st.stop()

month_labels = [
    pd.Timestamp(month).strftime("%B %Y")
    for month in months
]

selected_label = st.selectbox(
    "Select reporting month",
    month_labels,
    index=len(month_labels) - 1
)

selected_month = pd.Timestamp(
    months[month_labels.index(selected_label)]
)

previous_month = selected_month - pd.DateOffset(months=1)


# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------
def month_rows(frame, date_column, month):
    dates = pd.to_datetime(frame[date_column])

    return frame[
        dates.dt.to_period("M") == month.to_period("M")
    ].copy()


def numeric_values(frame, column):
    return pd.to_numeric(
        frame[column],
        errors="coerce"
    ).dropna()


def aggregate_value(frame, column, aggregation="sum"):
    values = numeric_values(frame, column)

    if values.empty:
        return None

    if aggregation == "median":
        return float(values.median())

    return float(values.sum())


def previous_value(
    frame,
    date_column,
    value_column,
    month,
    aggregation="sum"
):
    rows = month_rows(frame, date_column, month)

    return aggregate_value(
        rows,
        value_column,
        aggregation
    )


def trend_text(current, previous, unit=""):
    if current is None or previous is None:
        return None

    difference = current - previous

    if unit == "currency":
        return f"₹{difference:+,.0f} vs previous month"

    if unit == "count":
        return f"{difference:+,.0f} vs previous month"

    return f"{difference:+.2f} pp vs previous month"


def department_compliance(
    frame,
    date_column,
    value_column,
    target_column,
    month,
    direction,
    target_multiplier=1.0
):
    actual = month_rows(
        frame,
        date_column,
        month
    )

    targets = data["targets"].copy()
    targets["month"] = pd.to_datetime(targets["month"])

    targets = targets[
        targets["month"].dt.to_period("M")
        == month.to_period("M")
    ]

    if actual.empty or targets.empty:
        return "No target data"

    comparison = actual.merge(
        targets[["department_id", target_column]],
        on="department_id",
        how="inner"
    )

    comparison[value_column] = pd.to_numeric(
        comparison[value_column],
        errors="coerce"
    )

    comparison[target_column] = pd.to_numeric(
        comparison[target_column],
        errors="coerce"
    ) * target_multiplier

    comparison = comparison.dropna(
        subset=[value_column, target_column]
    )

    if comparison.empty:
        return "No reportable departments"

    if direction == "higher":
        met = (
            comparison[value_column]
            >= comparison[target_column]
        )
    else:
        met = (
            comparison[value_column]
            <= comparison[target_column]
        )

    return (
        f"{int(met.sum())}/{len(comparison)} "
        "departments meet target"
    )


def display_card(
    title,
    metric_id,
    value,
    delta,
    target,
    status
):
    with st.container(border=True):
        st.markdown(f"**{title}**")

        st.metric(
            label=metric_id,
            value=value,
            delta=delta,
            delta_color="off"
        )

        st.caption(f"Target: {target}")
        st.caption(f"Status: {status}")

        st.page_link(
            "pages/2_Task15_KPI_Details.py",
            label="View KPI details →",
            query_params={"metric": metric_id}
        )


# --------------------------------------------------
# SELECTED MONTH DATA
# --------------------------------------------------
hc = month_rows(
    data["headcount"],
    "month_start_date",
    selected_month
)

attr = month_rows(
    data["attrition"],
    "month_start_date",
    selected_month
)

cost = month_rows(
    data["cost"],
    "period_end_date",
    selected_month
)

ot = month_rows(
    data["overtime"],
    "period_end_date",
    selected_month
)

att = month_rows(
    data["attendance"],
    "period_end_date",
    selected_month
)

rev = month_rows(
    data["revenue"],
    "month_start_date",
    selected_month
)

profit = month_rows(
    data["profit"],
    "month_start_date",
    selected_month
)

margin = month_rows(
    data["margin"],
    "month_start_date",
    selected_month
)


# --------------------------------------------------
# KPI CALCULATIONS
# --------------------------------------------------

# M01: Sum of reportable department headcounts
headcount_value = aggregate_value(
    hc,
    "headcount"
)

# M04: Median of reportable department attrition rates
attr_value = aggregate_value(
    attr,
    "attrition_pct",
    "median"
)

# M09: Sum of reportable department employer costs
cost_value = aggregate_value(
    cost,
    "employer_cost"
)

# M11: Median of reportable department overtime rates
ot_value = aggregate_value(
    ot,
    "overtime_share_pct",
    "median"
)

# M13: Median of reportable department attendance rates
att_value = aggregate_value(
    att,
    "attendance_rate_pct",
    "median"
)

# M16: Sum of account-level revenue rows
revenue_value = aggregate_value(
    rev,
    "revenue"
)

# M17: Company-level net profit
profit_value = aggregate_value(
    profit,
    "net_profit"
)

# M18: Company-level operating margin
margin_value = aggregate_value(
    margin,
    "operating_margin_pct"
)


# --------------------------------------------------
# PREVIOUS MONTH VALUES
# --------------------------------------------------
prev_hc = previous_value(
    data["headcount"],
    "month_start_date",
    "headcount",
    previous_month
)

prev_attr = previous_value(
    data["attrition"],
    "month_start_date",
    "attrition_pct",
    previous_month,
    "median"
)

prev_cost = previous_value(
    data["cost"],
    "period_end_date",
    "employer_cost",
    previous_month
)

prev_ot = previous_value(
    data["overtime"],
    "period_end_date",
    "overtime_share_pct",
    previous_month,
    "median"
)

prev_att = previous_value(
    data["attendance"],
    "period_end_date",
    "attendance_rate_pct",
    previous_month,
    "median"
)

prev_rev = previous_value(
    data["revenue"],
    "month_start_date",
    "revenue",
    previous_month
)

prev_profit = previous_value(
    data["profit"],
    "month_start_date",
    "net_profit",
    previous_month
)

prev_margin = previous_value(
    data["margin"],
    "month_start_date",
    "operating_margin_pct",
    previous_month
)


# --------------------------------------------------
# DEPARTMENT TARGET COMPLIANCE
# --------------------------------------------------
attr_status = department_compliance(
    data["attrition"],
    "month_start_date",
    "attrition_pct",
    "attrition_monthly_target_pct",
    selected_month,
    "lower"
)

ot_status = department_compliance(
    data["overtime"],
    "period_end_date",
    "overtime_share_pct",
    "overtime_share_target_pct",
    selected_month,
    "lower"
)

att_status = department_compliance(
    data["attendance"],
    "period_end_date",
    "attendance_rate_pct",
    "attendance_rate_target",
    selected_month,
    "higher",
    100
)


# --------------------------------------------------
# DISPLAY FORMATTING
# --------------------------------------------------
def format_number(value, decimals=0):
    if value is None:
        return "N/A"

    return f"{value:,.{decimals}f}"


def format_currency(value):
    if value is None:
        return "N/A"

    return f"₹{value:,.0f}"


# --------------------------------------------------
# EXECUTIVE SCORECARD
# --------------------------------------------------
st.divider()

st.subheader(
    f"Executive KPI Scorecard — {selected_label}"
)

st.caption(
    "Department-level rates are shown as the median of "
    "reportable department rates. Target status shows "
    "department compliance, not a weighted company-wide rate."
)


cards = [
    (
        "Workforce headcount",
        "M01",
        format_number(headcount_value),
        trend_text(headcount_value, prev_hc, "count"),
        "No target configured",
        "No target configured"
    ),
    (
        "Monthly attrition",
        "M04",
        (
            f"{attr_value:.2f}%"
            if attr_value is not None else "N/A"
        ),
        trend_text(attr_value, prev_attr),
        "1.00% per department",
        attr_status
    ),
    (
        "Employer cost",
        "M09",
        format_currency(cost_value),
        trend_text(cost_value, prev_cost, "currency"),
        "No target configured",
        "No target configured"
    ),
    (
        "Overtime share",
        "M11",
        (
            f"{ot_value:.2f}%"
            if ot_value is not None else "N/A"
        ),
        trend_text(ot_value, prev_ot),
        "Department-specific (0.5% or 3.0%)",
        ot_status
    ),
    (
        "Attendance rate",
        "M13",
        (
            f"{att_value:.2f}%"
            if att_value is not None else "N/A"
        ),
        trend_text(att_value, prev_att),
        "94.00% per department",
        att_status
    ),
    (
        "Revenue",
        "M16",
        format_currency(revenue_value),
        trend_text(revenue_value, prev_rev, "currency"),
        "No target configured",
        "No target configured"
    ),
    (
        "Net profit",
        "M17",
        format_currency(profit_value),
        trend_text(profit_value, prev_profit, "currency"),
        "No target configured",
        "No target configured"
    ),
    (
        "Operating margin",
        "M18",
        (
            f"{margin_value:.2f}%"
            if margin_value is not None else "N/A"
        ),
        trend_text(margin_value, prev_margin),
        "No target configured",
        "No target configured"
    )
]


# Two-column KPI layout
for start in range(0, len(cards), 2):
    left, right = st.columns(2)

    with left:
        display_card(*cards[start])

    with right:
        display_card(*cards[start + 1])


# --------------------------------------------------
# SOURCES AND PRIVACY NOTES
# --------------------------------------------------
st.divider()

st.caption(
    "Sources: M01, M04, M09, M11, M13, M16, M17 and M18 "
    "metric views; department targets from raw.kpi_targets."
)

st.caption(
    "Privacy: department metrics follow the minimum group-size "
    "rules built into the source metric views. Null or suppressed "
    "values are not treated as zero."
)

st.caption(
    "Interpretation: trends compare with the previous calendar "
    "month. No target is invented where kpi_targets has no "
    "configured target."
)


# --------------------------------------------------
# A4 PRINT-FRIENDLY CSS
# --------------------------------------------------
st.markdown(
    """
    <style>
    @media print {

        @page {
            size: A4 portrait;
            margin: 5mm;
        }

        body {
            zoom: 0.78;
        }

        [data-testid="stSidebar"],
        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stPageLink"],
        [data-testid="stStatusWidget"],
        footer {
            display: none !important;
        }

        .block-container {
            padding: 0 !important;
            margin: 0 auto !important;
            max-width: 100% !important;
        }

        h1 {
            font-size: 18pt !important;
            margin: 0 0 3px 0 !important;
            padding: 0 !important;
        }

        h2, h3 {
            font-size: 11pt !important;
            margin: 3px 0 !important;
            padding: 0 !important;
        }

        p, label {
            font-size: 7pt !important;
            margin: 1px 0 !important;
            line-height: 1.15 !important;
        }

        [data-testid="stSelectbox"] {
            margin-bottom: 2px !important;
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            padding: 3px !important;
            margin: 0 !important;
            break-inside: avoid !important;
        }

        [data-testid="stMetric"] {
            padding: 0 !important;
            margin: 0 !important;
            gap: 0 !important;
        }

        [data-testid="stMetricLabel"] {
            font-size: 8pt !important;
        }

        [data-testid="stMetricValue"] {
            font-size: 15pt !important;
        }

        [data-testid="stCaptionContainer"] p {
            font-size: 7pt !important;
            margin: 1px 0 !important;
        }

        [data-testid="stHorizontalBlock"] {
            gap: 5px !important;
        }

        [data-testid="stVerticalBlock"] {
            gap: 4px !important;
        }

        [data-testid="stElementContainer"] {
            margin: 0 !important;
            padding: 0 !important;
        }

        hr {
            margin: 3px 0 !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True
)
