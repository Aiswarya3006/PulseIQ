from pathlib import Path
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

ROOT_DIR = Path(__file__).resolve().parent.parent
CLEAN_DIR = ROOT_DIR / "clean"

DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "pulseiq_dw",
    "user": "pulseiq",
    "password": "pulseiq_dev",
}


def read_csv(filename):
    path = CLEAN_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return pd.read_csv(path)


def val(value):
    if value is None or pd.isna(value):
        return None
    return value


def as_date(value):
    value = val(value)
    return None if value is None else pd.to_datetime(value).date()


def as_float(value):
    value = val(value)
    return None if value is None else float(value)


def as_int(value):
    value = val(value)
    return None if value is None else int(value)


def load_departments(conn, employees, salary, payroll):
    departments = {}

    for frame in (salary, payroll):
        if "department_id" in frame.columns:
            for item in frame["department_id"].dropna():
                departments[str(item)] = str(item)

    if "department" in employees.columns:
        for item in employees["department"].dropna():
            departments.setdefault(str(item), str(item))

    data = list(departments.items())

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO dim_department (department_id, department_name)
            VALUES %s
            ON CONFLICT (department_id)
            DO UPDATE SET department_name = EXCLUDED.department_name
            """,
            data,
        )

    print("dim_department:", len(data))


def load_roles(conn, salary):
    cols = [
        "role_id", "role_title", "level", "grade",
        "band_min_annual", "band_mid_annual", "band_max_annual",
    ]

    for col in cols:
        if col not in salary.columns:
            salary[col] = None

    frame = salary[cols].dropna(subset=["role_id"])
    frame = frame.drop_duplicates(subset=["role_id"])

    data = [
        tuple(val(item) for item in row)
        for row in frame.itertuples(index=False, name=None)
    ]

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO dim_role (
                role_id, role_title, level, grade,
                band_min_annual, band_mid_annual, band_max_annual
            )
            VALUES %s
            ON CONFLICT (role_id)
            DO UPDATE SET
                role_title = EXCLUDED.role_title,
                level = EXCLUDED.level,
                grade = EXCLUDED.grade,
                band_min_annual = EXCLUDED.band_min_annual,
                band_mid_annual = EXCLUDED.band_mid_annual,
                band_max_annual = EXCLUDED.band_max_annual
            """,
            data,
        )

    print("dim_role:", len(data))


def load_employees(conn, employees):
    cols = [
        "employee_id", "employee_name", "joining_date",
        "leaving_date", "department",
    ]

    for col in cols:
        if col not in employees.columns:
            employees[col] = None

    employees = employees.dropna(subset=["employee_id"])
    employees = employees.drop_duplicates(subset=["employee_id"])

    data = []

    for _, row in employees.iterrows():
        joining = as_date(row["joining_date"])
        leaving = as_date(row["leaving_date"])

        data.append((
            str(row["employee_id"]),
            val(row["employee_name"]),
            val(row["department"]),
            None,
            joining,
            leaving,
            joining or pd.Timestamp("2000-01-01").date(),
            None,
            True,
        ))

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO dim_employee (
                employee_id, employee_name, department_id, role_id,
                joining_date, leaving_date, valid_from, valid_to, is_current
            )
            VALUES %s
            ON CONFLICT (employee_id, valid_from) DO NOTHING
            """,
            data,
        )

    print("dim_employee source rows:", len(data))


def load_payroll(conn, payroll):
    cols = [
        "payroll_item_id", "employee_id", "date_key", "period_end_date",
        "department_id", "role_id", "gross_pay", "net_pay",
        "total_deductions", "employer_cost", "payable_days",
        "lop_days", "headcount_flag",
    ]

    for col in cols:
        if col not in payroll.columns:
            payroll[col] = None

    payroll = payroll.dropna(subset=["payroll_item_id", "employee_id"])
    data = []

    for _, r in payroll.iterrows():
        data.append((
            str(r["payroll_item_id"]),
            str(r["employee_id"]),
            as_int(r["date_key"]),
            as_date(r["period_end_date"]),
            val(r["department_id"]),
            val(r["role_id"]),
            as_float(r["gross_pay"]),
            as_float(r["net_pay"]),
            as_float(r["total_deductions"]),
            as_float(r["employer_cost"]),
            as_float(r["payable_days"]),
            as_float(r["lop_days"]),
            as_int(r["headcount_flag"]),
        ))

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO fact_payroll (
                payroll_item_id, employee_id, date_key, period_end_date,
                department_id, role_id, gross_pay, net_pay,
                total_deductions, employer_cost, payable_days,
                lop_days, headcount_flag
            )
            VALUES %s
            ON CONFLICT (payroll_item_id)
            DO UPDATE SET
                employee_id = EXCLUDED.employee_id,
                date_key = EXCLUDED.date_key,
                period_end_date = EXCLUDED.period_end_date,
                department_id = EXCLUDED.department_id,
                role_id = EXCLUDED.role_id,
                gross_pay = EXCLUDED.gross_pay,
                net_pay = EXCLUDED.net_pay,
                total_deductions = EXCLUDED.total_deductions,
                employer_cost = EXCLUDED.employer_cost,
                payable_days = EXCLUDED.payable_days,
                lop_days = EXCLUDED.lop_days,
                headcount_flag = EXCLUDED.headcount_flag
            """,
            data,
            page_size=1000,
        )

    print("fact_payroll:", len(data))


