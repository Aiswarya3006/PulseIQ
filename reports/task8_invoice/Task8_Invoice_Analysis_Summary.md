# Task 8 â€” Invoice & Cash Flow Insights

**Cutoff date:** 30 September 2026

## Reconciliation
- Calculated closing receivables: â‚¹139,394,278.00
- Expected closing receivables: â‚¹139,394,278.00
- Difference: â‚¹0.00
- Calculated bank balance (account 1001): â‚¹290,962,361.45
- Expected bank balance: â‚¹290,962,361.45
- Difference: â‚¹0.00

## DSO (M20)
DSO = closing receivables Ã· invoice revenue including GST for the last 90 days Ã— 90.
- 90-day revenue including GST: â‚¹261,376,644.00
- DSO: 48.00 days

## Projection assumptions
1. Only positive-balance invoices due after 30-Sep-2026 are treated as expected collections.
2. Only UNPAID expenses due after 30-Sep-2026 are included as projected cash outflows.
3. Due dates are used as a simple timing proxy; actual collection/payment timing may differ.
4. December values are zero where no matching due-date records exist; this does not prove there will be no December cash flow.
5. Projection is a net movement estimate, not a full forecast of closing bank balance.
6. DRAFT and CANCELLED invoices are excluded from receivables.
7. Source data is not modified. Differences are documented for review.

## Projection
| month   |   Expected collections |   Expected unpaid expenses |   Net projected movement |
|:--------|-----------------------:|---------------------------:|-------------------------:|
| 2026-10 |            7.98536e+07 |                7.59607e+06 |              7.22575e+07 |
| 2026-11 |            3.24298e+07 |                2.32406e+06 |              3.01058e+07 |
| 2026-12 |            0           |                0           |              0           |

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

## Reconciliation findings — Final validation

- Bank account 1001 reconciles successfully: calculated and expected balance are both INR 290,962,361.45.
- Invoice INV-00385 (journal entry JE-001194) requires review. Invoice amount_paid is INR 1,049,828, while recorded payments total INR 1,049,728, leaving a INR 100 discrepancy and a negative INR 100 balance due.
- The overall invoice-payment reconciliation difference is -INR 100.
- Original source data was not changed. The discrepancy remains documented for investigation.

