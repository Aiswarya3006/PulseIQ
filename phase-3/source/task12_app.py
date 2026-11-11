
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st


# ---------------------------------------------------------
# 1. PAGE CONFIGURATION
# ---------------------------------------------------------

st.set_page_config(
    page_title="PulseIQ | Task 12 Receivables Analytics",
    page_icon="💰",
    layout="wide"
)

st.title("PulseIQ | Invoices, Receivables & Cash Flow")
st.caption(
    "Task 12 - Receivables ageing, client payment behaviour "
    "and monthly cash movement"
)

DB_PATH = Path(__file__).resolve().parent / "pulseiq.duckdb"

OPEN_STATUSES = ["SENT", "OVERDUE", "PARTIALLY_PAID"]

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

        # Open invoices: only the three statuses specified
        # in the Task 12 instructions.

        open_invoices = con.execute("""
            SELECT
                i.invoice_id,
                i.invoice_number,
                i.client_id,
                c.client_name,
                i.invoice_date,
                i.due_date,
                i.total_amount,
                i.amount_paid,
                i.balance_due,
                i.status,
                i.days_past_due_at_cutoff,
                i.ageing_bucket_at_cutoff
            FROM raw.fact_invoice i
            LEFT JOIN raw.dim_client c
                ON i.client_id = c.client_id
            WHERE i.status IN (
                'SENT',
                'OVERDUE',
                'PARTIALLY_PAID'
            )
              AND i.balance_due > 0
        """).fetchdf()

        # Ageing buckets.
        # Not-yet-due invoices are included in 0-30 days
        # so all four buckets reconcile to total open AR.

        ageing = con.execute("""
            SELECT
                CASE
                    WHEN days_past_due_at_cutoff <= 30
                        THEN '0-30 days'
                    WHEN days_past_due_at_cutoff <= 60
                        THEN '31-60 days'
                    WHEN days_past_due_at_cutoff <= 90
                        THEN '61-90 days'
                    ELSE '90+ days'
                END AS ageing_bucket,

                COUNT(*) AS invoice_count,
                ROUND(SUM(balance_due), 2)
                    AS outstanding_amount

            FROM raw.fact_invoice

            WHERE status IN (
                'SENT',
                'OVERDUE',
                'PARTIALLY_PAID'
            )
              AND balance_due > 0

            GROUP BY 1

            ORDER BY
                CASE
                    WHEN ageing_bucket = '0-30 days' THEN 1
                    WHEN ageing_bucket = '31-60 days' THEN 2
                    WHEN ageing_bucket = '61-90 days' THEN 3
                    ELSE 4
                END
        """).fetchdf()

        # Average days to pay by client.
        # Paid invoices with valid days_to_pay only.

        client_payment = con.execute("""
            SELECT
                c.client_name,
                COUNT(*) AS paid_invoice_count,

                ROUND(
                    AVG(i.days_to_pay),
                    2
                ) AS average_days_to_pay,

                MAX(c.payment_terms_days)
                    AS payment_terms_days

            FROM raw.fact_invoice i

            JOIN raw.dim_client c
                ON i.client_id = c.client_id

            WHERE i.status = 'PAID'
              AND i.days_to_pay IS NOT NULL

            GROUP BY c.client_name

            ORDER BY average_days_to_pay DESC
        """).fetchdf()

        # Overdue clients.
        # Only invoices actually past due are included.

        overdue_clients = con.execute("""
            SELECT
                c.client_name,

                COUNT(*) AS overdue_invoice_count,

                ROUND(
                    SUM(i.balance_due),
                    2
                ) AS overdue_amount,

                MAX(i.days_past_due_at_cutoff)
                    AS max_days_overdue

            FROM raw.fact_invoice i

            JOIN raw.dim_client c
                ON i.client_id = c.client_id

            WHERE i.status IN (
                'SENT',
                'OVERDUE',
                'PARTIALLY_PAID'
            )
              AND i.days_past_due_at_cutoff > 0
              AND i.balance_due > 0

            GROUP BY c.client_name

            ORDER BY overdue_amount DESC
        """).fetchdf()

        # Monthly cash received from invoice payments.

        cash_in = con.execute("""
            SELECT
                DATE_TRUNC(
                    'month',
                    payment_date
                )::DATE AS month,

                ROUND(
                    SUM(amount),
                    2
                ) AS cash_in

            FROM raw.fact_invoice_payment

            WHERE payment_date IS NOT NULL

            GROUP BY 1
        """).fetchdf()

        # Monthly cash paid from actual paid expenses.
        # Unpaid expenses are excluded.

        cash_out = con.execute("""
            SELECT
                DATE_TRUNC(
                    'month',
                    paid_date
                )::DATE AS month,

                ROUND(
                    SUM(total_amount),
                    2
                ) AS cash_out

            FROM raw.fact_expense

            WHERE status = 'PAID'
              AND paid_date IS NOT NULL

            GROUP BY 1
        """).fetchdf()

        # Merge cash in and cash out by month.

        monthly_cash = pd.merge(
            cash_in,
            cash_out,
            on="month",
            how="outer"
        )

        monthly_cash["cash_in"] = (
            monthly_cash["cash_in"].fillna(0)
        )

        monthly_cash["cash_out"] = (
            monthly_cash["cash_out"].fillna(0)
        )

        monthly_cash["net_cash_movement"] = (
            monthly_cash["cash_in"]
            - monthly_cash["cash_out"]
        )

        monthly_cash = monthly_cash.sort_values(
            "month"
        ).reset_index(drop=True)

        # Total open receivables.

        total_open = con.execute("""
            SELECT
                COUNT(*) AS invoice_count,

                ROUND(
                    SUM(balance_due),
                    2
                ) AS total_open_receivables

            FROM raw.fact_invoice

            WHERE status IN (
                'SENT',
                'OVERDUE',
                'PARTIALLY_PAID'
            )
              AND balance_due > 0
        """).fetchdf()

        return (
            open_invoices,
            ageing,
            client_payment,
            overdue_clients,
            monthly_cash,
            total_open
        )

    finally:
        con.close()


