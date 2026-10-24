# Person 2 weather review — Super Bowl LX (observed airport proxy)

**Scope and date.** Super Bowl LX was in Santa Clara on **February 8, 2026**. This review covers seven calendar days before (February 1–7), game day, and seven after (February 9–15). It compares San Jose airport (SJC), an aviation-weather proxy for the host area, with Los Angeles International Airport (LAX), the fictional FBO's airport. The 2027 planning weather is still unknown.

**Critical provenance.** The flight counts below are *observed FAA CountOps itinerant General Aviation (GA) operations*, split into arrivals and departures. They exclude the FAA Air Taxi and Air Carrier categories, but **GA is broader than the selected private fleets**. These are neither observed fleet bookings nor FBO demand. FAA airport movement counts do not identify diversions, cancellations, parking, dwell time, or weather-caused delay. Do not call the differences below a causal weather effect or a measured private-fleet forecast error.

## What happened

- **Game day, February 8:** SJC recorded **39 GA arrivals and 43 GA departures**; LAX recorded **9 arrivals and 12 departures**. The National Weather Service (NWS) recorded **0.00 in rain** at both stations; SJC's high was **69°F** and peak wind **28 mph**, versus LAX **82°F** and **28 mph**.
- **Seven days before versus seven days after:** SJC averaged **35.4 arrivals / 30.7 departures per day** before and **35.7 / 38.6** after. LAX averaged **17.4 / 17.4** before and **20.7 / 20.4** after. These periods have different weekdays, event activity and restrictions, so they are descriptive counts.
- **Rain days versus other days within these 15 dates:** Define a rain day as NWS daily precipitation **at least 0.01 in**. This is a narrow, auditable weather proxy; a dry day can still have poor visibility or wind. SJC had 3 rain days (Feb 10, 11, 15): mean **28.7 GA arrivals / 24.7 departures** versus **37.6 / 37.8** on 12 other days. LAX had 2 rain days (Feb 10, 11): mean **15.5 / 17.0** versus **18.8 / 18.7** on 13 other days. The SJC descriptive differences are **−24% arrivals and −35% departures**; LAX **−18% and −9%**. Tiny samples and event/day-of-week effects prevent causal attribution.
- **A like-weekday check shows the ambiguity:** Comparing dry Tuesday–Wednesday Feb 3–4 with rainy Tuesday–Wednesday Feb 10–11, LAX changed from **40 arrivals / 37 departures** to **31 / 34**; SJC changed from **62 / 78** to **66 / 51**. SJC arrivals rose while departures fell. A single weather multiplier for both directions would misrepresent this period.
- **After the Feb 10–11 rain:** On Feb 12, LAX rose to **31 arrivals / 18 departures** and SJC to **56 / 59** (SJC reported a trace of rain). That is an observed rebound in completed operations, **not proof** that specific delayed flights were recovered. SJC had another 0.49 in of rain on Feb 15, with **20 / 23** GA arrivals/departures; this is the last day of the requested window. LAX's larger February 16 storm falls *outside* it.

| Date 2026 | Period | SJC rain (in) | SJC GA in | SJC GA out | LAX rain (in) | LAX GA in | LAX GA out |
|---|---|---:|---:|---:|---:|---:|---:|
| Feb 1 | before | 0.00 | 44 | 41 | 0.00 | 17 | 13 |
| Feb 2 | before | 0.00 | 49 | 35 | 0.00 | 24 | 27 |
| Feb 3 | before | 0.00 | 37 | 39 | 0.00 | 21 | 17 |
| Feb 4 | before | trace | 25 | 39 | 0.00 | 19 | 20 |
| Feb 5 | before | 0.00 | 31 | 23 | 0.00 | 17 | 16 |
| Feb 6 | before | 0.00 | 31 | 20 | 0.00 | 14 | 18 |
| Feb 7 | before | 0.00 | 31 | 18 | 0.00 | 10 | 11 |
| Feb 8 | game | 0.00 | 39 | 43 | 0.00 | 9 | 12 |
| Feb 9 | after | 0.00 | 26 | 46 | 0.00 | 19 | 15 |
| Feb 10 | after | 0.10 | 37 | 26 | 0.10 | 13 | 15 |
| Feb 11 | after | 0.33 | 29 | 25 | 0.54 | 18 | 19 |
| Feb 12 | after | trace | 56 | 59 | 0.00 | 31 | 18 |
| Feb 13 | after | 0.00 | 42 | 54 | 0.00 | 31 | 25 |
| Feb 14 | after | 0.00 | 40 | 37 | 0.00 | 16 | 15 |
| Feb 15 | after | 0.49 | 20 | 23 | 0.00 | 17 | 36 |

**Count check.** LAX CountOps GA itinerant movements total **553** over these 15 days. The FAA ATADS airport report's GA category totals **556** for the same dates, a difference of three movements. CountOps supplies the direction split; retain both raw sources and investigate the small discrepancy before treating one as interchangeable with the other. SJC's **68 local GA operations** in the CountOps report are excluded because they are not itinerant arrivals or departures.

## Weather and operational interpretation

The 2026 Super Bowl itself had no measured rain at SJC or LAX. February 10–11 rain coincided with fewer SJC GA departures, while LAX showed a smaller change. Counts cannot reveal whether rain caused delay, a reservation was shifted, the FAA imposed a ground program, or the event's PPR/TFR shaped the schedule. The FAA's Super Bowl LX notice required event reservations for participating Bay Area airports from Feb 4–9 and warned of traffic-management measures; SJC is covered, LAX is not. The venue and restriction regime therefore differ from the proposed LAX-based 2027 FBO.

