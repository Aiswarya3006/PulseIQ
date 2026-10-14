
from pathlib import Path
import logging
import pandas as pd

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

def main():
    input_file = RAW_DIR / "employee.csv"

    # 1. Check whether the input file exists
    if not input_file.exists():
        print("Error: employee.csv not found inside raw folder")
        return

    # 2. Load the CSV dataset
    df = pd.read_csv(input_file)
    print("Original rows:", len(df))

    # 3. Remove extra spaces from column names
    df.columns = df.columns.str.strip()

    # 4. Clean employee names
    df["employee_name"] = df["employee_name"].astype("string").str.strip()

    # 5. Convert dates into proper date format
    df["joining_date"] = pd.to_datetime(
        df["joining_date"], errors="coerce"
    )
    df["leaving_date"] = pd.to_datetime(
        df["leaving_date"], errors="coerce"
    )

    # 6. Reject rows with missing employee IDs or joining dates
    invalid_required = (
        df["employee_id"].isna()
        | df["employee_id"].astype("string").str.strip().eq("")
        | df["joining_date"].isna()
    )

    # 7. Reject leaving dates earlier than joining dates
    invalid_dates = (
        df["leaving_date"].notna()
        & (df["leaving_date"] < df["joining_date"])
    )

    rejected_mask = invalid_required | invalid_dates

    rejected = df[rejected_mask].copy()
    rejected["rejection_reason"] = "Invalid required field or date order"

    clean = df[~rejected_mask].copy()

    # 8. Remove duplicate employee IDs
    clean = clean.drop_duplicates(
        subset=["employee_id"], keep="first"
    )

    # 9. Save clean and rejected records separately
    clean.to_csv(CLEAN_DIR / "employee_clean.csv", index=False)
    rejected.to_csv(REJECTED_DIR / "employee_rejected.csv", index=False)

    # 10. Log pipeline results
    logging.info("Input rows: %s", len(df))
    logging.info("Clean rows: %s", len(clean))
    logging.info("Rejected rows: %s", len(rejected))

    print("Clean rows:", len(clean))
    print("Rejected rows:", len(rejected))
    print("ETL cleaning completed!")
    print("Check the clean and rejected folders.")

if __name__ == "__main__":
    main()
