
from pathlib import Path
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

FILE = "raw/03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx"
TODAY = pd.Timestamp("2026-09-30")
OUT = Path("reports/task8_invoice")
OUT.mkdir(parents=True, exist_ok=True)

# ---------- Load source data ----------
inv = pd.read_excel(FILE, sheet_name="fact_invoice")
pay = pd.read_excel(FILE, sheet_name="fact_invoice_payment")
exp = pd.read_excel(FILE, sheet_name="fact_expense")

ledger = pd.read_excel(FILE, sheet_name="fact_ledger")
clients = pd.read_excel(FILE, sheet_name="dim_client")

for df, cols in [
    (inv, ["invoice_date", "due_date"]),
    (pay, ["payment_date"]),
    (exp, ["expense_date", "due_date", "paid_date"]),
]:
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

for df, cols in [
    (inv, ["total_amount", "amount_paid", "balance_due"]),
    (pay, ["amount"]),
    (exp, ["total_amount"]),
]:
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

# Find client-name column without assuming its exact name
name_cols = [
    c for c in clients.columns
    if c.lower() in ["client_name", "client", "name"]
]
if "client_id" in clients.columns and name_cols:
    inv = inv.merge(
        clients[["client_id", name_cols[0]]].drop_duplicates("client_id"),
        on="client_id", how="left"
    )
    inv = inv.rename(columns={name_cols[0]: "client_name"})
else:
    inv["client_name"] = inv["client_id"].astype(str)

# Exclude drafts and cancelled invoices from receivables
eligible = inv[~inv["status"].isin(["DRAFT", "CANCELLED"])].copy()
receivables = eligible[eligible["balance_due"] > 0].copy()

# ---------- 1. Ageing as at 30 Sep 2026 ----------
receivables["days_past_due"] = (
    TODAY - receivables["due_date"]
).dt.days

def ageing(days):
    if pd.isna(days) or days <= 0:
        return "Not yet due"
    if days <= 30:
        return "1-30 days"
    if days <= 60:
        return "31-60 days"
    if days <= 90:
        return "61-90 days"
    return "90+ days"

receivables["ageing_bucket"] = receivables["days_past_due"].apply(ageing)
bucket_order = [
    "Not yet due", "1-30 days", "31-60 days",
    "61-90 days", "90+ days"
]
ageing_summary = (
    receivables.groupby("ageing_bucket")["balance_due"]
    .agg(invoice_count="count", outstanding="sum")
    .reindex(bucket_order, fill_value=0)
    .reset_index()
)

# ---------- 2. Monthly invoiced vs collected ----------
eligible["month"] = eligible["invoice_date"].dt.to_period("M").astype(str)
pay["month"] = pay["payment_date"].dt.to_period("M").astype(str)

invoiced = eligible.groupby("month")["total_amount"].sum().rename("Invoiced")
collected = pay.groupby("month")["amount"].sum().rename("Collected")

monthly_invoice_collection = pd.concat(
    [invoiced, collected], axis=1
).fillna(0).sort_index().reset_index()

# ---------- 3. Overdue invoices by client ----------
overdue = receivables[
    receivables["due_date"].notna()
    & (receivables["due_date"] < TODAY)
].copy()

overdue_by_client = (
    overdue.groupby("client_name")
    .agg(
        overdue_invoice_count=("invoice_id", "nunique"),
        overdue_balance=("balance_due", "sum"),
    )
    .sort_values("overdue_balance", ascending=False)
    .reset_index()
)

# ---------- 4. Cash in vs cash out by month ----------
cash_in = pay.dropna(subset=["payment_date"]).copy()
cash_in["month"] = cash_in["payment_date"].dt.to_period("M").astype(str)
cash_in = cash_in.groupby("month")["amount"].sum().rename("Cash in")

paid_exp = exp[
    exp["status"].eq("PAID") & exp["paid_date"].notna()
].copy()
paid_exp["month"] = paid_exp["paid_date"].dt.to_period("M").astype(str)
cash_out = paid_exp.groupby("month")["total_amount"].sum().rename("Cash out")

cash_flow = pd.concat([cash_in, cash_out], axis=1).fillna(0)
cash_flow = cash_flow.sort_index().reset_index()

# ---------- 5. Three-month due-date projection ----------
future_inv = receivables[
    receivables["due_date"] > TODAY
].copy()
future_inv["month"] = future_inv["due_date"].dt.to_period("M").astype(str)

future_exp = exp[
    exp["status"].eq("UNPAID")
    & exp["due_date"].notna()
    & (exp["due_date"] > TODAY)
].copy()
future_exp["month"] = future_exp["due_date"].dt.to_period("M").astype(str)

months = ["2026-10", "2026-11", "2026-12"]
projection = pd.DataFrame({"month": months})