data = load_data(
    str(DB_PATH),
    DB_PATH.stat().st_mtime
)

(
    open_invoices,
    ageing,
    client_payment,
    overdue_clients,
    monthly_cash,
    total_open
) = data


# ---------------------------------------------------------
# 3. FILTERS
# ---------------------------------------------------------

st.sidebar.header("Dashboard Filters")

selected_statuses = st.sidebar.multiselect(
    "Invoice Status",
    options=OPEN_STATUSES,
    default=OPEN_STATUSES
)

if not selected_statuses:
    selected_statuses = OPEN_STATUSES

filtered_invoices = open_invoices[
    open_invoices["status"].isin(selected_statuses)
].copy()


# ---------------------------------------------------------
# 4. KEY RECEIVABLES METRICS
# ---------------------------------------------------------

st.subheader("1. Receivables Overview")

filtered_total = filtered_invoices["balance_due"].sum()

filtered_count = len(filtered_invoices)

overdue_total = filtered_invoices.loc[
    filtered_invoices["days_past_due_at_cutoff"] > 0,
    "balance_due"
].sum()

col1, col2, col3 = st.columns(3)

col1.metric(
    "Open Receivables",
    f"₹{filtered_total:,.0f}"
)

col2.metric(
    "Open Invoices",
    f"{filtered_count:,}"
)

col3.metric(
    "Overdue Amount",
    f"₹{overdue_total:,.0f}"
)

st.caption(
    "Open statuses: SENT, OVERDUE and PARTIALLY_PAID. "
    "DRAFT and CANCELLED invoices are excluded."
)


# ---------------------------------------------------------
# 5. RECEIVABLES AGEING ANALYSIS
# ---------------------------------------------------------

st.subheader("2. Receivables Ageing Analysis")

ageing_display = ageing.copy()

bucket_total = ageing_display[
    "outstanding_amount"
].sum()

all_open_total = float(
    total_open.loc[0, "total_open_receivables"]
)

difference = bucket_total - all_open_total

ageing_col1, ageing_col2, ageing_col3 = st.columns(3)

