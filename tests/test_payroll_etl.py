
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent

CLEAN_FILE = BASE_DIR / "clean" / "payroll_clean.csv"
REJECTED_FILE = BASE_DIR / "rejected" / "payroll_rejected.csv"
PARQUET_FILE = BASE_DIR / "clean" / "payroll_clean.parquet"


def test_clean_and_rejected_row_counts():
    clean = pd.read_csv(CLEAN_FILE)
    rejected = pd.read_csv(REJECTED_FILE)

    assert len(clean) == 7340
    assert len(rejected) == 4
    assert len(clean) + len(rejected) == 7344


def test_clean_payroll_has_no_duplicate_employee_runs():
    clean = pd.read_csv(CLEAN_FILE)

    assert not clean.duplicated(
        subset=["employee_id", "run_id"]
    ).any()


def test_rejected_records_have_reasons():
    rejected = pd.read_csv(REJECTED_FILE)

    assert "rejection_reason" in rejected.columns
    assert rejected["rejection_reason"].notna().all()
    assert rejected["rejection_reason"].str.strip().ne("").all()


def test_clean_payroll_has_valid_employee_keys():
    clean = pd.read_csv(CLEAN_FILE)

    keys = pd.to_numeric(clean["employee_key"], errors="coerce")

    assert keys.notna().all()
    assert (keys > 0).all()


def test_clean_payroll_gross_pay_calculation():
    clean = pd.read_csv(CLEAN_FILE)

    expected_gross = (
        clean["earned_fixed_pay"]
        + clean["overtime_pay"]
        + clean["variable_pay"]
    )

    assert ((clean["gross_pay"] - expected_gross).abs() < 0.02).all()


def test_parquet_matches_csv_row_count():
    csv_data = pd.read_csv(CLEAN_FILE)
    parquet_data = pd.read_parquet(PARQUET_FILE)

    assert len(csv_data) == 7340
    assert len(parquet_data) == len(csv_data)


def test_parquet_columns_match_csv():
    csv_data = pd.read_csv(CLEAN_FILE)
    parquet_data = pd.read_parquet(PARQUET_FILE)

    assert list(parquet_data.columns) == list(csv_data.columns)


def test_rejected_file_contains_four_records():
    rejected = pd.read_csv(REJECTED_FILE)

    assert len(rejected) == 4
