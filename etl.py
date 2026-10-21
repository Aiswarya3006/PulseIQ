
from pathlib import Path
from datetime import datetime, timezone
import json
import logging

import pandas as pd


# --------------------------------------------------
# 1. PROJECT PATHS
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = (
    BASE_DIR.parent.parent
    / "03_Data-20261019T074427Z-1-001"
    / "03_Data"
    / "csv"
)

REPORT_DIR = BASE_DIR / "reports"
CLEAN_DIR = REPORT_DIR / "clean"
REJECTED_DIR = REPORT_DIR / "rejected"

for folder in (REPORT_DIR, CLEAN_DIR, REJECTED_DIR):
    folder.mkdir(parents=True, exist_ok=True)

LOG_FILE = REPORT_DIR / "etl_run_log.txt"
SUMMARY_FILE = REPORT_DIR / "etl_summary.json"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8",
)


# --------------------------------------------------
# 2. HELPER FUNCTIONS
# --------------------------------------------------

def normalise_name(name):
    """Normalise column names for reliable comparisons."""
    return str(name).strip().lower()


def find_column(df, *candidates):
    """Find a column without depending on capitalisation."""
    columns = {
        normalise_name(column): column
        for column in df.columns
    }

    for candidate in candidates:
        if normalise_name(candidate) in columns:
            return columns[normalise_name(candidate)]

    return None


def add_reason(reasons, mask, message):
    """Add a rejection reason to rows matching a condition."""
    if mask is None:
        return

    mask = pd.Series(mask, index=reasons.index).fillna(False).astype(bool)
    reasons.loc[mask] = reasons.loc[mask].apply(
        lambda existing: (
            f"{existing}; {message}" if existing else message
        )
    )


def numeric_series(df, column):
    """Convert a column to numeric values for validation."""
    return pd.to_numeric(df[column], errors="coerce")


# --------------------------------------------------
# 3. DATA QUALITY VALIDATION
# --------------------------------------------------

