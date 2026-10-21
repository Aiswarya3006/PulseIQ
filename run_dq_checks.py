
import duckdb
from datetime import datetime

DB_FILE = "pulseiq.duckdb"

CHECKS = [
    (
        "DQ-C01", "Payroll equals ledger", "Critical",
        """
        WITH p AS (
            SELECT SUM(employer_cost) AS payroll_total
            FROM raw.fact_payroll
            WHERE run_id = 'PR-2026-06'
        ),
        l AS (
            SELECT SUM(credit - debit) AS ledger_total
            FROM raw.fact_ledger
            WHERE account_code IN ('5001','5002','5003','5004','5005')
              AND source_id = 'PR-2026-06'
        )
        SELECT 'PR-2026-06' AS bad_key
        FROM p CROSS JOIN l
        WHERE ABS(COALESCE(p.payroll_total, 0)
                - COALESCE(l.ledger_total, 0)) > 0.01
        """
    ),
    (
        "DQ-C02", "Ledger balanced", "Critical",
        """
        SELECT CAST(entry_id AS VARCHAR) AS bad_key
        FROM raw.fact_ledger
        GROUP BY entry_id
        HAVING ABS(SUM(debit) - SUM(credit)) > 0.01
        """
    ),
    (
        "DQ-C03", "Unique payroll rows", "Critical",
        """
        SELECT employee_id || ':' || run_id AS bad_key
        FROM raw.fact_payroll
        GROUP BY employee_id, run_id
        HAVING COUNT(*) > 1
        """
    ),
    (
        "DQ-C04", "No orphan employees", "Critical",
        """
        SELECT DISTINCT CAST(p.employee_id AS VARCHAR) AS bad_key
        FROM raw.fact_payroll p
        LEFT JOIN raw.dim_employee d
          ON p.employee_id = d.employee_id
        WHERE d.employee_id IS NULL
        """
    ),
    (
        "DQ-C05", "No attendance after exit", "Warning",
        """
        SELECT DISTINCT CAST(a.employee_id AS VARCHAR) AS bad_key
        FROM raw.fact_attendance_monthly a
        JOIN raw.dim_employee d
          ON a.employee_id = d.employee_id
         AND d.is_current = 'Y'
        WHERE d.exit_date IS NOT NULL
          AND a.period_end_date > CAST(d.exit_date AS DATE)
        """
    ),
    (
        "DQ-C06", "Unpaid absence review", "Warning",
        """
        SELECT CAST(employee_id AS VARCHAR) AS bad_key
        FROM raw.fact_attendance_monthly
        WHERE COALESCE(unpaid_absence_days, 0) > 0
           OR COALESCE(half_days_unpaid, 0) > 0
        """
    ),
    (
        "DQ-C07", "Invoice arithmetic", "Warning",
        """
        SELECT CAST(invoice_id AS VARCHAR) AS bad_key
        FROM raw.fact_invoice
        WHERE ABS(
            COALESCE(subtotal, 0) + COALESCE(gst_amount, 0)
            - COALESCE(total_amount, 0)
        ) > 0.01
        OR ABS(
            COALESCE(amount_paid, 0) + COALESCE(balance_due, 0)
            - COALESCE(total_amount, 0)
        ) > 0.01
        OR COALESCE(amount_paid, 0) > COALESCE(total_amount, 0) + 0.01
        """
    ),
    (
        "DQ-C08", "Expense arithmetic", "Warning",
        """
        SELECT CAST(expense_id AS VARCHAR) AS bad_key
        FROM raw.fact_expense
        WHERE ABS(
            COALESCE(amount_excl_gst, 0) + COALESCE(gst_amount, 0)
            - COALESCE(total_amount, 0)
        ) > 0.01
        """
    ),
    (
        "DQ-C09", "Task dates sensible", "Warning",
        """
        SELECT CAST(task_id AS VARCHAR) AS bad_key
        FROM raw.fact_task
        WHERE (
            started_date IS NOT NULL
            AND completed_date IS NOT NULL
            AND TRY_CAST(completed_date AS DATE)
                < TRY_CAST(started_date AS DATE)
        )
        OR (status = 'Done' AND completed_date IS NULL)
        """
    ),
    (
        "DQ-C10", "Leave dates sensible", "Warning",
        """
        SELECT CAST(leave_request_id AS VARCHAR) AS bad_key
        FROM raw.fact_leave
        WHERE TRY_CAST(end_date AS DATE)
              < TRY_CAST(start_date AS DATE)
        """
    ),
    (
        "DQ-C11", "AI feeds are fresh", "Warning",
        """
        SELECT CAST(prediction_id AS VARCHAR) AS bad_key
        FROM raw.fact_attrition_risk
        WHERE TRY_CAST(as_of_date AS DATE)
              < CURRENT_DATE - INTERVAL 30 DAY
        """
    ),
    (
        "DQ-C12", "Dimension history does not overlap", "Critical",
        """
        SELECT CAST(a.employee_key AS VARCHAR) AS bad_key
        FROM raw.dim_employee a
        JOIN raw.dim_employee b
          ON a.employee_id = b.employee_id
         AND a.employee_key < b.employee_key
         AND CAST(a.valid_from AS DATE) <=
             COALESCE(CAST(b.valid_to AS DATE), DATE '9999-12-31')
         AND CAST(b.valid_from AS DATE) <=
             COALESCE(CAST(a.valid_to AS DATE), DATE '9999-12-31')
        """
    ),
    (
        "DQ-C13", "Pipeline freshness", "Critical",
        """
        SELECT CAST(finished_at AS VARCHAR) AS bad_key
        FROM etl_run_log
        WHERE status = 'SUCCESS'
          AND finished_at < CURRENT_TIMESTAMP - INTERVAL 24 HOUR
        """
    ),
    (
        "DQ-C14", "Minimum group size", "Critical",
        """
        WITH threshold AS (
            SELECT TRY_CAST(
                REGEXP_EXTRACT(minimum_group_size, '[0-9]+')
                AS INTEGER
            ) AS min_size
            FROM raw.metric_dictionary
            WHERE metric_id = 'M27'
        ),
        department_counts AS (
            SELECT d.department_id,
                   COUNT(DISTINCT r.employee_id) AS employee_count
            FROM raw.fact_attrition_risk r
            JOIN raw.dim_employee d
              ON r.employee_id = d.employee_id
             AND d.is_current = 'Y'
            WHERE d.department_id IS NOT NULL
            GROUP BY d.department_id
        )
        SELECT CAST(dc.department_id AS VARCHAR) AS bad_key
        FROM department_counts dc
        CROSS JOIN threshold t
        WHERE t.min_size IS NOT NULL
          AND dc.employee_count < t.min_size
        """
    ),
]


