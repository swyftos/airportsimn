# Person 2 — AI Demand Forecasting

This is Marvin's runnable forecasting module. The current committed release uses observed daily FAA LAX general-aviation and air-taxi operations from 2023–2025, converted to an **estimated fictional-FBO history** using an assumed 10% share, 50/50 direction split, and 47/33/20 aircraft mix. It is not a forecast validated against FBO bookings. The key outputs are `demand_predictions.csv` and `uncertainty_results.csv`; see [PROVISIONAL_ASSUMPTIONS.md](PROVISIONAL_ASSUMPTIONS.md) for the current inputs and evidence. The `--demo` option below remains a separate synthetic example.

## Review without FBO records

Run `python marvin/person_2_forecasting/sensitivity_review.py` from the repository root. It regenerates [SENSITIVITY_REVIEW.md](SENSITIVITY_REVIEW.md), `sensitivity_forecast_totals.csv`, `analog_scenario_check.csv`, and `event_stress_cases.csv` from the committed release outputs. It compares 5%, 10%, and 15% assumed FBO shares, checks the current Low–High event band against public airport analogs, adds a larger event stress case, and summarizes the rolling backtest. It does not change the shared forecast or parking outputs. The share scaling only applies while the planning inputs have zero reservation floors.

Run `python marvin/person_2_forecasting/frozen_2026_holdout.py` to regenerate [FROZEN_2026_HOLDOUT.md](FROZEN_2026_HOLDOUT.md) and its daily/monthly scores. The model remains frozen at the end of 2025; 273 finalized January–September 2026 FAA LAX days test the airport-level daily pattern. The public extract can be regenerated with `python marvin/person_2_forecasting/calibration_evidence/fetch_2026_holdout.py`. It reconciles every month to a separate FAA monthly query and leaves release inputs unchanged.

Run `python marvin/person_2_forecasting/operational_stress.py` to regenerate [OPERATIONAL_STRESS.md](OPERATIONAL_STRESS.md) and its CSV. It compares ordinary arrival shares of 40%, 50%, and 60%, and a case with event arrivals one day earlier and departures one day later. These cases pass modified planning ranges to Elia's existing parking model without replacing the current release. They are assumption tests, not FBO measurements or calibrated probabilities.

## Run

Requires Python 3.10 or later. No packages or API keys are required. From this folder:

```text
python forecast_model.py --demo --output-dir demo_results
python forecast_model.py --history historical_traffic.csv --planning planning_inputs.csv --output-dir real_input_results
python -m unittest -v test_forecast_model.py
```

Use the included demo_historical_traffic.csv and demo_planning_inputs.csv as schema examples. The demo generator has a fixed seed (42). Outputs use the seven planning dates specified in the brief: February 11–17, 2027. The event dates are taken from the supplied project brief, not independently researched.

## Explainable model

A separate statistical learning model is fitted for each aircraft category and direction (arrivals/departures). It learns ordinary daily traffic from month and weekday:

```text
baseline = (sum of training counts for that month/weekday
            + 14 × mean training count for that weekday)
           / (number of matching training days + 14)

event forecast = baseline × [1 + event_indicator × (scenario multiplier − 1)]
reservation floor = reserved movements × assumed show rate
expected demand = max(event forecast, reservation floor)
```

The 14-day smoothing weight is a fixed modeling assumption, not a tuned or validated optimum. Reservations overlap the total demand forecast, so they are not added to it. The maximum is a transparent planning heuristic, not a learned reservation-conversion model. No identities, tail numbers, passenger details, or aircraft-owner data are needed.

Every prediction includes the ordinary baseline, event multiplier, reservation floor, reservation adjustment, incremental demand, provenance, and lower/upper bounds. These fields expose exactly what drives the estimate. Expected counts remain fractional; capacity planning can round upward downstream.

Low, Medium, and High are conditional assumptions, not probabilities or statistical quantiles. Demo event profiles assume arrivals build before the event and departures rise afterward. Medium arrival multipliers are 1.25, 1.6, 2.2, 1.8, 1.1, 1, 1; departure multipliers are 1, 1, 1.1, 1.3, 2.5, 1.8, 1.2. Low uses half the incremental uplift; High uses 1.6 times the incremental uplift. These are illustrative and must be replaced with evidence-backed team assumptions. The demo's 90% reservation show rate is also an assumption.

## Person 1 input contract

historical_traffic.csv: one row per calendar date and aircraft category, including explicit zero-traffic days.

