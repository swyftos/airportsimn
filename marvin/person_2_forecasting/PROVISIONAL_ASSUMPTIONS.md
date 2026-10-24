# Provisional forecast assumptions — private (Part 91) scope, daily FAA history

This release applies the team's private-only scope (Part 91 general aviation; air taxi/charter, airlines and military excluded), trains on observed daily FAA counts instead of monthly totals spread evenly across days, adds a Presidents' Day effect learned from history, and derives all three event scenarios from FAA measurements. It is still an estimated fictional-FBO scenario model, not a validated forecast of observed FBO demand.

## Sources and original data

Ordinary input: **FAA ATADS/OPSNET** LAX daily tower operations, itinerant general aviation, 2023–2025 (1,096 days), in alan/elia_output/data/processed/opsnet_lax_daily.csv (retrieved 2026-10-24, https://aspm.faa.gov/opsnet/sys/Airport.asp). The daily values are identical to marvin/person_2_forecasting/private_only_review/ga_only_daily_source.csv. Each month's daily sum is checked against the FAA monthly total (opsnet_lax_monthly.csv); all 36 months match exactly, and the conversion stops if one does not.

Event evidence: the same FAA source, daily counts around Super Bowl LVI:
- alan/elia_output/data/processed/superbowl_lvi_surge.csv.
- alan/elia_output/data/processed/superbowl_lvi_daily_profile.csv.
- alan/elia_output/data/processed/opsnet_daily_superbowl.csv.
- alan/elia_output/scripts/analyze_superbowl_lvi.py.

## Baseline allocation

| Driver | Value | Meaning |
| --- | --- | --- |
| Scope | LAX itinerant general aviation (Part 91) | Includes some non-FBO flying (training, positioning); FAA does not split it further |
| FBO capture | 20% of GA | Team ledger value ALAN-fbo_market_share; one setting, FBO_SHARE in convert_monthly_to_daily.py |
| Direction split | 50% arrivals / 50% departures | Assumed |
| Category mix | 47% light, 33% midsize, 20% large | Team assumption; no official source found (alan/docs/traffic_categories_and_fleet_mix.md) |
| Daily pattern | Observed day by day | Weekday and holiday variation comes from the data |
| Provenance | estimated on every history row | Observed airport counts times assumed shares are not observed FBO counts |
| Reservations | Zero synthetic placeholders; show rate zero | No booking data supplied |

The 20% share now matches Alan's baseline policy, so nazar/scripts/release_team.py reports no share or window mismatch. Marvin's private_only_review applies a further 50% private-eligibility filter (effective 10%). That filter is a placeholder and is not used here; if the team adopts it, change FBO_SHARE once.

## Presidents' Day

Monday 2027-02-15 is Presidents' Day. The model learns a factor per holiday from its training days: observed count divided by the ordinary month/weekday prediction. The training split contains the 2023 and 2024 holidays and gives **1.053**. Measured against the surrounding Mondays, GA was 1.17, 0.96 and 1.36 times a normal Monday in 2023, 2024 and 2025, so the effect is real but noisy. The factor applies to the baseline, so the ordinary week includes it too.

## Event scenarios

The event window is Thursday–Monday around February 13, 2022. Each day's baseline is the median of the same weekday outside the event window. The five-day ratio is divided by the mean ratio in control years 2019, 2023 and 2024.

| Scenario | Five-day excess | Source |
| --- | --- | --- |
| Low | 3.1% | LAX general aviation, control-adjusted |
| Medium | 15.5% | LAX air taxi, control-adjusted, used as the analog for event-driven business-jet demand |
| High | 31% | Twice Medium, stress case |

Why Medium uses air taxi: the GA category mixes FBO visitors with training and local flying, and the event TFR banned training, so GA hides the event response (six-airport GA: −25%; LAX GA control years range from 1.14 to 1.43). Air taxi is the cleanest measured response of business jets to the game. Only the size of the response is borrowed; the counts are GA.

Timing and direction are unchanged: the positive regional air-taxi daily shape spreads the excess over Thursday–Monday, scaled so baseline-weighted five-day forecast movements rise by exactly the scenario excess. Aircraft are conserved: extra arrivals Thursday to Saturday plus half of game day, the same number of extra departures on the other half of game day and Monday. Tuesday and Wednesday stay at baseline. The scenarios are assumptions, not confidence bounds or probabilities. Per-day multipliers are in provisional_inputs/event_evidence.json and planning_inputs.csv.

## Evaluation and uncertainty

The 2023–2025 chronological split has 657 training, 219 calibration and 220 test dates. Training ends 2024-10-18; calibration starts 2024-10-19; testing starts 2025-05-26. The calibrated model is frozen.

Because the history is now observed daily counts, the holdout measures real daily accuracy of the airport GA pattern:

| Measure on the 2025 test days | Value |
| --- | --- |
| Average daily error, model | 25.9% of the mean |
| Average daily error, overall average | 27.8% |
| Improvement | 7.1% |
| Days inside the nominal 90% range | 85.5% |

This is the accuracy of the airport-level daily pattern; the FBO share is a constant, so it does not change these percentages. It is not observed FBO accuracy. Event ranges are assumption-scaled planning ranges with unvalidated coverage.

## Matching parking outputs

Elia's optimizer is rerun on this release. Opening inventory is recomputed as first-day baseline arrivals times the 1.1-day dwell assumption (4.3 aircraft). Ramp capacity and other operating assumptions are unchanged.

## Release and review

Producer filenames, CSV column order and metadata keys are preserved; convert_monthly_to_daily.py keeps its name for the release contract although it now reads daily data. The 20-file release manifest lists opsnet_lax_daily.csv as its source in place of the LAWA monthly series (nazar/readiness/release_status.py updated to match), and monthly_reconciliation.csv names its airport column airport_ga_ops (nazar/scripts/release_team.py updated). Additional evidence is hashed in event_evidence_manifest.json.

Run from the repository root, using Python with numpy and pandas:

    python marvin/person_2_forecasting/run_provisional.py

Alan: confirm the 20% share for GA-only scope and the air-taxi analog for Medium. Passing integration tests is not model validation.