def add_missing_employees(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH employee_sources AS (
                SELECT employee_id,
                       MAX(department_id) AS department_id,
                       MAX(role_id) AS role_id,
                       MIN(period_end_date) AS first_seen
                FROM fact_payroll
                GROUP BY employee_id
            )
            INSERT INTO dim_employee (
                employee_id, employee_name, department_id, role_id,
                joining_date, leaving_date, valid_from, valid_to, is_current
            )
            SELECT p.employee_id, NULL, p.department_id, p.role_id,
                   NULL, NULL,
                   COALESCE(p.first_seen, DATE '2000-01-01'),
                   NULL, TRUE
            FROM employee_sources p
            WHERE NOT EXISTS (
                SELECT 1 FROM dim_employee e
                WHERE e.employee_id = p.employee_id
                  AND e.is_current = TRUE
            )
            ON CONFLICT (employee_id, valid_from) DO NOTHING
            """
        )
    print("Missing payroll employees checked")


def load_leave(conn, leave):
    cols = [
        "leave_request_id", "employee_id", "leave_type_code",
        "start_date", "end_date", "days",
    ]

    for col in cols:
        if col not in leave.columns:
            leave[col] = None

    leave_types = [
        (str(x),) for x in
        leave["leave_type_code"].dropna().astype(str).unique()
    ]

    data = []

    for _, r in leave.iterrows():
        if val(r["employee_id"]) is None:
            continue

        request_id = val(r["leave_request_id"])
        data.append((
            str(r["employee_id"]),
            val(r["leave_type_code"]),
            as_date(r["start_date"]),
            as_date(r["end_date"]),
            as_float(r["days"]),
            str(request_id) if request_id is not None else None,
        ))

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO dim_leave_type (leave_type)
            VALUES %s
            ON CONFLICT (leave_type) DO NOTHING
            """,
            leave_types,
        )

        cur.execute("""
            ALTER TABLE fact_leave
            ADD COLUMN IF NOT EXISTS leave_request_id TEXT
        """)

        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_fact_leave_request_id
            ON fact_leave (leave_request_id)
            WHERE leave_request_id IS NOT NULL
        """)

        execute_values(
            cur,
            """
            INSERT INTO fact_leave (
                employee_id, leave_type, start_date,
                end_date, leave_days, leave_request_id
            )
            VALUES %s
            ON CONFLICT (leave_request_id)
            WHERE leave_request_id IS NOT NULL
            DO UPDATE SET
                employee_id = EXCLUDED.employee_id,
                leave_type = EXCLUDED.leave_type,
                start_date = EXCLUDED.start_date,
                end_date = EXCLUDED.end_date,
                leave_days = EXCLUDED.leave_days
            """,
            data,
            page_size=1000,
        )

    print("fact_leave:", len(data))


def prepare_attendance(conn):
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE fact_attendance
                ADD COLUMN IF NOT EXISTS scheduled_days NUMERIC(8,2),
                ADD COLUMN IF NOT EXISTS present_days NUMERIC(8,2),
                ADD COLUMN IF NOT EXISTS wfh_days NUMERIC(8,2),
                ADD COLUMN IF NOT EXISTS half_days_unpaid NUMERIC(8,2),
                ADD COLUMN IF NOT EXISTS paid_leave_days NUMERIC(8,2),
                ADD COLUMN IF NOT EXISTS unpaid_absence_days NUMERIC(8,2),
                ADD COLUMN IF NOT EXISTS late_arrivals INTEGER,
                ADD COLUMN IF NOT EXISTS avg_hours_worked NUMERIC(8,2),
                ADD COLUMN IF NOT EXISTS overtime_hours NUMERIC(8,2),
                ADD COLUMN IF NOT EXISTS attendance_rate NUMERIC(8,4),
                ADD COLUMN IF NOT EXISTS source_attendance_fact_id TEXT
        """)