projection["Expected collections"] = projection["month"].map(
    future_inv.groupby("month")["balance_due"].sum()
).fillna(0)

projection["Expected unpaid expenses"] = projection["month"].map(
    future_exp.groupby("month")["total_amount"].sum()
).fillna(0)

projection["Net projected movement"] = (
    projection["Expected collections"]
    - projection["Expected unpaid expenses"]
)

# ---------- 6. DSO: M20 ----------
# Revenue including GST, invoice-date basis, last 90 days through cutoff
start_90 = TODAY - pd.Timedelta(days=89)
recent_invoices = eligible[
    eligible["invoice_date"].between(start_90, TODAY)
]
revenue_90 = recent_invoices["total_amount"].sum()
closing_ar = receivables["balance_due"].sum()
dso = closing_ar / revenue_90 * 90 if revenue_90 else None

# ---------- 7. Reconciliation ----------
bank_rows = ledger[
    ledger["account_code"].astype(str).str.strip().eq("1001")
]
bank_balance = pd.to_numeric(
    bank_rows["signed_amount_debit_positive"], errors="coerce"
).fillna(0).sum()

expected_ar = 139394278.00
expected_bank = 290962361.45

reconciliation = pd.DataFrame([
    {
        "Metric": "Closing receivables at 30-Sep-2026",
        "Calculated": round(closing_ar, 2),
        "Expected": expected_ar,
        "Difference": round(closing_ar - expected_ar, 2),
    },
    {
        "Metric": "Bank balance (account 1001)",
        "Calculated": round(bank_balance, 2),
        "Expected": expected_bank,
        "Difference": round(bank_balance - expected_bank, 2),
    },
    {
        "Metric": "Invoice payments vs invoice amount_paid",
        "Calculated": round(pay["amount"].sum(), 2),
        "Expected": round(inv["amount_paid"].sum(), 2),
        "Difference": round(pay["amount"].sum() - inv["amount_paid"].sum(), 2),
    },
])

# ---------- 8. Charts ----------
def save_bar(data, x, y, title, filename, rotation=35):
    ax = data.plot(x=x, y=y, kind="bar", legend=False, figsize=(10, 5))
    ax.set_title(title)
    ax.set_xlabel(x.replace("_", " ").title())
    ax.set_ylabel("Amount (INR)")
    plt.xticks(rotation=rotation, ha="right")
    plt.tight_layout()
    plt.savefig(OUT / filename, dpi=150)
    plt.close()

save_bar(
    monthly_invoice_collection, "month",
    ["Invoiced", "Collected"],
    "Monthly Invoiced vs Collected",
    "invoiced_vs_collected_monthly.png"
) if False else None

ax = monthly_invoice_collection.set_index("month")[
    ["Invoiced", "Collected"]
].plot(kind="bar", figsize=(11, 5))
ax.set_title("Monthly Invoiced vs Collected")
ax.set_ylabel("Amount (INR)")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.savefig(OUT / "invoiced_vs_collected_monthly.png", dpi=150)
plt.close()

save_bar(
    overdue_by_client.head(15), "client_name", "overdue_balance",
    "Top 15 Clients by Overdue Balance", "overdue_by_client.png"
)

ax = cash_flow.set_index("month")[["Cash in", "Cash out"]].plot(
    kind="line", marker="o", figsize=(11, 5)
)
ax.set_title("Monthly Cash In vs Cash Out")
ax.set_ylabel("Amount (INR)")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.savefig(OUT / "cash_in_vs_cash_out.png", dpi=150)
plt.close()

save_bar(
    ageing_summary, "ageing_bucket", "outstanding",
    "Outstanding Receivables by Ageing", "outstanding_balance_by_ageing.png"
)

ax = projection.set_index("month")[
    ["Expected collections", "Expected unpaid expenses"]
].plot(kind="bar", figsize=(9, 5))
ax.set_title("3-Month Cash Projection Based on Due Dates")
ax.set_ylabel("Amount (INR)")
plt.xticks(rotation=0)
plt.tight_layout()
plt.savefig(OUT / "three_month_cash_projection.png", dpi=150)
plt.close()

# Existing status chart
inv["status"].fillna("MISSING").value_counts().plot(
    kind="bar", title="Invoice Count by Status", figsize=(8, 4)
)
plt.xlabel("Invoice Status")
plt.ylabel("Invoice Count")
plt.tight_layout()
plt.savefig(OUT / "invoice_count_by_status.png", dpi=150)
plt.close()

# ---------- 9. Excel dashboard export ----------
# Excel tables have filters, including client and status on invoice detail.
detail_cols = [
    c for c in [
        "invoice_id", "invoice_number", "client_id", "client_name",
        "invoice_date", "due_date", "total_amount", "amount_paid",
        "balance_due", "status", "days_past_due_at_cutoff"
    ] if c in inv.columns
]

