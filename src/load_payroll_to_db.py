
from pathlib import Path
import pandas as pd
import psycopg2
from getpass import getpass

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_FILE = BASE_DIR / "clean" / "payroll_clean.csv"

def main():
    df = pd.read_csv(CSV_FILE)

    # Convert pandas missing values to Python None
    df = df.astype(object).where(pd.notna(df), None)

    connection = None

    try:
        password = getpass("Enter PostgreSQL password: ")

        connection = psycopg2.connect(
            host="localhost",
            port=5432,
            database="pulseiq_db",
            user="postgres",
            password=password
        )

        cursor = connection.cursor()

        columns = list(df.columns)
        column_names = ", ".join(f'"{col}"' for col in columns)
        placeholders = ", ".join(["%s"] * len(columns))

        insert_sql = (
            f"INSERT INTO public.stg_payroll_raw ({column_names}) "
            f"VALUES ({placeholders})"
        )

        records = list(df.itertuples(index=False, name=None))

        cursor.executemany(insert_sql, records)
        connection.commit()

        print("Payroll records loaded:", len(records))
        print("PostgreSQL staging load successful!")

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
