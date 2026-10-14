
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
    filename=str(LOG_DIR / "etl.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

EXCEL_FILE = RAW_DIR / "03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx"


def process_sheet(sheet_name, output_name, date_columns=None):
    df = pd.read_excel(EXCEL_FILE, sheet_name=sheet_name)
    input_rows = len(df)
    df.columns = df.columns.str.strip()

    reasons = pd.Series("", index=df.index, dtype="string")

    # Standardize text values
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].map(
            lambda value: value.strip() if isinstance(value, str) else value
        )

    # Convert relevant dates and reject invalid non-empty dates
    for col in (date_columns or []):
        if col not in df.columns:
            raise ValueError(f"{sheet_name}: missing date column {col}")

        original = df[col]
        parsed = pd.to_datetime(original, errors="coerce")
        invalid = original.notna() & parsed.isna()
        reasons.loc[invalid] += f"Invalid {col}; "
        df[col] = parsed

    # Reject completely duplicated rows
    duplicate = df.duplicated(keep="first")
    reasons.loc[duplicate] += "Duplicate row; "

    rejected_mask = reasons.ne("")
    clean = df.loc[~rejected_mask].copy()
    rejected = df.loc[rejected_mask].copy()
    rejected["rejection_reason"] = reasons.loc[rejected_mask].str.rstrip("; ")

    clean.to_csv(CLEAN_DIR / f"{output_name}_clean.csv", index=False)
    rejected.to_csv(REJECTED_DIR / f"{output_name}_rejected.csv", index=False)

    logging.info(
        "%s ETL: input=%s clean=%s rejected=%s",
        sheet_name, input_rows, len(clean), len(rejected)
    )
    print(
        f"{sheet_name}: input={input_rows}, "
        f"clean={len(clean)}, rejected={len(rejected)}"
    )


def main():
    if not EXCEL_FILE.exists():
        raise FileNotFoundError(f"Excel file not found: {EXCEL_FILE}")

    process_sheet(
        "fact_attendance_monthly",
        "attendance",
        ["period_end_date"],
    )
    process_sheet(
        "fact_leave",
        "leave",
        ["start_date", "end_date", "applied_on", "decided_on"],
    )
    process_sheet(
        "dim_role",
        "salary_band",
    )


if __name__ == "__main__":
    main()
