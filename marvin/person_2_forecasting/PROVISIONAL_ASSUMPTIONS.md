# Provisional forecast assumptions — Part 91 + Part 135 scope, daily FAA history

This release applies the team's scope (Part 91 general aviation plus Part 135 air taxi; airlines and military excluded), trains on observed daily FAA counts instead of monthly totals spread evenly across days, adds a Presidents' Day effect learned from history, and derives all three event scenarios from FAA measurements. It is still an estimated fictional-FBO scenario model, not a validated forecast of observed FBO demand.

## Sources and original data

Ordinary input: **FAA ATADS/OPSNET** LAX daily tower operations, itinerant general aviation plus air taxi, 2023–2025 (1,096 days), in alan/elia_output/data/processed/opsnet_lax_daily.csv (retrieved 2026-10-24, https://aspm.faa.gov/opsnet/sys/Airport.asp). The GA values are identical to marvin/person_2_forecasting/private_only_review/ga_only_daily_source.csv and the air-taxi values to alan/data/processed/historical_traffic_air_taxi_interim.csv. Each month's daily sum is checked against the FAA monthly total (opsnet_lax_monthly.csv); all 36 months match exactly, and the conversion stops if one does not.

Event evidence: the same FAA source, daily counts around Super Bowl LVI:
- alan/elia_output/data/processed/superbowl_lvi_surge.csv.
- alan/elia_output/data/processed/superbowl_lvi_daily_profile.csv.
- alan/elia_output/data/processed/opsnet_daily_superbowl.csv.
- alan/elia_output/scripts/analyze_superbowl_lvi.py.

## Baseline allocation

| Driver | Value | Meaning |
| --- | --- | --- |
| Scope | LAX general aviation (Part 91) + air taxi (Part 135) | GA includes training and positioning; air taxi includes cargo feeders and small commuter flights; FAA does not split them further. Air taxi is about 63% of the total |
| FBO share | 10% of GA + air taxi | fbo_market_share in alan/assumptions.csv: 50% private-eligible x 20% capture, range 5–15%; one setting, FBO_SHARE in convert_monthly_to_daily.py |
| Direction split | 50% arrivals / 50% departures | Assumed |
| Category mix | 47% light, 33% midsize, 20% large | Team assumption; no official source found (alan/docs/traffic_categories_and_fleet_mix.md) |
| Daily pattern | Observed day by day | Weekday and holiday variation comes from the data |
| Provenance | estimated on every history row | Observed airport counts times assumed shares are not observed FBO counts |
| Reservations | Zero synthetic placeholders; show rate zero | No booking data supplied |

The 10% share is the value in Alan's ledger, so nazar/scripts/release_team.py reports no share or window mismatch. Both factors are assumptions: the 50% private-eligible fraction is a placeholder from Marvin's sensitivity table, and the 20% capture is team judgment.

## Presidents' Day

Monday 2027-02-15 is Presidents' Day. Each year's holiday is compared with the same weekday one to three weeks before and after, and the ratios are averaged. The final forecast takes them from the long FAA history (GA + air taxi, 2016–2019 and 2023–2025, seven holidays; provisional_inputs/holiday_history.csv): **1.25**. Ratios are scale-free, so the pre-COVID level shift does not matter. The evaluated model learns the same ratio from its own training days only. The factor applies to the baseline, so the ordinary week includes it too.

## Event scenarios

The event window is Thursday–Monday around February 13, 2022. Each day's baseline is the median of the same weekday outside the event window. The five-day ratio is divided by the mean ratio in control years 2019, 2023 and 2024.

| Scenario | Five-day excess | Source |
| --- | --- | --- |
| Low | 3.1% | LAX general aviation, control-adjusted |
| Medium | 15.5% | LAX air taxi, control-adjusted |
| High | 31% | Twice Medium, stress case |

Why Medium uses air taxi: the GA category mixes FBO visitors with training and local flying, and the event TFR banned training, so GA hides the event response (six-airport GA: −25%; LAX GA control years range from 1.14 to 1.43). Air taxi is the cleanest measured response of business jets to the game, and with Part 135 in scope it is a direct measurement for most of the modeled traffic.

Timing and direction: the positive regional air-taxi daily shape spreads the excess over Thursday–Monday, scaled so baseline-weighted five-day forecast movements rise by exactly the scenario excess. Aircraft are conserved: extra arrivals Thursday to Saturday plus half of game day, the same number of extra departures on the other half of game day and Monday. Tuesday and Wednesday stay at baseline. Per-day multipliers are in provisional_inputs/event_evidence.json and planning_inputs.csv.

### Test against other Super Bowls

The same method, applied to the host-city airports of seven other games (alan/elia_output/data/processed/superbowl_hosts_excess.csv, FAA daily counts fetched with `fetch_opsnet.py hosts`), gives these five-day air-taxi excesses:

| Game | Host airports | Air taxi | Position vs scenarios |
| --- | --- | --- | --- |
| LII 2018 Minneapolis | MSP, STP, FCM | +90% | above High |
| LIII 2019 Atlanta | ATL, PDK, FTY | +12% | Low to Medium |
| LIV 2020 Miami | MIA, OPF, FLL, FXE, TMB | +32% | just above High |
| LVI 2022 Los Angeles | LAX | +15.5% | Medium (the anchor) |
| LVII 2023 Phoenix | PHX, SDL, DVT, IWA, FFZ | −22% | below Low |
| LVIII 2024 Las Vegas | LAS, VGT, HND | +19% | Medium to High |
| LIX 2025 New Orleans | MSY, NEW | +285% | above High |
| LX 2026 Bay Area | SJC, OAK, PAO, RHV | +61% | above High |

In the large metro areas (Atlanta, Miami, Los Angeles, Phoenix, Las Vegas, Bay Area), three of six events fall inside Low–High, one sits on the High edge, one is above (Bay Area) and one below (Phoenix, where the Phoenix Open golf tournament fills the same week in every control year). Small markets (Minneapolis, New Orleans) jump far more because their ordinary traffic is small. Medium (+15.5%) is close to the large-metro median; High (+31%) was exceeded in two of six large-metro events, so it is a stress case, not a worst case. GA alone falls at most host airports because the security restriction bans training flights.

## Evaluation and uncertainty

The 2023–2025 chronological split has 657 training, 219 calibration and 220 test dates. Training ends 2024-10-18; calibration starts 2024-10-19; testing starts 2025-05-26. Metrics come from the train-only model. The forecast then refits on every day of 2023–2025, so the most recent year informs it, and its range is the 90% conformal radius of the held-out errors over the calibration and test periods together (wider than the calibration-only radius, which covered 86.8% of test days).

| Measure on the 2025 test days (single split) | Value |
| --- | --- |
| Average daily error, model | 17.2% of the mean |
| Average daily error, overall average | 19.8% |
| Improvement | 13.3% |
| Days inside the nominal 90% range | 86.8% |

**Rolling backtest** (backtest.py, backtest_metrics.csv): every Monday of 2025 (51 origins), the model is fitted only on earlier days and forecasts the next seven days, against four simple baselines.

| Model | Average daily error (WAPE) |
| --- | --- |
| This model (month and weekday, holiday ratio) | **14.9%** |
| Same weekday, mean of the last 8 weeks | 16.6% |
| Same day last year | 17.8% |
| Overall mean | 18.4% |
| Same day last week | 21.5% |

Rolling 90% ranges built from the previous 12 weeks' errors covered 87.9% of days. On Presidents' Day 2025 the model was off by 4.2%, against 15.8% for the 8-week weekday mean. This is the accuracy of the airport-level daily pattern; the FBO share is a constant, so it does not change these percentages. It is not observed FBO accuracy. Event ranges are assumption-scaled planning ranges with unvalidated coverage.

## Matching parking outputs

Elia's optimizer is rerun on this release. Opening inventory is recomputed as first-day baseline arrivals times the 1.1-day dwell assumption (6.1 aircraft). Ramp capacity and other operating assumptions are unchanged.

## Release and review

Producer filenames, CSV column order and metadata keys are preserved; convert_monthly_to_daily.py keeps its name for the release contract although it now reads daily data. The 20-file release manifest lists opsnet_lax_daily.csv as its source in place of the LAWA monthly series (nazar/readiness/release_status.py updated to match), and monthly_reconciliation.csv names its airport column airport_private_ops (nazar/scripts/release_team.py updated). Additional evidence is hashed in event_evidence_manifest.json.

Run from the repository root, using Python with numpy and pandas:

    python marvin/person_2_forecasting/run_provisional.py

Alan: confirm the air-taxi analog for Medium. Passing integration tests is not model validation.
