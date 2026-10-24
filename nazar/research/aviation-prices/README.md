# LA aviation price research

Retrieved October 23, 2026. Routes: New York JFK and Newark EWR, Miami MIA, and Las Vegas LAS paired with LAX. Target future trip: February 11–15, 2027. No date-specific 2027 fares have been verified.

## Historical commercial fares

USD per passenger, average each-way fare. These are directionless airport-pair markets covering both directions and all ticket classes, including taxes and airport fees but excluding ancillary charges. They are not economy-only quotes, round-trip tickets, annual averages, or Super Bowl-week observations. Q1 (January–March) is shown because it covers February. Values are nominal, not inflation-adjusted.

[DOT Table 1a data](https://data.transportation.gov/Aviation/Consumer-Airfare-Report-Table-1a-All-U-S-Airport-P/tfrh-tu9e) · [Fare definitions](https://www.transportation.gov/policy/aviation-policy/air-fare-information-consumers)

| Year, Q1 | JFK–LAX | EWR–LAX | MIA–LAX | LAS–LAX |
|---|---:|---:|---:|---:|
| 2016 | $391.36 | $349.22 | $269.66 | $126.56 |
| 2017 | $385.40 | $338.55 | $308.95 | $119.98 |
| 2018 | $385.73 | $354.20 | $315.10 | $122.41 |
| 2019 | $360.05 | $299.29 | $353.10 | $114.44 |
| 2023 | $442.43 | $327.54 | $367.11 | $127.23 |
| 2024 | $476.13 | $358.13 | $333.32 | $142.99 |
| 2025 | $453.93 | $379.24 | $427.71 | $128.55 |
| 2026 | $508.31 | $405.75 | $483.48 | $143.77 |

2020–2022 are excluded as an explicit working assumption requested by the team; originals remain in the raw data. Keep those years available for sensitivity/event analysis rather than declaring them unusable for every purpose. The downloaded extract contains 2016 Q1 through 2026 Q1. The DOT sampling system changed from DB1B to OD40/DB1C; check comparability before fitting a long-run model. [BTS methodology notice](https://www.bts.gov/air-fares).

The JSON includes every available quarter, exclusion flags, and derived annual averages for complete years. Annual aggregation weights each quarterly fare by passengers per day × calendar days in that quarter. No partial-year number is presented as a full-year average.

## Historical fuel benchmark

Annual U.S. Gulf Coast jet-fuel spot price, USD per US gallon. This measures wholesale market movement; it does not represent fuel purchased at an LAX FBO.

[EIA source](https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=EER_EPJK_PF4_RGC_DPG&f=A)

| Year | USD/US gallon |
|---|---:|
| 2016 | $1.252 |
| 2017 | $1.558 |
| 2018 | $2.027 |
| 2019 | $1.879 |
| 2023 | $2.699 |
| 2024 | $2.338 |
| 2025 | $2.114 |

## Current LAX retail fuel snapshot

- Atlantic Aviation: posted Jet A $13.32; page reports October 20, 2026. [AirNav listing](https://www.airnav.com/airport/KLAX/ATLANTIC).
- Signature Aviation: posted Jet A $13.12; page reports October 23, 2026. [AirNav listing](https://www.airnav.com/airport/KLAX/SIGNATURE).

Both listings say full-service, taxes included, prices not guaranteed. Confirm current units and a written quote before operational use. Do not infer FBO profit by subtracting the Gulf Coast benchmark from a posted retail price.

## Private charter pricing

A whole-aircraft charter is priced per aircraft and trip, not per airline seat. Paramount publishes 2026 all-inclusive one-way starting estimates for New York → Los Angeles: $40,000 super midsize, $45,000 large jet, $62,000 ultra-long-range. Its Los Angeles → Las Vegas estimates are $7,500 turboprop, $9,500 very light jet, and $11,000 light jet. The latter is the reverse direction of the requested trip and must remain labelled that way. These city-level estimates do not establish LAX-specific prices or February 2027 availability.

[Paramount pricing source](https://www.paramountbusinessjets.com/private-jet-rental-cost)

No consistent verified annual 2016-present history for these private-charter routes was located. Miami → LA remains unverified. Do not backfill missing years with current prices or scale the whole charter price using fuel prices alone. A historical model would require dated operator quotes/invoices or a clearly labelled estimate with separate aircraft, fuel, crew, positioning, airport-fee and tax assumptions.

## How to use this in the hackathon

Use fares and wholesale fuel as contextual economic variables. They do not directly establish FBO aircraft arrivals or parking occupancy. Fit a price-demand relationship only if you have matching observed private-aircraft demand; otherwise present scenario assumptions rather than a claimed measured causal effect. Maintain separate source types: historical observed averages, current posted retail prices, indicative charter estimates, and future quotes.

Files: [price-data.json](price-data.json) contains normalized observations and definitions; [dot-original-records.json](dot-original-records.json) preserves the official response, including excluded years. This research is not wired into the dashboard or forecasting pipeline.

## Reproducing the commercial extract

The DOT Socrata endpoint is `https://data.transportation.gov/resource/tfrh-tu9e.json`. The extract uses these query parameters:

```text
$where=year >= 2016 AND ((airport_1 = 'LAX' AND airport_2 in ('JFK','EWR','MIA','LAS')) OR (airport_2 = 'LAX' AND airport_1 in ('JFK','EWR','MIA','LAS')))
$order=year,quarter,airport_1,airport_2
$limit=5000
```

URL-encode the parameters when requesting the API. This snapshot has 164 quarterly records, including 48 flagged COVID-period records and 116 included records. The derived annual table has 28 rows: four airport pairs for each complete included year (2016–2019 and 2023–2025). The 2026 observations cover Q1 only. Future refreshes may contain additional periods or revisions; retain a retrieval date and recheck completeness before aggregation.