ageing_col1.metric(
    "Total Open Receivables",
    f"₹{all_open_total:,.0f}"
)

ageing_col2.metric(
    "Ageing Bucket Total",
    f"₹{bucket_total:,.0f}"
)

ageing_col3.metric(
    "Reconciliation Difference",
    f"₹{difference:,.2f}"
)

if abs(difference) < 0.01:
    st.success(
        "PASS: Ageing bucket total matches total open receivables."
    )
else:
    st.error(
        "FAIL: Ageing bucket total does not match open receivables."
    )

st.caption(
    "Bucket definition: 0-30 days includes invoices not yet due "
    "and invoices up to 30 days past due. The remaining buckets "
    "represent 31-60, 61-90 and 90+ days past due."
)

fig_ageing = px.bar(
    ageing_display,
    x="ageing_bucket",
    y="outstanding_amount",
    color="ageing_bucket",
    text="outstanding_amount",
    title="Outstanding Receivables by Ageing Bucket",
    labels={
        "ageing_bucket": "Ageing Bucket",
        "outstanding_amount": "Outstanding Amount (₹)"
    }
)

fig_ageing.update_traces(
    texttemplate="₹%{text:,.0f}",
    textposition="outside"
)

st.plotly_chart(
    fig_ageing,
    use_container_width=True
)

st.dataframe(
    ageing_display,
    use_container_width=True,
    hide_index=True
)


# ---------------------------------------------------------
# 6. TOP OVERDUE CLIENTS
# ---------------------------------------------------------

st.subheader("3. Clients with Highest Overdue Amount")

if overdue_clients.empty:

    st.info("No overdue invoices found.")

else:

    top_overdue = overdue_clients.head(10)

    fig_overdue = px.bar(
        top_overdue.sort_values("overdue_amount"),
        x="overdue_amount",
        y="client_name",
        orientation="h",
        text="overdue_amount",
        title="Top 10 Clients by Overdue Receivables",
        labels={
            "overdue_amount": "Overdue Amount (₹)",
            "client_name": "Client"
        }
    )

    fig_overdue.update_traces(
        texttemplate="₹%{text:,.0f}",
        textposition="outside"
    )

    st.plotly_chart(
        fig_overdue,
        use_container_width=True
    )

    st.dataframe(
        top_overdue,
        use_container_width=True,
        hide_index=True
    )


# ---------------------------------------------------------
# 7. CLIENT PAYMENT BEHAVIOUR
# ---------------------------------------------------------

st.subheader("4. Average Days to Pay by Client")

payment_display = client_payment.copy()

payment_display["days_over_terms"] = (
    payment_display["average_days_to_pay"]
    - payment_display["payment_terms_days"]
)

payment_display = payment_display.sort_values(
    "average_days_to_pay",
    ascending=False
)

fig_payment = px.bar(
    payment_display.head(15).sort_values(
        "average_days_to_pay"
    ),
    x="average_days_to_pay",
    y="client_name",
    orientation="h",
    color="days_over_terms",
    title="15 Slowest-Paying Clients",
    labels={
        "average_days_to_pay": "Average Days to Pay",
        "client_name": "Client",
        "days_over_terms": "Days Above Payment Terms"
    }
)

st.plotly_chart(
    fig_payment,
    use_container_width=True
)

st.dataframe(
    payment_display,
    use_container_width=True,
    hide_index=True
)

st.caption(
    "Average payment days are calculated from paid invoices "
    "with a recorded days_to_pay value. Payment terms are "
    "shown for comparison."
)


# ---------------------------------------------------------
# 8. MONTHLY CASH IN VS CASH OUT
# ---------------------------------------------------------

st.subheader("5. Monthly Cash In vs Cash Out")

