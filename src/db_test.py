
import psycopg
from getpass import getpass

try:
    password = getpass("Enter PostgreSQL password: ")

    with psycopg.connect(
        host="localhost",
        port=5432,
        dbname="pulseiq_db",
        user="postgres",
        password=password
    ) as conn:
        print("PostgreSQL connection successful!")

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM dim_employee")
            count = cur.fetchone()[0]
            print("Employee records:", count)

except Exception as e:
    print("Connection failed:", e)
