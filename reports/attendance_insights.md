# Attendance and Leave Insights — PulseIQ

## 1. Objective

This analysis examines attendance trends, department-level attendance, leave patterns, late arrivals, and potential attendance anomalies using the available PulseIQ dataset. The goal is to identify patterns that HR can investigate and use for workforce planning.

## 2. Key Findings

### Finding 1: Monthly Attendance Trend

Attendance improved from **94.29% in August 2026 to 95.22% in September 2026**, an increase of **0.93 percentage points**.

The three-month rolling attendance rate increased from **93.88% in August 2026 to 94.57% in September 2026**.

**Interpretation:** The latest month shows an improvement in the recorded attendance rate. This single-month increase does not prove a long-term improvement or identify its cause.

**Recommended HR action:** Continue monitoring monthly attendance and compare future results with staffing levels, approved leave, and operational requirements.

### Finding 2: Department-Level Attendance

The department summary contains 11 departments. Recorded attendance rates vary across departments, with the available results generally ranging from approximately **94.4% to 94.9%**.

Examples from the summary include:
- Department D05: approximately 94.4%
- Department D10: approximately 94.4%
- Department D01: approximately 94.5%
- Department D04: approximately 94.8%
- Department D03: approximately 94.9%

**Interpretation:** The observed differences are relatively small. Departments with lower rates may need further review, but comparisons should account for differences in record counts, scheduled days, staffing, and leave.

**Recommended HR action:** Compare department attendance using consistent denominators and investigate persistent differences before recommending interventions.

### Finding 3: Leave Patterns

The available leave summary reports the following approved leave totals:

| Leave code | Requests | Approved days |
|---|---:|---:|
| EL | 1,130 | 2,336 |
| CL | 977 | 1,995 |
| SL | 836 | 1,769 |
| ML | 7 | 910 |
| BL | 80 | 137 |
| LOP | 58 | 129 |

The code meanings must be confirmed against the official leave codebook. In particular, the reported 910 approved days associated with `ML` should be validated against the original leave records and the applicable code definition.

**Interpretation:** The leave summary shows differences in request counts and approved days by code. These totals alone do not establish why employees took leave or whether any pattern is unusual.

**Recommended HR action:** Validate leave codes, date ranges, and approved durations, then review leave patterns alongside attendance and staffing needs.

## 3. Late Arrivals and Potential Anomalies

The available data records late arrivals and attendance measures at employee-period level. The monthly summary reports **569 late arrivals in August 2026** and **618 in September 2026**.

The raw count increased by 49. However, the number of records and exposure to scheduled work may also affect this count. Therefore, the increase should not automatically be interpreted as a deterioration in punctuality.

An exploratory Isolation Forest analysis was run on **7,343 attendance employee-period records** using available attendance features. It flagged **220 records** as potential anomalies.

These flags are model-generated signals for further review. They are not confirmed policy violations, misconduct, or proof of incorrect attendance.

**Recommended HR action:**
- Validate flagged records against source attendance logs and approved leave.
- Review late-arrival rates relative to scheduled days and comparable employee groups.
- Document the model's input features and parameters before using its output for operational decisions.

The original AI/ML team's anomaly sample file was not located in the project files inspected. The current anomaly output is therefore an exploratory analysis, not a verified integration of the original team sample.

## 4. Data Limitations

- The available attendance records are aggregated by employee-period. The `period_end_date` is a reporting-period end date, not necessarily the date on which an employee attended work.
- Daily attendance records were not found in the files inspected. Consequently, Monday-to-Sunday attendance patterns cannot be reliably calculated from the available attendance data.
- Exact daily anomaly dates cannot be verified from the monthly employee-period records.
- The original AI/ML anomaly sample was not located in the project files inspected.
- Leave codes `EL`, `CL`, `SL`, `ML`, `BL`, and `LOP` require confirmation against the official codebook.
- The dataset may contain synthetic data. Observed changes do not establish causation and should be validated against actual HR records.
- Department comparisons and raw late-arrival counts should be interpreted alongside record counts and scheduled work exposure.

## 5. Dashboard and Supporting Files

The Superset dashboard is named **Attendance & Leave**. It is intended to present the available attendance and leave visualizations. Dashboard filters, chart behavior, and saved configuration should be tested in Superset before being reported as verified.

Supporting files:
- `reports/attendance_monthly_trend.csv`
- `reports/attendance_department_summary.csv`
- `reports/approved_leave_by_type.csv`
- `reports/attendance_anomalies.csv`
- `dashboards/attendance_monthly_chart_data.csv`
- `dashboards/attendance_department_chart_data.csv`
- `sql/task4_attendance_analysis.sql`

## 6. Conclusion

The available data shows a higher recorded attendance rate in September 2026 than in August 2026, small differences across departments, and variation in approved leave totals. The exploratory Isolation Forest analysis flagged 220 employee-period records for further review.

These results provide a starting point for HR investigation rather than definitive conclusions. Daily attendance records and the original AI/ML anomaly sample are needed to complete weekday analysis and integrate the team's anomaly results. All findings should be validated against authoritative HR records before operational decisions are made.