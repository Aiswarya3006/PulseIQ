import csv
import glob
import os
import getpass
import psycopg

files = glob.glob("reports/clean/*_clean.csv")
conn = psycopg.connect(
    host="localhost",
    dbname="pulseiq_wh",
    user="postgres",
    password=getpass.getpass("PostgreSQL password: ")
)

mismatches = []

with conn.cursor() as cur:
    for file in files:
        table = os.path.basename(file).replace("_clean.csv", "")

        with open(file, encoding="utf-8-sig", newline="") as f:
            csv_count = sum(1 for _ in csv.reader(f)) - 1

        cur.execute(f'SELECT COUNT(*) FROM dw."{table}"')
        db_count = cur.fetchone()[0]

        status = "OK" if csv_count == db_count else "MISMATCH"
        print(f"{table}: CSV={csv_count}, DB={db_count}, {status}")

        if csv_count != db_count:
            mismatches.append((table, csv_count, db_count))

print("\nFiles checked:", len(files))
print("Mismatches:", mismatches)
conn.close()