
import psycopg2
from getpass import getpass

conn = psycopg2.connect(
    dbname="pulseiq_wh",
    user=input("PostgreSQL username: "),
    password=getpass("PostgreSQL password: "),
    host="localhost",
    port=5432
)

try:
    with conn.cursor() as cur:

        # Check employee-key orphans
        cur.execute("""
            SELECT COUNT(*)
            FROM dw.fact_payroll f
            LEFT JOIN dw.dim_employee d
                ON f.employee_key = d.employee_key
            WHERE d.employee_key IS NULL
        """)
        employee_orphans = cur.fetchone()[0]
        print("Payroll employee-key orphans:", employee_orphans)

        # Check department orphans
        cur.execute("""
            SELECT COUNT(*)
            FROM dw.fact_payroll f
            LEFT JOIN dw.dim_department d
                ON f.department_id = d.department_id
            WHERE d.department_id IS NULL
        """)
        department_orphans = cur.fetchone()[0]
        print("Payroll department orphans:", department_orphans)

finally:
    conn.close()
