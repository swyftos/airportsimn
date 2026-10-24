# Person 2 — Explainable AI Demand Forecasting

**Planning window: February 11–17, 2027. Scope: a fictional FBO at LAX.**

## Deliverables

- `forecast_model.py`: executable training, evaluation, forecasting, and uncertainty pipeline.
- `demand_predictions.csv`: daily arrivals/departures by aircraft category and Low/Medium/High scenario.
- `uncertainty_results.csv`: matching 90% conditional mean confidence bounds and 90% predictive ranges.

Additional integration aids: `daily_summary.csv`, `prediction_explanations.csv`, `model_coefficients.csv`, `evaluation_metrics.csv`, `backtest_predictions.csv`, `model_report.json`, demo inputs, and tests.

## Run

Python 3.10+ with NumPy and Pandas. No scikit-learn, API key, or network access is required.

```
pip install numpy pandas
python forecast_model.py
python test_forecast_model.py
```

The default run **generates synthetic daily history and simulated reservations** and writes the outputs beside the script. The seed makes results reproducible. Demo history covers 2023–2025; it is NOT a reconstruction of real LAX operations. No real daily historical outcome dataset was supplied with the team guidelines.

Use Person 1's data when available:

```
python forecast_model.py --history historical_traffic.csv --reservations reservations.csv --baseline baseline.csv --as-of 2026-10-23 --output-dir results
```

Omit `--baseline` or `--reservations` if unavailable. Airport-wide history additionally requires `--fbo-share 0.10` (example assumption only). Share is applied to modeled airport traffic, never silently treated as measured FBO market share. Airport-scope evaluation remains airport-scope; it does not establish FBO accuracy. Do not supply airport-wide movements as arrivals and departures by copying the same total into both columns.

## Input contracts for Person 1

`historical_traffic.csv`: one DAILY row per date and aircraft category:

```
date,aircraft_category,arrivals,departures,traffic_scope,data_classification,source
```

- Separate actual arrivals and departures, not undifferentiated movement totals.
- `traffic_scope`: exactly one of `fbo` or `airport` throughout the file.
- `data_classification`: `verified_public`, `estimated_benchmark`, or `synthetic`.
- `source`: document/URL or synthetic generator attribution.
- Include at least 210 daily records per category, with sufficient continuity for lags and seven-day evaluation blocks. The final 28 days must be complete.
- Missing dates are not zeros. Monthly aggregates cannot be expanded into "observed" daily records. Any disaggregation must remain estimated/synthetic and cannot establish verified daily accuracy.
- Categories may describe general aviation or air taxi fleets; the demo uses light, super midsize, and large business jets. No airline-commercial uplift is inferred from business-jet benchmarks.
- Years 2020, 2021, and 2022 are excluded before fitting, calibration, and evaluation per revised instructions. The 2022 LA Super Bowl cannot simultaneously be claimed as a held-out validation result under this exclusion.

`reservations.csv`: aggregate counts only, one row per date/category:

```
date,aircraft_category,reserved_arrivals,reserved_departures,as_of_date,data_classification
```

Snapshots must be known at forecast issue time. Counts are FBO counts, even if historical scope is airport. Missing rows mean no supplied reservations, not proof of zero actual bookings. Person 3 retains responsibility for individual parking requests, durations, occupancy, size, capacity, and resource constraints.

Optional `baseline.csv`: one FBO ordinary-day expectation per date/category:

```
date,aircraft_category,arrivals,departures,traffic_scope,data_classification
```

This is a comparison reference for additional demand; it does not replace the learned model. Missing rows use the learned normal forecast.

## Explainability for judges

1. Fit separate ridge regressions for each aircraft category and direction on `log(1 + movements)`.
2. Normal-demand variables: weekday, annual sine/cosine seasonality, linear time trend, seven-day lag, and trailing 28-day mean. Category affects predictions through its own fitted model. Ridge stabilizes coefficients when predictors overlap. Coefficients are associations, not causal effects. Point estimates are log-scale model back-transforms, not unbiased arithmetic expectations.
3. Recursively forecast the normal baseline through the entire historical-data gap, without inventing observations.
4. Apply a visible, hand-specified seven-day event profile. `--la-premium .20` increases the **incremental event lift** by 20%; it does not increase total traffic by 20%. This is a scenario assumption, not an empirically estimated LAX effect.
5. Low/Medium/High scale incremental event lift by 0.70/1.00/1.40. They are planning assumptions, not probability quantiles or claims about parking capacity.
6. Final planning estimate = `max(event-adjusted normal forecast, reservations × assumed show rate)`. Reservations are already part of total demand, so adding them directly would double count. Default show rate is an assumed 90%.

