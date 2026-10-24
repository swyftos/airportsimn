# P3 parking model: assumptions, variants and exports

**Status: provisional.** Inputs are Marvin's provisional forecasts (`marvin/person_2_forecasting/`, synthetic demo history) and the P3 assumption ledger `assumptions_p3.csv`, which Alan is reviewing. Every number below is a planning assumption or a model output, not an observation. Regenerate everything with `python parking_optimizer.py`.

## Units and aircraft sizes

One space unit (su) is one light-jet parking position. Footprints: light jet 1.0 su, midsize jet 1.5 su, large jet 2.5 su (estimates). P2 categories `light_jet`, `midsize_jet`, `large_jet` map to these three. With the current mix (47 / 33 / 20 %), the average aircraft occupies 1.47 su. A unit is a planning abstraction, not a validated parking position or a safe layout.

## Capacity

The main ramp holds **90 su. This value is synthetic** and stays labeled as such until a measured apron area supports it. Tow-in packing adds 10 % and the remote overflow apron 40 su, both estimates that need management approval before use.

## Starting inventory

12 transient aircraft are parked on the morning of 2027-02-11, split by the category mix (synthetic). The same opening inventory is used for the ordinary week, the standard event week and the delay variant, so the three runs are comparable.

## How turn, overnight and multi-day stays are represented

The model does not track individual aircraft or draw a stay length per aircraft. P2 forecasts arrivals and departures as independent daily flows per category, and the ramp is simulated as an inventory:

- **Within a day**, half of the day's departures (`dep_share_before_peak` = 0.5) leave before the arrival peak, the rest after it. Every arrival of the day is on the ramp at the peak. A same-day **turn** therefore always occupies a position at the daily peak, which is conservative for parking.
- **Overnight and multi-day stays** are whatever aircraft remain after the day's departures. The share of stays of each length is not an input. It follows from how P2's departure flow lags its arrival flow (for the event, the departure wave on Monday 15 and Tuesday 16).
- **Check against Alan's benchmark.** Alan's ledger uses an ordinary-week mix of 40 % turns (0.5 day), 45 % overnight (1 day) and 15 % multi-day (3 days), an average dwell of 1.1 days. Little's law on the ordinary-week run gives an implied average dwell of **1.41 days** (average daily-peak aircraft divided by average daily arrivals). The model holds aircraft somewhat longer than Alan's benchmark, partly because it measures the daily peak rather than an average over the day.

## Ordinary-week baseline (`ordinary_week_parking.csv`)

Same model, units, opening inventory, capacity and staffing rules, run on P2's ordinary forecast for the same dates (`baseline_arrivals`, `baseline_departures`, checked to be identical across P2 scenarios). The range is P2's nominal 90 % baseline interval (baseline ± `baseline_radius`, floored at zero). 10,000 Monte Carlo paths.

Result: daily parking peaks between 27 and 39 su at P50, no day above 44 % of the 90 su ramp, and 2 to 3 technicians needed on the busiest shift.

**Open point with Alan.** `alan/baseline.csv` gives `parking_units` of 7 to 12, computed as FBO arrivals × 1.1 days of dwell. That is a count of aircraft, from lower arrivals (6 to 11 a day) than P2's baseline (13 to 20 a day). To compare both baselines in the same unit, Alan's value should be multiplied by 1.47 su per aircraft, and the two baselines should agree on daily arrivals. Until then, the dashboard should not plot both as the same quantity.

## 24-hour departure-delay variant

`resource_requirements_departure_delay_24h.csv` and `scenario_recommendations_departure_delay_24h.json`.

Definition: from game day (Sunday 2027-02-14, `delay_24h_first_day` = 3) onward, 100 % of each day's departures (`delay_24h_share`) leave 24 hours later. This represents a post-game ground stop, weather hold or slot restriction. The variant is a **separate simulation** on the same 10,000 demand paths as the standard run (same seed). Departures, parking, prepared capacity, staffing, fuel, costs, impact and recommendations are all recomputed. Departures scheduled for 2027-02-17 move to 2027-02-18, outside the window, so those aircraft stay parked.

Effect in the Medium scenario: Monday's parking peak goes from 72 to 122 su at P50, the probability of exceeding the 90 su ramp goes from 27 % to 78 % on Monday, and the plan adds referrals and prior reservations (PPR). In the Low scenario, the delay alone is enough to require the overflow apron.

## Aircraft still parked after 2027-02-17 (`parking_carryover.csv`)

One row per variant and scenario: opening aircraft, aircraft remaining after the last day (P10, P50, P90, demand not limited by capacity), space units remaining at P50, and departures pushed past the window by the delay.

| Variant | Remaining aircraft P50 (Low / Medium / High) |
|---|---|
| ordinary | 15.8 |
| standard | 17.4 / 17.6 / 18.3 |
| departure_delay_24h | 29.0 / 29.7 / 31.5 |

Even the ordinary week ends above its opening inventory of 12, so the synthetic opening value is slightly below the steady state implied by P2's flows. This should be revisited together with the dwell assumption.

## Stable outputs and new export fields (for Nazar)

The standard outputs keep exactly their previous schema and values: `resource_requirements.csv`, `scenario_recommendations.json`, `assumptions_p3.csv` (two keys added: `delay_24h_first_day`, `delay_24h_share`). `nazar/scripts/verify_team_pipeline.py` still reports `matched`.

New files, to agree with Nazar before he wires them in:

| File | Rows | Fields |
|---|---|---|
| `resource_requirements_departure_delay_24h.csv` | 21 | Same columns as `resource_requirements.csv` |
| `scenario_recommendations_departure_delay_24h.json` | 3 scenarios | Same structure as the standard file; `meta` adds `variant` and `data_status: provisional` |
| `ordinary_week_parking.csv` | 7 | `date, variant, arrivals_baseline, departures_baseline, parking_demand_su_p10, parking_demand_su_p50, parking_demand_su_p90, capacity_normal_su, utilization_normal_p50, prob_over_normal_capacity, risk_level, staff_required_peak_shift, techs_normal_per_shift, fuel_gallons_p50, data_status` |
| `parking_carryover.csv` | 7 | `variant, scenario, opening_aircraft, aircraft_remaining_p10, aircraft_remaining_p50, aircraft_remaining_p90, parking_su_remaining_p50, departures_pushed_past_window_p50, data_status` |

For the dashboard's ordinary parking bar, use `parking_demand_su_p50` from `ordinary_week_parking.csv`: same unit and same daily-peak definition as the event table.

## Human authority

The variants change no rule: every action still carries `requires_human_approval` and a named approver, and the model never accepts, refuses or cancels an individual aircraft.
