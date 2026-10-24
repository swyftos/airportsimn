# Frozen 2026 airport holdout

The current demand model was fitted to 2023–2025 and was not updated with 2026 counts.
The 273 January–September 2026 LAX daily observations are from FAA OPSNET; their GA and
air-taxi daily sums match all nine FAA monthly totals. February also matches the separately
collected February 2026 extract. No FBO records are included.

| Method | Airport WAPE | Airport MAE/day | Airport bias/day |
| --- | ---: | ---: | ---: |
| Frozen model | 15.0% | 14.443 | -2.800 |
| Same weekday in 2025 | 16.1% | 15.469 | -2.700 |

A descriptive ±54.9 airport-operation band comes from 84 prequential days in the last 12 rolling 2025 backtest origins. It covered 98.5% of 2026 holdout days. This is a drift diagnostic, not calibrated 2026 coverage or a validated FBO interval.

Monthly scores are in `frozen_2026_metrics.csv`; daily predictions and FAA observations are
in `frozen_2026_daily.csv`. The FAA extracts and monthly reconciliation are in
`calibration_evidence/`. Values are airport operations (takeoffs plus landings). The model
first predicts estimated FBO movements using the assumed 10% share, then divides by that
same share for this airport comparison. This cancellation tests the daily airport pattern
only. It does not measure FBO capture, direction split, aircraft mix, reservations, event
demand, or parking capacity.

No 2026 observations were used to fit or select this model. Do not describe these scores
as FBO forecast accuracy.
