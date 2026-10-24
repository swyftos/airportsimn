# Marvin directional and event timing stress

The 2027 forecast assumes a 50/50 ordinary arrival/departure split. These cases keep the
same airport operations and event extra movements while changing that ordinary split to
40/60 or 60/40. Opening inventory changes with first-day ordinary arrivals. The timing
case moves event extra arrivals one day earlier and extra departures one day later, within
the seven-day window. It preserves the weekly total in each direction and aircraft category.
Each case uses the existing parking model and 2,000 Monte Carlo runs. Its P2 planning ranges
are scaled with the new point forecasts; they are not newly calibrated intervals.

| Case | Scenario | Peak day | Peak P50 space units | Peak P90 | Max probability over normal ramp |
| --- | --- | --- | ---: | ---: | ---: |
| current | Low | 2027-02-15 | 14.1 | 18.5 | 39.1% |
| current | Medium | 2027-02-14 | 17.4 | 21.6 | 80.7% |
| current | High | 2027-02-14 | 23.1 | 28.4 | 99.7% |
| arrivals 40 percent | Low | 2027-02-11 | 8.9 | 10.6 | 0.3% |
| arrivals 40 percent | Medium | 2027-02-12 | 10.7 | 13.1 | 1.7% |
| arrivals 40 percent | High | 2027-02-12 | 14.9 | 18.1 | 48.1% |
| arrivals 60 percent | Low | 2027-02-17 | 33.8 | 43.7 | 100.0% |
| arrivals 60 percent | Medium | 2027-02-17 | 33.4 | 42.7 | 100.0% |
| arrivals 60 percent | High | 2027-02-14 | 35.4 | 44.0 | 100.0% |
| early arrivals late departures | Low | 2027-02-15 | 14.6 | 19.1 | 44.4% |
| early arrivals late departures | Medium | 2027-02-15 | 18.4 | 22.9 | 88.4% |
| early arrivals late departures | High | 2027-02-15 | 24.1 | 30.1 | 99.9% |

These are model stress results for a fictional FBO. FAA airport counts do not
measure this FBO’s arrival/departure split, reservation timing, parking capacity,
or actual overflow probability. Elia’s action approval rules still apply. Do not
interpret the case names as forecast probabilities.
