# Provisional forecast assumptions — FAA ATADS/OPSNET update

This release fixes the training window and replaces the earlier illustrative event multipliers with scenarios anchored to FAA ATADS/OPSNET evidence. It is still an estimated fictional-FBO scenario model, not a validated forecast of observed FBO demand.

## Sources and original data

The ordinary input uses the unchanged LAWA monthly airport series in alan/elia_output/data/processed/lax_monthly_movements.csv, restricted to 2023–2025 (36 months, 1,096 days). Original monthly records remain separate. Each derived row is estimated and retains its source marker. September 2025 is an annual-residual value. The FAA cross-check now explains the 2018 gap as preliminary September/October LAWA values; those years are outside this run.

Event evidence: **FAA ATADS/OPSNET**, airport tower operations, retrieved 2026-10-23:
https://aspm.faa.gov/opsnet/sys/Airport.asp

Repository evidence:
- alan/elia_output/data_sources_lawa_bts.md, section FAA ATADS/OPSNET.
- alan/elia_output/data/processed/superbowl_lvi_surge.csv.
- alan/elia_output/data/processed/superbowl_lvi_daily_profile.csv.
- alan/elia_output/data/processed/opsnet_daily_superbowl.csv.
- alan/elia_output/scripts/analyze_superbowl_lvi.py.

PR #17 delivered these files; it is not the underlying source.

## Baseline allocation

| Driver | Value | Meaning |
| --- | --- | --- |
| FBO capture | 25% of GA + Air Taxi | Provisional effective share; not observed |
| Direction split | 50% arrivals / 50% departures | Assumed |
| Ordinary category mix | 47% light, 33% midsize, 20% large | Assumed; retained across scenarios |
| Daily allocation | Uniform across actual calendar days | Includes leap days; fractional counts retained |
| Provenance | estimated on every history row | Public monthly observations do not make derived FBO counts observed |
| Reservations | Zero synthetic placeholders; show rate zero | No booking data supplied; demo bookings cannot override evidence-based multipliers |

Alan accepted the share, direction split and uniform allocation for provisional use in issue #10. His separate baseline uses 20% capture. That discrepancy is still explicit and requires team reconciliation. His requested larger-aircraft event mix remains pending: FAA operational categories do not identify aircraft size, and no size-specific uplift is invented here.

## What the FAA analysis measures

The event window is Thursday–Monday around February 13, 2022. Each day's baseline is the median of the same weekday outside the event window. The five-day ratio is divided by the mean corresponding ratio in control years 2019, 2023 and 2024.

The rounded source results show:
- Six-airport control-adjusted excess: 8.5%.
- LAX control-adjusted excess: 15.5%.
- Regional Monday raw same-weekday ratio: 1.330.

The Monday 33% increase is **total air-taxi operations**, including takeoffs and landings. It is not a measured departures-only uplift and is not control-adjusted in the daily profile file. It cannot be combined with the five-day adjusted percentages as if all were the same statistic.

## Reproducible event mapping

The central (Medium) case uses the positive regional daily excess shape for Thursday–Monday and scales it so that baseline-weighted five-day **forecast total movements** increase by 15.5%, matching the rounded LAX aggregate excess. The regional shape is computed from air_taxi / baseline using source counts rather than rounded ratios.

For each event day i:

    shape_i = max(0, regional_operations_i / regional_baseline_i - 1)
    scale = 0.155 * sum(forecast_baseline_i) / sum(forecast_baseline_i * shape_i)
    Medium_multiplier_i = 1 + scale * shape_i
    Low_multiplier_i = 1
    High_multiplier_i = 1 + 2 * (Medium_multiplier_i - 1)

Both directions receive the same multiplier because no observed directional split exists. This does not model a measured arrival-then-departure wave. Tuesday/Wednesday remain at baseline; this is a boundary assumption, not evidence of no event effect.

Low is a no-excess sensitivity case; High doubles the central excess. They are assumptions, not confidence bounds, observed extremes or event probabilities. The 8.5% regional excess is context, not substituted for the 15.5% LAX anchor. The 33% raw regional Monday result informs the shape, not a forced 1.33 departure multiplier.

Applying this air-taxi event signal to the GA+air-taxi fictional-FBO baseline is an explicit transfer assumption. A single recovery-era event cannot establish a causal 2027 forecast. Current per-day multipliers and evidence details are generated in provisional_inputs/event_evidence.json and planning_inputs.csv.

## Evaluation and uncertainty

The 2023–2025 chronological split has 657 training, 219 calibration and 220 test dates per category. Training ends 2024-10-18; calibration starts 2024-10-19; testing starts 2025-05-26. The calibrated model is frozen.

MAE, benchmark improvement and interval coverage against uniformly allocated daily rows are **allocation diagnostics only**. They do not establish real daily predictive accuracy, weekday patterns, event prediction accuracy or observed FBO performance. They must not be presented as such.

Nominal baseline coverage remains 90%; empirical coverage on the estimated holdout is approximately 46.82%. The residual bands are inadequately calibrated even against those allocations. Event ranges are assumption-scaled planning ranges with unvalidated coverage. Uniform allocation omits real variability. Real monthly holdout validation at airport scope and independent observed daily/FBO validation remain next work.

## Matching parking outputs

The current main version of Elia's optimizer is retained, including ordinary parking, carryover and the 24-hour departure-delay variant. All are regenerated from this exact P2 release. Opening inventory is recomputed as first-day baseline arrivals times the existing 1.1-day dwell assumption (13.0 aircraft, rather than the old 22.2); ramp capacity and other operating assumptions remain unchanged. Parking simulations treat points as medians and supplied ranges as assumed percentiles; these extra assumptions do not validate P2 coverage. Balanced direction multipliers may understate event accumulation; delayed-departure results provide a separate sensitivity case, not observed dwell evidence.

## Release and review

Existing producer filenames, CSV column order and metadata keys are preserved. excluded_years remains the COVID exclusion list [2020, 2021, 2022] for compatibility; the separately enforced training bounds are 2023-01-01 through 2025-12-31, stated in run_metadata.json's caution and this document.

nazar/ is unchanged. The release manifest retains exactly its existing 20-file contract. Additional event sources and conversion code are hashed separately in event_evidence_manifest.json, linked to the release run ID. Nazar’s current dashboard does not validate that extra sidecar.

Run from the repository root, using Python with numpy and pandas:

    python marvin/person_2_forecasting/run_provisional.py

Alan: review the event mapping, direction/size limitations, 25% share and sensitivity choices. Nazar: existing output formats remain stable; display allocation diagnostics as non-observed and event ranges as unvalidated. Do not interpret passing integration tests as model validation.

