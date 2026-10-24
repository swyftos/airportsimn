# P3 parking model: assumptions, variants and exports

**Status: provisional.** Inputs are Marvin's provisional estimated forecasts (`marvin/person_2_forecasting/`, built from the LAWA monthly series with a 25 % FBO capture assumption, pending Alan's review) and the P3 assumption ledger `assumptions_p3.csv`. Every number below is a planning assumption or a model output, not an observation. Regenerate the complete release from the repository root with `python marvin/person_2_forecasting/run_provisional.py`. This verifies all parking variants and refreshes the release hashes together.

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

13.0 transient aircraft are parked on the morning of 2027-02-11, split by the category mix. The value follows Little's law: P2's ordinary arrivals on 2027-02-11 (11.79) times an average dwell of 1.1 days (Alan's ledger, `avg_dwell_days`). It is written in the ledger so the dashboard can check it, `run_provisional.py` refreshes it with each P2 release, and `test_opening_inventory_follows_p2_baseline` fails if the two drift apart. With this opening value, the ordinary week ends at 13.0 aircraft at P50, so the run is at steady state.

The same opening inventory is used for the ordinary week, the standard event week and the delay variant.

## How turn, overnight and multi-day stays are represented

The model does not track individual aircraft or draw a stay length per aircraft. P2 forecasts arrivals and departures as independent daily flows per category, and the ramp is simulated as an inventory:

- **Within a day**, half of the day's departures (`dep_share_before_peak` = 0.5) leave before the arrival peak, the rest after it. Every arrival of the day is on the ramp at the peak. A same-day **turn** therefore always occupies a position at the daily peak, which is conservative for parking.
- **Overnight and multi-day stays** are whatever aircraft remain after the day's departures. The share of stays of each length is not an input. It follows from how P2's departure flow lags its arrival flow. For the event, P2 now puts the extra arrivals on Thursday to Saturday and half of game day, and the same number of extra departures on the other half of game day and Monday, so event aircraft stay one to four nights and accumulate until game day.
- **Check against Alan's benchmark.** Alan's ledger uses 40 % turns (0.5 day), 45 % overnight (1 day) and 15 % multi-day (3 days), an average of 1.1 days. The ordinary-week run gives a peak-occupancy-to-arrival ratio of **1.60 days** (average daily-peak aircraft divided by average daily arrivals). Because this uses daily peaks rather than time-average occupancy, it is a diagnostic ratio, not a Little's-law estimate of actual dwell time.

## Ordinary-week baseline (`ordinary_week_parking.csv`)

Same model, units, opening inventory, capacity and staffing rules, run on P2's ordinary forecast for the same dates (`baseline_arrivals`, `baseline_departures`, checked to be identical across P2 scenarios). The range is P2's nominal 90 % baseline interval (baseline ± `baseline_radius`, floored at zero). 10,000 Monte Carlo paths.

Result: a daily parking peak of 27.7 su at P50 on every day (P2's ordinary forecast is flat at 11.8 arrivals a day, because its history allocates monthly totals equally across days), 37 % of the 75 su ramp, no chance of exceeding it, and 2 technicians on the busiest shift.

**This level depends on P2's ordinary forecast.** P2 now trains on 2023–2025 only (11.8 arrivals a day, against 20 when 2016–2019 were included). It has no weekday or holiday effect yet: Presidents' Day falls on Monday 2027-02-15, and observed LAX daily data (FAA OPSNET, PR #22) puts Presidents' Day traffic 17 to 24 % above a normal Monday.

**Open point with Alan.** `alan/baseline.csv` gives `parking_units` of 7 to 12, computed as FBO arrivals × 1.1 days (a count of aircraft, at a 20 % share). To compare it with P3 in the same unit, multiply by 1.47 su per aircraft, and agree first on the capture share (Alan 20 %, P2 25 %) and the training window.

## Event week (`resource_requirements.csv`)

With P2's FAA-anchored scenarios (five-day operations excess of 0 / 15.5 / 31 % for Low / Medium / High), the P50 parking peak is 27.7 / 38.9 / 51.4 su, reached on game day. Event aircraft build up from Thursday and leave on Sunday evening and Monday. No scenario exceeds the 75 su ramp at P50, so the plan recommends no parking measure; High adds technician shifts only. The binding risks are therefore an operational disruption (see the delay variant) and the scenario assumptions themselves, which remain provisional.

## 24-hour departure-delay variant

`resource_requirements_departure_delay_24h.csv` and `scenario_recommendations_departure_delay_24h.json`.

Definition: from game day (Sunday 2027-02-14, `delay_24h_first_day` = 3) onward, 100 % of each day's departures (`delay_24h_share`) leave 24 hours later. This represents a post-game ground stop, weather hold or slot restriction. The variant is a **separate simulation** on the same 10,000 demand paths as the standard run (same seed). Departures, parking, prepared capacity, staffing, fuel, costs, impact and recommendations are all recomputed. Departures scheduled for 2027-02-17 move to 2027-02-18, outside the window, so those aircraft stay parked.

Effect in the Medium scenario: Monday's parking peak goes from 32 to 56 su at P50, and aircraft keep accumulating until the delayed departures leave. In the Low scenario, the peak goes from 28 to 45 su. No scenario exceeds the 75 su ramp at P50, even with the delay (High peaks at 69 su).

## Aircraft still parked after 2027-02-17 (`parking_carryover.csv`)

One row per variant and scenario: opening aircraft, aircraft remaining after the last day (P10, P50, P90, demand not limited by capacity), space units remaining at P50, and departures pushed past the window by the delay.

| Variant | Remaining aircraft P50 (Low / Medium / High) |
|---|---|
| ordinary | 13.0 |
| standard | 13.0 / 12.5 / 12.3 |
| departure_delay_24h | 24.8 / 24.4 / 24.2 |

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
