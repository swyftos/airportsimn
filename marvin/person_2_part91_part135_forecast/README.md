# Person 2: selected-fleet Part 91 and Part 135 forecast

This standalone **placeholder forecast** covers February 11–17, 2027 for a fictional LAX FBO. It includes selected fleets' Part 91 and Part 135 movements and excludes Part 121 and outside fleets. It does not replace the shared `marvin/person_2_forecasting` release or Nazar's dashboard data.

Run `python run_demo.py` from this folder and open [results/report.html](results/report.html). Validate with `python -m unittest test_forecast_model test_operations_extension -v`. Python 3.10+ and the standard library suffice. The default seed is 42; `--seed` changes the synthetic history and reservations reproducibly.

## What the forecast uses

- Daily history and reservations are **synthetic**. A 70% Part 91 / 30% Part 135 selected-fleet split, 20% FBO capture and 47/33/20 aircraft-size mix are unmeasured assumptions. The capture is applied to the eligible synthetic pool once; Part 121 never enters it.
- The Part 91 event profile is illustrative. The Part 135 Medium scenario transfers LAX's **observed +15.5% five-day 2022 FAA Air Taxi excess** to Friday–Tuesday of the 2027 planning week. Low uses 0% and High 31%. This mapping and its use for both arrivals and departures are assumptions. FAA Air Taxi is broader than the selected fleets' Part 135 activity; it does not validate these scenario multipliers.
- Separate month/weekday models are fitted for each aircraft size, Part and direction using synthetic 2023–2025 history. Reservations are overlapping demand floors, never added twice. The chronological holdout measures synthetic pipeline behavior only. Ordinary 90% ranges and event-scaled ranges are not validated Super Bowl coverage.

The combined forecast remains in `results/demand_predictions.csv`, `results/daily_totals.csv` and `results/uncertainty_results.csv`. The new `results/part_demand_predictions.csv` and `results/part_daily_totals.csv` show the Part 91/135 components. `results/air_taxi_event_reference.csv` records the observed airport-category signal, repository source path and transfer limit.

## Planning outputs and decision boundary

`results/capacity_plan.csv` compares forecast demand with an **invented 24-stand** ceiling and an inherited, unverified 75-space-unit estimate. It flags `parking_overflow_to_resolve` for a manager. It makes no landing acceptance, refusal or cancellation decision. `departure_inventory_gap_to_reconcile` flags an aggregate inventory inconsistency; it does not claim aircraft are stuck or identify which departure depends on an arrival. Both ceilings remain placeholders in this standalone sensitivity.

The hourly curve, service-stage durations, weather cases and hypothetical presidential movement pauses remain synthetic sensitivities. `results/parking_price_scenarios.csv` now illustrates a 15% early-arrival discount at each scenario level, with no scenario-based price premium. No actual FBO tariff, operational delay, airport closure or presidential visit is asserted.

The model is reproducible through `run_demo.py`; the SHA-256 file list is in `results/placeholder_manifest.json`. Any operational use needs selected-fleet history and bookings, current PPR capacity, observed service records and human review. Do not publish this standalone package as the coordinated team release.