dashboard = inv[detail_cols].copy()
summary = pd.DataFrame([
    ["Cutoff date", "2026-09-30"],
    ["Closing receivables", round(closing_ar, 2)],
    ["Expected receivables", expected_ar],
    ["Bank balance", round(bank_balance, 2)],
    ["Expected bank balance", expected_bank],
    ["Revenue including GST, last 90 days", round(revenue_90, 2)],
    ["DSO (days)", round(dso, 2) if dso is not None else "N/A"],
])

with pd.ExcelWriter(OUT / "Task8_Invoice_Cashflow_Dashboard.xlsx",
                    engine="openpyxl") as writer:
    summary.to_excel(writer, sheet_name="Dashboard Summary", index=False,
                     header=["Metric", "Value"])
    monthly_invoice_collection.to_excel(
        writer, sheet_name="Monthly Invoice Collection", index=False
    )
    overdue_by_client.to_excel(
        writer, sheet_name="Overdue by Client", index=False
    )
    cash_flow.to_excel(writer, sheet_name="Cash In Out", index=False)
    ageing_summary.to_excel(writer, sheet_name="Ageing", index=False)
    projection.to_excel(writer, sheet_name="Cash Projection", index=False)
    reconciliation.to_excel(writer, sheet_name="Reconciliation", index=False)
    dashboard.to_excel(writer, sheet_name="Invoice Detail", index=False)

    for ws in writer.book.worksheets:
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for col_cells in ws.columns:
            letter = col_cells[0].column_letter
            max_len = max(
                (len(str(cell.value)) if cell.value is not None else 0)
                for cell in col_cells
            )
            ws.column_dimensions[letter].width = min(max_len + 2, 35)

# ---------- 10. Written assumptions and insights ----------
insights = f"""# Task 8 — Invoice & Cash Flow Insights

**Cutoff date:** 30 September 2026

## Reconciliation
- Calculated closing receivables: ₹{closing_ar:,.2f}
- Expected closing receivables: ₹{expected_ar:,.2f}
- Difference: ₹{closing_ar - expected_ar:,.2f}
- Calculated bank balance (account 1001): ₹{bank_balance:,.2f}
- Expected bank balance: ₹{expected_bank:,.2f}
- Difference: ₹{bank_balance - expected_bank:,.2f}

## DSO (M20)
DSO = closing receivables ÷ invoice revenue including GST for the last 90 days × 90.
- 90-day revenue including GST: ₹{revenue_90:,.2f}
- DSO: {dso:.2f} days

## Projection assumptions
1. Only positive-balance invoices due after 30-Sep-2026 are treated as expected collections.
2. Only UNPAID expenses due after 30-Sep-2026 are included as projected cash outflows.
3. Due dates are used as a simple timing proxy; actual collection/payment timing may differ.
4. December values are zero where no matching due-date records exist; this does not prove there will be no December cash flow.
5. Projection is a net movement estimate, not a full forecast of closing bank balance.
6. DRAFT and CANCELLED invoices are excluded from receivables.
7. Source data is not modified. Differences are documented for review.

## Projection
{projection.to_markdown(index=False)}

## Data-quality note
Invoice payment totals and invoice amount_paid totals may differ. Investigate invoice-level differences without silently changing the source data.

## Dashboard contents
- Monthly invoiced vs collected
- Overdue invoices by client
- Cash in vs cash out
- Receivables ageing
- Three-month due-date projection
- Invoice Detail sheet with client and status filters
- Reconciliation table
"""
(OUT / "Task8_Invoice_Analysis_Summary.md").write_text(
    insights, encoding="utf-8"
)
Path("reports/insights-cashflow.md").write_text(insights, encoding="utf-8")

# Export tables as standalone CSVs too
ageing_summary.to_csv(OUT / "receivables_ageing.csv", index=False)
monthly_invoice_collection.to_csv(
    OUT / "monthly_invoiced_vs_collected.csv", index=False
)
overdue_by_client.to_csv(OUT / "overdue_by_client.csv", index=False)
cash_flow.to_csv(OUT / "monthly_cash_in_out.csv", index=False)
projection.to_csv(OUT / "three_month_cash_projection.csv", index=False)
reconciliation.to_csv(OUT / "reconciliation.csv", index=False)

print("\nTask 8 outputs created:")
for path in sorted(OUT.iterdir()):
    if path.is_file():
        print(path)
print("\nReceivables:", round(closing_ar, 2))
print("Expected receivables:", expected_ar)
print("Bank balance:", round(bank_balance, 2))
print("Expected bank balance:", expected_bank)
print("DSO:", round(dso, 2) if dso is not None else "N/A")