`prediction_explanations.csv` gives an additive reconciliation: normal forecast + event addition + any reservation-floor addition = final estimate. `model_coefficients.csv` exposes every model coefficient. `model_report.json` records all event, scenario, issue-date, share, and provenance assumptions.

## Event assumptions and the available reference

WINGX's February 12, 2026 Bay Area event report, reproduced by GlobalAir, reports over 1,000 business-jet arrivals February 5–8 (approximately twice normal) and nearly 600 departures February 9 (approximately three times normal):

https://www.globalair.com/articles/bay-area-airports-report-3x-the-normal-business-jets-traffic-during-super-bowl/11933

These are regional aggregate business-jet benchmarks, NOT LAX totals, not FBO counts, and not seven daily observations. They motivate stress testing only. The script does not fit daily LAX event coefficients from these two aggregates. All seven daily uplift values and the extra LA premium are explicit assumptions. Do not present the demo totals as an established real-world expectation. Person 1 must provide real daily history and appropriate comparable event observations for a credible event calibration.

## Uncertainty

Two distinct quantities are provided for each prediction:

- `lower90_mean`, `upper90_mean`: moving-block residual bootstrap confidence interval for the conditional model point estimate, holding scenario, booking show rate, capture share, and event profile fixed.
- `lower90_prediction`, `upper90_prediction`: simulated future-demand range incorporating bootstrap paths, empirical historical log residuals, triangular event-lift variability (0.7, 1.0, 1.3), and binomial booking show uncertainty.

Seven-day blocks preserve some temporal residual dependence. Prediction ranges are model-based, continuous expected-count ranges; do not treat fractional counts as assignable aircraft. Round up operational requirements downstream. No passenger data is used.

A separate split-conformal 90% interval is calibrated and scored on ordinary historical weeks. **That historical coverage is NOT a guarantee for event-week ranges.** The CSV explicitly sets `event_coverage_validated=False`. Long data gaps, structural changes, capture-share uncertainty, incomplete booking capture, and cross-category correlation are not fully represented. Do not sum category interval endpoints to obtain a valid total interval.

## Accuracy evaluation

Chronological split per category/direction: first 65% of usable dates train, next 17% calibrate, final 18% test. Held-out evaluation uses disjoint seven-day forecast blocks; no within-block outcomes are fed into predictors. The baseline is the previous eight weeks' average for the same weekday. Calibration residuals set the conformal radius; only the final test segment measures coverage and MAE. After evaluation, the production forecast model refits on all supplied historical data.

`evaluation_metrics.csv` reports model MAE, baseline MAE, percentage improvement (negative is worse), interval coverage, evaluation scope, provenance, and sample sizes. `backtest_predictions.csv` supports auditing actuals versus predictions.

**Default results are synthetic test performance, not observed historical accuracy.** Real-data metrics require verified observed daily outcomes. No claim of outperforming the historical baseline should be made unless those results support it. No observed Super Bowl daily outcomes are available here, so event-week accuracy is unmeasured. Estimated or mixed inputs are labeled accordingly.

## Integration with Persons 3 and 4

Join the two primary CSVs on `date,scenario,aircraft_category,direction`. `expected_movements` is the central planning estimate; use the prediction range to stress-test resources. `normal_fbo_baseline` is the ordinary-traffic comparison. `daily_summary.csv` sums category point forecasts for presentation. All dates are Los Angeles calendar dates. No passenger identities, registration numbers, or owner details are required.

This module neither allocates parking nor approves/cancels reservations, aircraft movements, facility activation, spending, or staffing changes. Those remain recommendations and human decisions elsewhere in the system.
