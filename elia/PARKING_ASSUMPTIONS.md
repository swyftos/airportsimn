# P3 parking model: assumptions, variants and exports

**Status: provisional.** Inputs are the provisional estimated forecasts in `marvin/person_2_forecasting/` (Part 91 + Part 135 scope: observed daily FAA general-aviation and air-taxi counts at LAX with a 10 % FBO share: 50 % private-eligible × 20 % capture, pending Alan's review) and the P3 assumption ledger `assumptions_p3.csv`. Every number below is a planning assumption or a model output, not an observation. Regenerate the complete release from the repository root with `python marvin/person_2_forecasting/run_provisional.py`. This verifies all parking variants and refreshes the release hashes together.

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

5.9 transient aircraft are parked on the morning of 2027-02-11, split by the category mix. The value follows Little's law: P2's ordinary arrivals on 2027-02-11 (5.38) times an average dwell of 1.1 days (Alan's ledger, `avg_dwell_days`). It is written in the ledger so the dashboard can check it, `run_provisional.py` refreshes it with each P2 release, and `test_opening_inventory_follows_p2_baseline` fails if the two drift apart. With this opening value, the ordinary week ends at 5.9 aircraft at P50, so the run is at steady state.

The same opening inventory is used for the ordinary week, the standard event week and the delay variant.

## How turn, overnight and multi-day stays are represented

The model does not track individual aircraft or draw a stay length per aircraft. P2 forecasts arrivals and departures as independent daily flows per category, and the ramp is simulated as an inventory:

- **Within a day**, half of the day's departures (`dep_share_before_peak` = 0.5) leave before the arrival peak, the rest after it. Every arrival of the day is on the ramp at the peak. A same-day **turn** therefore always occupies a position at the daily peak, which is conservative for parking.
- **Overnight and multi-day stays** are whatever aircraft remain after the day's departures. The share of stays of each length is not an input. It follows from how P2's departure flow lags its arrival flow. For the event, P2 now puts the extra arrivals on Thursday to Saturday and half of game day, and the same number of extra departures on the other half of game day and Monday, so event aircraft stay one to four nights and accumulate until game day.
- **Check against Alan's benchmark.** Alan's ledger uses 40 % turns (0.5 day), 45 % overnight (1 day) and 15 % multi-day (3 days), an average of 1.1 days. The ordinary-week run gives a peak-occupancy-to-arrival ratio of **1.71 days** (average daily-peak aircraft divided by average daily arrivals). Because this uses daily peaks rather than time-average occupancy, it is a diagnostic ratio, not a Little's-law estimate of actual dwell time.

## Ordinary-week baseline (`ordinary_week_parking.csv`)

Same model, units, opening inventory, capacity and staffing rules, run on P2's ordinary forecast for the same dates (`baseline_arrivals`, `baseline_departures`, checked to be identical across P2 scenarios). The range is P2's nominal 90 % baseline interval (baseline ± `baseline_radius`, floored at zero). 10,000 Monte Carlo paths.

Result: a daily parking peak of 11.3 to 13.1 su at P50 (lowest on Saturday, highest on Presidents' Day, Monday 2027-02-15), 15 to 17 % of the 75 su ramp, no chance of exceeding it, and 1 technician on the busiest shift.

**This level depends on P2's ordinary forecast.** P2 trains on observed daily FAA GA and air-taxi counts for 2023–2025 (3.7 to 6.1 arrivals a day). The weekday pattern comes from the data, and Presidents' Day carries a factor of 1.20 learned from the 2023 and 2024 holidays.

**Alignment with Alan.** P2 and `alan/baseline.csv` use the same 10 % share, Part 91 + 135 scope and training window. `parking_units` there is a count of aircraft; multiply by 1.47 su per aircraft to compare with P3.

## Event week (`resource_requirements.csv`)

With P2's FAA-anchored scenarios (five-day operations excess of 3.1 / 15.5 / 31 % for Low / Medium / High), the P50 parking peak is 13.8 / 17.0 / 22.6 su, reached on Presidents' Day in Low and on game day in Medium and High. Event aircraft build up from Thursday and leave on Sunday evening and Monday. No scenario comes close to the 75 su ramp, so parking is not the constraint at this capacity. Alan's ledger now gives `fbo_capacity_su` = 87.5 su (Atlantic's 5-jet hangar, 12.5 su, plus the 75 su ramp); this model still uses the 75 su ramp alone. Both describe Atlantic's whole facility, so neither is sized to a 10 % share; the team still has to decide whether to scale capacity to the share.

## 24-hour departure-delay variant

`resource_requirements_departure_delay_24h.csv` and `scenario_recommendations_departure_delay_24h.json`.

Definition: from game day (Sunday 2027-02-14, `delay_24h_first_day` = 3) onward, 100 % of each day's departures (`delay_24h_share`) leave 24 hours later. This represents a post-game ground stop, weather hold or slot restriction. The variant is a **separate simulation** on the same 10,000 demand paths as the standard run (same seed). Departures, parking, prepared capacity, staffing, fuel, costs, impact and recommendations are all recomputed. Departures scheduled for 2027-02-17 move to 2027-02-18, outside the window, so those aircraft stay parked.

Effect in the Medium scenario: Monday's parking peak goes from 15.4 to 25.8 su at P50, and aircraft keep accumulating until the delayed departures leave. In the Low scenario, it goes from 13.8 to 21.9 su. No scenario exceeds the 75 su ramp at P50, even with the delay (High peaks at 31.6 su).

## Game-day security restriction variant

`resource_requirements_security_restriction.csv` and `scenario_recommendations_security_restriction.json`.

Input: Alan's `alan/data/processed/security_restriction_model_input.csv`. No private movements on Sunday 2027-02-14 between 14:30 and 20:30, the window of the Super Bowl LVI security TFR (FAA flight advisory), with LAX inside the 10 NM inner ring. This is a precedent-based assumption; no TFR has been published for 2027.

Method: movements are spread evenly within each shift (morning 06–14, day 14–22, night 22–06). The window covers 6 of the day shift's 8 hours, so 30 % of game-day movements are blocked. They are released evenly over `security_release_hours` (4 h) after 20:30. Game-day shift shares go from 40 / 40 / 20 % to 40 / 21 / 39 %, so the night shift handles almost twice its usual share. `security_next_day_share` (0 by default, because LAX is open 24 h) sends a share of blocked departures to Monday instead. Same 10,000 demand paths as the standard run.

Result at the current demand: parking is unchanged with no next-day slips (13.8 / 17.0 / 22.6 su P50 peaks). If half or all blocked departures slip to Monday, the peaks rise to 14.2–14.7 / 17.6–18.1 / 23.2–23.9 su. The normal crew of 3 technicians per shift covers the game-day night surge in every scenario, so the plan recommends no action. With a larger FBO share, the night shift is the first place this variant would require extra staff.

The dashboard contract (`nazar/readiness/contracts.py`) accepts only the standard and 24-hour delay variants, so these two files are not displayed yet, and the carryover table does not include them.

## Aircraft still parked after 2027-02-17 (`parking_carryover.csv`)

One row per variant and scenario: opening aircraft, aircraft remaining after the last day (P10, P50, P90, demand not limited by capacity), space units remaining at P50, and departures pushed past the window by the delay.

| Variant | Remaining aircraft P50 (Low / Medium / High) |
|---|---|
| ordinary | 5.9 |
| standard | 5.9 / 6.0 / 6.4 |
| departure_delay_24h | 10.3 / 10.4 / 10.9 |

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
