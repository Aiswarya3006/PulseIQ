
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st


# ---------------------------------------------------------
# 1. PAGE CONFIGURATION
# ---------------------------------------------------------

st.set_page_config(
    page_title="PulseIQ | Task 11 Finance Analytics",
    page_icon="📊",
    layout="wide"
)

st.title("PulseIQ | Profit & Loss and Expense Analytics")
st.caption(
    "Task 11 - Revenue, expenses, margin and vendor analytics"
)

DB_PATH = Path(__file__).resolve().parent / "pulseiq.duckdb"

if not DB_PATH.exists():
    st.error(f"DuckDB database not found: {DB_PATH}")
    st.stop()


# ---------------------------------------------------------
# 2. DATABASE CONNECTION AND DATA LOADING
# ---------------------------------------------------------

@st.cache_data
def load_data(database_path, modified_time):

    con = duckdb.connect(
        database_path,
        read_only=True
    )

    try:

        # Detail P&L accounts only.
        # Group accounts are excluded to avoid double counting.

        accounts = con.execute("""
            SELECT
                account_code,
                account_name,
                account_type,
                normal_balance,
                parent_code,
                statement
            FROM raw.dim_account
            WHERE
                lower(coalesce(cast(is_group AS VARCHAR), 'n'))
                    NOT IN ('y', 'yes', 'true', '1')
                AND lower(coalesce(statement, ''))
                    = lower('Profit & Loss')
        """).df()

        # Ledger data for P&L.

        ledger = con.execute("""
            SELECT
                l.line_id,
                l.entry_id,
                CAST(l.entry_date AS DATE) AS entry_date,
                l.account_code,
                l.debit,
                l.credit,
                l.cost_center_department_id,
                d.department_name
            FROM raw.fact_ledger l
            LEFT JOIN raw.dim_department d
                ON CAST(l.cost_center_department_id AS VARCHAR)
                 = CAST(d.department_id AS VARCHAR)
            WHERE l.entry_date IS NOT NULL
        """).df()

        # Expense data for category and vendor analysis.
        # This is intentionally separate from ledger P&L.

        expenses = con.execute("""
            SELECT
                e.expense_id,
                CAST(e.expense_date AS DATE) AS expense_date,
                e.category_account,
                e.vendor_id,
                e.department_id,
                e.amount_excl_gst,
                e.gst_amount,
                e.total_amount,
                e.status,
                e.description,
                v.vendor_name,
                a.account_name AS category_name,
                d.department_name
            FROM raw.fact_expense e
            LEFT JOIN raw.dim_vendor v
                ON CAST(e.vendor_id AS VARCHAR)
                 = CAST(v.vendor_id AS VARCHAR)
            LEFT JOIN raw.dim_account a
                ON CAST(e.category_account AS VARCHAR)
                 = CAST(a.account_code AS VARCHAR)
            LEFT JOIN raw.dim_department d
                ON CAST(e.department_id AS VARCHAR)
                 = CAST(d.department_id AS VARCHAR)
            WHERE e.expense_date IS NOT NULL
        """).df()

        return accounts, ledger, expenses

    finally:
        con.close()


try:
    accounts, ledger, expenses = load_data(
        str(DB_PATH),
        DB_PATH.stat().st_mtime
    )

except Exception as error:
    st.error(f"Unable to load Task 11 data: {error}")
    st.stop()


if ledger.empty or accounts.empty:
    st.error("P&L data or account master data is empty.")
    st.stop()


# ---------------------------------------------------------
# 3. DATA PREPARATION
# ---------------------------------------------------------

ledger["entry_date"] = pd.to_datetime(
    ledger["entry_date"],
    errors="coerce"
)

expenses["expense_date"] = pd.to_datetime(
    expenses["expense_date"],
    errors="coerce"
)

ledger["debit"] = pd.to_numeric(
    ledger["debit"], errors="coerce"
).fillna(0)

ledger["credit"] = pd.to_numeric(
    ledger["credit"], errors="coerce"
).fillna(0)

expenses["amount_excl_gst"] = pd.to_numeric(
    expenses["amount_excl_gst"], errors="coerce"
).fillna(0)

expenses["total_amount"] = pd.to_numeric(
    expenses["total_amount"], errors="coerce"
).fillna(0)

ledger["account_code"] = ledger["account_code"].astype(str)
accounts["account_code"] = accounts["account_code"].astype(str)

