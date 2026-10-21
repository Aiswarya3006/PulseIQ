import getpass
import psycopg

password = getpass.getpass("PostgreSQL password: ")
conn = psycopg.connect(
    host="localhost",
    dbname="pulseiq_wh",
    user="postgres",
    password=password
)

with conn.cursor() as cur:
    cur.execute("""
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = 'dw'
          AND table_type = 'BASE TABLE'
    """)
    print("Tables in dw:", cur.fetchone()[0])

    cur.execute("""
        SELECT COUNT(*) FROM dw.fact_payroll
    """)
    print("Payroll rows:", cur.fetchone()[0])

    cur.execute("""
        SELECT COUNT(DISTINCT run_id)
        FROM dw.fact_payroll
    """)
    print("Distinct payroll runs:", cur.fetchone()[0])

conn.close()
