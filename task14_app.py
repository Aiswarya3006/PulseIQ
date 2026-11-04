
from pathlib import Path

import duckdb
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# ---------------------------------------------------------
# 1. PAGE CONFIGURATION
# ---------------------------------------------------------

st.set_page_config(
    page_title="PulseIQ | Task 14 AI Signals",
    page_icon="ðŸ“Š",
    layout="wide"
)

st.title("PulseIQ | AI Signals Dashboard")
st.caption(
    "Task 14 - Anomalies, forecasts and attrition-risk signals"
)

DB_PATH = Path(__file__).resolve().parent / "pulseiq.duckdb"

AI_LABEL = "AI-generated, for human review"


# ---------------------------------------------------------
# 2. DATABASE CONNECTION
# ---------------------------------------------------------

if not DB_PATH.exists():
    st.error(f"DuckDB database not found: {DB_PATH}")
    st.stop()


@st.cache_data
def load_query(query: str, database_path: str, modified_time: float):
    con = duckdb.connect(database_path, read_only=True)
    try:
        return con.execute(query).fetchdf()
    finally:
        con.close()


def get_data(query: str) -> pd.DataFrame:
    return load_query(
        query,
        str(DB_PATH),
        DB_PATH.stat().st_mtime
    )


# ---------------------------------------------------------
# 3. LOAD AI DATA
# ---------------------------------------------------------

anomaly_data = get_data("""
    SELECT
        reason_code,
        COUNT(*) AS anomaly_count,
        COUNT(money_at_risk) AS records_with_money,
        SUM(money_at_risk)
            FILTER (WHERE isfinite(money_at_risk)) AS money_at_risk
    FROM raw.fact_anomaly
    WHERE flagged = 'Y'
    GROUP BY reason_code
    ORDER BY money_at_risk DESC NULLS LAST
""")

forecast_data = get_data("""
    SELECT
        forecast_month,
        metric,
        department_id,
        forecast_value,
        lower_80,
        upper_80,
        method,
        trained_through
    FROM raw.fact_forecast
    ORDER BY metric, department_id, forecast_month
""")

risk_data = get_data("""
    SELECT
        department_id,
        risk_band,
        COUNT(*) AS employee_records,
        AVG(risk_score_12m) AS avg_risk_score
    FROM raw.fact_attrition_risk
    GROUP BY department_id, risk_band
""")

actual_data = get_data("""
    SELECT
        month_start_date,
        SUM(headcount_start) AS headcount_start,
        SUM(exits) AS total_exits,
        SUM(headcount_end) AS headcount_end,
        100.0 * SUM(exits)
            / NULLIF(SUM(headcount_start), 0) AS actual_attrition_pct
    FROM raw.fact_headcount_monthly
    GROUP BY month_start_date
    ORDER BY month_start_date
""")

st.success("AI source data loaded successfully.")

st.write("Task 14 dashboard foundation is ready.")

# ---------------------------------------------------------
# 4. ANOMALIES RANKED BY MONEY AT RISK
# ---------------------------------------------------------

st.divider()
st.header("1. AI Anomaly Signals")

money_total = anomaly_data["money_at_risk"].sum()
total_anomalies = int(anomaly_data["anomaly_count"].sum())
records_with_money = int(anomaly_data["records_with_money"].sum())
records_without_money = total_anomalies - records_with_money

col1, col2, col3 = st.columns(3)

col1.metric("Flagged anomalies", f"{total_anomalies:,}")
col2.metric("Valid money at risk", f"â‚¹{money_total:,.2f}")
col3.metric("Without money value", f"{records_without_money:,}")

st.caption(AI_LABEL)

chart_data = anomaly_data.dropna(subset=["money_at_risk"]).copy()
chart_data = chart_data.sort_values("money_at_risk", ascending=True)

fig_anomaly = go.Figure(
    go.Bar(
        x=chart_data["money_at_risk"],
        y=chart_data["reason_code"],
        orientation="h",
        text=chart_data["money_at_risk"].apply(
            lambda value: f"â‚¹{value:,.0f}"
        ),
        textposition="auto",
        hovertemplate=(
            "Reason: %{y}<br>"
            "Money at risk: â‚¹%{x:,.2f}"
            "<extra></extra>"
        )
    )
)

fig_anomaly.update_layout(
    title="Anomalies ranked by money at risk",
    xaxis_title="Money at risk (â‚¹)",
    yaxis_title="Anomaly type",
    height=450,
    yaxis={"categoryorder": "total ascending"}
)

st.plotly_chart(fig_anomaly, width='stretch')

st.info(
    "Plain-language note: Statistical outliers and gross-above-norm "
    "records account for most of the identified financial exposure. "
    "These are flagged signals for investigation, not confirmed losses."
)

st.subheader("Anomaly details")
st.dataframe(
    anomaly_data.sort_values(
        "money_at_risk", ascending=False, na_position="last"
    ),
    width='stretch',
    hide_index=True
)