| Column | Meaning |
| --- | --- |
| date | ISO date, 2016–2025 |
| aircraft_category | Stable category name, e.g. light_jet |
| arrivals, departures | Nonnegative counts or documented estimated counts |
| scope | Must be fbo |
| data_class | observed, estimated, or synthetic |
| source | Source reference or documented derivation |

The current forecast trains on 2023–2025 daily counts. The 2016–2019 airport history helps estimate the scale-free Presidents' Day factor; 2020–2022 are excluded from ordinary training. February 2022 event observations inform event scenarios separately and are not silently reintroduced into the ordinary baseline.

Airport-wide movements are not FBO demand, and total movements cannot identify arrivals and departures without another assumption. The current conversion uses **observed daily** airport counts and labels the share-allocated rows `estimated`; no monthly-to-daily allocation is used. Missing rows are not zeroes: complete the dataset deliberately before running. The model accepts irregular dates, but missingness can bias the averages and must be reviewed.

planning_inputs.csv: exactly one row per planning date and historical aircraft category.

| Column | Meaning |
| --- | --- |
| date, aircraft_category | Join keys |
| event_indicator | 0 or 1 |
| reserved_arrivals, reserved_departures | Aggregate reservations scheduled for that date/direction |
| reservation_show_rate | Assumed fraction from 0 to 1 |
| reservation_class | observed, estimated, or synthetic |
| assumption_source | Evidence reference or explicit assumption description |
| arrivals_multiplier_low/medium/high | Three separate columns; ordered and at least 1 |
| departures_multiplier_low/medium/high | Three separate columns; ordered and at least 1 |

A parking reservation with arrival and departure dates contributes once to each corresponding daily aggregate. Category shares are learned separately from their historical records rather than inferred from aircraft size. Size, length of stay, and parking space equivalents belong to Person 3.

## Accuracy and uncertainty

Unique historical dates are split chronologically into the first 60% for training, next 20% for calibration, and final 20% for testing. No future/test values enter model fitting or calibration. At least 180 dates and 30 rows per category in each split are required. The benchmark is each category/direction's training historical mean. evaluation_metrics.csv reports model MAE, benchmark MAE, percentage improvement (which may be negative), and empirical test interval coverage. Synthetic or estimated input yields a non_observed_demonstration label; its metrics are not real historical forecasting performance.

Baseline uncertainty uses absolute calibration residuals and the finite-sample split-conformal rank ceil((n+1) × coverage), with nominal coverage 90% by default. These are prediction intervals for daily counts, not confidence intervals for a mean. Time dependence, changing operating conditions, and the long gap to 2027 can invalidate the exchangeability assumption; nominal coverage is not a guarantee. The calibrated model stays frozen rather than refitting on the test period. Thus later history evaluates the model but does not update its learned averages. For production, establish rolling-origin evaluation and a fresh calibration period before retraining.

Event planning ranges scale the baseline bounds by the scenario multiplier. Their upper bound expands if reservations dominate; reservations do not raise the lower bound because cancellations remain possible. These ranges do not quantify uncertainty in the event multipliers or independently validate reservation show rates. `event_coverage_validated` is always False. FAA airport operations around Super Bowl LVI inform the scenario multipliers, and other host-city airport analogs show substantial variation; none validates the transfer to this fictional FBO. Do not label these as validated 90% Super Bowl intervals in the dashboard. Do not sum category bounds and call the result a calibrated total interval; correlations are not modeled.

## Handoff to Persons 3 and 4

- demand_predictions.csv: 63 rows = 7 days × 3 scenarios × 3 demo aircraft categories. Use expected_arrivals and expected_departures, grouped by date/scenario/category.
- uncertainty_results.csv: 126 rows, with separate arrival and departure ranges.
- daily_totals.csv: 21 date/scenario rows for dashboard totals and increases over ordinary traffic.
- evaluation_metrics.csv: six demo evaluation rows with provenance and chronological split information.
- run_metadata.json: model configuration and provenance.

Arrivals and departures are independently forecast flows, not matched individual itineraries. Person 3 must supply opening aircraft inventory and reconcile departures, dwell times, and occupancy. A Low scenario does not automatically imply sufficient capacity, nor High automatically a shortage; the optimizer must determine that. This module never accepts or rejects reservations, authorizes movements, or commits resources. Consequential recommendations require human approval.

## Honest demo pitch

“We learn ordinary daily patterns from FAA airport operations, then convert them to an estimated fictional-FBO forecast using clearly stated shares and aircraft mix. Public Super Bowl airport activity shapes Low, Medium, and High planning cases. Our backtest evaluates airport-level daily patterns; without FBO bookings, we cannot measure this FBO's forecast accuracy or claim that the event range contains every plausible outcome.”