if not monthly_cash.empty:

    cash_chart_data = monthly_cash.melt(
        id_vars=["month"],
        value_vars=["cash_in", "cash_out"],
        var_name="cash_type",
        value_name="amount"
    )

    fig_cash = px.bar(
        cash_chart_data,
        x="month",
        y="amount",
        color="cash_type",
        barmode="group",
        title="Monthly Cash Received vs Paid Expenses",
        labels={
            "month": "Month",
            "amount": "Amount (₹)",
            "cash_type": "Cash Movement"
        }
    )

    st.plotly_chart(
        fig_cash,
        use_container_width=True
    )

    fig_net = px.line(
        monthly_cash,
        x="month",
        y="net_cash_movement",
        markers=True,
        title="Monthly Net Cash Movement",
        labels={
            "month": "Month",
            "net_cash_movement": "Net Cash Movement (₹)"
        }
    )

    st.plotly_chart(
        fig_net,
        use_container_width=True
    )

    st.dataframe(
        monthly_cash,
        use_container_width=True,
        hide_index=True
    )

st.caption(
    "Cash in represents recorded invoice payments. Cash out "
    "represents paid expenses with a payment date. This view "
    "does not include payroll or other unrecorded cash outflows "
    "and should not be interpreted as total company cash flow."
)


# ---------------------------------------------------------
# 9. BUSINESS INSIGHTS
# ---------------------------------------------------------

st.subheader("6. Business Insights")

if not overdue_clients.empty:

    highest_client = overdue_clients.iloc[0]

    st.write(
        f"**Highest overdue balance:** "
        f"{highest_client['client_name']} has "
        f"₹{highest_client['overdue_amount']:,.0f} overdue."
    )

if not payment_display.empty:

    slowest_client = payment_display.iloc[0]

    st.write(
        f"**Slowest average payer:** "
        f"{slowest_client['client_name']} takes "
        f"{slowest_client['average_days_to_pay']:.2f} days "
        f"on average, against payment terms of "
        f"{slowest_client['payment_terms_days']} days."
    )

if not monthly_cash.empty:

    best_cash_month = monthly_cash.loc[
        monthly_cash["cash_in"].idxmax()
    ]

    st.write(
        f"**Highest cash collection month:** "
        f"{best_cash_month['month'].strftime('%B %Y')} "
        f"with ₹{best_cash_month['cash_in']:,.0f} received."
    )


# ---------------------------------------------------------
# 10. FINANCE RISK THINKING
# ---------------------------------------------------------

st.subheader("7. Finance Risk Discussion")

st.markdown("""
**Scenario:** A client consistently pays after 75 days.

This may create a cash-flow and collection risk when the
agreed payment terms are shorter than 75 days.

Questions to discuss with the finance team:

1. Is the client regularly exceeding the agreed payment terms?
2. What is the total outstanding balance for this client?
3. Are there invoice disputes or approval delays?
4. Should the credit limit or payment terms be reviewed?
5. Would advance payments, milestone billing or collection
   reminders reduce the risk?
""")


# ---------------------------------------------------------
# 11. OPEN INVOICE DETAILS
# ---------------------------------------------------------

st.subheader("8. Open Invoice Details")

st.dataframe(
    filtered_invoices,
    use_container_width=True,
    hide_index=True
)


# ---------------------------------------------------------
# 12. EVIDENCE DOWNLOADS
# ---------------------------------------------------------

st.subheader("9. Task 12 Evidence Downloads")

st.download_button(
    "Download Receivables Ageing CSV",
    data=ageing.to_csv(index=False).encode("utf-8"),
    file_name="task12_receivables_ageing.csv",
    mime="text/csv"
)

st.download_button(
    "Download Top Overdue Clients CSV",
    data=overdue_clients.to_csv(index=False).encode("utf-8"),
    file_name="task12_overdue_clients.csv",
    mime="text/csv"
)

st.download_button(
    "Download Client Payment Days CSV",
    data=payment_display.to_csv(index=False).encode("utf-8"),
    file_name="task12_client_payment_days.csv",
    mime="text/csv"
)

st.download_button(
    "Download Monthly Cash Flow CSV",
    data=monthly_cash.to_csv(index=False).encode("utf-8"),
    file_name="task12_monthly_cash.csv",
    mime="text/csv"
)

st.caption(
    "Task 12 | PulseIQ Finance Analytics | "
    "Receivables, ageing, client payment behaviour "
    "and recorded monthly cash movements."
)