st.warning(
    f"{records_without_money:,} flagged records have no money-at-risk "
    "value. These are not treated as zero financial exposure; "
    "they are reported separately."
)

# ---------------------------------------------------------
# 5. FORECAST VS ACTUAL
# ---------------------------------------------------------

st.divider()
st.header("2. AI Forecast vs Actual")

# Headcount forecast for the whole company
headcount_forecast = forecast_data[
    (forecast_data["metric"] == "headcount_end")
    & (forecast_data["department_id"] == "ALL")
].sort_values("forecast_month")

fig_headcount = go.Figure()

fig_headcount.add_trace(go.Scatter(
    x=actual_data["month_start_date"],
    y=actual_data["headcount_end"],
    mode="lines",
    name="Actual headcount",
    line=dict(width=2)
))

fig_headcount.add_trace(go.Scatter(
    x=headcount_forecast["forecast_month"],
    y=headcount_forecast["upper_80"],
    mode="lines",
    line=dict(width=0),
    showlegend=False,
    hoverinfo="skip"
))

fig_headcount.add_trace(go.Scatter(
    x=headcount_forecast["forecast_month"],
    y=headcount_forecast["lower_80"],
    mode="lines",
    line=dict(width=0),
    fill="tonexty",
    fillcolor="rgba(100,149,237,0.20)",
    name="80% confidence interval"
))

fig_headcount.add_trace(go.Scatter(
    x=headcount_forecast["forecast_month"],
    y=headcount_forecast["forecast_value"],
    mode="lines+markers",
    name="Forecast headcount",
    line=dict(dash="dash", width=3)
))

fig_headcount.update_layout(
    title="Company headcount: actual and forecast",
    xaxis_title="Month",
    yaxis_title="Headcount",
    hovermode="x unified",
    height=450
)

st.caption(AI_LABEL)
st.plotly_chart(fig_headcount, width='stretch')

st.info(
    "Plain-language note: The solid line shows historical company "
    "headcount. The dashed line shows projected headcount from "
    "October 2026 to March 2027. The shaded area is the model's "
    "80% forecast interval, not a guarantee."
)


# Monthly attrition forecast
attrition_forecast = forecast_data[
    (forecast_data["metric"] == "attrition_rate_monthly_pct")
    & (forecast_data["department_id"] == "ALL")
].sort_values("forecast_month")

fig_attrition = go.Figure()

fig_attrition.add_trace(go.Scatter(
    x=actual_data["month_start_date"],
    y=actual_data["actual_attrition_pct"],
    mode="lines",
    name="Actual attrition",
    line=dict(width=2)
))

fig_attrition.add_trace(go.Scatter(
    x=attrition_forecast["forecast_month"],
    y=attrition_forecast["upper_80"],
    mode="lines",
    line=dict(width=0),
    showlegend=False,
    hoverinfo="skip"
))

fig_attrition.add_trace(go.Scatter(
    x=attrition_forecast["forecast_month"],
    y=attrition_forecast["lower_80"],
    mode="lines",
    line=dict(width=0),
    fill="tonexty",
    fillcolor="rgba(255,165,0,0.20)",
    name="80% confidence interval"
))

fig_attrition.add_trace(go.Scatter(
    x=attrition_forecast["forecast_month"],
    y=attrition_forecast["forecast_value"],
    mode="lines+markers",
    name="Forecast attrition",
    line=dict(dash="dash", width=3)
))

fig_attrition.update_layout(
    title="Monthly attrition: actual and forecast",
    xaxis_title="Month",
    yaxis_title="Attrition rate (%)",
    hovermode="x unified",
    height=450
)

st.caption(AI_LABEL)
st.plotly_chart(fig_attrition, width='stretch')

st.info(
    "Plain-language note: Actual attrition is calculated using "
    "total exits divided by total starting headcount across "
    "departments. Forecast values are model estimates; the shaded "
    "area shows the 80% forecast interval."
)


# ---------------------------------------------------------
# 6. FORECAST ERROR AVAILABILITY
# ---------------------------------------------------------

st.subheader("Forecast error evaluation")

forecast_error_status = pd.DataFrame([
    {
        "Metric": "Headcount end",
        "Actual data through": actual_data["month_start_date"].max(),
        "Forecast starts": headcount_forecast["forecast_month"].min(),
        "Overlapping months": 0,
        "Forecast error": "Not measurable yet"
    },
    {
        "Metric": "Monthly attrition rate",
        "Actual data through": actual_data["month_start_date"].max(),
        "Forecast starts": attrition_forecast["forecast_month"].min(),
        "Overlapping months": 0,
        "Forecast error": "Not measurable yet"
    }
])

st.dataframe(
    forecast_error_status,
    width='stretch',
    hide_index=True
)

st.warning(
    "Forecast error cannot currently be calculated for the supplied "
    "forecasts: actual data ends in September 2026, and the forecast "
    "period begins in October 2026. Recalculate error after actual "
    "results become available for forecast months. No error percentage "
    "has been invented."
)

# ---------------------------------------------------------
# 7. AI ATTRITION RISK SIGNALS
# ---------------------------------------------------------

