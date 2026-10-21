from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

DB_PATH = Path(__file__).resolve().parents[1] / "pulseiq.duckdb"

st.set_page_config(page_title="PulseIQ | Workforce Details", layout="wide")
st.title("Workforce Details")
st.caption("Department-level trends from approved metric views")

@st.cache_data
def load_metrics():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        headcount = con.execute("SELECT * FROM m01_headcount").fetchdf()
        hires = con.execute("SELECT * FROM m02_hires").fetchdf()
        exits = con.execute("SELECT * FROM m03_exits").fetchdf()
        attrition = con.execute("SELECT * FROM m04_monthly_attrition").fetchdf()
    finally:
        con.close()

    for df in (headcount, hires, exits, attrition):
        if "month_start_date" in df.columns:
            df["month_start_date"] = pd.to_datetime(df["month_start_date"])
    return headcount, hires, exits, attrition

try:
    headcount, hires, exits, attrition = load_metrics()
except Exception as exc:
    st.error(f"Unable to load metric views: {exc}")
    st.stop()

if headcount.empty:
    st.warning("No headcount data available.")
    st.stop()

departments = sorted(headcount["department_id"].dropna().astype(str).unique())
department = st.selectbox("Department", ["All departments"] + departments)

min_date = headcount["month_start_date"].min().date()
max_date = headcount["month_start_date"].max().date()
date_range = st.date_input(
    "Date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

if isinstance(date_range, (tuple, list)):
    start_date, end_date = date_range[0], date_range[-1]
else:
    start_date = end_date = date_range

def apply_filters(df):
    out = df.copy()
    dates = out["month_start_date"].dt.date
    out = out[(dates >= start_date) & (dates <= end_date)]
    if department != "All departments":
        out = out[out["department_id"].astype(str) == department]
    return out

hc = apply_filters(headcount)
hi = apply_filters(hires)
ex = apply_filters(exits)
at = apply_filters(attrition)

if hc.empty:
    st.warning("No results for the selected filters.")
    st.stop()

trend = hc.groupby("month_start_date", as_index=False)["headcount"].sum()
st.subheader("Headcount Trend")
st.plotly_chart(
    px.line(trend, x="month_start_date", y="headcount", markers=True,
            labels={"month_start_date": "Month", "headcount": "Employees"}),
    width="stretch",
)
if len(trend) > 1:
    change = int(trend.iloc[-1]["headcount"] - trend.iloc[0]["headcount"])
    st.caption(f"Insight: Headcount changed by {change:+,} over the selected period.")

left, right = st.columns(2)
with left:
    st.subheader("Monthly Hires")
    hire_trend = hi.groupby("month_start_date", as_index=False)["hires"].sum()
    st.plotly_chart(
        px.bar(hire_trend, x="month_start_date", y="hires",
               labels={"month_start_date": "Month", "hires": "Hires"}),
        width="stretch",
    )
    st.caption(f"Insight: {int(hi['hires'].sum()) if not hi.empty else 0:,} hires in the selected period.")

with right:
    st.subheader("Monthly Exits")
    exit_trend = ex.groupby("month_start_date", as_index=False)["exits"].sum()
    st.plotly_chart(
        px.bar(exit_trend, x="month_start_date", y="exits",
               labels={"month_start_date": "Month", "exits": "Exits"}),
        width="stretch",
    )
    st.caption(f"Insight: {int(ex['exits'].sum()) if not ex.empty else 0:,} exits in the selected period.")

st.subheader("Monthly Attrition")
if not at.empty:
    attr_trend = at.groupby("month_start_date", as_index=False)["attrition_pct"].mean()
    st.plotly_chart(
        px.line(attr_trend, x="month_start_date", y="attrition_pct", markers=True,
                labels={"month_start_date": "Month", "attrition_pct": "Attrition"}),
        width="stretch",
    )
    latest = attr_trend.iloc[-1]["attrition_pct"]
    st.caption(f"Insight: Latest displayed attrition is {latest:.2f}%.")
else:
    st.info("No attrition values available for these filters.")
