
from pathlib import Path
import pandas as pd
import psycopg2
from getpass import getpass

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_FILE = BASE_DIR / "rejected" / "payroll_rejected.csv"

def main():
    df = pd.read_csv(CSV_FILE)
    df = df.astype(object).where(pd.notna(df), None)

    connection = None

    try:
        connection = psycopg2.connect(
            host="localhost",
            port=5432,
            database="pulseiq_db",
            user="postgres",
            password=getpass("Enter PostgreSQL password: ")
        )

        cursor = connection.cursor()

        columns = list(df.columns)
        column_names = ", ".join(f'"{col}"' for col in columns)
        placeholders = ", ".join(["%s"] * len(columns))

        sql = (
            f"INSERT INTO public.stg_payroll_rejected "
            f"({column_names}) VALUES ({placeholders})"
        )

        cursor.executemany(
            sql,
            list(df.itertuples(index=False, name=None))
        )

        connection.commit()
        print("Rejected records loaded:", len(df))
        print("Rejected data load successful!")

        cursor.close()

    except Exception as error:
        if connection:
            connection.rollback()
        print("Database load failed:", error)

    finally:
        if connection:
            connection.close()

if __name__ == "__main__":
    main()
