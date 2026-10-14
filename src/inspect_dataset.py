from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
file = BASE_DIR / "raw" / "03_PulseIQ_Analytics_Star_Schema_Dataset.xlsx"

df = pd.read_excel(file, sheet_name="dq_checks_catalog")

print(df[[
    "check_id",
    "check_name",
    "description",
    "logic_sql_or_rule",
    "fix_guidance"
]].to_string(index=False))