def validate_table(table_name, df, all_tables):
    """
    Validate a DataFrame and return:
    clean_df, rejected_df

    Each rejected row contains a rejection_reason column.
    """
    df = df.copy()
    df.columns = [str(column).strip() for column in df.columns]

    reasons = pd.Series("", index=df.index, dtype="object")

    # Reject completely empty rows.
    empty_rows = df.isna().all(axis=1)
    add_reason(reasons, empty_rows, "Entire row is empty")

    # DQ-C02: Journal entry debits must equal credits.
    if table_name == "fact_ledger":
        entry_col = find_column(df, "entry_id")
        debit_col = find_column(df, "debit")
        credit_col = find_column(df, "credit")

        if entry_col and debit_col and credit_col:
            debit = numeric_series(df, debit_col)
            credit = numeric_series(df, credit_col)

            totals = pd.DataFrame({
                "entry": df[entry_col],
                "debit": debit,
                "credit": credit,
            }).groupby("entry", dropna=False).sum()

            unbalanced_entries = totals.index[
                (totals["debit"] - totals["credit"]).abs() > 0.005
            ]

            add_reason(
                reasons,
                df[entry_col].isin(unbalanced_entries),
                "DQ-C02: Journal entry debits and credits do not balance",
            )

    # DQ-C03: One payroll row per employee per payroll run.
    if table_name == "fact_payroll":
        employee_col = find_column(df, "employee_id")
        run_col = find_column(
            df,
            "run_id",
            "payroll_run_id",
            "payroll_run",
            "run_code",
        )

        if employee_col and run_col:
            duplicate = df.duplicated(
                subset=[employee_col, run_col],
                keep=False,
            )
            add_reason(
                reasons,
                duplicate,
                "DQ-C03: Duplicate employee and payroll run",
            )

    # DQ-C04: Payroll employee IDs must exist in dim_employee.
    if table_name == "fact_payroll":
        employee_col = find_column(df, "employee_id")
        employee_table = all_tables.get("dim_employee")

        if employee_col is not None and employee_table is not None:
            master_id = find_column(employee_table, "employee_id")

            if master_id:
                valid_ids = set(
                    employee_table[master_id].dropna().astype(str).str.strip()
                )
                payroll_ids = df[employee_col].astype(str).str.strip()

                add_reason(
                    reasons,
                    ~payroll_ids.isin(valid_ids),
                    "DQ-C04: Employee ID missing from dim_employee",
                )

    # DQ-C05: Attendance month must not be after employee exit month.
    if table_name == "fact_attendance_monthly":
        employee_col = find_column(df, "employee_id")
        month_col = find_column(
            df, "month", "attendance_month", "month_start", "month_date"
        )
        employee_table = all_tables.get("dim_employee")

        if employee_col and month_col and employee_table is not None:
            master_id = find_column(employee_table, "employee_id")
            exit_col = find_column(employee_table, "exit_date")

            if master_id and exit_col:
                master = employee_table[[master_id, exit_col]].copy()
                master[exit_col] = pd.to_datetime(
                    master[exit_col], errors="coerce"
                )
                master = master.dropna(subset=[master_id]).drop_duplicates(
                    subset=[master_id], keep="last"
                )

                check = df[[employee_col, month_col]].copy()
                check["_row_index"] = df.index
                check["_month"] = pd.to_datetime(
                    check[month_col], errors="coerce"
                )

                check = check.merge(
                    master,
                    left_on=employee_col,
                    right_on=master_id,
                    how="left",
                )

                invalid_indices = check.loc[
                    check[exit_col].notna()
                    & check["_month"].notna()
                    & (
                        check["_month"].dt.to_period("M")
                        > check[exit_col].dt.to_period("M")
                    ),
                    "_row_index",
                ]

                add_reason(
                    reasons,
                    df.index.isin(invalid_indices),
                    "DQ-C05: Attendance recorded after employee exit month",
                )

    # DQ-C07: Invoice payment and balance values must be sensible.
    if table_name == "fact_invoice":
        paid_col = find_column(df, "amount_paid")
        total_col = find_column(df, "total_amount")
        balance_col = find_column(df, "balance_due")

        if paid_col and total_col:
            paid = numeric_series(df, paid_col)
            total = numeric_series(df, total_col)

            add_reason(
                reasons,
                paid.notna() & total.notna() & (paid > total + 0.01),
                "DQ-C07: Amount paid exceeds invoice total",
            )

        if balance_col:
            balance = numeric_series(df, balance_col)

            add_reason(
                reasons,
                balance.notna() & (balance < -0.01),
                "DQ-C07: Invoice balance is negative",
            )

    # DQ-C08: Expense total must equal amount excluding GST plus GST.
    if table_name == "fact_expense":
        total_col = find_column(df, "total_amount")
        base_col = find_column(df, "amount_excl_gst")
        gst_col = find_column(df, "gst_amount")

        if total_col and base_col and gst_col:
            total = numeric_series(df, total_col)
            base = numeric_series(df, base_col)
            gst = numeric_series(df, gst_col)

            comparable = total.notna() & base.notna() & gst.notna()

            add_reason(
                reasons,
                comparable & ((total - base - gst).abs() > 0.01),
                "DQ-C08: Expense total does not equal base amount plus GST",
            )

    # DQ-C09: Task dates must be sensible.
    if table_name == "fact_task":
        start_col = find_column(df, "started_date")
        complete_col = find_column(df, "completed_date")
        status_col = find_column(df, "status")

        if start_col and complete_col:
            start = pd.to_datetime(df[start_col], errors="coerce")
            complete = pd.to_datetime(df[complete_col], errors="coerce")

            add_reason(
                reasons,
                start.notna() & complete.notna() & (complete < start),
                "DQ-C09: Task completion date is before start date",
            )

        if status_col and complete_col:
            done = df[status_col].astype(str).str.strip().str.lower().isin(
                ["done", "completed", "complete"]
            )
            missing_completion = pd.to_datetime(
                df[complete_col], errors="coerce"
            ).isna()

            add_reason(
                reasons,
                done & missing_completion,
                "DQ-C09: Completed task has no completion date",
            )

    # DQ-C10: Leave end date cannot precede start date.
    if table_name == "fact_leave":
        start_col = find_column(df, "start_date")
        end_col = find_column(df, "end_date")

        if start_col and end_col:
            start = pd.to_datetime(df[start_col], errors="coerce")
            end = pd.to_datetime(df[end_col], errors="coerce")

            add_reason(
                reasons,
                start.notna() & end.notna() & (end < start),
                "DQ-C10: Leave end date is before start date",
            )

    # DQ-C11: Attrition risk as-of dates should be recent.
    if table_name == "fact_attrition_risk":
        date_col = find_column(df, "as_of_date")

        if date_col:
            dates = pd.to_datetime(df[date_col], errors="coerce")
            latest_date = dates.max()

            if pd.notna(latest_date):
                stale = dates.notna() & (
                    (latest_date - dates).dt.days > 7
                )
                add_reason(
                    reasons,
                    stale,
                    "DQ-C11: Risk prediction as-of date is more than 7 days old",
                )

    # DQ-C12: Employee history validity intervals must not overlap.
    if table_name == "dim_employee":
        id_col = find_column(df, "employee_id")
        start_col = find_column(df, "valid_from")
        end_col = find_column(df, "valid_to")

        if id_col and start_col and end_col:
            history = df[[id_col, start_col, end_col]].copy()
            history["_row_index"] = df.index
            history["_start"] = pd.to_datetime(
                history[start_col], errors="coerce"
            )
            history["_end"] = pd.to_datetime(
                history[end_col], errors="coerce"
            )
            history["_end"] = history["_end"].fillna(
                pd.Timestamp.max.normalize()
            )
            history = history.sort_values(
                [id_col, "_start"], na_position="last"
            )

            overlapping_indices = []

            for _, group in history.groupby(id_col, dropna=False):
                previous_end = None

                for _, row in group.iterrows():
                    start = row["_start"]
                    end = row["_end"]

                    if pd.isna(start):
                        continue

                    if previous_end is not None and start <= previous_end:
                        overlapping_indices.append(row["_row_index"])

                    if previous_end is None or end > previous_end:
                        previous_end = end

            add_reason(
                reasons,
                df.index.isin(overlapping_indices),
                "DQ-C12: Employee history intervals overlap",
            )

    rejected_mask = reasons.ne("")

    clean_df = df.loc[~rejected_mask].copy()
    rejected_df = df.loc[rejected_mask].copy()

    if not rejected_df.empty:
        rejected_df["rejection_reason"] = reasons.loc[rejected_mask]

    return clean_df, rejected_df


