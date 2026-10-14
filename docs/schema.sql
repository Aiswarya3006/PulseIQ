
-- PulseIQ Database Schema

CREATE TABLE IF NOT EXISTS dim_department (
    department_id SERIAL PRIMARY KEY,
    department_name VARCHAR(100) UNIQUE NOT NULL,
    effective_from DATE,
    effective_to DATE,
    is_current BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS dim_employee (
    employee_key SERIAL PRIMARY KEY,
    employee_id VARCHAR(50) NOT NULL,
    employee_name VARCHAR(150),
    department_id INTEGER REFERENCES dim_department(department_id),
    joining_date DATE,
    leaving_date DATE,
    effective_from DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_to DATE,
    is_current BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS dim_role (
    role_id SERIAL PRIMARY KEY,
    role_name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE UNIQUE NOT NULL,
    day_number INTEGER NOT NULL,
    month_number INTEGER NOT NULL,
    month_name VARCHAR(20) NOT NULL,
    quarter_number INTEGER NOT NULL,
    year_number INTEGER NOT NULL,
    weekday_name VARCHAR(20) NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_leave_type (
    leave_type_id SERIAL PRIMARY KEY,
    leave_type_name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_attendance (
    attendance_id SERIAL PRIMARY KEY,
    employee_key INTEGER REFERENCES dim_employee(employee_key),
    attendance_date DATE NOT NULL,
    attendance_status VARCHAR(30),
    check_in_time TIME,
    check_out_time TIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (employee_key, attendance_date)
);

CREATE TABLE IF NOT EXISTS fact_payroll (
    payroll_id SERIAL PRIMARY KEY,
    employee_key INTEGER REFERENCES dim_employee(employee_key),
    payroll_month DATE NOT NULL,
    basic_salary NUMERIC(12,2),
    bonus NUMERIC(12,2) DEFAULT 0,
    deductions NUMERIC(12,2) DEFAULT 0,
    net_salary NUMERIC(12,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (employee_key, payroll_month)
);

CREATE TABLE IF NOT EXISTS fact_leave (
    leave_id SERIAL PRIMARY KEY,
    employee_key INTEGER REFERENCES dim_employee(employee_key),
    leave_type_id INTEGER REFERENCES dim_leave_type(leave_type_id),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    leave_status VARCHAR(30),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (end_date >= start_date)
);

CREATE TABLE IF NOT EXISTS fact_headcount_monthly (
    headcount_id SERIAL PRIMARY KEY,
    month_date DATE NOT NULL,
    department_id INTEGER REFERENCES dim_department(department_id),
    total_employees INTEGER NOT NULL,
    new_joiners INTEGER DEFAULT 0,
    leavers INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (month_date, department_id),
    CHECK (total_employees >= 0),
    CHECK (new_joiners >= 0),
    CHECK (leavers >= 0)
);
