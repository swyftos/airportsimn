# Public calibration checks for Person 2

These files test the forecast's weakest assumptions using observed **airport operations**. They do not measure the fictional FBO's bookings, selected Part 91 fleets, or the eligible subset of Part 135. No file here replaces `demand_predictions.csv`, `uncertainty_results.csv`, or a dashboard input. One operation is one takeoff or landing. `general_aviation` and `air_taxi` are FAA tower categories; Part 121 air carrier and military counts are excluded from every extract.

## Sources and reproducibility

- `opsnet_super_bowl_analog_daily.csv`: 29 days around the second Sunday of February in 2019, 2023, 2024, and 2025 for airport groups in the [FAA LVII Phoenix release](https://www.faa.gov/newsroom/ready-kickoff-what-ga-pilots-need-know-about-super-bowl-lvii), [FAA LVIII Las Vegas notice](https://www.faa.gov/air_traffic/publications/domesticnotices/dom24001_sp.html), and [FAA LIX New Orleans notice](https://www.faa.gov/air_traffic/publications/domesticnotices/dom24038_sp.html). The 2019 date is a calendar-matched reference; [Super Bowl LIII](https://www.faa.gov/newsroom/atlanta-no-drone-zone-during-super-bowl-liii) itself was on February 3, not February 10. Rows come from [FAA OPSNET/ATADS](https://www.aspm.faa.gov/opsnet/sys/Airport.asp), using the repository's `alan/elia_output/scripts/fetch_opsnet.py` parser. Each row carries its retrieval time and source.
- `opsnet_lax_feb2026.csv`: all 28 LAX daily GA and air taxi rows for February 2026 from the same FAA source. Its sums, 1,072 GA and 1,892 air taxi operations, match [LAWA's February 2026 monthly report](https://www.lawa.org/sites/lawa/files/2026-03/Tcom%200226.pdf), already captured in `alan/elia_output/data/processed/lax_monthly_movements.csv`. The first 15 days sum to 556 GA operations, matching the separately collected 2026 weather review.
- `fetch_public_counts.py` refreshes the two observed extracts; it requires access to FAA OPSNET. `analyze_public_proxies.py` regenerates the five derived CSVs without network access. `validate_evidence.py` checks dates, duplicate keys, category counts, comparison coverage, and the independent LAWA monthly reconciliation. Run both local scripts from the repository root with `python marvin/person_2_forecasting/calibration_evidence/<script>.py`.

## Super Bowl analog checks

For each host airport group and comparison year, the code sums Thursday through Monday operations around the second Sunday of February. That is the actual game weekend in 2023–2025 and a calendar-matched reference weekend in 2019. It divides that total by a matched-weekday baseline: the median for each airport and weekday outside the five-day window, but within the surrounding 29 days. The event-year ratio is divided by the mean of the **recent** non-host-year ratios (2023–2025). `super_bowl_analog_year_ratios.csv` retains actual operations and baseline counts; `super_bowl_analog_summary.csv` includes both recent-only and a 2019-plus-recent control comparison. This is an exploratory difference-in-ratios calculation, not an estimate of selected-fleet bookings or a causal Super Bowl effect.

| Host event | Complete airport coverage | GA excess vs recent controls | Air taxi excess vs recent controls |
| --- | --- | ---: | ---: |
| LVII 2023 Phoenix | 8 of 8 listed | -24.47% | -17.85% |
| LVIII 2024 Las Vegas | 3 of 4 listed | -10.20% | +17.45% |
| LIX 2025 New Orleans | 2 of 5 listed | -6.45% | +277.98% |

See `super_bowl_analog_airport_coverage.csv`: BVU, ASD, and APS have no returned rows for any queried year; HDC has data only in 2023 and 2025. The smaller New Orleans group omits listed reliever airports, so its large air taxi ratio must **not** be transferred to LAX. GA includes ordinary training and other non-FBO activity; air taxi includes Part 135 activity outside the selected private fleets. Host airports differ in geography, capacity, reporting coverage, and normal traffic. Other events, weather, and shifts between airports are not controlled. The older LVI LAX +15.5% air taxi result in `alan/elia_output/data/processed/superbowl_lvi_surge.csv` remains a **LAX airport-category** estimate, not FBO calibration. The three new analogs show why one portable multiplier cannot be justified from public airport counts alone.

## Presidents' Day checks

`presidents_day_airport_checks.csv` compares the third Monday of February with the median of the other February Mondays in the **same year**, separately for GA and air taxi. The recent LAX GA ratios are 1.0698 (2023), 1.0571 (2024), 1.3514 (2025), and 1.4082 (2026). Their median is 1.211, but four descriptive holiday dates cannot isolate a holiday effect from weather, normal year-to-year level changes, or unrelated events. The 2015–2019 and 2020–2022 rows are separate reference regimes, not additional ordinary-training samples.

`presidents_day_frozen_model_check.csv` reconstructs the 60% chronological training split and smoothed month/weekday ordinary baseline used by the current provisional GA-only model. The two in-training holidays imply 1.0525, matching its roughly +5.3% point estimate. Observed-to-frozen-ordinary ratios are 1.2681 in held-out 2025 and 1.7500 in 2026. The 2026 number also reflects any forecast level drift since training ended in October 2024; it is **not** a measured +75% holiday lift. Keep the holiday adjustment as a weak, explicit sensitivity until more comparable observations and a rolling ordinary baseline are available. These checks do not replace the model's existing uncertainty range.

## Aircraft mix and FBO conversion still need operational data

The [FAA CountOps custom report](https://www.aspm.faa.gov/aspmhelp/index/CountOps_Reports_Manual.html) can group LAX operations by category, equipment, operation type, and ATC weight class. A future **aggregate** LAX extract filtered to GA and air taxi, with Part 121 removed, could improve the airport-wide aircraft-type proxy. No such extract was available for this update. Its ATC weight classes also do not equal the project's light/midsize/large parking footprint bins. The inherited 47/33/20 mix remains an assumption. The [FAA national GA and Part 135 survey](https://www.faa.gov/data_research/aviation_data_statistics/general_aviation/cy2024) cannot identify the LAX or FBO mix.

The [LAWA aviation activity analysis](https://www.lawa.org/lawa-our-lax/studies-and-reports/aviation-activity-analysis) reports airport-wide activity, not one FBO's visits. Leased area is not traffic share. No public source found here measures a comparable FBO's booking-to-operation conversion. `FBO_AGGREGATE_DATA_REQUEST.md` specifies the smallest useful anonymized extract. Until it is available, keep eligibility, FBO capture, direction split, and aircraft footprint explicit and low-confidence. Do not treat all air taxi or all GA operations as selected-fleet demand.

## Integration decision

These observed checks narrow the holiday and event evidence gaps but do not validate a new demand multiplier. They deliberately leave the shared forecast, parking model, and Nazar's release inputs unchanged. Any future calibration should use the selected-fleet/FBO denominator and be reviewed by the forecast, historical-data, parking, and dashboard owners together.
