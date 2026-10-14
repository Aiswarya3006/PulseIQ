
from pathlib import Path
import logging
import pandas as pd

# 1. Project paths
BASE_DIR = Path(__file__).resolve().parent.parent

RAW_DIR = BASE_DIR / "raw"
CLEAN_DIR = BASE_DIR / "clean"
REJECTED_DIR = BASE_DIR / "rejected"
LOG_DIR = BASE_DIR / "logs"

# 2. Create folders
for folder in [CLEAN_DIR, REJECTED_DIR, LOG_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

# 3. Configure logging
logging.basicConfig(
    filename=str(LOG_DIR / "etl.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def main():
    try:
        # 4. Locate input Excel file
        input_file = (
            RAW_DIR / "03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx"
        )

        if not input_file.exists():
            raise FileNotFoundError(
                f"Excel file not found: {input_file}"
            )

        logging.info("Payroll ETL pipeline started")

        # 5. Read payroll data
        df = pd.read_excel(
            input_file,
            sheet_name="fact_payroll"
        )

        df.columns = df.columns.str.strip()

        print("Original payroll rows:", len(df))

        # 6. Check required columns
        required_columns = [
            "employee_key",
            "employee_id",
            "run_id",
            "earned_fixed_pay",
            "overtime_pay",
            "variable_pay",
            "gross_pay",
        ]

        missing_columns = [
            column
            for column in required_columns
            if column not in df.columns
        ]

        if missing_columns:
            raise ValueError(
                f"Missing required columns: {missing_columns}"
            )

        # 7. Create rejection reasons
        reasons = pd.Series(
            "",
            index=df.index,
            dtype="string"
        )

        # 8. Reject invalid employee keys
        employee_keys = pd.to_numeric(
            df["employee_key"],
            errors="coerce"
        )

        invalid_key = (
            employee_keys.isna()
            | (employee_keys <= 0)
        )

        reasons.loc[invalid_key] = (
            reasons.loc[invalid_key]
            + "Invalid employee_key; "
        )

        # 9. Identify duplicate employee/run pairs
        duplicate_pair = df.duplicated(
            subset=["employee_id", "run_id"],
            keep="first"
        )

        reasons.loc[duplicate_pair] = (
            reasons.loc[duplicate_pair]
            + "Duplicate employee_id and run_id; "
        )

        # 10. Separate clean and rejected records
        rejected_mask = reasons.ne("")

        clean = df.loc[~rejected_mask].copy()
        rejected = df.loc[rejected_mask].copy()

        rejected["rejection_reason"] = (
            reasons.loc[rejected_mask]
            .str.rstrip("; ")
        )

        # 11. Save clean CSV
        clean.to_csv(
            CLEAN_DIR / "payroll_clean.csv",
            index=False
        )

        # 12. Save clean Parquet
        clean.to_parquet(
            CLEAN_DIR / "payroll_clean.parquet",
            index=False
        )

        # 13. Save rejected records
        rejected.to_csv(
            REJECTED_DIR / "payroll_rejected.csv",
            index=False
        )

        # 14. Log results
        logging.info("Input payroll rows: %s", len(df))
        logging.info("Clean payroll rows: %s", len(clean))
        logging.info("Rejected payroll rows: %s", len(rejected))
        logging.info("Payroll ETL completed successfully")

        # 15. Display results
        print("Clean payroll rows:", len(clean))
        print("Rejected payroll rows:", len(rejected))
        print(
            "Clean CSV:",
            CLEAN_DIR / "payroll_clean.csv"
        )
        print(
            "Clean Parquet:",
            CLEAN_DIR / "payroll_clean.parquet"
        )
        print(
            "Rejected CSV:",
            REJECTED_DIR / "payroll_rejected.csv"
        )
        print("ETL processing completed successfully!")

    except Exception as error:
        logging.exception("Payroll ETL failed")
        print("ETL ERROR:", error)


if __name__ == "__main__":
    main()
