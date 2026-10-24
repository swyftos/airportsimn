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
| Reference ramp (Atlantic) | 75 su | 52,600 × 0.85 / 600. Range 61 to 91 su for 550 to 650 m² per su and 75 to 95 % usable |
| Atlantic's traffic share | 50 % | Its 55.8 % of the two incumbents' leased land (NAZAR-S01) applied to the 90 % of traffic this FBO does not capture. Land share as a traffic proxy is an assumption |
| **Main ramp (this FBO)** | **15 su** | 75 × 0.10 / 0.50: sized to this FBO's 10 % share (`fbo_market_share`, alan/assumptions.csv). `run_provisional.py` recomputes it when the share changes |

Atlantic's whole ramp was the earlier capacity, which no event scenario could fill. The fictional FBO now gets a ramp proportional to its share. Because demand and ramp both scale with the share, ramp use no longer depends on the share guess (`sensitivity_share_robustness.csv`: identical utilization for 5, 10 and 15 %). Tow-in packing (+10 %) and the remote overflow apron (up to 40 su, leased only for the space units needed at $100 per su per day) remain estimates that need management approval. The area figure dates from 2008 and should be replaced by a measured apron area or a real stand count when one is found.

## Starting inventory

6.1 transient aircraft are parked on the morning of 2027-02-11, split by the category mix. The value follows Little's law: P2's ordinary arrivals on 2027-02-11 (5.50) times an average dwell of 1.1 days (Alan's ledger, `avg_dwell_days`). It is written in the ledger so the dashboard can check it, `run_provisional.py` refreshes it with each P2 release, and `test_opening_inventory_follows_p2_baseline` fails if the two drift apart. With this opening value, the ordinary week ends at 6.1 aircraft at P50, so the run is at steady state.

The same opening inventory is used for the ordinary week, the standard event week and the delay variant.

## How turn, overnight and multi-day stays are represented

The model does not track individual aircraft or draw a stay length per aircraft. P2 forecasts arrivals and departures as independent daily flows per category, and the ramp is simulated as an inventory:

- **Within a day**, half of the day's departures (`dep_share_before_peak` = 0.5) leave before the arrival peak, the rest after it. Every arrival of the day is on the ramp at the peak. A same-day **turn** therefore always occupies a position at the daily peak, which is conservative for parking.
- **Overnight and multi-day stays** are whatever aircraft remain after the day's departures. The share of stays of each length is not an input. It follows from how P2's departure flow lags its arrival flow. For the event, P2 now puts the extra arrivals on Thursday to Saturday and half of game day, and the same number of extra departures on the other half of game day and Monday, so event aircraft stay one to four nights and accumulate until game day.
- **Check against Alan's benchmark.** Alan's ledger uses 40 % turns (0.5 day), 45 % overnight (1 day) and 15 % multi-day (3 days), an average of 1.1 days. The ordinary-week run gives a peak-occupancy-to-arrival ratio of **1.72 days** (average daily-peak aircraft divided by average daily arrivals). Because this uses daily peaks rather than time-average occupancy, it is a diagnostic ratio, not a Little's-law estimate of actual dwell time.

## Ordinary-week baseline (`ordinary_week_parking.csv`)

Same model, units, opening inventory, capacity and staffing rules, run on P2's ordinary forecast for the same dates (`baseline_arrivals`, `baseline_departures`, checked to be identical across P2 scenarios). The range is P2's nominal 90 % baseline interval (baseline ± `baseline_radius`, floored at zero). 10,000 Monte Carlo paths.

Result: a daily parking peak of 11.6 to 13.7 su at P50 (lowest on Saturday, highest on Presidents' Day, Monday 2027-02-15), 78 to 91 % of the 15 su ramp, up to a 21 % chance of exceeding it on Presidents' Day, and 1 technician on the busiest shift. A ramp this full in an ordinary week suggests 15 su is at the small end of a plausible range.

**This level depends on P2's ordinary forecast.** P2 trains on observed daily FAA GA and air-taxi counts for 2023–2025 (3.8 to 6.4 arrivals a day). The weekday pattern comes from the data, and Presidents' Day carries a factor of 1.25 measured on seven holidays (2016–2019, 2023–2025). In a rolling backtest over every week of 2025 the forecast's average daily error is 14.9%, better than four simple baselines (see marvin/person_2_forecasting/PROVISIONAL_ASSUMPTIONS.md).

**Alignment with Alan.** P2 and `alan/baseline.csv` use the same 10 % share, Part 91 + 135 scope and training window. `parking_units` there is a count of aircraft; multiply by 1.47 su per aircraft to compare with P3.

## Event week (`resource_requirements.csv`)

With P2's FAA-anchored scenarios (five-day operations excess of 3.1 / 15.5 / 31 % for Low / Medium / High), the P50 parking peak is 14.2 / 17.4 / 23.0 su, reached on Presidents' Day in Low and on game day in Medium and High. Event aircraft build up from Thursday and leave on Sunday evening and Monday. Against the 15 su ramp, measured on the same 10,000 demand paths with and without the plan:

| Scenario | Plan (approved by the GM) | Cost | Aircraft not accommodated, no plan → plan | Plan pays off in |
|---|---|---|---|---|
| Low | Tow-in packing, lease 1 su of overflow | $1,000 | 1.0 → 0.3 | 41 % of runs |
| Medium | Tow-in packing, overflow lease | $3,500 | 2.3 → 0.1 | 62 % |
| High | Tow-in packing, overflow lease | $9,100 | 6.0 → 0.1 | 78 % |

In Low, preparing costs more than it saves in most runs, and the plan says so; a manager could decline. Alan's ledger gives `fbo_capacity_su` = 87.5 su (Atlantic's hangar plus its whole ramp); that describes Atlantic's facility, not a share-sized one, and is not used.

## 24-hour departure-delay variant

`resource_requirements_departure_delay_24h.csv` and `scenario_recommendations_departure_delay_24h.json`.

Definition: from game day (Sunday 2027-02-14, `delay_24h_first_day` = 3) onward, 100 % of each day's departures (`delay_24h_share`) leave 24 hours later. This represents a post-game ground stop, weather hold or slot restriction. The variant is a **separate simulation** on the same 10,000 demand paths as the standard run (same seed). Departures, parking, prepared capacity, staffing, fuel, costs, impact and recommendations are all recomputed. Departures scheduled for 2027-02-17 move to 2027-02-18, outside the window, so those aircraft stay parked.

Effect in the Medium scenario: Monday's parking peak goes from 15.8 to 26.5 su at P50, and aircraft keep accumulating until the delayed departures leave. In the Low scenario, it goes from 14.2 to 22.5 su. Every scenario now exceeds the 15 su ramp: without a plan 5.5 / 8.0 / 12.0 aircraft are not accommodated, with it 0.2 / 0.1 / 0.2, and the plan ($6,000 / $11,200 / $16,800) pays off in 84 / 89 / 92 % of runs. Preparation matters most when something goes wrong.

## Game-day security restriction variant

`resource_requirements_security_restriction.csv` and `scenario_recommendations_security_restriction.json`.

Input: Alan's `alan/data/processed/security_restriction_model_input.csv`. No private movements on Sunday 2027-02-14 between 14:30 and 20:30, the window of the Super Bowl LVI security TFR (FAA flight advisory), with LAX inside the 10 NM inner ring. This is a precedent-based assumption; no TFR has been published for 2027.

Method: movements are spread evenly within each shift (morning 06–14, day 14–22, night 22–06). The window covers 6 of the day shift's 8 hours, so 30 % of game-day movements are blocked. They are released evenly over `security_release_hours` (4 h) after 20:30. Game-day shift shares go from 40 / 40 / 20 % to 40 / 21 / 39 %, so the night shift handles almost twice its usual share. `security_next_day_share` (0 by default, because LAX is open 24 h) sends a share of blocked departures to Monday instead. Same 10,000 demand paths as the standard run.

Result at the current demand: parking is unchanged with no next-day slips (14.2 / 17.4 / 23.0 su P50 peaks). If half or all blocked departures slip to Monday, the peaks rise to 14.7–15.1 / 17.9–18.5 / 23.6–24.3 su. The normal crew of 3 technicians per shift covers the game-day night surge in every scenario, so the plan recommends no action. With a larger FBO share, the night shift is the first place this variant would require extra staff.

The dashboard contract (`nazar/readiness/contracts.py`) accepts only the standard and 24-hour delay variants, so these two files are not displayed yet, and the carryover table does not include them.

## Heavy-rain variant

`resource_requirements_heavy_rain.csv` and `scenario_recommendations_heavy_rain.json`.

The effect is measured, not assumed: on LAX days with at least 0.5 in of rain, completed operations were 9.8 % lower for Part 91 (GA) and 4.1 % lower for Part 135 (air taxi) than on dry days of the same weekday and month (NOAA daily weather joined with FAA daily counts, 2016–2019 and 2023–2025; `marvin/person_2_part91_part135_forecast/results/weather_effect_measured.csv`). Weighted by the 2023–2025 traffic split, that is −6.3 %. On the heavy-rain day (`heavy_rain_day`, default game day) that share of arrivals and departures happens the next day instead. About 5 % of February days at LAX have heavy rain.

Result: the game-day peak moves from 17.4 to 17.1 su in Medium (14.2 → 14.5 su Low, 23.0 → 22.8 su High, where Monday absorbs the delayed movements). Weather is a minor factor for parking compared with the event scenarios or a 24-hour delay.

## Sensitivity and capacity stress (`sensitivity.py`)

`sensitivity_tornado.csv` and `capacity_stress.csv` (2,000 Monte Carlo paths per run, same seed; written by Gemini, reviewed). One input changes at a time, Medium scenario, standard variant (base peak 17.4 su):

| Input (low / base / high) | Medium peak P50, su | Swing |
|---|---|---|
| FBO share 5 % / 10 % / 15 % | 8.7 / 17.4 / 26.0 | 17.3 |
| Opening dwell 0.8 / 1.1 / 1.5 days | 15.0 / 17.4 / 20.5 | 5.5 |
| Aircraft mix light-heavy / 47-33-20 / large-heavy | 15.4 / 17.4 / 20.0 | 4.6 |
| Departures before the peak 30 / 50 / 70 % | 18.8 / 17.4 / 15.9 | 2.9 |
| Large-jet footprint 2.0 / 2.5 / 3.0 su | 16.1 / 17.4 / 18.5 | 2.4 |

The FBO share drives the result far more than anything else, and it is an assumption. Dwell time and aircraft mix come next; both could be measured with ADS-B data.

Capacity stress: the same demand against ramps of 10 to 75 su. Parking never binds above 40 su. The smallest tested ramp at which fewer than 0.5 aircraft a run go unaccommodated without preparation is 20 / 20 / 30 su (Low / Medium / High), and 30 / 30 / 40 su with the 24-hour delay. Below that, tow-in packing (free) and an overflow lease sized to the shortfall remove almost all unaccommodated aircraft. At 10 su the plan pays off in 77 to 99 % of runs; at 15 su (the share-sized ramp) in 40 / 55 / 82 % (standard) and 82 / 89 / 92 % (24-hour delay), from this 2,000-path run.

## Arrival-slot and price incentives (`slot_advisor.py`)

`slot_advisor.csv` and `slot_recommendations.json`, same demand paths as the parking plan, plain 15 su ramp. Two levers, each at 0 / 10 / 20 / 30 % take-up because nobody knows how many owners accept an offer:

- **Cheap early arrival (Thursday or Friday instead of the weekend)** does not free parking. Departures do not move, so the aircraft stay longer: at 30 % take-up the Medium game-day peak stays at 17.3 su and unaccommodated aircraft rise from 2.3 to 4.3. It only spreads the handling workload.
- **Drop-and-go credit ($500, about one landing fee plus handling)** for Super Bowl arrivals: drop passengers, reposition to a partner field, return for pickup. At 30 % take-up the Medium game-day peak falls from 17.4 to 15.9 su and unaccommodated aircraft from 2.3 to 1.6 (net +$1,000); in High from 23.0 to 20.0 su and 6.0 to 4.2 (net +$3,100). Not worth it in Low. Each acceptance adds two handling movements.

The advisor recommends the drop-and-go offer in Medium and High as a complement to the ramp plan, never on its own. Past Super Bowls filled parking without raising prices, so reservations (PPR) stay the primary tool. Every recommendation is an offer approved by the FBO general manager; the system never refuses or reassigns an aircraft.

## Aircraft still parked after 2027-02-17 (`parking_carryover.csv`)

One row per variant and scenario: opening aircraft, aircraft remaining after the last day (P10, P50, P90, demand not limited by capacity), space units remaining at P50, and departures pushed past the window by the delay.

| Variant | Remaining aircraft P50 (Low / Medium / High) |
|---|---|
| ordinary | 6.1 |
| standard | 6.1 / 6.0 / 6.3 |
| departure_delay_24h | 10.8 / 10.7 / 11.0 |

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