ledger = ledger.merge(
    accounts[
        [
            "account_code",
            "account_name",
            "normal_balance",
            "account_type"
        ]
    ],
    on="account_code",
    how="inner"
)

ledger["normal_balance"] = (
    ledger["normal_balance"]
    .astype(str)
    .str.upper()
    .str.strip()
)

# Revenue: credit minus debit.
# Expenses: debit minus credit.

ledger["revenue_amount"] = 0.0
ledger["expense_amount"] = 0.0

revenue_mask = ledger["normal_balance"] == "CREDIT"
expense_mask = ledger["normal_balance"] == "DEBIT"

ledger.loc[revenue_mask, "revenue_amount"] = (
    ledger.loc[revenue_mask, "credit"]
    - ledger.loc[revenue_mask, "debit"]
)

ledger.loc[expense_mask, "expense_amount"] = (
    ledger.loc[expense_mask, "debit"]
    - ledger.loc[expense_mask, "credit"]
)

ledger["month"] = (
    ledger["entry_date"].dt.to_period("M").astype(str)
)

expenses["month"] = (
    expenses["expense_date"].dt.to_period("M").astype(str)
)

ledger = ledger[
    ledger["normal_balance"].isin(["CREDIT", "DEBIT"])
].copy()


# ---------------------------------------------------------
# 4. DATE AND DEPARTMENT FILTERS
# ---------------------------------------------------------

valid_dates = ledger["entry_date"].dropna()

if valid_dates.empty:
    st.error("No valid ledger dates found.")
    st.stop()

minimum_date = valid_dates.min().date()
maximum_date = valid_dates.max().date()

st.sidebar.header("Dashboard Filters")

selected_dates = st.sidebar.date_input(
    "Select Date Range",
    value=(minimum_date, maximum_date),
    min_value=minimum_date,
    max_value=maximum_date
)

if not isinstance(selected_dates, (tuple, list)):
    st.warning("Please select a start date and an end date.")
    st.stop()

if len(selected_dates) != 2:
    st.info("Select both start date and end date.")
    st.stop()

start_date, end_date = selected_dates

if start_date > end_date:
    st.error("Start date cannot be after end date.")
    st.stop()

# Inclusive date filter.
# Selecting September 1 to September 30 includes the full month.

ledger_filtered = ledger[
    (ledger["entry_date"].dt.date >= start_date)
    & (ledger["entry_date"].dt.date <= end_date)
].copy()

expenses_filtered = expenses[
    (expenses["expense_date"].dt.date >= start_date)
    & (expenses["expense_date"].dt.date <= end_date)
].copy()

department_values = sorted(
    ledger_filtered["department_name"]
    .dropna()
    .astype(str)
    .unique()
)

department_options = ["All departments"] + department_values

selected_department = st.sidebar.selectbox(
    "Department",
    department_options
)

if selected_department != "All departments":

    ledger_filtered = ledger_filtered[
        ledger_filtered["department_name"].astype(str)
        == selected_department
    ]

    expenses_filtered = expenses_filtered[
        expenses_filtered["department_name"].astype(str)
        == selected_department
    ]

vendor_values = sorted(
    expenses_filtered["vendor_name"]
    .dropna()
    .astype(str)
    .unique()
)

vendor_options = ["All vendors"] + vendor_values

selected_vendor = st.sidebar.selectbox(
    "Vendor",
    vendor_options
)

if selected_vendor != "All vendors":
    expenses_filtered = expenses_filtered[
        expenses_filtered["vendor_name"].astype(str)
        == selected_vendor
    ]


# ---------------------------------------------------------
# 5. MONTHLY P&L CALCULATION
# ---------------------------------------------------------

monthly = (
    ledger_filtered.groupby("month", as_index=False)
    .agg(
        Revenue=("revenue_amount", "sum"),
        Expenses=("expense_amount", "sum")
    )
    .sort_values("month")
)

if monthly.empty:
    st.warning("No P&L records found for the selected filters.")
    st.stop()

monthly["Net Profit"] = (
    monthly["Revenue"] - monthly["Expenses"]
)

monthly["Profit Margin (%)"] = (
    monthly["Net Profit"]
    / monthly["Revenue"].replace(0, pd.NA)
    * 100
).fillna(0)

total_revenue = monthly["Revenue"].sum()
total_expenses = monthly["Expenses"].sum()
net_profit = total_revenue - total_expenses

