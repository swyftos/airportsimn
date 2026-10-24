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

The 12 monthly values add up **exactly** to LAWA's official annual totals for air taxi, general aviation and total movements in 10 of 11 years (2015 to 2017, 2019 to 2025). The exception is 2018, where the gap is 369 air taxi, 184 GA and 1,560 total movements (0.2 % of the total). The FAA OPSNET cross-check (below) explains it exactly: LAWA's September and October 2018 reports carry preliminary values, and OPSNET's revised figures for those two months are higher by 256 + 113 = 369 air taxi, 137 + 47 = 184 GA and 1,169 + 391 = 1,560 total movements. Use OPSNET for September and October 2018. Separately, the LAWA page links the February 2018 report in place of March and April 2018; those two months come from the March and April 2019 reports and match OPSNET.

Value sources: 124 months read from their own report, 15 months from the next year's report (mislinked or duplicated files on the LAWA page), 1 month derived. September 2025 is a scanned PDF with no text layer; its values are the official 2025 annual total minus the other 11 months (`value_source=annual_residual`), which is exact for annual consistency.

## Known limitations

- These are **airport-wide FAA tower counts**, not FBO demand and not parking occupancy. An arrival and a departure each count as one movement.
- FAA categories are operational, not aircraft types. "Air taxi" covers Part 135 on-demand charter (much of the business-jet traffic) but also small commuter operators; "general aviation" mixes private business jets with piston aircraft. No split by aircraft size is available.
- **Structural break.** GA plus air taxi movements fell from about 265 per day in 2015 to about 100 per day in 2024 and 2025. Air taxi alone went from 61,652 (2015) to 22,041 (2025). The 2016 to 2019 level is not comparable to the post-COVID level, so trend models should not blend them without a level shift.
- August 2016 shows 10,912 air taxi movements, about twice the neighbouring months. The value is consistent with the official 2016 annual total, so it is in the source data; treat it as an outlier, not a parsing error.
- Monthly granularity cannot isolate a one-week event (see below).
- The TCOM movement figures equal FAA OPSNET tower counts for 123 of 132 months (see the OPSNET section).

## Findings useful to the team

1. **Current level (2025):** 22,041 air taxi and 12,234 GA movements at LAX, about 94 GA plus air taxi movements per day, roughly 47 arrivals per day airport-wide.
2. **February seasonality:** across non-COVID years, February GA plus air taxi traffic per day runs at 1.08 times the annual daily mean (standard deviation 0.09). January (1.10) and February are the busiest months; June, July, September and December the quietest.
3. **Super Bowl LVI (13 Feb 2022, SoFi):** February 2022 per-day traffic at LAX was 6.8 % above the January and March 2022 average. Ordinary Februaries in other years range from -6.7 % to +11.1 % on the same measure, so **the event is not distinguishable in LAX monthly data.** This does not mean there was no surge: a one-week surge is diluted in a monthly count, and business jets for the 2022 game largely used other fields. Step 4 needs daily data or other airports (VNY, HHR, LGB, BUR, SMO).

## BTS (Bureau of Transportation Statistics)

BTS describes the T-100 Air Carrier Statistics database as "domestic and international airline market and segment data" that "certificated U.S. air carriers report monthly ... using Form T-100" (B1). Private general aviation flights and on-demand Part 135 charter, which make up most FBO traffic, do not file T-100. BTS is therefore **not usable for GA or air-taxi demand at our FBO** and is not cited as a data source for it. The TranStats data portal itself was under maintenance on the retrieval date; only the database description page was reachable.

## FAA ATADS/OPSNET (Marvin's Step 2 piece, pulled by Elia)

| # | Source | URL | What was pulled | Classification | Confidence |
|---|---|---|---|---|---|
| F1 | FAA Air Traffic Activity Data System (ATADS), OPSNET airport operations, standard report | https://aspm.faa.gov/opsnet/sys/Airport.asp | LAX monthly tower operations 2015-01 to 2025-12 by category (itinerant air carrier, air taxi, GA, military; local civil and military). Daily operations at LAX, VNY, BUR, HHR, LGB, SMO for 30 Jan to 26 Feb of 2019, 2022, 2023, 2024 | verified_public | High |

