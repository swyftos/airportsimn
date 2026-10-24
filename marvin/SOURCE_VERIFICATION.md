# LAX sources and verification paths

Prepared October 23, 2026. Paths use downloaded main snapshot 3f8aa2b, not a fresh audit of latest main. The FAA live portal was checked; counts below are calculated from the repository export, not independently re-downloaded this turn.

## Marvin: before, during and after Super Bowl LVI

[FAA ATADS/OPSNET](https://aspm.faa.gov/opsnet/sys/Airport.asp) is the primary source.
Select LAX, daily grouping, January 30–February 26, 2022. Keep operational categories separate. Each takeoff or landing counts as one operation, not one aircraft visit.

Repository chain:
- [data_sources.md](https://github.com/swyftos/airportsimn/blob/3f8aa2bbd348fcef7c0e52200352adbcf9bc7263/data_sources.md)
- [alan/elia_output/data_sources_lawa_bts.md](https://github.com/swyftos/airportsimn/blob/3f8aa2bbd348fcef7c0e52200352adbcf9bc7263/alan/elia_output/data_sources_lawa_bts.md)
- [alan/elia_output/scripts/fetch_opsnet.py](https://github.com/swyftos/airportsimn/blob/3f8aa2bbd348fcef7c0e52200352adbcf9bc7263/alan/elia_output/scripts/fetch_opsnet.py)
- [alan/elia_output/data/processed/opsnet_daily_superbowl.csv](https://github.com/swyftos/airportsimn/blob/3f8aa2bbd348fcef7c0e52200352adbcf9bc7263/alan/elia_output/data/processed/opsnet_daily_superbowl.csv)
- [alan/elia_output/scripts/analyze_superbowl_lvi.py](https://github.com/swyftos/airportsimn/blob/3f8aa2bbd348fcef7c0e52200352adbcf9bc7263/alan/elia_output/scripts/analyze_superbowl_lvi.py)
- [alan/elia_output/data/processed/superbowl_lvi_surge.csv](https://github.com/swyftos/airportsimn/blob/3f8aa2bbd348fcef7c0e52200352adbcf9bc7263/alan/elia_output/data/processed/superbowl_lvi_surge.csv)
- [alan/elia_output/data/processed/superbowl_lvi_daily_profile.csv](https://github.com/swyftos/airportsimn/blob/3f8aa2bbd348fcef7c0e52200352adbcf9bc7263/alan/elia_output/data/processed/superbowl_lvi_daily_profile.csv)
- [alan/elia_output/data/processed/opsnet_lax_monthly.csv](https://github.com/swyftos/airportsimn/blob/3f8aa2bbd348fcef7c0e52200352adbcf9bc7263/alan/elia_output/data/processed/opsnet_lax_monthly.csv)

### Descriptive LAX counts

Calculated from the CSV linked above. Different window lengths and weekday mixes mean this is not a causal event-impact estimate.

| 2022 period | Days | Air taxi total | Air taxi/day | GA total | GA + air taxi/day | All operations/day |
|---|---:|---:|---:|---:|---:|---:|
| Before: February 3–9 | 7 | 594 | 84.9 | 257 | 121.6 | 1,399.4 |
| Event: February 10–14 | 5 | 528 | 105.6 | 275 | 160.6 | 1,517.4 |
| After: February 15–21 | 7 | 647 | 92.4 | 337 | 140.6 | 1,487.3 |

All operations includes commercial airlines. Air taxi and GA are relevant proxies, not exclusively business jets and not FBO customer counts.

The existing surge analysis estimates **15.5% control-adjusted excess for LAX air taxi**, and **8.5% across six airports** during Thursday–Monday. It uses same-weekday medians outside the event window and control years 2019, 2023 and 2024. These are team calculations from FAA data, not percentages published by FAA.

The **33% Monday increase is six-airport air-taxi operations versus a same-weekday baseline**, not LAX-only, not departure-only, and not the control-adjusted five-day result. One pandemic-era event does not prove a 2027 multiplier.

### Official cross-checks

- [LAWA monthly traffic](https://www.lawa.org/lawa-investor-relations/statistics-for-lax/volume-of-air-traffic).
- [LAWA annual FAA aircraft movements](https://www.lawa.org/lawa-investor-relations/statistics-for-lax/10-year-summary/faa-aircraft-movements).
- [LAWA April 4, 2022 release](https://www.lawa.org/news-releases/2022/news-release-023): 4,080,905 February passengers, 3.1% above January. LAWA attributes growth to both Super Bowl activity and recovering travel. Passengers are not aircraft movements or FBO demand.

Keep 2016–2025 history, exclude 2020–2022 from ordinary training, and retain 2022 separately for the event study. Account for the pre/post-COVID level change. FBO capture, direction split and aircraft mix remain assumptions.

## Service durations: sources and manual gaps

No verified LAX-FBO-specific numerical duration for each requested task was established. Keep gaps unknown or clearly placeholder. These are newly researched sources, not necessarily already used by the model.

| Task | Link | Supported use / gap |
|---|---|---|
| Landing | [NASA LAX study, 2001](https://aviationsystems.arc.nasa.gov/facilities/ffc/laxphase2_report.pdf), Appendix D | Definitions and historical simulation, not observed 2022 business-jet landing times. Measure touchdown-to-runway-exit separately from approach/taxi. |
| Taxi in/out | [BTS reporting-carrier fields](https://transtats.bts.gov/Fields.asp?gnoyr_VQ=FGJ) | TaxiIn, TaxiOut, WheelsOn and WheelsOff support airline analysis. Filter LAX and February 2022; this does not establish FBO taxi times. |
| Loading | [Atlantic LAX](https://www.atlanticaviation.com/locations/LAX/) / [Signature LAX](https://www.signatureaviation.com/locations/LAX) | Request boarding start/end, baggage completion and doors-closed by aircraft class. No confirmed duration found. |
| Unloading | Same operator links | Request chocks-on, doors-open, last passenger off and baggage-unload completion. No confirmed duration found. |
| Refueling | Same operator links | Request truck waiting, setup, pumping and disconnection times, gallons and aircraft type. No verified LAX duration or flow rate found. Volume / flow estimates pumping only. |
| Takeoff | BTS fields and flight/operator records | Separate taxi, queue, line-up and takeoff roll. No verified business-jet takeoff-roll duration established. |
| Full turnaround | [NBAA quick-turn guidance](https://nbaa.org/news/business-aviation-insider/2026-05/best-practices-for-safe-business-aviation-quick-turns/) | Wheels Up describes under-an-hour turns as quick turns. Operator practice, not a measured LAX average. The article's 10/15-minute figures are advance calls, not fueling durations. |

Services can overlap; do not add every task sequentially. Overnight parking dwell is separate from active turnaround.

Manual contacts verified on operator pages:
- Atlantic LAX: **+1 310 258 9884**, link above.
- Signature LAX: **+1 310 410 9605**, link above.

Ask for anonymized normal-week and event-week timestamps, aircraft class, passenger count, gallons and sample size. Calculate median and 90th percentile, separating queues from service. Label a staff estimate as an expert estimate, not observed data.

## Other teammates: short traces

Follow each source-register path to the listed external URLs. These are traced links, not a fresh authenticity/content audit of every document.

### alan/docs/data_sources_alan.md

[Repository source register](https://github.com/swyftos/airportsimn/blob/3f8aa2bbd348fcef7c0e52200352adbcf9bc7263/alan/docs/data_sources_alan.md)

- [External source](https://www.faa.gov/air_traffic/flight_info/aeronav/aero_data/)
- [External source](https://www.airnav.com/airport/LAX)
- [External source](https://basedaircraft.com)
- [External source](https://lawa.granicus.com/MetaViewer.php?clip_id=689&meta_id=46799&view_id=4)

### alan/docs/data_sources_nazar.md

[Repository source register](https://github.com/swyftos/airportsimn/blob/3f8aa2bbd348fcef7c0e52200352adbcf9bc7263/alan/docs/data_sources_nazar.md)

- [External source](https://lawa.granicus.com/MetaViewer.php?clip_id=689&meta_id=46799&view_id=4)
- [External source](https://www.lawa.org/sites/lawa/files/documents/Atlantic%20Aviation%20Final%20Draft%20IS%20Negative%20Declaration_09%2009%202013.pdf)
- [External source](https://cityclerk.lacity.org/onlinedocs/2014/14-0370_misc_4-8-2014.pdf)
- [External source](https://aeronav.faa.gov/d-tpp/2610/00237AD.PDF)
- [External source](https://www.lawa.org/sites/lawa/files/2026-02/ASM%202026.02.pdf)
- [External source](https://www.signatureaviation.com/locations/LAX)
- [External source](https://www.ainonline.com/aviation-news/business-aviation/2008-02-08/atlantic-completes-los-angeles-and-santa-barbara-fbos)
- [External source](https://www.atlanticaviation.com/Locations/LAX)
- [External source](https://www.atlanticaviation.com/media/enfizdvr/lax-atlantic.pdf)
- [External source](https://www.lawa.org/groups-and-divisions/airport-operations/airside-operations/airfield-maps)
- [External source](https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/dafd/)
- [External source](https://www.faa.gov/airports/runway_safety/diagrams/)

### alan/elia_output/data_sources_lawa_bts.md

[Repository source register](https://github.com/swyftos/airportsimn/blob/3f8aa2bbd348fcef7c0e52200352adbcf9bc7263/alan/elia_output/data_sources_lawa_bts.md)

- [External source](https://www.lawa.org/lawa-investor-relations/statistics-for-lax/volume-of-air-traffic)
- [External source](https://www.lawa.org/lawa-investor-relations/statistics-for-lax/10-year-summary/faa-aircraft-movements)
- [External source](https://www.lawa.org/lawa-investor-relations/statistics-for-lax/fbo-rental-car-services-lax-and-vny)
- [External source](https://www.transtats.bts.gov/DatabaseInfo.asp?QO_VQ=EEE&DB_URL=)
- [External source](https://aspm.faa.gov/opsnet/sys/Airport.asp)

## Assumptions are not evidence

The shared assumptions.csv and elia/assumptions_p3.csv contain dwell, fuel uplift, technician productivity and truck-cycle estimates. These are planning inputs, not observed LAX service durations. Random placeholder forecasts are not external evidence. Lease acreage is not usable apron area; historical ramp acreage is not a current survey; blank based-aircraft fields are not zero.

Save the original source download, filters, retrieval date, units and scope. Separate observations, derived statistics, benchmarks, expert estimates and placeholders.
