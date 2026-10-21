
"""Load CSV files into DuckDB raw schema."""

import duckdb
import glob
import os

CSV_FOLDER = r"C:\Users\AISWARYA\OneDrive\Documents\Desktop\PulseIQ\03_Data-20261019T074427Z-1-001\03_Data\csv"

con = duckdb.connect("pulseiq.duckdb")
con.execute("CREATE SCHEMA IF NOT EXISTS raw")

files = sorted(glob.glob(os.path.join(CSV_FOLDER, "*.csv")))

if not files:
    print("ERROR: No CSV files found. Check the CSV_FOLDER path.")
else:
    print(f"Found {len(files)} CSV files.")

    for f in files:
        table_name = os.path.basename(f)[:-4]
        safe_path = f.replace("\\", "/").replace("'", "''")

        con.execute(
            f'CREATE OR REPLACE TABLE raw."{table_name}" '
            f"AS SELECT * FROM read_csv_auto('{safe_path}', header=true)"
        )

        row_count = con.execute(
            f'SELECT COUNT(*) FROM raw."{table_name}"'
        ).fetchone()[0]

        print(f"raw.{table_name}: {row_count} rows")

    print("\nCSV loading completed.")

con.close()