For the **private-fleet placeholder model**, keep the existing good/moderate/severe weather cases as *unmeasured sensitivities*. Do not fit a permanent 9%, 18% or 35% penalty from this 15-day comparison. When fleet bookings and operational records exist, estimate separate effects on **requested arrivals**, **accepted arrivals**, **departures**, **delay**, **cancellation**, and **diversion**, controlling for day of week and event schedule. A forecast should preserve the distinction between demand changing and runway/ground acceptance shrinking.

The current Person 2 demo assumes a **15% rain throughput reduction** and **35% low-visibility reduction**, with illustrative landing/takeoff delays of **9/12 minutes** in rain and **24/30 minutes** in low visibility. These are **PLACEHOLDER** sensitivity inputs, not measured from the February 2026 records. The CountOps/NWS join cannot validate those minute estimates. These factors do not change the demo forecast demand or accepted-aircraft counts.

## Diversion recommendation

**Include diversion as a contingency workflow; exclude it as a predicted count or automated airport-routing decision for now.** Before accepting a diverted selected-fleet aircraft, the planner should show the operator/pilot a candidate alternate only after checking current weather and approach minima, NOTAMs/TFRs, runway suitability, fuel, local PPR and FBO parking/service capacity. Record the operator's decision and new ETA, then rerun stand occupancy and downstream departures. The pilot/operator and ATC retain flight-routing authority. A provisional dashboard may show an editable “delayed / canceled / diverted” sensitivity and unfilled-capacity consequences, but must not invent actual diversion rates.

This recommendation follows FAA guidance that persistent weather can produce holding and diversions, while event-specific airport reservations and nearby parking constraints require coordination. The FAA's Super Bowl LX notice also prohibited routine airborne IFR destination changes within 200 nautical miles of the Bay Area except emergencies; that was an event-specific rule, **not a general rule for LAX 2027**.

## Live sources and exact retrieval paths

1. [NFL event date and location](https://operations.nfl.com/gameday/nfl-schedule/2026-important-nfl-dates): Super Bowl LX, Feb 8, 2026, Santa Clara.
2. [FAA CountOps report interface](https://www.aspm.faa.gov/cops/sys/COPS.asp): choose **Airport Summary Report**, **LAX** or **SJC**, range **Feb 1–15, 2026**, grouping **Date**, HTML. Read the **IFR + VFR General Aviation** columns separately under **Itinerant Arrivals** and **Itinerant Departures**. Retrieved Oct 23–24, 2026. [FAA report field definitions](https://www.aspm.faa.gov/aspmhelp/index/CountOps__Airport_Summary_Report.html) explain the split. The generated report URL is session based, so use this retrieval path to reproduce it.
3. [FAA ATADS airport operations interface](https://www.aspm.faa.gov/opsnet/sys/Airport.asp): LAX, Feb 1–15, 2026, Date grouping; cross-check GA category total 556. This source combines arrivals and departures.
4. [NWS Los Angeles airport February 2026 daily climate](https://forecast.weather.gov/product.php?format=TXT&glossary=0&issuedby=LAX&product=CF6&site=NWS&version=9): daily precipitation, temperature and peak wind.
5. [NWS San Jose airport February 2026 daily climate](https://forecast.weather.gov/product.php?format=TXT&glossary=0&issuedby=SJC&product=CF6&site=NWS&version=9): same measures.
6. [FAA Super Bowl LX special air traffic procedures](https://www.faa.gov/air_traffic/publications/domesticnotices/dom26007_sp.html): PPR, nearby parking constraints, destination-change restriction and routing.
7. [FAA weather-delay explanation](https://www.faa.gov/nextgen/programs/weather/faq): why weather can slow, hold or divert flights; this does not quantify this event.
8. [FAA instrument procedures handbook](https://www.faa.gov/sites/faa.gov/files/regulations_policies/handbooks_manuals/aviation/instrument_procedures_handbook/FAA-H-8083-16B.pdf): Part 91 alternate-airport planning rules and weather minima.

## February 2027 planning sensitivity — PLACEHOLDER, not a weather forecast

The accompanying [`weather_sensitivity_placeholder.csv`](weather_sensitivity_placeholder.csv) repeats each synthetic weather case for every Feb 11–17, 2027 planning date and Low/Medium/High demand tier. It is a scenario input table, **not** a forecast of which conditions will occur or a fitted estimate of operational impact. It does not alter predicted fleet demand or accepted aircraft counts.

| Synthetic case | Airfield throughput factor | Landing to parking | Parking to takeoff | Added time vs clear |
|---|---:|---:|---:|---:|
| Clear | 1.00 | 12.7 min | 13.7 min | 0 / 0 min |
| Rain | 0.85 | 21.7 min | 25.7 min | +9 / +12 min |
| Low visibility | 0.65 | 36.7 min | 43.7 min | +24 / +30 min |

The factors and minutes are **PLACEHOLDER assumptions**; neither CountOps nor the NWS observations identifies them for the fictional FBO. The CSV is retained separately from the observed 2026 comparisons above so a later model run can replace it with evidence without changing the observed-data record. Historical GA counts are broader than the selected private fleets. Air taxi, charter, and commercial counts are excluded from this weather comparison.
