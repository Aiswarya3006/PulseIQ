from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

DB_PATH = Path(__file__).parent / "pulseiq.duckdb"

st.set_page_config(
    page_title="PulseIQ | Workforce",
    page_icon="📊",
    layout="wide",
)

st.title("PulseIQ — Workforce & Headcount")
st.caption("Workforce overview | Source: approved metric views")

@st.cache_data
def load_data():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        data = {
            "headcount": con.execute(
                "SELECT * FROM m01_headcount"
            ).fetchdf(),
            "hires": con.execute(
                "SELECT * FROM m02_hires"
            ).fetchdf(),
            "exits": con.execute(
                "SELECT * FROM m03_exits"
            ).fetchdf(),
            "attrition": con.execute(
                "SELECT * FROM m04_monthly_attrition"
            ).fetchdf(),
            "location": con.execute(
                "SELECT * FROM m29_headcount_by_location_tier"
            ).fetchdf(),
            "work_mode": con.execute(
                "SELECT * FROM m30_headcount_by_work_mode"
            ).fetchdf(),
        }
    finally:
        con.close()

    for key in ("headcount", "hires", "exits", "attrition"):
        if "month_start_date" in data[key].columns:
            data[key]["month_start_date"] = pd.to_datetime(
                data[key]["month_start_date"]
            )

    return data


try:
    data = load_data()
except Exception as exc:
    st.error(f"Unable to load metric views: {exc}")
    st.info("Check that pulseiq.duckdb and all six metric views exist.")
    st.stop()

hc = data["headcount"].copy()

if hc.empty:
    st.warning("The headcount metric view has no rows.")
    st.stop()

hc["month_start_date"] = pd.to_datetime(hc["month_start_date"])
min_date = hc["month_start_date"].min().date()
max_date = hc["month_start_date"].max().date()

st.sidebar.header("Dashboard Filters")

departments = sorted(
    hc["department_id"].dropna().astype(str).unique().tolist()
)
selected_department = st.sidebar.selectbox(
    "Department",
    ["All departments"] + departments,
)

selected_dates = st.sidebar.date_input(
    "Date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

if isinstance(selected_dates, (tuple, list)):
    start_date = selected_dates[0]
    end_date = selected_dates[-1]
else:
    start_date = selected_dates
    end_date = selected_dates

def filter_metric(df):
    result = df.copy()

    if "month_start_date" in result.columns:
        dates = pd.to_datetime(result["month_start_date"])
        result = result[
            (dates.dt.date >= start_date)
            & (dates.dt.date <= end_date)
        ]

    if (
        selected_department != "All departments"
        and "department_id" in result.columns
    ):
        result = result[
            result["department_id"].astype(str) == selected_department
        ]

    return result


hc_filtered = filter_metric(hc)
hires_filtered = filter_metric(data["hires"])
exits_filtered = filter_metric(data["exits"])
attr_filtered = filter_metric(data["attrition"])

if hc_filtered.empty:
    st.warning("No headcount data matches these filters.")
    st.stop()

monthly = (
    hc_filtered.groupby("month_start_date", as_index=False)["headcount"]
    .sum()
    .sort_values("month_start_date")
)

latest_month = monthly["month_start_date"].max()
latest_headcount = int(
    monthly.loc[monthly["month_start_date"] == latest_month, "headcount"].sum()
)
total_hires = int(hires_filtered["hires"].sum()) if not hires_filtered.empty else 0
total_exits = int(exits_filtered["exits"].sum()) if not exits_filtered.empty else 0

if not attr_filtered.empty:
    latest_attr_date = attr_filtered["month_start_date"].max()
    latest_attrition = attr_filtered.loc[
        attr_filtered["month_start_date"] == latest_attr_date,
        "attrition_pct",
    ].mean()
else:
    latest_attrition = None

k1, k2, k3, k4 = st.columns(4)
k1.metric("Latest Reportable Headcount", f"{latest_headcount:,}")
k2.metric("Hires in Selected Period", f"{total_hires:,}")
k3.metric("Exits in Selected Period", f"{total_exits:,}")
k4.metric(
    "Latest Monthly Attrition",
    f"{latest_attrition:.1f}%" if pd.notna(latest_attrition) else "N/A",
)

st.divider()
left, right = st.columns(2)

with left:
    st.subheader("Headcount trend across the selected period")
    fig = px.line(
        monthly,
        x="month_start_date",
        y="headcount",
        markers=True,
        labels={
            "month_start_date": "Month",
            "headcount": "Employees",
        },
    )
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, width='stretch')

    if len(monthly) >= 2:
        first = int(monthly.iloc[0]["headcount"])
        last = int(monthly.iloc[-1]["headcount"])
        change = last - first
        pct = (change / first * 100) if first else 0
        st.caption(
            f"Insight: Headcount changed from {first:,} to {last:,} "
            f"({change:+,}; {pct:+.1f}%) during the selected period."
        )
    else:
        st.caption(
            f"Insight: Headcount for the selected month is {latest_headcount:,}."
        )

with right:
    st.subheader("Department with the largest reportable headcount")
    dept = (
        hc_filtered[hc_filtered["month_start_date"] == latest_month]
        .groupby("department_id", as_index=False)["headcount"]
        .sum()
        .sort_values("headcount", ascending=False)
    )
    fig = px.bar(
        dept,
        x="department_id",
        y="headcount",
        labels={
            "department_id": "Department",
            "headcount": "Employees",
        },
    )
    st.plotly_chart(fig, width='stretch')

    if not dept.empty:
        top = dept.iloc[0]
        st.caption(
            f"Insight: {top['department_id']} has the largest displayed "
            f"headcount ({int(top['headcount']):,}) in the latest selected month."
        )

st.divider()
left, right = st.columns(2)

with left:
    st.subheader("Location tier with the highest current headcount")
    location = data["location"].copy()

    if not location.empty:
        fig = px.bar(
            location,
            x="city_tier",
            y="headcount",
            labels={"city_tier": "Location tier", "headcount": "Employees"},
        )
        st.plotly_chart(fig, width='stretch')
        top = location.loc[location["headcount"].idxmax()]
        st.caption(
            f"Insight: {top['city_tier']} has the highest current snapshot "
            f"headcount ({int(top['headcount']):,})."
        )
    else:
        st.info("No location-tier data is available.")

with right:
    st.subheader("Largest current work-mode group")
    work_mode = data["work_mode"].copy()

    if not work_mode.empty:
        fig = px.pie(
            work_mode,
            names="work_mode",
            values="headcount",
            hole=0.4,
        )
        st.plotly_chart(fig, width='stretch')
        top = work_mode.loc[work_mode["headcount"].idxmax()]
        st.caption(
            f"Insight: {top['work_mode']} is the largest current work-mode "
            f"group ({int(top['headcount']):,})."
        )
    else:
        st.info("No work-mode data is available.")

st.caption(
    "Note: Location tier and work mode show the current workforce snapshot. "
    "The date filter applies to the time-based metrics."
)

