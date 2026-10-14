
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
RAW_FILE = ROOT / "raw" / "03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx"
OUT = ROOT / "reports" / "task7_ledger_analytics"
CHARTS = OUT / "charts"

OUT.mkdir(parents=True, exist_ok=True)
CHARTS.mkdir(parents=True, exist_ok=True)


def load_sheet(sheet):
    return pd.read_excel(RAW_FILE, sheet_name=sheet)


def save_csv(df, filename):
    df.to_csv(OUT / filename, index=False)


def main():
    print("Loading Task 7 datasets...")

    ledger = load_sheet("fact_ledger")
    accounts = load_sheet("dim_account")
    answer = load_sheet("reconciliation_answer_key")
    known_issues = load_sheet("dq_known_issues")

    # Standardize account codes for reliable joins.
    ledger["account_code"] = (
        pd.to_numeric(ledger["account_code"], errors="coerce")
        .astype("Int64")
    )
    accounts["account_code"] = (
        pd.to_numeric(accounts["account_code"], errors="coerce")
        .astype("Int64")
    )

    ledger["entry_date"] = pd.to_datetime(
        ledger["entry_date"], errors="coerce"
    )
    ledger["posting_period"] = ledger["entry_date"].dt.strftime("%Y-%m")

    for col in ["debit", "credit", "signed_amount_debit_positive"]:
        ledger[col] = pd.to_numeric(ledger[col], errors="coerce").fillna(0)

    ledger = ledger.merge(
        accounts[
            [
                "account_code", "account_name", "account_type",
                "normal_balance", "statement", "is_group"
            ]
        ],
        on="account_code",
        how="left",
        validate="many_to_one"
    )

    # 1. Data quality and structural checks.
    duplicate_lines = ledger[
        ledger["line_id"].duplicated(keep=False)
    ].copy()

    unmapped_accounts = ledger[
        ledger["account_name"].isna()
    ].copy()

    entry_balance = (
        ledger.groupby("entry_id", dropna=False)
        .agg(
            line_count=("line_id", "count"),
            total_debit=("debit", "sum"),
            total_credit=("credit", "sum"),
            signed_difference=(
                "signed_amount_debit_positive", "sum"
            ),
        )
        .reset_index()
    )
    entry_balance["is_balanced"] = (
        entry_balance["signed_difference"].abs() <= 0.01
    )

    # 2. Account-wise analysis.
    # Group/header accounts are excluded to avoid double counting.
    posting = ledger[
        ledger["is_group"].astype(str).str.upper().ne("Y")
    ].copy()

    account_summary = (
        posting.groupby(
            [
                "account_code", "account_name", "account_type",
                "normal_balance", "statement"
            ],
            dropna=False
        )
        .agg(
            line_count=("line_id", "count"),
            total_debit=("debit", "sum"),
            total_credit=("credit", "sum"),
            net_debit_positive=(
                "signed_amount_debit_positive", "sum"
            ),
        )
        .reset_index()
        .sort_values(["account_type", "account_code"])
    )

    # 3. Monthly totals using the account dimension.
    # Income has a credit-normal balance, so revenue is reported positive.
    income = posting[posting["account_type"].eq("INCOME")]
    expenses = posting[posting["account_type"].eq("EXPENSE")]

    monthly_revenue = (
        income.groupby("posting_period")[
            "signed_amount_debit_positive"
        ].sum().mul(-1).rename("ledger_revenue")
    )

    monthly_expense = (
        expenses.groupby("posting_period")[
            "signed_amount_debit_positive"
        ].sum().rename("ledger_total_expense")
    )

    # Salary-related expenses: salaries, overtime, incentives/bonus,
    # employer PF and employer ESI.
    salary_codes = [5001, 5002, 5003, 5004, 5005]
    salary_rows = posting[
        posting["account_code"].isin(salary_codes)
    ]

    monthly_salary = (
        salary_rows.groupby("posting_period")[
            "signed_amount_debit_positive"
        ].sum().rename("ledger_salary_related_expense")
    )

    # Monthly bank and receivables movement.
    bank_rows = posting[posting["account_code"].eq(1001)]
    ar_rows = posting[posting["account_code"].eq(1100)]

    monthly_bank_movement = (
        bank_rows.groupby("posting_period")[
            "signed_amount_debit_positive"
        ].sum().rename("bank_movement")
    )
    monthly_ar_movement = (
        ar_rows.groupby("posting_period")[
            "signed_amount_debit_positive"
        ].sum().rename("receivables_movement")
    )

    monthly = pd.concat(
        [
            monthly_revenue,
            monthly_expense,
            monthly_salary,
            monthly_bank_movement,
            monthly_ar_movement,
        ],
        axis=1
    ).fillna(0).reset_index().rename(
        columns={"posting_period": "month"}
    )

    monthly["ledger_net_profit"] = (
        monthly["ledger_revenue"] - monthly["ledger_total_expense"]
    )

    # Reconstruct closing balances cumulatively across all ledger periods.
    monthly = monthly.sort_values("month").reset_index(drop=True)
    monthly["bank_closing_balance"] = monthly["bank_movement"].cumsum()
    monthly["receivables_closing_balance"] = (
        monthly["receivables_movement"].cumsum()
    )

    # 4. Reconciliation against the supplied answer key.
    answer["month"] = pd.to_datetime(
        answer["month"], errors="coerce"
    ).dt.strftime("%Y-%m")

    reconcile = answer.merge(
        monthly,
        on="month",
        how="outer",
        suffixes=("_expected", "_calculated"),
        indicator=True
    )

    compare_fields = [
        ("ledger_salary_related_expense", "payroll_employer_cost"),
        ("ledger_revenue", "ledger_revenue"),
        ("ledger_total_expense", "ledger_total_expense"),
        ("ledger_net_profit", "ledger_net_profit"),
        ("bank_closing_balance", "bank_closing_balance"),
        ("receivables_closing_balance", "receivables_closing_balance"),
    ]

    # Compare expected answer-key values against our calculated values.
    for metric, expected_col in compare_fields:
        calculated_col = (
            f"{metric}_calculated"
            if f"{metric}_calculated" in reconcile.columns
            else metric
        )

        if calculated_col in reconcile.columns and expected_col in reconcile.columns:
            reconcile[f"{metric}_difference"] = (
                pd.to_numeric(reconcile[calculated_col], errors="coerce")
                - pd.to_numeric(reconcile[expected_col], errors="coerce")
            )

    # The provided key directly defines payroll vs ledger difference.
    if "payroll_vs_ledger_difference" in reconcile.columns:
        reconcile["answer_key_payroll_ledger_check"] = (
            pd.to_numeric(
                reconcile["payroll_vs_ledger_difference"],
                errors="coerce"
            ).abs() <= 0.01
        )

    # Explicitly flag the documented June 2026 exception.
    dq04 = reconcile[reconcile["month"].eq("2026-06")].copy()
    if not dq04.empty:
        dq04["known_issue_id"] = "DQ-04"
        dq04["known_issue_description"] = (
            "June 2026 ledger salary expense is ₹18,450 above payroll."
        )

    # 5. Additional ledger exception register.
    exception_rows = []

    for _, row in entry_balance[
        ~entry_balance["is_balanced"]
    ].iterrows():
        exception_rows.append({
            "check": "JOURNAL_NOT_BALANCED",
            "record_id": row["entry_id"],
            "details": f"Signed difference: {row['signed_difference']:.2f}"
        })

    for _, row in duplicate_lines.iterrows():
        exception_rows.append({
            "check": "DUPLICATE_LEDGER_LINE_ID",
            "record_id": row["line_id"],
            "details": "line_id occurs more than once"
        })

    for _, row in unmapped_accounts.iterrows():
        exception_rows.append({
            "check": "UNMAPPED_ACCOUNT_CODE",
            "record_id": row["line_id"],
            "details": f"Account code: {row['account_code']}"
        })

    exceptions = pd.DataFrame(
        exception_rows,
        columns=["check", "record_id", "details"]
    )

    # Preserve documented issues as a separate report.
    save_csv(known_issues, "known_data_quality_issues.csv")
    save_csv(account_summary, "account_wise_summary.csv")
    save_csv(monthly, "monthly_ledger_summary.csv")
    save_csv(entry_balance, "journal_balance_check.csv")
    save_csv(exceptions, "ledger_exceptions.csv")
    save_csv(reconcile, "monthly_reconciliation.csv")
    save_csv(dq04, "dq04_june_2026_review.csv")

    # 6. Charts.
    if not monthly.empty:
        plt.figure(figsize=(12, 5))
        plt.plot(
            monthly["month"], monthly["ledger_revenue"],
            label="Revenue"
        )
        plt.plot(
            monthly["month"], monthly["ledger_total_expense"],
            label="Expenses"
        )
        plt.xticks(rotation=60, ha="right")
        plt.title("Monthly Ledger Revenue vs Expenses")
        plt.ylabel("Amount")
        plt.legend()
        plt.tight_layout()
        plt.savefig(CHARTS / "monthly_revenue_expenses.png", dpi=150)
        plt.close()

        plt.figure(figsize=(12, 5))
        plt.plot(
            monthly["month"],
            monthly["ledger_salary_related_expense"],
            marker="o"
        )
        plt.xticks(rotation=60, ha="right")
        plt.title("Monthly Salary-Related Ledger Expense")
        plt.ylabel("Amount")
        plt.tight_layout()
        plt.savefig(CHARTS / "monthly_salary_expense.png", dpi=150)
        plt.close()

    # 7. Excel workbook containing the report tables.
    workbook = OUT / "Task7_Ledger_Analytics.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        account_summary.to_excel(
            writer, sheet_name="Account Summary", index=False
        )
        monthly.to_excel(
            writer, sheet_name="Monthly Ledger", index=False
        )
        reconcile.to_excel(
            writer, sheet_name="Reconciliation", index=False
        )
        entry_balance.to_excel(
            writer, sheet_name="Journal Balance", index=False
        )
        exceptions.to_excel(
            writer, sheet_name="Ledger Exceptions", index=False
        )
        known_issues.to_excel(
            writer, sheet_name="Known DQ Issues", index=False
        )

    print("\nTASK 7 FIRST-PASS RUN COMPLETE")
    print("Ledger rows:", len(ledger))
    print("Account summary rows:", len(account_summary))
    print("Monthly summary rows:", len(monthly))
    print("Unbalanced journal entries:", int((~entry_balance["is_balanced"]).sum()))
    print("Duplicate ledger line IDs:", len(duplicate_lines))
    print("Unmapped account rows:", len(unmapped_accounts))
    print("Output folder:", OUT)
    print("Excel workbook:", workbook)
    print("\nIMPORTANT: Reconciliation differences must be reviewed.")
    print("The known June 2026 DQ-04 mismatch is not automatically corrected.")


if __name__ == "__main__":
    main()