st.divider()
st.header("3. AI Attrition-Risk Signals")

risk_summary = get_data("""
    SELECT
        risk_band,
        COUNT(*) AS employee_records,
        ROUND(AVG(risk_score_12m) * 100, 1) AS avg_risk_pct
    FROM raw.fact_attrition_risk
    GROUP BY risk_band
    ORDER BY
        CASE risk_band
            WHEN 'High' THEN 1
            WHEN 'Medium' THEN 2
            WHEN 'Low' THEN 3
        END
""")

risk_department = get_data("""
    SELECT
        department_id,
        COUNT(*) AS high_risk_records,
        ROUND(AVG(risk_score_12m) * 100, 1) AS avg_risk_pct
    FROM raw.fact_attrition_risk
    WHERE risk_band = 'High'
    GROUP BY department_id
    ORDER BY high_risk_records DESC, department_id
""")

total_risk_records = int(risk_summary["employee_records"].sum())

high_risk_records = int(
    risk_summary.loc[
        risk_summary["risk_band"] == "High",
        "employee_records"
    ].sum()
)

medium_risk_records = int(
    risk_summary.loc[
        risk_summary["risk_band"] == "Medium",
        "employee_records"
    ].sum()
)

low_risk_records = int(
    risk_summary.loc[
        risk_summary["risk_band"] == "Low",
        "employee_records"
    ].sum()
)

risk_col1, risk_col2, risk_col3, risk_col4 = st.columns(4)

risk_col1.metric("Total predictions", f"{total_risk_records:,}")
risk_col2.metric("High risk", f"{high_risk_records:,}")
risk_col3.metric("Medium risk", f"{medium_risk_records:,}")
risk_col4.metric("Low risk", f"{low_risk_records:,}")

# Risk band chart
fig_risk = go.Figure()

fig_risk.add_trace(go.Bar(
    x=risk_summary["risk_band"],
    y=risk_summary["employee_records"],
    text=risk_summary["employee_records"],
    textposition="auto",
    name="Prediction records",
    hovertemplate=(
        "Risk band: %{x}<br>"
        "Records: %{y}<extra></extra>"
    )
))

fig_risk.update_layout(
    title="Attrition-risk predictions by risk band",
    xaxis_title="Risk band",
    yaxis_title="Number of prediction records",
    height=400
)

st.caption(AI_LABEL)
st.plotly_chart(fig_risk, width='stretch')

st.info(
    "Plain-language note: High, Medium and Low bands represent "
    "model-assigned risk groups. A high-risk prediction is not "
    "proof that an employee will leave. It is a signal for "
    "appropriate human review and supportive retention planning."
)

# High-risk department chart
fig_department_risk = go.Figure()

fig_department_risk.add_trace(go.Bar(
    x=risk_department["department_id"],
    y=risk_department["high_risk_records"],
    text=risk_department["high_risk_records"],
    textposition="auto",
    name="High-risk records",
    hovertemplate=(
        "Department: %{x}<br>"
        "High-risk records: %{y}<extra></extra>"
    )
))

fig_department_risk.update_layout(
    title="High-risk prediction records by department",
    xaxis_title="Department",
    yaxis_title="High-risk prediction records",
    height=400
)

st.caption(AI_LABEL)
st.plotly_chart(fig_department_risk, width='stretch')

st.info(
    "Plain-language note: This chart highlights departments with "
    "more high-risk prediction records. Review the underlying "
    "prediction reasons and workforce context before taking action."
)

st.subheader("High-risk department details")
st.dataframe(
    risk_department,
    width='stretch',
    hide_index=True
)

st.caption(
    "All attrition-risk predictions are decision-support signals "
    "and must be reviewed by a human."
)

# ---------------------------------------------------------
# 8. SAVE FORECAST ERROR EVIDENCE
# ---------------------------------------------------------

REPORTS_DIR = Path(__file__).resolve().parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

forecast_error_path = REPORTS_DIR / "task14_forecast_error_evaluation.csv"

forecast_error_status.to_csv(
    forecast_error_path,
    index=False
)

st.success("Forecast error evaluation CSV saved successfully.")

st.download_button(
    label="Download forecast error evaluation CSV",
    data=forecast_error_status.to_csv(index=False).encode("utf-8"),
    file_name="task14_forecast_error_evaluation.csv",
    mime="text/csv"
)
# ---------------------------------------------------------
# 9. CRITICAL THINKING: FORECAST ERROR
# ---------------------------------------------------------

st.divider()
st.subheader("Critical Thinking: Is 12% Forecast Error Good?")

st.info(
    "A 12% forecast error is not automatically good or bad. "
    "It must be compared with a baseline forecast, business "
    "tolerance and historical performance. We should also check "
    "whether the model consistently overpredicts or underpredicts. "
    "Headcount and attrition need separate evaluation. Percentage "
    "errors can be misleading when actual attrition is very low. "
    "In this dataset, 12% is not a measured result because no "
    "forecast months overlap with available actual data."
)
