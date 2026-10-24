# Aggregate data needed to calibrate FBO demand

The public FAA data count airport operations. To estimate arrivals, departures, aircraft size, and parking for one FBO, request **aggregates** from a consenting comparable FBO or its booking system. No tail numbers, names, customer IDs, exact itineraries, or individual booking records belong in this repository.

## Minimum extract

One row per local date, airport, FBO/site, operation basis, fleet segment, and parking-size bin. Include ordinary weeks, comparable major-event weeks, and at least several February holiday weekends. A useful starting period is 2023–2026; document missing dates and any changes in operating hours or booking policy. Suppress or combine small cells before transfer.

| Field | Meaning |
| --- | --- |
| `local_date`, `airport`, `site_code` | Day, airport, and stable anonymized FBO identifier. |
| `fleet_segment` | Selected Part 91, selected on-demand Part 135, other Part 135, other GA, or unknown. Record the eligibility rule. Do not equate the FAA air taxi label with selected Part 135. |
| `size_bin`, `bin_definition` | Counts by ramp-relevant wingspan/footprint bin or aircraft model mapping. Preserve unknowns. Include method and date of mapping. |
| `booking_requests`, `confirmed_reservations` | Unique visit requests and confirmed visits, deduplicated across updates. Record whether a reservation covers an arrival, departure, or both. |
| `completed_arrivals`, `completed_departures` | Actual aircraft movements served by the FBO, separately by direction. Reconcile the two to visit and parking ledgers. |
| `cancellations`, `no_shows`, `diversions` | Counts under stable, documented definitions. Manager decisions remain outside the forecasting model. |
| `start_parked`, `end_parked`, `peak_parked_units` | Inventory and ramp footprint, including aircraft already parked before the extract window. |
| `usable_capacity_units` | Actual operational capacity after closures and reserved areas, if the FBO can provide it. |
| `data_quality_notes` | Missing coverage, unusual events, system changes, deduplication, and category uncertainty. |

An aggregate airport denominator by date, direction, eligibility segment, and size bin is also required for a measured FBO capture share. FAA GA and air taxi category totals alone do not supply that denominator. If only FBO aggregates are available, estimate booking-to-completed-operation rates and the FBO's own seasonal/event pattern, while leaving airport-to-FBO capture unidentified.

## Calculation and validation plan

1. Agree on the selected fleet definition with the historical-data and forecast owners. Keep Part 91 and eligible Part 135; exclude Part 121. Separate unknown eligibility rather than assigning it silently.
2. Reconcile daily completed arrivals and departures to the FBO's own operational log. Treat a paired arrival and departure as one visit but two airport operations. Check opening and closing parking inventory, including carryover aircraft.
3. Estimate `completed_arrivals / confirmed_reservations` only after matching the same cohort and time window. Reservations are advance evidence of demand, not extra arrivals to add to an operations baseline.
4. Estimate airport-to-FBO capture only when the numerator and airport denominator cover the **same** fleet, direction, size bin, and dates. Report coverage and uncertainty; do not use leased square footage as a conversion rate.
5. Hold out entire events and holidays during validation. Report errors at FBO scope and compare them with airport-category diagnostics separately. Do not label airport backtests as FBO accuracy.

Without this extract, the forecast can carry scenarios but cannot claim a measured 47/33/20 aircraft mix, measured FBO market share, or validated selected-fleet event and holiday uplift.
