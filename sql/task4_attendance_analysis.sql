-- Task 4 Attendance & Leave Analysis
SELECT date_trunc('month', attendance_date)::date AS month,
       AVG(attendance_rate) AS avg_attendance_rate,
       SUM(late_arrivals) AS late_arrivals,
       COUNT(*) AS employee_period_records
FROM fact_attendance
GROUP BY 1 ORDER BY 1;

SELECT department_id, AVG(attendance_rate) AS avg_attendance_rate,
       SUM(late_arrivals) AS late_arrivals, COUNT(*) AS records
FROM fact_attendance
GROUP BY department_id ORDER BY avg_attendance_rate;

SELECT leave_type, COUNT(*) AS approved_requests,
       SUM(leave_days) AS approved_leave_days
FROM fact_leave
WHERE lower(status) = 'approved'
GROUP BY leave_type ORDER BY approved_leave_days DESC;

-- Weekday analysis requires daily-grain attendance; this dataset is monthly aggregated.
