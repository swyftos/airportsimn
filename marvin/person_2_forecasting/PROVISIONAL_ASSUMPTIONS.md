# Provisional monthly-to-daily FBO conversion — Alan review requested

Status: provisional assumptions, not approved by Alan. These outputs are not observed FBO traffic or validated event forecasts.

## Original source, kept separate

The converter reads alan/elia_output/data/processed/lax_monthly_movements.csv unchanged. It uses 2016–2019 and 2023–2025 (84 months), excluding 2020–2022 from the ordinary baseline. Monthly GA and air-taxi counts are airport-wide operations. Air carrier and military operations are not included in the FBO proxy. All source URLs and the source value_source marker are carried into each converted row. The LAWA source documentation flags 2018 discrepancies and annual-residual derivation for September 2025. No monthly count is corrected or silently averaged with another source.

## Assumptions for review

| Driver | Provisional value | Meaning and limitation |
| --- | --- | --- |
| Effective FBO capture share | 25% | A fictional operator captures one quarter of the airport's combined GA + air-taxi movements. This combines eligibility and market share; it is not a measured share. GA includes non-jets and air taxi includes commuter activity. |
| Arrival/departure split | 50% / 50% | Balanced monthly directional demand; no actual directional observations. |
| Aircraft mix | light_jet 47%, midsize_jet 33%, large_jet 20% | Planning allocation to supported model categories, aligned with P3's initial-inventory mix. These are not FAA aircraft-type observations. |
| Daily allocation | Equal share per calendar day | Monthly count divided by actual days in that month, including leap days. No invented weekday or within-month trend. |
| Precision | Fractional counts retained | No daily rounding; category/direction/day totals recover the assumed monthly FBO share. |
| Historical provenance | estimated on every row | Source monthly airport observations do not make derived FBO counts observed. |
| Reservation provenance | synthetic | Existing illustrative reservations retained from demo_planning_inputs.csv. They are not actual bookings. |
| Reservation show rate | 90% | Unvalidated assumption retained from existing planning inputs. |

For every date/category:
arrivals = (monthly_air_taxi + monthly_GA) × 0.25 / days_in_month × category_share × 0.50.
Departures use the remaining 0.50. The model applies reservations as an overlapping floor, not additional demand.

## Event multipliers — explicit assumptions, unchanged from the demo

| Date | Arrivals Low | Medium | High | Departures Low | Medium | High |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2027-02-11 | 1.125 | 1.25 | 1.40 | 1.00 | 1.00 | 1.00 |
| 2027-02-12 | 1.30 | 1.60 | 1.96 | 1.00 | 1.00 | 1.00 |
| 2027-02-13 | 1.60 | 2.20 | 2.92 | 1.05 | 1.10 | 1.16 |
| 2027-02-14 | 1.40 | 1.80 | 2.28 | 1.15 | 1.30 | 1.48 |
| 2027-02-15 | 1.05 | 1.10 | 1.16 | 1.75 | 2.50 | 3.40 |
| 2027-02-16 | 1.00 | 1.00 | 1.00 | 1.40 | 1.80 | 2.28 |
| 2027-02-17 | 1.00 | 1.00 | 1.00 | 1.10 | 1.20 | 1.32 |

All event indicators equal 1. Low uses half the Medium incremental uplift; High uses 1.6 times that uplift. The monthly February 2022 comparison does not validate these multipliers. Scenarios are conditional assumptions, not probabilities.

## Interpretation and model limitations

The existing seasonal shrinkage model and chronological 60/20/20 evaluation remain unchanged. Its metrics compare forecasts with allocated estimates, never observed FBO outcomes. Smooth daily allocations suppress real daily variability, so residual-based bands can understate operational uncertainty. The nominal 90% baseline coverage refers to the model calibration target; event-week ranges remain unvalidated planning ranges.

The source documents a structural level change between pre-COVID and recent years. The frozen model trains on the earliest 60% of usable dates; later periods evaluate it, not refit it. This provisional run can therefore reflect outdated traffic levels. Do not claim it is the preferred production forecast or hide poor holdout results. Alan should review the training-period suitability along with capture share and aircraft allocation.

Elia's existing simulation is rerun on this exact uncertainty file. Its algorithm treats expected counts as lognormal medians and maps supplied ranges to assumed 5th/95th percentiles. That is an additional simulation assumption, not validation of P2 coverage or proof that expected values are true medians. Capacity, opening inventory, fuel, staffing and cost assumptions remain P3's existing estimates/synthetic settings. Results remain conditional simulations, not observed operational benefits.

## Reproduce and release together

From the repository root, using Python with numpy and pandas installed:

    python marvin/person_2_forecasting/run_provisional.py

The runner converts inputs, runs the existing P2 model, then runs P3 standard, ordinary-week, delayed-departure and carryover simulations on those exact outputs. The read-only team pipeline verifier must pass before the runner stamps the release. It verifies current output columns and metadata keys, validates category-range agreement, and writes a separate release_manifest.json with SHA-256 hashes covering 20 files, including all four parking comparison artifacts. The refreshed manifest supersedes the 16-file manifest from the supplied ZIP. That sidecar does not change any existing producer schema. Both producer output sets must ship in the same commit. The runner should be used on an isolated branch, not directly on a dashboard's live data directory.

Alan: please review the 25% effective FBO share, 50/50 split, 47/33/20 mix, uniform daily allocation, source caveats, and historical training window. Until reviewed, retain the provisional/estimated labels.

