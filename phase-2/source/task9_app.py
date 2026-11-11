
import duckdb
import pandas as pd
import streamlit as st
import plotly.express as px
from pathlib import Path

st.set_page_config(
    page_title="PulseIQ | Payroll Cost Dashboard",
    page_icon="📊",
    layout="wide",
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "pulseiq.duckdb"

st.title("PulseIQ — Payroll Cost Dashboard")
st.caption("Task 9 | Payroll cost trends, department analysis and reconciliation")

if not DB_PATH.exists():
    st.error(f"DuckDB database not found: {DB_PATH}")
    st.stop()


@st.cache_data
def load_payroll():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        query = """
            SELECT
                g.period_end_date,
                g.department_id,
                g.employees_paid,
                g.gross_pay,
                n.net_pay,
                e.employer_cost,
                h.cost_per_head
            FROM m07_gross_pay g
            JOIN m08_net_pay n
              USING (period_end_date, department_id)
            JOIN m09_employer_cost e
              USING (period_end_date, department_id)
            JOIN m10_cost_per_head h
              USING (period_end_date, department_id)
            ORDER BY g.period_end_date, g.department_id
        """
        return con.execute(query).fetchdf()
    finally:
        con.close()


df = load_payroll()
df["period_end_date"] = pd.to_datetime(df["period_end_date"])

# Privacy rule: suppress groups with fewer than five employees.
df = df[df["employees_paid"] >= 5].copy()

metric_columns = [
    "gross_pay", "net_pay", "employer_cost", "cost_per_head"
]
for column in metric_columns:
    df[column] = pd.to_numeric(df[column], errors="coerce")

df = df.dropna(subset=["gross_pay", "net_pay", "employer_cost"])

if df.empty:
    st.warning("No payroll groups meet the minimum-size and data-quality rules.")
    st.stop()

st.sidebar.header("Dashboard Filters")

min_date = df["period_end_date"].min().date()
max_date = df["period_end_date"].max().date()

date_range = st.sidebar.date_input(
    "Payroll period",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

departments = sorted(df["department_id"].dropna().unique().tolist())
selected_departments = st.sidebar.multiselect(
    "Departments",
    options=departments,
    default=departments,
)

if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start_date, end_date = date_range
    filtered = df[
        df["period_end_date"].dt.date.between(start_date, end_date)
        & df["department_id"].isin(selected_departments)
    ].copy()
else:
    filtered = df[
        df["period_end_date"].dt.date == date_range
    ].copy()
    filtered = filtered[
        filtered["department_id"].isin(selected_departments)
    ]

if filtered.empty:
    st.info("No data available for the selected filters.")
    st.stop()

gross_total = filtered["gross_pay"].sum()
net_total = filtered["net_pay"].sum()
employer_total = filtered["employer_cost"].sum()
employees_total = filtered.groupby(
    "period_end_date"
)["employees_paid"].sum().mean()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Gross Pay", f"₹{gross_total:,.2f}")
c2.metric("Net Pay", f"₹{net_total:,.2f}")
c3.metric("Employer Cost", f"₹{employer_total:,.2f}")
c4.metric("Avg. Employees Paid / Month", f"{employees_total:,.0f}")

st.subheader("Monthly Payroll Cost Trends")

monthly = (
    filtered.groupby("period_end_date", as_index=False)
    .agg(
        gross_pay=("gross_pay", "sum"),
        net_pay=("net_pay", "sum"),
        employer_cost=("employer_cost", "sum"),
    )
    .sort_values("period_end_date")
)

trend = monthly.melt(
    id_vars="period_end_date",
    value_vars=["gross_pay", "net_pay", "employer_cost"],
    var_name="metric",
    value_name="amount",
)

fig_trend = px.line(
    trend,
    x="period_end_date",
    y="amount",
    color="metric",
    markers=True,
    title="Gross Pay, Net Pay and Employer Cost",
    labels={
        "period_end_date": "Month",
        "amount": "Amount (₹)",
        "metric": "Metric",
    },
)
st.plotly_chart(fig_trend, use_container_width=True)

st.subheader("Department-wise Payroll Cost")

department_summary = (
    filtered.groupby("department_id", as_index=False)
    .agg(
        employees_paid=("employees_paid", "mean"),
        gross_pay=("gross_pay", "mean"),
        net_pay=("net_pay", "mean"),
        employer_cost=("employer_cost", "mean"),
        cost_per_head=("cost_per_head", "mean"),
    )
)

left, right = st.columns(2)

with left:
    fig_dept = px.bar(
        department_summary,
        x="department_id",
        y="employer_cost",
        title="Average Monthly Employer Cost by Department",
        labels={
            "department_id": "Department",
            "employer_cost": "Average Cost (₹)",
        },
    )
    st.plotly_chart(fig_dept, use_container_width=True)

with right:
    fig_head = px.bar(
        department_summary,
        x="department_id",
        y="cost_per_head",
        title="Average Cost per Employee by Department",
        labels={
            "department_id": "Department",
            "cost_per_head": "Average Cost per Employee (₹)",
        },
    )
    st.plotly_chart(fig_head, use_container_width=True)

st.subheader("Department Summary")
display_summary = department_summary.copy()
for column in ["gross_pay", "net_pay", "employer_cost", "cost_per_head"]:
    display_summary[column] = display_summary[column].round(2)

st.dataframe(display_summary, use_container_width=True, hide_index=True)

st.subheader("Payroll Reconciliation Evidence")

recon_path = BASE_DIR / "reports" / "reconciliation_payroll_answer_key.csv"

if recon_path.exists():
    recon = pd.read_csv(recon_path)

    diff_cols = [
        "payroll_gross_pay_difference",
        "payroll_net_pay_difference",
        "payroll_employer_cost_difference",
    ]
    for col in diff_cols:
        recon[col] = pd.to_numeric(recon[col], errors="coerce")

    mismatch_mask = recon[diff_cols].abs().gt(0.01).any(axis=1)
    mismatch = recon[mismatch_mask].copy()
    match_count = int((~mismatch_mask).sum())

    col1, col2, col3 = st.columns(3)
    col1.metric("Months Compared", len(recon))
    col2.metric("Months Matching", match_count)
    col3.metric("Months Needing Review", len(mismatch))

    if mismatch.empty:
        st.success("All compared months match the supplied answer key.")
    else:
        st.warning(
            "Reconciliation is not complete. Differences below are shown "
            "without adjustment; investigate before reporting the totals as reconciled."
        )
        st.dataframe(mismatch, use_container_width=True, hide_index=True)

    st.caption(
        "Difference = cleaned payroll total minus answer-key total. "
        "Negative values mean the cleaned total is lower."
    )
    with st.expander("View all monthly reconciliation results"):
        st.dataframe(recon, use_container_width=True, hide_index=True)

    st.download_button(
        "Download Reconciliation CSV",
        data=recon.to_csv(index=False).encode("utf-8"),
        file_name="task9_payroll_reconciliation.csv",
        mime="text/csv",
    )
else:
    st.warning("Reconciliation evidence file was not found.")

excluded_path = (
    BASE_DIR / "reports" / "rejected" / "payroll_excluded_rows_evidence.csv"
)

st.subheader("Excluded Payroll Rows")
if excluded_path.exists():
    excluded = pd.read_csv(excluded_path)
    # Show identifiers and reasons only, never salary amounts.
    st.dataframe(excluded, use_container_width=True, hide_index=True)
    st.download_button(
        "Download Excluded Rows CSV",
        data=excluded.to_csv(index=False).encode("utf-8"),
        file_name="task9_excluded_payroll_rows.csv",
        mime="text/csv",
    )
else:
    st.warning("Excluded-row evidence file was not found.")

st.caption(
    "Privacy rule: groups with fewer than five employees are suppressed. "
    "Dashboard figures are based on the available payroll metric views. "
    "Reconciliation differences require review; this dashboard does not "
    "represent unresolved differences as reconciled."
)
