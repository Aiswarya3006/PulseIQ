# PulseIQ – Task 12: Invoices, Receivables & Cash Flow

## Objective
Analyse invoice receivables, ageing, client payment behaviour, overdue balances and monthly cash movements.

## Data Sources
- `raw.fact_invoice`
- `raw.fact_invoice_payment`
- `raw.dim_client`
- `raw.fact_expense`

## Business Rules
- Open invoice statuses: `SENT`, `OVERDUE`, `PARTIALLY_PAID`.
- Ageing buckets: 0–30, 31–60, 61–90 and 90+ days.
- Average days to pay is calculated using paid invoices with available `days_to_pay`.
- Cash in is based on recorded invoice payments.
- Cash out includes paid expenses with a recorded payment date.

## Key Results

| Metric | Result |
|---|---:|
| Open invoices | 62 |
| Total open receivables | ₹139,394,278 |
| Overdue amount | ₹27,110,866 |
| Ageing bucket total | ₹139,394,278 |
| Reconciliation difference | ₹0.00 |

## Receivables Ageing

| Ageing bucket | Invoice count | Outstanding amount |
|---|---:|---:|
| 0–30 days | 59 | ₹134,417,038 |
| 31–60 days | 0 | ₹0 |
| 61–90 days | 1 | ₹1,940,982 |
| 90+ days | 2 | ₹3,036,258 |

**Reconciliation:** PASS – Ageing bucket total matches total open receivables.

Note: The 0–30 days bucket includes invoices not yet due and invoices up to 30 days past due.

## Key Business Insights
- Marina Media Works has the highest overdue balance of ₹7,110,208.
- Siruvani Agro Tech has an invoice 548 days overdue.
- Triveni Steel Industries has an invoice 438 days overdue.
- Triveni Steel Industries has the highest average payment time at 121.25 days, against 60-day payment terms.
- July 2026 has the highest recorded monthly cash collection at approximately ₹113,663,012.

## Cash Flow Scope
Cash in represents recorded invoice payments. Cash out represents paid expenses with a payment date. Payroll and other unrecorded cash outflows are excluded; therefore, this analysis is not total company cash flow.

## Evidence Files
- `task12_dashboard.png`
- `task12_ageing_reconciliation.png`
- `task12_receivables_ageing.csv`
- `task12_overdue_clients.csv`
- `task12_client_payment_days.csv`
- `task12_monthly_cash.csv`

## Finance Risk Discussion
A client consistently paying after 75 days may create collection and cash-flow risk when payment terms are shorter. Finance should review overdue balances, payment behaviour, invoice disputes, credit limits and possible changes to payment terms.

## Deliverable
A Streamlit dashboard providing receivables ageing, overdue client analysis, average days to pay, monthly cash movement and a reconciliation check.
