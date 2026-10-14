
import pandas as pd
from pathlib import Path

root = Path(__file__).resolve().parent.parent
input_file = root / "reports" / "attendance_monthly_trend.csv"
output_file = root / "reports" / "attendance_anomalies.csv"

df = pd.read_csv(input_file)
df["attendance_rate"] = pd.to_numeric(
    df["attendance_rate"], errors="coerce"
)
df["rolling_3_month_rate"] = pd.to_numeric(
    df["rolling_3_month_rate"], errors="coerce"
)

# Exploratory monthly deviation; this is NOT a daily anomaly model.
df["deviation"] = (
    df["attendance_rate"] - df["rolling_3_month_rate"]
)
df["flagged"] = df["deviation"].abs() >= 0.015

df["flag_reason"] = df["flagged"].map({
    True: "Attendance differs from 3-month average by at least 1.5 percentage points",
    False: "No threshold breach"
})

df.to_csv(output_file, index=False)
print(f"Saved: {output_file}")
print(df.loc[df["flagged"], [
    "month", "attendance_rate",
    "rolling_3_month_rate", "deviation"
]].to_string(index=False))
