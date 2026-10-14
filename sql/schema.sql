
CREATE TABLE IF NOT EXISTS dim_department (
    department_key SERIAL PRIMARY KEY,
    department_id TEXT UNIQUE NOT NULL,
    department_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_role (
    role_key SERIAL PRIMARY KEY,
    role_id TEXT UNIQUE NOT NULL,
    role_title TEXT,
    level TEXT,
    grade TEXT,
    band_min_annual NUMERIC(14,2),
    band_mid_annual NUMERIC(14,2),
    band_max_annual NUMERIC(14,2)
);

CREATE TABLE IF NOT EXISTS dim_employee (
    employee_sk BIGSERIAL PRIMARY KEY,
    employee_id TEXT NOT NULL,
    employee_name TEXT,
    department_id TEXT,
    role_id TEXT,
    joining_date DATE,
    leaving_date DATE,
    valid_from DATE NOT NULL,
    valid_to DATE,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (employee_id, valid_from)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_employee_current
ON dim_employee(employee_id)
WHERE is_current = TRUE;

CREATE TABLE IF NOT EXISTS dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE UNIQUE NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_name TEXT NOT NULL,
    weekday_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_leave_type (
    leave_type_key SERIAL PRIMARY KEY,
    leave_type TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_payroll (
    payroll_item_id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL,
    date_key INTEGER,
    period_end_date DATE,
    department_id TEXT,
    role_id TEXT,
    gross_pay NUMERIC(14,2),
    net_pay NUMERIC(14,2),
    total_deductions NUMERIC(14,2),
    employer_cost NUMERIC(14,2),
    payable_days NUMERIC(8,2),
    lop_days NUMERIC(8,2),
    headcount_flag INTEGER
);

CREATE TABLE IF NOT EXISTS fact_leave (
    leave_id BIGSERIAL PRIMARY KEY,
    employee_id TEXT NOT NULL,
    leave_type TEXT,
    start_date DATE,
    end_date DATE,
    leave_days NUMERIC(8,2)
);

CREATE TABLE IF NOT EXISTS fact_attendance (
    employee_id TEXT NOT NULL,
    attendance_date DATE NOT NULL,
    department_id TEXT,
    status TEXT,
    late_minutes INTEGER DEFAULT 0,
    PRIMARY KEY (employee_id, attendance_date)
);

CREATE TABLE IF NOT EXISTS fact_headcount_monthly (
    month_start DATE NOT NULL,
    department_id TEXT NOT NULL,
    headcount INTEGER NOT NULL,
    PRIMARY KEY (month_start, department_id)
);