def load_attendance(conn, attendance):
    cols = [
        "attendance_fact_id", "employee_id", "department_id",
        "scheduled_days", "present_days", "wfh_days", "half_days_unpaid",
        "paid_leave_days", "unpaid_absence_days", "late_arrivals",
        "avg_hours_worked", "overtime_hours", "attendance_rate",
        "period_end_date",
    ]

    for col in cols:
        if col not in attendance.columns:
            attendance[col] = None

    attendance = attendance.dropna(
        subset=["employee_id", "period_end_date"]
    )

    data = []

    for _, r in attendance.iterrows():
        data.append((
            str(r["employee_id"]),
            as_date(r["period_end_date"]),
            val(r["department_id"]),
            as_float(r["scheduled_days"]),
            as_float(r["present_days"]),
            as_float(r["wfh_days"]),
            as_float(r["half_days_unpaid"]),
            as_float(r["paid_leave_days"]),
            as_float(r["unpaid_absence_days"]),
            as_int(r["late_arrivals"]),
            as_float(r["avg_hours_worked"]),
            as_float(r["overtime_hours"]),
            as_float(r["attendance_rate"]),
            str(r["attendance_fact_id"]),
        ))

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO fact_attendance (
                employee_id, attendance_date, department_id,
                scheduled_days, present_days, wfh_days, half_days_unpaid,
                paid_leave_days, unpaid_absence_days, late_arrivals,
                avg_hours_worked, overtime_hours, attendance_rate,
                source_attendance_fact_id
            )
            VALUES %s
            ON CONFLICT (employee_id, attendance_date)
            DO UPDATE SET
                department_id = EXCLUDED.department_id,
                scheduled_days = EXCLUDED.scheduled_days,
                present_days = EXCLUDED.present_days,
                wfh_days = EXCLUDED.wfh_days,
                half_days_unpaid = EXCLUDED.half_days_unpaid,
                paid_leave_days = EXCLUDED.paid_leave_days,
                unpaid_absence_days = EXCLUDED.unpaid_absence_days,
                late_arrivals = EXCLUDED.late_arrivals,
                avg_hours_worked = EXCLUDED.avg_hours_worked,
                overtime_hours = EXCLUDED.overtime_hours,
                attendance_rate = EXCLUDED.attendance_rate,
                source_attendance_fact_id =
                    EXCLUDED.source_attendance_fact_id
            """,
            data,
            page_size=1000,
        )

    print("fact_attendance:", len(data))


def load_dates(conn, payroll, attendance, leave):
    dates = set()

    for frame, columns in [
        (payroll, ["period_end_date"]),
        (attendance, ["period_end_date"]),
        (leave, ["start_date", "end_date"]),
    ]:
        for col in columns:
            if col in frame.columns:
                for item in frame[col].dropna():
                    dates.add(pd.to_datetime(item).date())

    data = []

    for d in sorted(dates):
        data.append((
            int(d.strftime("%Y%m%d")),
            d,
            d.year,
            d.month,
            d.strftime("%B"),
            d.strftime("%A"),
        ))

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO dim_date (
                date_key, full_date, year, month, month_name, weekday_name
            )
            VALUES %s
            ON CONFLICT (date_key)
            DO UPDATE SET
                full_date = EXCLUDED.full_date,
                year = EXCLUDED.year,
                month = EXCLUDED.month,
                month_name = EXCLUDED.month_name,
                weekday_name = EXCLUDED.weekday_name
            """,
            data,
        )

    print("dim_date:", len(data))


def load_headcount(conn):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO fact_headcount_monthly (
                month_start, department_id, headcount
            )
            SELECT
                DATE_TRUNC('month', period_end_date)::date,
                department_id,
                COUNT(DISTINCT employee_id)::integer
            FROM fact_payroll
            WHERE period_end_date IS NOT NULL
              AND department_id IS NOT NULL
            GROUP BY 1, 2
            ON CONFLICT (month_start, department_id)
            DO UPDATE SET headcount = EXCLUDED.headcount
        """)
        print("Headcount records updated:", cur.rowcount)


def print_counts(conn):
    tables = [
        "dim_department", "dim_role", "dim_employee", "dim_date",
        "dim_leave_type", "fact_payroll", "fact_leave",
        "fact_attendance", "fact_headcount_monthly",
    ]

    print("\n--- WAREHOUSE ROW COUNTS ---")

    with conn.cursor() as cur:
        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            print(f"{table}: {cur.fetchone()[0]}")


def main():
    employees = read_csv("employee_clean.csv")
    payroll = read_csv("payroll_clean.csv")
    attendance = read_csv("attendance_clean.csv")
    leave = read_csv("leave_clean.csv")
    salary = read_csv("salary_band_clean.csv")

    conn = psycopg2.connect(**DB_CONFIG)

    try:
        conn.autocommit = False

        load_departments(conn, employees, salary, payroll)
        load_roles(conn, salary)
        load_employees(conn, employees)
        load_payroll(conn, payroll)
        add_missing_employees(conn)
        load_leave(conn, leave)
        prepare_attendance(conn)
        load_attendance(conn, attendance)
        load_dates(conn, payroll, attendance, leave)
        load_headcount(conn)

        conn.commit()
        print_counts(conn)
        print("\nWarehouse load completed successfully.")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
