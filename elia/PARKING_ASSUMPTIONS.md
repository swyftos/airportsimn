# P3 parking model: assumptions, variants and exports

**Status: provisional.** Inputs are Marvin's provisional estimated forecasts (`marvin/person_2_forecasting/`, built from the LAWA monthly series with a 25 % FBO capture assumption, pending Alan's review) and the P3 assumption ledger `assumptions_p3.csv`. Every number below is a planning assumption or a model output, not an observation. Regenerate everything with `python parking_optimizer.py`.

## Units and aircraft sizes

One space unit (su) is one light-jet parking position. Footprints: light jet 1.0 su, midsize jet 1.5 su, large jet 2.5 su. P2 categories `light_jet`, `midsize_jet`, `large_jet` map to these three. With the current mix (47 / 33 / 20 %), the average aircraft occupies 1.47 su.

The ratios are checked against real aircraft: a position is the aircraft's span and length plus 3 m clearance, plus half of a 24 m taxilane shared by two facing rows. That gives 589 m² for a Citation CJ3, 862 m² for a Challenger 350 (1.46 su) and 1,515 m² for a Gulfstream G650 (2.57 su). A unit remains a planning abstraction, not a validated position or a safe layout.

## Capacity

| Item | Value | Basis |
|---|---|---|
| Ramp area | 52,600 m² | Atlantic Aviation LAX ramp reported as 13 acres in 2008 (AIN, Nazar's source NAZAR-S07). Atlantic is the team's reference facility for the fictional FBO. Low confidence as a present-day value |
| Area per su | 600 m² | Light-jet position computed above, rounded |
| Usable share | 85 % | Ramp left for parking after fuel-truck lanes, hangar fronts and ground equipment |
| **Main ramp** | **75 su** | 52,600 × 0.85 / 600. Range 61 to 91 su for 550 to 650 m² per su and 75 to 95 % usable |

This replaces the earlier synthetic 90 su. The value is now an estimate with a documented source, but it depends on a 2008 figure and should be replaced by a measured apron area or a real stand count when one is found. Tow-in packing (+10 %) and the remote overflow apron (+40 su) remain estimates that need management approval.

## Starting inventory

22.2 transient aircraft are parked on the morning of 2027-02-11, split by the category mix. The value follows Little's law: P2's ordinary arrivals on 2027-02-11 (20.14) times an average dwell of 1.1 days (Alan's ledger, `avg_dwell_days`). It is written in the ledger so the dashboard can check it, and `test_opening_inventory_follows_p2_baseline` fails if P2's baseline changes without the value being recomputed. With this opening value, the ordinary week ends at 22.7 aircraft at P50, close to where it started, so the run is near steady state. The previous synthetic value of 12 made the ordinary week drift upward.

The same opening inventory is used for the ordinary week, the standard event week and the delay variant.

## How turn, overnight and multi-day stays are represented

The model does not track individual aircraft or draw a stay length per aircraft. P2 forecasts arrivals and departures as independent daily flows per category, and the ramp is simulated as an inventory:

- **Within a day**, half of the day's departures (`dep_share_before_peak` = 0.5) leave before the arrival peak, the rest after it. Every arrival of the day is on the ramp at the peak. A same-day **turn** therefore always occupies a position at the daily peak, which is conservative for parking.
- **Overnight and multi-day stays** are whatever aircraft remain after the day's departures. The share of stays of each length is not an input. It follows from how P2's departure flow lags its arrival flow (for the event, the departure wave on Monday 15 and Tuesday 16).
- **Check against Alan's benchmark.** Alan's ledger uses 40 % turns (0.5 day), 45 % overnight (1 day) and 15 % multi-day (3 days), an average of 1.1 days. Little's law on the ordinary-week run gives an implied dwell of **1.62 days** (average daily-peak aircraft divided by average daily arrivals). The model measures the daily peak, not the average over the day, so it holds more aircraft than Alan's benchmark.

## Ordinary-week baseline (`ordinary_week_parking.csv`)

Same model, units, opening inventory, capacity and staffing rules, run on P2's ordinary forecast for the same dates (`baseline_arrivals`, `baseline_departures`, checked to be identical across P2 scenarios). The range is P2's nominal 90 % baseline interval (baseline ± `baseline_radius`, floored at zero). 10,000 Monte Carlo paths.

Result: daily parking peaks of 47 to 49 su at P50, up to 66 % of the 75 su ramp, at most a 4 % chance of exceeding it, and 3 technicians on the busiest shift.

**This level depends on P2's ordinary forecast of 20 arrivals a day.** P2 currently averages 2016 to 2019 with 2023 to 2025, while its own 2023 to 2025 history is about 11.7 arrivals a day. If P2 moves to the post-COVID window, as Alan's baseline does, ordinary and event demand both fall by roughly 40 %, and so does parking.

**Open point with Alan.** `alan/baseline.csv` gives `parking_units` of 7 to 12, computed as FBO arrivals × 1.1 days (a count of aircraft, at a 20 % share). To compare it with P3 in the same unit, multiply by 1.47 su per aircraft, and agree first on the capture share (Alan 20 %, P2 25 %) and the training window.

## 24-hour departure-delay variant

`resource_requirements_departure_delay_24h.csv` and `scenario_recommendations_departure_delay_24h.json`.

Definition: from game day (Sunday 2027-02-14, `delay_24h_first_day` = 3) onward, 100 % of each day's departures (`delay_24h_share`) leave 24 hours later. This represents a post-game ground stop, weather hold or slot restriction. The variant is a **separate simulation** on the same 10,000 demand paths as the standard run (same seed). Departures, parking, prepared capacity, staffing, fuel, costs, impact and recommendations are all recomputed. Departures scheduled for 2027-02-17 move to 2027-02-18, outside the window, so those aircraft stay parked.

Effect in the Medium scenario: Monday's parking peak goes from 98 to 153 su at P50, and the probability of exceeding the 75 su ramp from 81 % to 99 %. In the Low scenario, the probability of exceeding the ramp on Monday goes from 46 % to 92 %, and preparation becomes worthwhile in 76 % of runs instead of 40 %.

## Aircraft still parked after 2027-02-17 (`parking_carryover.csv`)

One row per variant and scenario: opening aircraft, aircraft remaining after the last day (P10, P50, P90, demand not limited by capacity), space units remaining at P50, and departures pushed past the window by the delay.

| Variant | Remaining aircraft P50 (Low / Medium / High) |
|---|---|
| ordinary | 22.7 |
| standard | 24.4 / 24.6 / 26.7 |
| departure_delay_24h | 43.9 / 45.6 / 49.0 |

## Stable outputs and export fields (for Nazar)

The standard outputs keep exactly their schema: `resource_requirements.csv`, `scenario_recommendations.json`, `assumptions_p3.csv`. `nazar/scripts/verify_team_pipeline.py` reports `matched` for the regenerated bundle.

| File | Rows | Fields |
|---|---|---|
| `resource_requirements_departure_delay_24h.csv` | 21 | Same columns as `resource_requirements.csv` |
| `scenario_recommendations_departure_delay_24h.json` | 3 scenarios | Same structure as the standard file; `meta` adds `variant` and `data_status: provisional` |
| `ordinary_week_parking.csv` | 7 | `date, variant, arrivals_baseline, departures_baseline, parking_demand_su_p10, parking_demand_su_p50, parking_demand_su_p90, capacity_normal_su, utilization_normal_p50, prob_over_normal_capacity, risk_level, staff_required_peak_shift, techs_normal_per_shift, fuel_gallons_p50, data_status` |
| `parking_carryover.csv` | 7 | `variant, scenario, opening_aircraft, aircraft_remaining_p10, aircraft_remaining_p50, aircraft_remaining_p90, parking_su_remaining_p50, departures_pushed_past_window_p50, data_status` |

## Human authority

The variants change no rule: every action still carries `requires_human_approval` and a named approver, and the model never accepts, refuses or cancels an individual aircraft.