Reproduce with `python alan/elia_output/scripts/fetch_opsnet.py` (the public form is posted the way the web page does it), then `python alan/elia_output/scripts/analyze_superbowl_lvi.py`.

Outputs in `alan/elia_output/data/processed/`: `opsnet_lax_monthly.csv`, `opsnet_daily_superbowl.csv`, `opsnet_vs_lawa_crosscheck.csv`, `superbowl_lvi_surge.csv`, `superbowl_lvi_daily_profile.csv`.

**Cross-check with LAWA.** 123 of 132 months are identical for air taxi, GA and total. The differences are September and October 2018 (LAWA preliminary, explained above), a constant gap of about 200 total movements per month from August 2015 to January 2016 with air taxi and GA within 14 movements, and 47 total movements in August 2025. OPSNET reports zero local GA operations at LAX, so GA there is itinerant traffic only.

**Super Bowl LVI signal (13 Feb 2022).** Method: event window Thursday to Monday around the game, each day compared with the median of the same weekday in the rest of the four-week window, and the 2022 ratio compared with control years 2019, 2023, 2024 aligned on the second Sunday of February. Air taxi operations are used as the business-jet proxy because they fly under instrument rules and are less sensitive to weather than piston GA; the control windows of 2019 and 2024 contain storm days that depress GA traffic.

- Six airports together: air taxi operations ran 17 % above the same-weekday baseline during the 2022 event window, against 8 % in control years, so an excess of about **+8 %** over five days.
- LAX alone: +15 % excess. BUR +18 %, HHR +14 %, LGB +118 % (small base), VNY -10 %, SMO -42 %.
- Daily profile, all six airports: +25 % on Friday, +6 % on Saturday, +11 % on game day, **+33 % on Monday** (departure wave).

Limits: one event, during the post-COVID recovery; tower operations count takeoffs and landings, not parked aircraft; air taxi includes some commuter flights; no split by aircraft size. This is a measured order of magnitude for event calibration, far below the "two to three times normal" business-jet benchmark reported for the Bay Area in 2026, which counts business jets only.

### LAX daily series 2015 to 2025

`python alan/elia_output/scripts/fetch_opsnet.py lax-daily`, then `python alan/elia_output/scripts/analyze_lax_daily.py`.

- `opsnet_lax_daily.csv`: 4,018 days from 2015-01-01 to 2025-12-31, no gaps, same categories as the monthly file, 2020 to 2022 flagged `excluded_covid`. Classification `verified_public`.
- `opsnet_lax_daily_check.csv`: the daily values add up exactly to the OPSNET monthly totals in all 132 months.
- `opsnet_lax_weekday_profile.csv`: weekday index of GA plus air-taxi operations, each day divided by its month's mean.

| Window | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|---|---|---|---|---|---|---|---|
| 2023 to 2025 | 1.04 | 0.89 | 0.99 | 1.09 | 1.07 | 0.81 | 1.11 |
| 2016 to 2019 | 1.04 | 1.02 | 1.05 | 1.09 | 1.04 | 0.80 | 0.96 |

Use for the team: these are observed airport-wide daily counts, so they can replace the illustrative weekday multipliers in `alan/assumptions.csv` (which put Tuesday and Wednesday at 1.12 and Sunday at 0.95) and the equal-share daily allocation in P2's provisional history. They also allow a daily backtest at airport scope, which is the only accuracy figure the team can present as measured. Daily GA plus air-taxi operations over 2023 to 2025 average 93 with a standard deviation of 22 (range 7 to 214), which is the day-to-day noise a forecast has to beat. FBO-level counts still need the agreed capture share, direction split and category mix, which remain assumptions.
