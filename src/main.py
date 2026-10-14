
from pathlib import Path
import logging
import subprocess
import sys

import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Column, DataFrameSchema


# --------------------------------------------------
# PATHS AND LOGGING
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "raw"
CLEAN_DIR = BASE_DIR / "clean"
REJECTED_DIR = BASE_DIR / "rejected"
LOG_DIR = BASE_DIR / "logs"

for folder in [CLEAN_DIR, REJECTED_DIR, LOG_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_DIR / "etl.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


# --------------------------------------------------
# PANDERA PAYROLL VALIDATION
# --------------------------------------------------

payroll_schema = DataFrameSchema(
    {
        "employee_key": Column(int, checks=pa.Check.gt(0)),
        "earned_fixed_pay": Column(float, checks=pa.Check.ge(0)),
        "overtime_pay": Column(float, checks=pa.Check.ge(0)),
        "variable_pay": Column(float, checks=pa.Check.ge(0)),
        "gross_pay": Column(float, checks=pa.Check.ge(0)),
    },
    strict=False,
    coerce=True,
)


# --------------------------------------------------
# EMPLOYEE ETL
# --------------------------------------------------

def process_employee():
    input_file = RAW_DIR / "employee.csv"

    if not input_file.exists():
        raise FileNotFoundError(
            f"Employee file not found: {input_file}"
        )

    df = pd.read_csv(input_file).dropna(how="all").reset_index(drop=True)
    df.columns = df.columns.str.strip().str.lower()
    input_rows = len(df)

    required = [
        "employee_id",
        "employee_name",
        "joining_date",
        "leaving_date",
        "department",
    ]

    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(
            f"Employee file missing columns: {missing}"
        )

    for col in ["employee_id", "employee_name", "department"]:
        df[col] = df[col].astype("string").str.strip()

    for col in ["joining_date", "leaving_date"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    reasons = pd.Series("", index=df.index, dtype="string")

    for col in ["employee_id", "employee_name", "department"]:
        bad = df[col].isna() | df[col].eq("")
        reasons.loc[bad] += f"Missing or empty {col}; "

    bad_join = df["joining_date"].isna()
    reasons.loc[bad_join] += "Invalid joining_date; "

    bad_exit = (
        df["leaving_date"].notna()
        & df["joining_date"].notna()
        & (df["leaving_date"] < df["joining_date"])
    )
    reasons.loc[bad_exit] += "Leaving date before joining date; "

    duplicate_ids = df["employee_id"].duplicated(keep="first")
    reasons.loc[duplicate_ids] += "Duplicate employee_id; "

    rejected_mask = reasons.ne("")
    clean = df.loc[~rejected_mask].copy()
    rejected = df.loc[rejected_mask].copy()

    rejected["rejection_reason"] = (
        reasons.loc[rejected_mask].str.rstrip("; ")
    )

    clean["joining_month"] = clean["joining_date"].dt.month
    clean["joining_year"] = clean["joining_date"].dt.year

    # Fixed reference date makes the result repeatable
    reference_date = pd.Timestamp("2026-01-01")
    clean["tenure_days"] = (
        clean["leaving_date"].fillna(reference_date)
        - clean["joining_date"]
    ).dt.days

    clean.to_csv(CLEAN_DIR / "employee_clean.csv", index=False)
    rejected.to_csv(
        REJECTED_DIR / "employee_rejected.csv",
        index=False,
    )

    logging.info(
        "Employee ETL: input=%s clean=%s rejected=%s",
        input_rows,
        len(clean),
        len(rejected),
    )

    print(
        f"Employee rows: {input_rows}; "
        f"clean: {len(clean)}; rejected: {len(rejected)}"
    )


# --------------------------------------------------
# PAYROLL ETL
# --------------------------------------------------

def process_payroll():
    input_file = RAW_DIR / (
        "03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx"
    )

    if not input_file.exists():
        raise FileNotFoundError(
            f"Excel file not found: {input_file}"
        )

    df = pd.read_excel(input_file, sheet_name="fact_payroll")
    df.columns = df.columns.str.strip()
    input_rows = len(df)

    required = [
        "employee_key",
        "employee_id",
        "run_id",
        "earned_fixed_pay",
        "overtime_pay",
        "variable_pay",
        "gross_pay",
    ]

    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(
            f"Payroll sheet missing columns: {missing}"
        )

    reasons = pd.Series("", index=df.index, dtype="string")

    df["employee_key"] = pd.to_numeric(
        df["employee_key"], errors="coerce"
    )

    amount_columns = [
        "earned_fixed_pay",
        "overtime_pay",
        "variable_pay",
        "gross_pay",
    ]

    for col in amount_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    bad_key = (
        df["employee_key"].isna()
        | (df["employee_key"] <= 0)
    )
    reasons.loc[bad_key] += "Invalid employee_key; "

    for col in amount_columns:
        bad_amount = df[col].isna() | (df[col] < 0)
        reasons.loc[bad_amount] += f"Invalid {col}; "

    duplicate_pair = df.duplicated(
        subset=["employee_id", "run_id"],
        keep="first",
    )
    reasons.loc[duplicate_pair] += (
        "Duplicate employee_id and run_id; "
    )

    candidates = df.loc[reasons.eq("")].copy()

    if not candidates.empty:
        try:
            payroll_schema.validate(candidates, lazy=True)
        except pa.errors.SchemaErrors as exc:
            raise ValueError(
                f"Payroll Pandera validation failed: {exc}"
            ) from exc

    rejected_mask = reasons.ne("")
    clean = df.loc[~rejected_mask].copy()
    rejected = df.loc[rejected_mask].copy()

    rejected["rejection_reason"] = (
        reasons.loc[rejected_mask].str.rstrip("; ")
    )

    clean.to_csv(CLEAN_DIR / "payroll_clean.csv", index=False)
    clean.to_parquet(
        CLEAN_DIR / "payroll_clean.parquet",
        index=False,
    )
    rejected.to_csv(
        REJECTED_DIR / "payroll_rejected.csv",
        index=False,
    )

    logging.info(
        "Payroll ETL: input=%s clean=%s rejected=%s",
        input_rows,
        len(clean),
        len(rejected),
    )

    print(
        f"Payroll rows: {input_rows}; "
        f"clean: {len(clean)}; rejected: {len(rejected)}"
    )


# --------------------------------------------------
# RUN ALL DATASETS
# --------------------------------------------------

def main():
    logging.info("ETL pipeline started")

    try:
        process_employee()
        process_payroll()

        other_script = Path(__file__).with_name(
            "process_other_data.py"
        )

        if not other_script.exists():
            raise FileNotFoundError(
                f"Other ETL script not found: {other_script}"
            )

        subprocess.run(
            [sys.executable, str(other_script)],
            check=True,
            cwd=BASE_DIR,
        )

        logging.info("ETL pipeline completed successfully")
        print("All ETL processing completed successfully.")

    except Exception:
        logging.exception("ETL pipeline failed")
        raise


if __name__ == "__main__":
    main()