def main():
    con = duckdb.connect(DB_FILE)
    results = []

    for check_id, name, severity, sql in CHECKS:
        run_time = datetime.now()

        try:
            bad_rows = con.execute(sql).fetchdf()
            count = len(bad_rows)

            if count == 0:
                status = "PASS"
            elif severity == "Critical":
                status = "FAIL"
            else:
                status = "WARNING"

            details = ", ".join(
                bad_rows.iloc[:5, 0].astype(str).tolist()
            )

        except Exception as exc:
            count = -1
            status = "BLOCKED"
            details = str(exc).splitlines()[0][:250]

        results.append((
            check_id, name, severity, count,
            status, run_time, details
        ))

        print(
            f"{check_id} | {name} | {status} "
            f"| bad_rows={count}"
        )
        if status == "BLOCKED":
            print(f"  Reason: {details}")

    con.execute("DROP TABLE IF EXISTS dq_results")
    con.execute("""
        CREATE TABLE dq_results (
            check_id VARCHAR,
            check_name VARCHAR,
            severity VARCHAR,
            bad_rows INTEGER,
            status VARCHAR,
            run_time TIMESTAMP,
            details VARCHAR
        )
    """)

    con.executemany("""
        INSERT INTO dq_results
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, results)

    print("\nLATEST RUN SUMMARY")
    print(con.execute("""
        SELECT status, COUNT(*) AS checks
        FROM dq_results
        GROUP BY status
        ORDER BY status
    """).fetchdf().to_string(index=False))

    print("\nLATEST CHECK DETAILS")
    print(con.execute("""
        SELECT check_id, check_name, severity, bad_rows, status
        FROM dq_results
        ORDER BY check_id
    """).fetchdf().to_string(index=False))

    con.close()


if __name__ == "__main__":
    main()
