
import getpass
import psycopg

password = getpass.getpass("PostgreSQL password: ")

conn = psycopg.connect(
    host="localhost",
    dbname="pulseiq_wh",
    user="postgres",
    password=password
)

try:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                run_id,
                COUNT(*) AS payroll_rows,
                COUNT(DISTINCT employee_key) AS employees_paid,
                ROUND(SUM(gross_pay)::numeric, 2) AS gross_pay,
                ROUND(SUM(net_pay)::numeric, 2) AS net_pay,
                ROUND(SUM(employer_cost)::numeric, 2) AS employer_cost
            FROM dw.fact_payroll
            WHERE run_id IN ('PR-2025-04', 'PR-2026-09')
            GROUP BY run_id
            ORDER BY run_id
        """)

        rows = cur.fetchall()

        if not rows:
            print("Reference payroll runs not found.")
        else:
            print(
                "Run ID | Payroll Rows | Employees Paid | "
                "Gross Pay | Net Pay | Employer Cost"
            )
            for row in rows:
                print(row)

finally:
    conn.close()