profit_margin = (
    net_profit / total_revenue * 100
    if total_revenue != 0
    else 0
)


# ---------------------------------------------------------
# 6. PROFIT & LOSS SUMMARY
# ---------------------------------------------------------

st.subheader("1. Profit & Loss Summary")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Revenue",
    f"₹{total_revenue:,.2f}"
)

col2.metric(
    "Expenses",
    f"₹{total_expenses:,.2f}"
)

col3.metric(
    "Net Profit",
    f"₹{net_profit:,.2f}"
)

col4.metric(
    "Profit Margin",
    f"{profit_margin:.2f}%"
)

st.caption(
    "P&L uses fact_ledger and detail accounts only. "
    "Credit-normal accounts are revenue. "
    "Debit-normal accounts are expenses. "
    "Expense analysis uses fact_expense separately."
)


# ---------------------------------------------------------
# 7. MONTHLY REVENUE, EXPENSES AND MARGIN
# ---------------------------------------------------------

st.subheader("2. Monthly Revenue, Expenses and Margin")

monthly_chart = monthly.melt(
    id_vars="month",
    value_vars=["Revenue", "Expenses"],
    var_name="Metric",
    value_name="Amount"
)

fig = px.bar(
    monthly_chart,
    x="month",
    y="Amount",
    color="Metric",
    barmode="group",
    title="Monthly Revenue vs Expenses",
    labels={
        "month": "Month",
        "Amount": "Amount (₹)"
    }
)

st.plotly_chart(fig, use_container_width=True)

margin_fig = px.line(
    monthly,
    x="month",
    y="Profit Margin (%)",
    markers=True,
    title="Monthly Profit Margin Trend"
)

st.plotly_chart(margin_fig, use_container_width=True)


# ---------------------------------------------------------
# 8. MONTHLY P&L TABLE
# ---------------------------------------------------------

st.subheader("3. Monthly P&L Table")

month_options = monthly["month"].tolist()

selected_month = st.selectbox(
    "Select Month",
    month_options,
    index=len(month_options) - 1
)

selected_month_ledger = ledger_filtered[
    ledger_filtered["month"] == selected_month
].copy()

account_pl = (
    selected_month_ledger.groupby(
        ["account_code", "account_name", "normal_balance"],
        as_index=False
    )
    .agg(
        Debit=("debit", "sum"),
        Credit=("credit", "sum")
    )
)

account_pl["P&L Amount"] = 0.0

account_pl.loc[
    account_pl["normal_balance"] == "CREDIT",
    "P&L Amount"
] = (
    account_pl["Credit"] - account_pl["Debit"]
)

account_pl.loc[
    account_pl["normal_balance"] == "DEBIT",
    "P&L Amount"
] = (
    account_pl["Debit"] - account_pl["Credit"]
)

st.dataframe(
    account_pl.sort_values("account_code"),
    use_container_width=True,
    hide_index=True
)

month_summary = monthly[
    monthly["month"] == selected_month
]

st.write("Selected Month Summary")

st.dataframe(
    month_summary,
    use_container_width=True,
    hide_index=True
)


# ---------------------------------------------------------
# 9. EXPENSE BY CATEGORY
# ---------------------------------------------------------

st.subheader("4. Expense by Category")

if expenses_filtered.empty:
    st.info("No expense records available for the selected filters.")

else:

    category_summary = (
        expenses_filtered.groupby(
            "category_name",
            dropna=False,
            as_index=False
        )
        .agg(
            Spend=("amount_excl_gst", "sum")
        )
        .sort_values("Spend", ascending=False)
    )

    category_summary["category_name"] = (
        category_summary["category_name"]
        .fillna("Unmapped Category")
    )

    category_fig = px.bar(
        category_summary,
        x="category_name",
        y="Spend",
        title="Expense by Category (Excluding GST)",
        labels={
            "category_name": "Expense Category",
            "Spend": "Spend (₹)"
        }
    )

    category_fig.update_layout(
        xaxis_tickangle=-35
    )

    st.plotly_chart(
        category_fig,
        use_container_width=True
    )

    st.dataframe(
        category_summary,
        use_container_width=True,
        hide_index=True
    )


# ---------------------------------------------------------
# 10. TOP 10 VENDORS
# ---------------------------------------------------------

st.subheader("5. Top 10 Vendors by Spend")

if expenses_filtered.empty:
    st.info("No vendor expense records available.")

