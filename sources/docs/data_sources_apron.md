# The dashboard team: LAX apron and ramp area

Retrieved **October 23, 2026**, America/Los_Angeles. This is the apron-area contribution to the data team's data workstream. Merge these source IDs into the eventual `data_sources.md`; the other three Step 2 pieces remain separately owned.

## Result and recommended use

Use **Atlantic Aviation LAX as the reference facility** for the fictional FBO. Its public lease/site records are stronger than Signature's ambiguous website claim. The current usable apron area and real parking stand count remain **unconfirmed**.

The historical ramp benchmark is **13 acres**, reported by AIN in 2008. Its exact unit conversion is **566,280 sq ft**, or approximately **566,000 sq ft / 52,600 m²** at the precision of the source. It is only an optional, low-confidence historical proxy if carried forward to the modeled period. It is not a measured 2026/2027 capacity and not a time series covering 2016–2025.

## Source register

Every source below was retrieved on 2026-10-23. Local copies or short source excerpts are in `../data/raw/fbo_apron/`; `source_manifest.json` records URLs, dates, locators, confidence, and SHA-256 checksums.

| ID | Source and date | What it supports | Reliability and limitation |
|---|---|---|---|
| DASH-S01 | [LAWA Board report](https://lawa.granicus.com/MetaViewer.php?clip_id=689&meta_id=46799&view_id=4), 2020-11-19, pp. 2–3 | Atlantic leased land: 666,502.84 sq ft. Signature leased land: 527,795 sq ft. Signature building rental area: 128,400 sq ft. | High for historical lease facts. Neither land total equals apron. Rental floor area need not equal a building footprint. |
| DASH-S02 | [Atlantic hangar and office initial study](https://www.lawa.org/sites/lawa/files/documents/Atlantic%20Aviation%20Final%20Draft%20IS%20Negative%20Declaration_09%2009%202013.pdf), 2013-09-12 | PDF p. 21 (A-7): proposed total building area 53,509 sq ft. PDF p. 23, Figure 3: detailed western site plan. PDF p. 19, Figure 2: airport context. | High for the documented proposal; not proof of completion or today's layout. Figure 3 crops out much of the ramp and cannot measure the entire FBO. |
| DASH-S03 | [City administrative report](https://cityclerk.lacity.org/onlinedocs/2014/14-0370_misc_4-8-2014.pdf), 2014-04-01, p. 1 | Atlantic leasehold rounded to 666,503 sq ft / 15.3008 acres. | High for historical cross-check; no apron-only area. |
| DASH-S04 | [FAA airport diagram, cycle 2610](https://aeronav.faa.gov/d-tpp/2610/00237AD.PDF) | Chart's validity strip: October 1–29, 2026. Identifies FBO vicinity relative to the airfield. | High for diagram context. No surveyed FBO apron boundary or area table. Archived chart expires; do not call it perpetually current. |
| DASH-S05 | [LAWA Movement Area Map 2026 v5](https://www.lawa.org/sites/lawa/files/2026-02/ASM%202026.02.pdf), p. 1 | Labels Atlantic FBO and Signature FBO separately. Map states effective September 14, 2026, despite the February URL path. | High for facility identification. Schematic reference map; not an area survey. |
| DASH-S06 | [Signature LAX operator page](https://www.signatureaviation.com/locations/LAX), undated | FAQ claims 200,000–300,000 sq ft of ramp. | Low: FAQ heading and neighboring answers mention Las Vegas. Preserve as an unverified range; not the selected facility. |
| DASH-S07 | [AIN historical report](https://www.ainonline.com/aviation-news/business-aviation/2008-02-08/atlantic-completes-los-angeles-and-santa-barbara-fbos), 2008-02-08 | Reports a 13-acre Atlantic ramp at LAX. | Secondary industry reporting; medium confidence as a historical statement, low as a present-day proxy. No current survey or stand count. Full page HTML/subheading and publication metadata were checked after browser retrieval failed. |
| DASH-S08 | [Atlantic LAX operator page](https://www.atlanticaviation.com/Locations/LAX), undated | Operator identity/address and PPR/event-compression advisories. | Qualitative context only; not a quantified surge signal or Super Bowl LVI observation. |
| DASH-S09 | [Atlantic-hosted FAA diagram](https://www.atlanticaviation.com/media/enfizdvr/lax-atlantic.pdf), chart marked 17229 | Discovered through Atlantic's live location page. | Stale chart. Archived to explain why a live operator link is not evidence of current geometry. Prefer S04. |

Discovery pages: [LAWA Airfield Maps](https://www.lawa.org/groups-and-divisions/airport-operations/airside-operations/airfield-maps), [FAA chart supplements](https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/dafd/), and [FAA airport diagrams](https://www.faa.gov/airports/runway_safety/diagrams/). Retrieved 2026-10-23; used for navigation, not numerical area claims.

## Checks and unresolved gaps

- The S01 Atlantic table prints **15.308 acres**, but 666,502.84 / 43,560 = **15.3008 acres**. The 2014 record supports the latter. Preserve square feet as the authoritative recorded value and flag the printed acres discrepancy.
- The historical 13-acre ramp fits inside the documented leasehold. That is a plausibility check only; dates and definitions differ, so it does not independently verify the ramp claim.
- No precise **current apron-only** area was established from the reviewed sources. No full current Airport Layout Plan with a usable FBO boundary was obtained. Neither an airport-wide paved area nor a partial building-project map should substitute for that boundary.
- The 2013 proposed building area must not simply be subtracted from the historical ramp. The project includes vehicle-parking land, and planned construction is not an as-built update.
- The 2020 source is a static facility/lease record. The data team's 2020–2022 traffic-trend exclusion does not invalidate it as facility context. It supplies no traffic observations; 2022 remains separately handled for the Super Bowl case study.

## How area should enter the model

Keep these concepts separate: gross reference ramp area, usable parking area, reserve for existing commitments, and aircraft-class parking envelopes. A planning calculation can use:

`usable_area = gross_reference_area * documented_usable_fraction`

`transient_area = max(0, usable_area - based_and_committed_reserve_area)`

`sum(parked_aircraft_by_class * area_envelope_by_class) <= transient_area`

The fractions, reserves, and class envelopes remain assumptions until supported. Geometry, access and clearance constraints can further reduce capacity. A scalar area budget does not establish a feasible parking layout.

The parking team's current model uses 90 main-ramp space units and 40 overflow units, both synthetic. This contribution does not validate or overwrite them. Do not equate space units with aircraft counts or claim that public records prove the fictional FBO can park 90 aircraft. Near-zero based-aircraft statistics also do not prove that all ramp space is available.

## What a future diagram estimate needs

Obtain a complete, dated ALP, lease exhibit or orthophoto with a reliable scale. Trace the FBO's actual apron boundary; remove buildings, vehicle lots, taxiways, access lanes and restricted areas explicitly. Save the polygon coordinates, image dimensions, scale calibration and exclusion polygons. Calculate polygon area and test plausible boundary/scale variation. Label the result **benchmark estimate**, including image vintage and an uncertainty range; do not label it public measured acreage. This handoff contains no invented polygon measurement.

## Handoff

- `sources/data/processed/apron_area.csv`: public evidence and explicit missing values.
- `sources/data/processed/assumptions_apron.csv`: selected reference, optional historical proxy, and unresolved model assumptions.
- `sources/data/processed/apron_area.json`: same evidence with explicit JSON nulls and provenance.
- `sources/data/raw/fbo_apron/`: archived source PDFs, excerpts and manifest.

Blank CSV numbers / JSON `null` mean unknown, never zero. `classification` uses `public data`, `benchmark estimate`, or `assumption`. Confidence assesses fitness for the stated use and is not a calibrated probability. `DASH-` IDs avoid collisions when the data team merges the four contributions.

These paths follow the shared repository structure and are proposed through a feature-branch PR. No teammate confirmation has been received. The data team can merge the source and assumption rows into the final `data_sources.md` and `assumptions.csv`, then use the area evidence for baseline/capacity work (§4/§5). Traffic histories and surge multipliers remain separate inputs to §3; this contribution does not create `historical_traffic.csv` or `baseline.csv`.
