
from pathlib import Path
import re
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = (
    BASE_DIR.parent.parent
    / "03_Data-20261019T074427Z-1-001"
    / "03_Data"
    / "csv"
)
REPORT_DIR = BASE_DIR / "reports"

FEEDS = {
    "AI anomaly results (fact_anomaly)": "fact_anomaly",
    "AI attrition risk (fact_attrition_risk)": "fact_attrition_risk",
    "AI forecast (fact_forecast)": "fact_forecast",
    "Task board (fact_task)": "fact_task",
}

def missing(value):
    return value.isna() | value.astype("string").str.strip().eq("")

def main():
    contract_file = DATA_DIR / "data_contracts.csv"
    if not contract_file.exists():
        raise FileNotFoundError(contract_file)

    contracts = pd.read_csv(contract_file).fillna("")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    all_issues = []
    total_rows = 0
    total_bad_rows = 0

    for feed, table in FEEDS.items():
        source = DATA_DIR / f"{table}.csv"
        if not source.exists():
            all_issues.append({
                "table": table, "row_number": "",
                "column": "", "reason": "Source file missing"
            })
            continue

        df = pd.read_csv(source, low_memory=False)
        total_rows += len(df)
        rules = contracts[contracts["feed"] == feed]
        row_reasons = [[] for _ in range(len(df))]

        actual = {str(c).strip().lower() for c in df.columns}
        expected = {
            str(c).strip().lower()
            for c in rules["column_name"]
            if str(c).strip()
        }

        if table == "fact_attrition_risk":
            expected.discard("top_reason_1..3")
            expected.update(
                {"top_reason_1", "top_reason_2", "top_reason_3"}
            )

        missing_columns = expected - actual
        extra_columns = actual - expected

        for column in sorted(missing_columns):
            all_issues.append({
                "table": table, "row_number": "",
                "column": column,
                "reason": "Required contract column missing"
            })

        # Extra columns are reported, not rejected automatically.
        for column in sorted(extra_columns):
            all_issues.append({
                "table": table, "row_number": "",
                "column": column,
                "reason": "Additional source column; review contract"
            })

        lookup = {
            str(c).strip().lower(): c for c in df.columns
        }

        for _, rule in rules.iterrows():
            name = str(rule["column_name"]).strip().lower()
            if name == "top_reason_1..3":
                columns = [
                    c for c in ("top_reason_1", "top_reason_2", "top_reason_3")
                    if c in lookup
                ]
            elif name in lookup:
                columns = [name]
            else:
                continue

            nullable_text = str(rule["nullable"]).strip().lower()
            allows_null = nullable_text in {"yes", "y", "true", "1", "nullable"}

            for name in columns:
                series = df[lookup[name]]
                empty = missing(series)

                if not allows_null:
                    for idx in df.index[empty]:
                        row_reasons[idx].append(
                            f"{name}: null/blank not allowed"
                        )

                dtype = str(rule["data_type"]).strip().lower()
                nonempty = series[~empty]

                if dtype in {"int", "integer"}:
                    converted = pd.to_numeric(nonempty, errors="coerce")
                    bad = converted.isna() | (converted % 1 != 0)
                elif dtype.startswith("decimal") or dtype in {"float", "number"}:
                    converted = pd.to_numeric(nonempty, errors="coerce")
                    bad = converted.isna()
                elif dtype == "date":
                    converted = pd.to_datetime(nonempty, errors="coerce")
                    bad = converted.isna()
                elif dtype == "timestamp":
                    converted = pd.to_datetime(nonempty, errors="coerce", utc=True)
                    bad = converted.isna()
                else:
                    bad = pd.Series(False, index=nonempty.index)

                for idx in nonempty.index[bad]:
                    row_reasons[idx].append(
                        f"{name}: invalid value for type {dtype}"
                    )

        # Business-rule checks for the supplied feeds.
        def check(mask, reason):
            for idx in df.index[mask.fillna(False)]:
                row_reasons[idx].append(reason)

        def num(col):
            return pd.to_numeric(df[col], errors="coerce") if col in df else None

        if table == "fact_anomaly":
            score = num("anomaly_score")
            if score is not None:
                check((score < 0) | (score > 1), "anomaly_score must be between 0 and 1")
            if "flagged" in df:
                check(~df["flagged"].astype(str).str.upper().isin(["Y", "N"]),
                      "flagged must be Y or N")

        elif table == "fact_attrition_risk":
            score = num("risk_score_12m")
            if score is not None:
                check((score < 0) | (score > 1), "risk_score_12m must be between 0 and 1")
            if "risk_band" in df:
                check(~df["risk_band"].astype(str).isin(["Low", "Medium", "High"]),
                      "risk_band must be Low, Medium or High")

        elif table == "fact_forecast":
            value = num("forecast_value")
            low = num("lower_80")
            high = num("upper_80")
            if value is not None:
                check(value < 0, "forecast_value cannot be negative")
            if value is not None and low is not None:
                check(low > value, "lower_80 must not exceed forecast_value")
            if value is not None and high is not None:
                check(high < value, "upper_80 must not be below forecast_value")

        elif table == "fact_task":
            points = num("story_points")
            if points is not None:
                check(~points.isin([1, 2, 3, 5, 8, 13]), "story_points must be 1, 2, 3, 5, 8 or 13")
            if "priority" in df:
                check(~df["priority"].astype(str).isin(["P1", "P2", "P3", "P4"]),
                      "priority must be P1-P4")
            if "task_type" in df:
                check(~df["task_type"].astype(str).isin(["Feature", "Bug", "Chore", "Spike"]),
                      "task_type is not an allowed value")
            if "status" in df:
                check(~df["status"].astype(str).isin(
                    ["Done", "In Progress", "Blocked", "To Do", "Cancelled"]),
                    "status is not an allowed value")
            if "reopened_count" in df:
                reopened = num("reopened_count")
                check(reopened < 0, "reopened_count cannot be negative")

        bad_mask = pd.Series(
            [bool(reasons) for reasons in row_reasons], index=df.index
        )
        clean = df.loc[~bad_mask].copy()
        rejected = df.loc[bad_mask].copy()

        rejected["rejection_reason"] = [
            "; ".join(row_reasons[idx]) for idx in rejected.index
        ]

        clean.to_csv(
            REPORT_DIR / f"{table}_contract_clean.csv", index=False
        )
        rejected.to_csv(
            REPORT_DIR / f"{table}_contract_rejected.csv", index=False
        )

        for idx, reasons in enumerate(row_reasons):
            for reason in reasons:
                all_issues.append({
                    "table": table,
                    "row_number": idx + 2,
                    "column": "",
                    "reason": reason
                })

        total_bad_rows += int(bad_mask.sum())
        print(
            f"{table}: input={len(df)}, "
            f"valid={len(clean)}, quarantined={len(rejected)}"
        )

    pd.DataFrame(all_issues).to_csv(
        REPORT_DIR / "contract_validation_issues.csv", index=False
    )

    print("\nContract validation finished.")
    print(f"Rows checked: {total_rows}")
    print(f"Rows with validation errors: {total_bad_rows}")
    print(f"Detailed report: {REPORT_DIR / 'contract_validation_issues.csv'}")
    print("Extra columns are reported for review, not rejected automatically.")

if __name__ == "__main__":
    main()