else:

    vendor_summary = (
        expenses_filtered.groupby(
            "vendor_name",
            dropna=False,
            as_index=False
        )
        .agg(
            Spend=("amount_excl_gst", "sum")
        )
        .sort_values("Spend", ascending=False)
        .head(10)
    )

    vendor_summary["vendor_name"] = (
        vendor_summary["vendor_name"]
        .fillna("Unknown Vendor")
    )

    vendor_fig = px.bar(
        vendor_summary.sort_values("Spend"),
        x="Spend",
        y="vendor_name",
        orientation="h",
        title="Top 10 Vendors by Spend (Excluding GST)",
        labels={
            "vendor_name": "Vendor",
            "Spend": "Spend (₹)"
        }
    )

    st.plotly_chart(
        vendor_fig,
        use_container_width=True
    )

    st.dataframe(
        vendor_summary,
        use_container_width=True,
        hide_index=True
    )


# ---------------------------------------------------------
# 11. README HEADLINE TIE-OUT
# ---------------------------------------------------------

st.subheader("6. README Headline Tie-out")

st.info(
    "The original PulseIQ_Dataset.xlsx README sheet "
    "provides dataset information and row counts, but "
    "does not provide Revenue, Expenses or Net Profit "
    "reference figures. Therefore, a financial README "
    "tie-out cannot be performed."
)

st.write("**Dashboard P&L figures for reference**")

dashboard_summary = pd.DataFrame({
    "Metric": [
        "Revenue",
        "Expenses",
        "Net Profit"
    ],
    "Dashboard Value (₹)": [
        total_revenue,
        total_expenses,
        net_profit
    ],
    "Reference Status": [
        "Not available in README",
        "Not available in README",
        "Not available in README"
    ]
})

st.dataframe(
    dashboard_summary,
    use_container_width=True,
    hide_index=True
)

st.caption(
    "No PASS/FAIL status is assigned because the "
    "original README does not contain financial "
    "headline values for comparison."
)

# ---------------------------------------------------------
# 12. THREE FINDINGS
# ---------------------------------------------------------

st.subheader("7. Three Findings")

first_month = monthly.iloc[0]
last_month = monthly.iloc[-1]

revenue_change = (
    last_month["Revenue"] - first_month["Revenue"]
)

margin_change = (
    last_month["Profit Margin (%)"]
    - first_month["Profit Margin (%)"]
)

if revenue_change > 0:
    revenue_finding = (
        f"Revenue increased by ₹{revenue_change:,.2f} "
        f"between {first_month['month']} and "
        f"{last_month['month']}."
    )
elif revenue_change < 0:
    revenue_finding = (
        f"Revenue decreased by ₹{abs(revenue_change):,.2f} "
        f"between {first_month['month']} and "
        f"{last_month['month']}."
    )
else:
    revenue_finding = (
        "Revenue remained unchanged between the first "
        "and last selected months."
    )

if margin_change > 0:
    margin_finding = (
        f"Profit margin improved by {margin_change:.2f} "
        "percentage points."
    )
elif margin_change < 0:
    margin_finding = (
        f"Profit margin declined by "
        f"{abs(margin_change):.2f} percentage points."
    )
else:
    margin_finding = "Profit margin remained unchanged."

if not expenses_filtered.empty:
    top_vendor_row = (
        expenses_filtered.groupby("vendor_name")[
            "amount_excl_gst"
        ].sum().sort_values(ascending=False)
    )

    top_vendor_name = str(top_vendor_row.index[0])
    top_vendor_spend = float(top_vendor_row.iloc[0])

    vendor_finding = (
        f"{top_vendor_name} is the highest-spend vendor "
        f"with ₹{top_vendor_spend:,.2f} spend excluding GST."
    )

else:
    top_vendor_name = "No vendor data"
    top_vendor_spend = 0.0
    vendor_finding = "No vendor spending data for this selection."

st.write("**Finding 1 - Revenue movement**")
st.write(revenue_finding)

st.write("**Finding 2 - Margin movement**")
st.write(margin_finding)

st.write("**Finding 3 - Vendor spending**")
st.write(vendor_finding)


# ---------------------------------------------------------
# 13. REASONS WHY REVENUE MAY GROW BUT MARGIN FALL
# ---------------------------------------------------------

st.markdown("### Think for yourself: Revenue grew but margin fell")

