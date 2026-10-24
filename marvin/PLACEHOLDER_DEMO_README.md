# Person 2 — AI Demand Forecasting (PLACEHOLDER DEMO)

**Every bundled input and result is a random or assumed placeholder.** Nothing in this package is observed FAA traffic, actual reservations, measured Super Bowl activity, validated FBO accuracy or a realistic operating baseline.

## Open the completed program

Open **results/report.html** in your browser. The ready-generated report shows seven-day scenarios, ordinary demand, event increments and synthetic evaluation results. No installation is required to view it.

To regenerate, install Python 3.10 or newer, then run from this folder:

    python run_demo.py

For different reproducible random values:

    python run_demo.py --seed 123

No third-party packages, API keys or internet connection are required. The default seed is 42.

## Responsibilities covered

| Person 2 task | Implementation |
| --- | --- |
| Expected arrivals and departures | Separate learned month/weekday models for light, midsize and large jets |
| Super Bowl activity increase | Random placeholder daily event profiles with explicit scenario multipliers |
| Historical demand | Seeded random daily category history for 2016–2025 |
| Simulated reservations | Random synthetic booked movements and show rates; overlapping demand floor, not added twice |
| Event indicators | Explicit event flag for each planning date/category |
| Seven-day forecast | February 11–17, 2027, as specified in the project brief |
| Low / Medium / High | Ordered multipliers: half / full / 1.6 times the central incremental uplift |
| Uncertainty | Nominal 90% baseline split-conformal prediction ranges, scaled for assumed events |
| Historical-baseline comparison | Synthetic holdout MAE versus training mean; not observed predictive accuracy |

The statistical model learns from data; it is an explainable seasonal shrinkage model, not a neural network. It uses 14 prior days to stabilize month/weekday means.

## Historical and source scope

The random history contains every date from 2016-01-01 through 2025-12-31, with three aircraft categories per day. Years 2020–2022 are excluded from fitting. The ordinary model uses only 2023–2025; older records remain reference data.

results/placeholder_feb2022_reference.csv preserves the February 2022 random rows. This is a placeholder reference, **not** an investigation of the real Super Bowl LVI surge. This demo does not collect FAA records or identify real GA/Air Taxi movements. The earlier FAA collection and observed-airport backtest remain separate deliverables.

Light/midsize/large jet categories are fictional FBO categories, not FAA operational classifications. Do not relabel them GA or Air Taxi.

## Placeholder generation

- Baseline category means: 7 light, 5 midsize, 3 large movements per direction/day.
- Invented seasonality: 15% cosine variation, peaking near February.
- Invented weekday factors: 1.2 on Monday/Friday/Sunday, 0.85 otherwise.
- Counts: nonnegative rounded Gaussian draws with category-dependent noise.
- Event profiles: random daily multipliers with an invented pre-game arrival peak and post-game departure peak.
- Reservations: random synthetic booked movements, assumed show rate between 75% and 95%.
- All history rows retain data_class=synthetic and a PLACEHOLDER source marker.
- Forecast rows retain reservation_class=synthetic, historical_data_class=synthetic and a PLACEHOLDER assumption_source.
- Evaluation rows remain non_observed_demonstration; metadata and the report explicitly state PLACEHOLDER.

The exact values used are saved in demo_planning_inputs.csv and placeholder_assumptions.json.

## Forecast calculation

    baseline = learned ordinary category/direction demand
    event demand = baseline × scenario multiplier
    reservation floor = reserved movements × assumed show rate
    expected demand = max(event demand, reservation floor)
    incremental demand = expected demand − baseline

Reservations overlap total demand. They are not extra aircraft added to the event estimate. This program forecasts movements, not parking occupancy, dwell duration or physical ramp capacity.

## Outputs

All files below are in results/:

| File | Contents |
| --- | --- |
| report.html | Readable standalone PLACEHOLDER report |
| demand_predictions.csv | 63 date/scenario/category forecasts |
| uncertainty_results.csv | 126 category/direction planning ranges |
| daily_totals.csv | 21 daily scenario totals |
| evaluation_metrics.csv | Six synthetic category/direction evaluations |
| run_metadata.json | Model, seed, provenance and limitations |
| demo_historical_traffic.csv | 10,959 random category-day rows for 2016–2025 |
| demo_planning_inputs.csv | 21 random reservation and event input rows |
| placeholder_feb2022_reference.csv | 84 February 2022 random category rows |
| placeholder_assumptions.json | Explicit invented settings |
| placeholder_manifest.json | SHA-256 fingerprints of generated artifacts |

Existing P2 CSV column order and metadata keys are preserved. This package is isolated and does not overwrite any FAA-based output or teammate-owned folder. Metadata records the synthetic seed and is not an approval record.

## Evaluation and uncertainty limits

The model uses the first 60% of 2023–2025 dates for training, the next 20% for calibration and the final 20% for testing. It stays frozen after fitting. MAE and historical-mean comparisons demonstrate program behavior on synthetic data only.

Prediction intervals describe individual outcomes, not confidence intervals on the mean. The 90% setting is nominal baseline coverage. Event multipliers, reservations and their uncertainty are invented; event coverage is not validated. Do not describe these outputs as observed FBO accuracy or as validated 90% event confidence bounds.

For measured accuracy, use the separate observed FAA airport backtest. Never combine those measured scores with these random FBO forecasts.

## Tests and handoff

    python -m unittest test_forecast_model -v

The tests cover forecast shape, bounds, ordered scenarios, event flags, reservation handling, rejected invalid inputs, test-period leakage and reproducible random generation.

Send the complete ZIP so the report, assumptions, program and CSVs stay together. The program is a demonstration only; it is not pushed to GitHub or wired into Nazar's dashboard. No P3 parking results are included in this standalone Person 2 package.

## Replacing placeholders later

Keep the current schemas and coordinate any changes with Nazar. Replace source history and reservations with documented inputs; keep derived FBO rows estimated even when airport observations are real. Review FBO capture, direction and aircraft-size allocations. Then regenerate the complete P2/P3 release and rerun validation. Do not remove PLACEHOLDER labels until the corresponding data and assumptions have actually been replaced.

