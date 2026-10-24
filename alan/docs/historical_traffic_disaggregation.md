# Step 3a: Alan's airport-wide daily intermediate

This extends Alan's Step 3 pipeline from PR #8 while preserving its `historical_traffic_interim.csv` filename and six-column handoff. It restricts the output to the agreed project years, increases fractional precision, carries monthly source provenance and adds validation. Its daily values are estimates derived from monthly counts. Alan should review the allocation assumptions before downstream forecasting.

## Run and handoff

From the repository root, using Python 3.9+ with no external packages:

```sh
python3 alan/scripts/build_historical_traffic.py
python3 -m unittest discover -s alan/tests -v
```

The script also works from another directory. Optional `--input` and `--output` paths override its defaults.

- Input: `alan/elia_output/data/processed/lax_monthly_movements.csv`.
- Daily handoff: `alan/data/processed/historical_traffic_interim.csv`.
- Reconciliation and hashes: `alan/data/processed/historical_traffic_interim.validation.json`.

Output columns, in order: `date, arrivals, departures, excluded_covid, data_class, source`. Dates use ISO calendar dates, flags use `True`/`False`, and every `data_class` is `estimated`. There is deliberately no `scope=fbo` or `aircraft_category` at this stage. The handoff documentation and row provenance identify airport-wide counts.

Nazar should read this intermediate, apply a separately documented FBO share, add `scope=fbo`, and append his provenance to `source`. Marvin should then apply an ordinary aircraft mix and export his model's exact contract. Retain the exclusion flag in intermediate/audit data even if the final model CSV omits it; 2020–2022 must remain excluded from ordinary training by date. Use `large_jet` rather than introducing `heavy_jet` unless the forecast and dashboard consumers are updated together.

## Allocation assumptions

For each month in **2016–2025**, let `M = air_taxi + general_aviation` and `D = number of calendar days`:

```text
daily total movements = M / D
daily arrivals        = (M / D) × 0.5
daily departures      = (M / D) × 0.5
```

Air carrier, military and the all-category total are not used. A movement is a takeoff or landing, so splitting the combined total in half avoids counting it twice. The **50/50 split is an assumption**, chosen because monthly data does not provide direction. It does not establish actual balanced daily flows, length of stay, opening inventory or parking occupancy.

**Uniform calendar-day allocation** is the v1 assumption: each day of a month has the same estimated flow. Day-of-week weighting is a possible refinement only with supporting evidence. This preserves monthly totals and monthly seasonality but supplies no observed within-month pattern. Evaluating daily forecasts against these rows measures agreement with the allocation assumptions, not observed daily FBO accuracy. Artificially smooth rows may make holdout scores look optimistic.

Fractional estimates are retained to 12 decimal places using decimal arithmetic. No integer rounding or last-day remainder creates a false traffic spike. Every month's summed arrivals plus departures reconciles to the supplied monthly GA + air-taxi count within **0.000000001 movements**. The JSON report records the maximum error, monthly controls and SHA-256 hashes of the exact input and output.

## Coverage and exclusions

The input contains 140 monthly records from 2015 through August 2026. The project window selects 120 months, producing 3,653 daily rows. The 20 out-of-window rows are explicitly counted in the report. Missing months, duplicates, invalid/negative/noninteger counts, missing source provenance and contradictory exclusion flags stop the build rather than being filled with zeroes. Valid zero counts remain zero.

All 1,096 dates in 2020–2022 are retained with `excluded_covid=True`. February 2022 has all 28 days, including Super Bowl LVI day, February 13. **These allocated February rows cannot reveal an event-week surge.** They are retained for completeness and as a pointer to the underlying month. Step 4 still needs independent daily/event evidence, and cannot treat this uniform allocation as observed event activity.

## Source and reliability

The input and its source URLs were already committed by Elia. This step does not retrieve new data or claim a new retrieval date. Elia's recorded retrieval date is **2026-10-23**; see [his source log](../elia_output/data_sources_lawa_bts.md) and [annual reconciliation](../elia_output/data/processed/validation_report.csv). Each daily source string retains the specific monthly URL, `value_source`, upstream classification, selected categories, allocation rule, days in month and both direction shares. Upstream `verified_public` provenance does not make the converted daily row observed.

Limitations inherited unchanged from that handoff:

- The 2018 monthly sum is 369 air-taxi and 184 GA movements below the official annual controls. March/April prior-year readings are retained as supplied. This conversion reconciles to the monthly input, not to revised annual totals; it does not silently distribute the difference.
- August 2016's high air-taxi value remains intact. Alan/Marvin should address it explicitly in analysis.
- September 2025 is an `annual_residual`, derived upstream from the annual total minus other months. That provenance stays attached to every allocated day.
- The pre/post-COVID change in traffic level must be considered in modeling. Retaining excluded years here does not authorize using them for ordinary trend training.
- GA and air taxi are operating categories, not aircraft sizes or a verified pool of FBO customers. FBO eligibility/share and aircraft mix are downstream assumptions.

Replace uniform allocation and the direction split with observed daily GA/air-taxi arrivals/departures, if available with consistent coverage and definitions. Preserve the monthly source and this v1 derivation for comparison rather than relabeling estimates as observed.