cause_data = pd.DataFrame({
    "Possible Cause": [
        "Expenses increased faster than revenue",
        "Revenue mix shifted to lower-margin services",
        "High or one-time vendor spending"
    ],
    "Data That Would Prove It": [
        "Monthly ledger expenses: salaries, cloud hosting, "
        "rent and marketing",
        "Monthly revenue by account: software, subscription, "
        "consulting and support",
        "Monthly vendor/category trends and invoice-level "
        "expense records"
    ]
})

st.dataframe(
    cause_data,
    use_container_width=True,
    hide_index=True
)


# ---------------------------------------------------------
# 14. SUPPORTING DATA FOR THE POSSIBLE CAUSES
# ---------------------------------------------------------

st.markdown("### Supporting Data for Margin Analysis")

# Monthly expense account trend.

expense_account_trend = (
    ledger_filtered[
        ledger_filtered["normal_balance"] == "DEBIT"
    ]
    .groupby(
        ["month", "account_code", "account_name"],
        as_index=False
    )
    .agg(
        Expense=("expense_amount", "sum")
    )
)

st.write("**Monthly expense by account**")

st.dataframe(
    expense_account_trend.sort_values(
        ["month", "Expense"],
        ascending=[True, False]
    ),
    use_container_width=True,
    hide_index=True
)

# Monthly revenue account trend.

revenue_account_trend = (
    ledger_filtered[
        ledger_filtered["normal_balance"] == "CREDIT"
    ]
    .groupby(
        ["month", "account_code", "account_name"],
        as_index=False
    )
    .agg(
        Revenue=("revenue_amount", "sum")
    )
)

st.write("**Monthly revenue by account**")

st.dataframe(
    revenue_account_trend.sort_values(
        ["month", "Revenue"],
        ascending=[True, False]
    ),
    use_container_width=True,
    hide_index=True
)

# Monthly vendor spending trend.

if not expenses_filtered.empty:

    monthly_vendor = (
        expenses_filtered.groupby(
            ["month", "vendor_name"],
            dropna=False,
            as_index=False
        )
        .agg(
            Spend=("amount_excl_gst", "sum")
        )
        .sort_values(
            ["month", "Spend"],
            ascending=[True, False]
        )
    )

    st.write("**Monthly vendor spending trend**")

    st.dataframe(
        monthly_vendor,
        use_container_width=True,
        hide_index=True
    )


# ---------------------------------------------------------
# 15. FILTERED EXPENSE DETAILS
# ---------------------------------------------------------

st.subheader("8. Filtered Expense Details")

if expenses_filtered.empty:

    st.info("No expense details for the selected filters.")

else:

    expense_display = expenses_filtered[
        [
            "expense_id",
            "expense_date",
            "category_account",
            "category_name",
            "vendor_id",
            "vendor_name",
            "department_name",
            "amount_excl_gst",
            "gst_amount",
            "total_amount",
            "status"
        ]
    ].copy()

    st.dataframe(
        expense_display.sort_values(
            "expense_date",
            ascending=False
        ),
        use_container_width=True,
        hide_index=True
    )

    st.download_button(
        "Download Filtered Expense Details CSV",
        data=expense_display.to_csv(index=False).encode("utf-8"),
        file_name="task11_filtered_expense_details.csv",
        mime="text/csv"
    )


# ---------------------------------------------------------
# 16. EVIDENCE DOWNLOADS
# ---------------------------------------------------------

st.subheader("9. Task 11 Evidence Downloads")

st.download_button(
    "Download Monthly P&L CSV",
    data=monthly.to_csv(index=False).encode("utf-8"),
    file_name="task11_monthly_pl.csv",
    mime="text/csv"
)

st.download_button(
    "Download Expense by Category CSV",
    data=(
        category_summary.to_csv(index=False).encode("utf-8")
        if not expenses_filtered.empty
        else b""
    ),
    file_name="task11_expense_by_category.csv",
    mime="text/csv"
)

st.download_button(
    "Download Top 10 Vendors CSV",
    data=(
        vendor_summary.to_csv(index=False).encode("utf-8")
        if not expenses_filtered.empty
        else b""
    ),
    file_name="task11_top_10_vendors.csv",
    mime="text/csv"
)

st.caption(
    "Task 11 | PulseIQ Finance Analytics | "
    "P&L is calculated from fact_ledger detail accounts. "
    "Vendor and category analysis is calculated separately "
    "from fact_expense."
)
