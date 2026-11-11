# Task 14 - AI Signals Dashboard

## Overview
The AI Signals Dashboard presents anomaly detection results, workforce forecasts and attrition-risk signals from PulseIQ source tables.

## 1. Anomaly Analysis
- Flagged anomalies: 405
- Records with valid money-at-risk values: 184
- Records with missing money values: 221
- Total measurable money at risk: Rs. 31,421,239.07
- Anomalies are ranked by money at risk, from highest to lowest.
- Missing money values are kept separate and are not treated as zero.

## 2. Forecast Analysis
- Actual data is available through September 2026.
- Forecasts begin in October 2026 and extend through March 2027.
- Headcount forecasts include 80% confidence intervals.
- Attrition forecasts include 80% confidence intervals.
- There are currently zero overlapping actual and forecast months.
- Forecast error is therefore reported as "Not measurable yet".

## 3. Critical Thinking: Forecast Error
A 12% forecast error is not automatically good or bad. It should be compared with a baseline forecast, business tolerance and historical performance. We should also examine whether predictions consistently overestimate or underestimate actual values. Headcount and attrition require separate evaluation. Percentage errors can be misleading when actual attrition is very low.

The supplied forecasts cannot currently be evaluated against actual results because their date ranges do not overlap.

## 4. Attrition Risk
- Total risk records: 430
- Low risk: 301
- Medium risk: 86
- High risk: 43

High-risk records are signals for human review, not certainty that an employee will leave. Risk scores should support investigation and planning, not automatic employment decisions.

## 5. Responsible AI Labelling
Every AI chart is labelled exactly:

AI-generated, for human review

## Evidence
- AI Signals Dashboard screenshots
- Forecast error evaluation CSV: reports/task14_forecast_error_evaluation.csv
