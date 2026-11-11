# Task 13 – Validation Vault Reference Difference Notes

## 1. Department-Month Matching
- Reference rows: 198
- Matched department-month keys: 198
- Unmatched keys: 0

## 2. Metrics Matching the Reference
The following metrics have zero differences:
- Employer Cost
- Gross Pay
- Overtime Pay
- Overtime Hours
- Headcount End
- Hires
- Exits
- Monthly Attrition

## 3. Late Arrivals
Two department-month differences remain:
- D01 – November 2025: Source result 209; reference 206.
- D04 – March 2026: Source result 60; reference 58.

The raw attendance source aggregation confirms the dashboard values. These differences are retained for transparency.

## 4. Attendance Rate
The reference comparison reports 127 differing department-month values.

The dashboard calculates attendance rate using:

Present Days / Scheduled Days × 100

The raw attendance source contains 7,343 records. In 532 records, the stored attendance_rate differs from the ratio of present_days to scheduled_days.

For D01, August 2025:
- Ratio of department totals: 94.3423%
- Average stored attendance rate: 94.4164%
- Reference attendance rate: 94.49%

For D00, August 2025:
- Average stored attendance rate: 92.11%
- Reference attendance rate: 92.11%

The attendance calculation difference remains documented and requires further source-definition validation. No source values or comparison tolerances were altered to force a match.

## 5. Validation Conclusion
Eight of ten compared metrics match the reference with zero differences. Department-month keys match completely.

The remaining late-arrival and attendance-rate differences are disclosed rather than silently adjusted.

## 6. Analytical Limitation
Higher overtime and higher attrition occurring together does not establish that overtime causes attrition. Workload, staffing, management, compensation, seasonality and job roles may also influence the relationship.