# Step 2 — LAWA statistics cross-check and BTS scope check (Elia)

Elia's part of Step 2, stored in `alan/elia_output/`, to be merged into `alan/docs/data_sources.md`. Retrieval date for every source below: **2026-10-23** (exact UTC timestamps in `alan/elia_output/data/processed/lawa_monthly_movements.csv`). Everything is reproducible:

```
python alan/elia_output/scripts/fetch_lawa_tcom.py 2015   # downloads 129 TCOM PDFs into alan/elia_output/data/raw/lawa_tcom/, parses FAA movement block
python alan/elia_output/scripts/build_lawa_series.py      # cleans, fills gaps, validates against LAWA official annual totals
```

## Sources

| # | Source | URL | What was pulled | Classification | Confidence |
|---|---|---|---|---|---|
| L1 | LAWA Traffic Comparison (TCOM), monthly PDF, tab 1 of "Volume of Air Traffic" | https://www.lawa.org/lawa-investor-relations/statistics-for-lax/volume-of-air-traffic | FAA aircraft movements at LAX by category (air carrier, air taxi, general aviation, military, total), every month Jan 2015 to Aug 2026 | verified_public | High |
| L2 | LAWA Ten Year Summary of FAA Aircraft Movements | https://www.lawa.org/lawa-investor-relations/statistics-for-lax/10-year-summary/faa-aircraft-movements | Annual movements by category, 2008 to 2025, used to validate L1 | verified_public | High |
| L3 | LAWA "FBO Rental Car Services at LAX and VNY" | https://www.lawa.org/lawa-investor-relations/statistics-for-lax/fbo-rental-car-services-lax-and-vny | Checked and **not used**: it reports car-rental revenue and transactions at FBOs, not aircraft activity | n/a | n/a |
| B1 | BTS Air Carrier Statistics (T-100) database description | https://www.transtats.bts.gov/DatabaseInfo.asp?QO_VQ=EEE&DB_URL= | Scope check only, no data pulled (see below) | n/a | n/a |

## Deliverables in `alan/elia_output/data/processed/`

- `lax_monthly_movements.csv`: 132 months (2015-01 to 2025-12, plus 2026 to August), one row per month. Columns `year, month, air_carrier, air_taxi, general_aviation, military, total, value_source, excluded_covid, data_classification, source_url`. Years 2020, 2021, 2022 are kept and flagged `excluded_covid=True`, never silently dropped.
- `lawa_annual_10yr.csv`: official annual totals (L2).
- `validation_report.csv`: sum of monthly values vs official annual totals.
- `lawa_monthly_movements.csv`: every raw reading, both columns of every report, for audit.

## Validation result

The 12 monthly values add up **exactly** to LAWA's official annual totals for air taxi, general aviation and total movements in 10 of 11 years (2015 to 2017, 2019 to 2025). The exception is 2018, where the gap is 369 air taxi, 184 GA and 1,560 total movements (0.2 % of the total). On the LAWA page, the March and April 2018 links open the February report, so those two months come from the prior-year column of the March and April 2019 reports, which are probably unrevised readings. They are kept as published and flagged by `value_source=tcom_prior_year`.

Value sources: 124 months read from their own report, 16 months from the next year's report (mislinked or duplicated files on the LAWA page), 1 month derived. September 2025 is a scanned PDF with no text layer; its values are the official 2025 annual total minus the other 11 months (`value_source=annual_residual`), which is exact for annual consistency.

## Known limitations

- These are **airport-wide FAA tower counts**, not FBO demand and not parking occupancy. An arrival and a departure each count as one movement.
- FAA categories are operational, not aircraft types. "Air taxi" covers Part 135 on-demand charter (much of the business-jet traffic) but also small commuter operators; "general aviation" mixes private business jets with piston aircraft. No split by aircraft size is available.
- **Structural break.** GA plus air taxi movements fell from about 265 per day in 2015 to about 100 per day in 2024 and 2025. Air taxi alone went from 61,652 (2015) to 22,041 (2025). The 2016 to 2019 level is not comparable to the post-COVID level, so trend models should not blend them without a level shift.
- August 2016 shows 10,912 air taxi movements, about twice the neighbouring months. The value is consistent with the official 2016 annual total, so it is in the source data; treat it as an outlier, not a parsing error.
- Monthly granularity cannot isolate a one-week event (see below).
- The TCOM movement figures should equal FAA OPSNET tower counts for LAX. Cross-check against Marvin's OPSNET pull when it lands; any difference must be documented, not averaged.

## Findings useful to the team

1. **Current level (2025):** 22,041 air taxi and 12,234 GA movements at LAX, about 94 GA plus air taxi movements per day, roughly 47 arrivals per day airport-wide.
2. **February seasonality:** across non-COVID years, February GA plus air taxi traffic per day runs at 1.08 times the annual daily mean (standard deviation 0.09). January (1.10) and February are the busiest months; June, July, September and December the quietest.
3. **Super Bowl LVI (13 Feb 2022, SoFi):** February 2022 per-day traffic at LAX was 6.8 % above the January and March 2022 average. Ordinary Februaries in other years range from -6.7 % to +11.1 % on the same measure, so **the event is not distinguishable in LAX monthly data.** This does not mean there was no surge: a one-week surge is diluted in a monthly count, and business jets for the 2022 game largely used other fields. Step 4 needs daily data or other airports (VNY, HHR, LGB, BUR, SMO).

## BTS (Bureau of Transportation Statistics)

BTS describes the T-100 Air Carrier Statistics database as "domestic and international airline market and segment data" that "certificated U.S. air carriers report monthly ... using Form T-100" (B1). Private general aviation flights and on-demand Part 135 charter, which make up most FBO traffic, do not file T-100. BTS is therefore **not usable for GA or air-taxi demand at our FBO** and is not cited as a data source for it. The TranStats data portal itself was under maintenance on the retrieval date; only the database description page was reachable.