# --------------------------------------------------
# 4. LOAD CSV FILES
# --------------------------------------------------

def load_csv_files():
    """Read every CSV file from the dataset folder."""
    if not DATA_DIR.is_dir():
        raise FileNotFoundError(
            f"Dataset folder not found: {DATA_DIR}"
        )

    csv_files = sorted(DATA_DIR.glob("*.csv"))

    if not csv_files:
        raise FileNotFoundError(
            f"No CSV files found in: {DATA_DIR}"
        )

    tables = {}

    for file_path in csv_files:
        table_name = file_path.stem.lower()

        try:
            tables[table_name] = pd.read_csv(
                file_path,
                low_memory=False,
            )
            print(
                f"Loaded {table_name}: "
                f"{len(tables[table_name])} rows"
            )
        except Exception as exc:
            logging.exception("Failed to read %s", file_path.name)
            raise RuntimeError(
                f"Could not read {file_path.name}: {exc}"
            ) from exc

    return tables


# --------------------------------------------------
# 5. RUN ETL AND SAVE REPORTS
# --------------------------------------------------

def main():
    started_at = datetime.now(timezone.utc)

    print("=" * 60)
    print("PulseIQ ETL - Data Quality Processing")
    print("=" * 60)
    print(f"Project folder: {BASE_DIR}")
    print(f"Data folder: {DATA_DIR}")

    logging.info("ETL run started")

    tables = load_csv_files()

    summary = {
        "project": "PulseIQ",
        "started_at_utc": started_at.isoformat(),
        "data_folder": str(DATA_DIR),
        "tables_processed": 0,
        "rows_in": 0,
        "rows_passed": 0,
        "rows_rejected": 0,
        "tables": {},
        "status": "RUNNING",
    }

    for table_name, df in tables.items():
        clean_df, rejected_df = validate_table(
            table_name,
            df,
            tables,
        )

        clean_path = CLEAN_DIR / f"{table_name}_clean.csv"
        rejected_path = REJECTED_DIR / f"{table_name}_rejected.csv"

        clean_df.to_csv(clean_path, index=False)
        rejected_df.to_csv(rejected_path, index=False)

        row_count = len(df)
        clean_count = len(clean_df)
        rejected_count = len(rejected_df)

        summary["tables"][table_name] = {
            "rows_in": row_count,
            "rows_passed": clean_count,
            "rows_rejected": rejected_count,
            "clean_file": str(clean_path),
            "rejected_file": str(rejected_path),
        }

        summary["tables_processed"] += 1
        summary["rows_in"] += row_count
        summary["rows_passed"] += clean_count
        summary["rows_rejected"] += rejected_count

        print(
            f"{table_name}: total={row_count}, "
            f"passed={clean_count}, rejected={rejected_count}"
        )

        logging.info(
            "%s | total=%s | passed=%s | rejected=%s",
            table_name,
            row_count,
            clean_count,
            rejected_count,
        )

    # Compatibility fields required by the automated tests
    summary["results"] = summary["tables"]
    summary["total_rows_in"] = summary["rows_in"]
    summary["total_rows_passed"] = summary["rows_passed"]
    summary["total_rows_rejected"] = summary["rows_rejected"]

    summary["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    summary["status"] = "SUCCESS"

    with SUMMARY_FILE.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, ensure_ascii=False)

    print("-" * 60)
    print(f"Tables processed: {summary['tables_processed']}")
    print(f"Rows in: {summary['rows_in']}")
    print(f"Rows passed: {summary['rows_passed']}")
    print(f"Rows rejected: {summary['rows_rejected']}")
    print(f"Summary report: {SUMMARY_FILE}")
    print(f"Clean files: {CLEAN_DIR}")
    print(f"Rejected files: {REJECTED_DIR}")
    print("=" * 60)

    logging.info(
        "ETL finished: %s tables, %s input rows, %s rejected rows",
        summary["tables_processed"],
        summary["rows_in"],
        summary["rows_rejected"],
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logging.exception("ETL run failed")
        print(f"\nETL FAILED: {exc}")
        raise
