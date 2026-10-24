# FAA ATADS/OPSNET event update — review package

Based on main snapshot 3f8aa2bbd348fcef7c0e52200352adbcf9bc7263, inspected October 23, 2026. PR #17 is merged. The earlier provisional P2 release and newer P3/dashboard work are now on main, but the downloaded model still blended pre-COVID years. This package applies the post-COVID correction and FAA event mapping on top of that shared version.

## Changes

- Training, calibration and testing restricted to 2023–2025; 3,288 estimated category rows.
- Event source cited as FAA ATADS/OPSNET, not “source #17”.
- Medium scenario uses the FAA-derived LAX five-day adjusted excess of 15.5%.
- Regional daily timing is normalized to that LAX aggregate, weighted by forecast baseline movements.
- Low has no excess; High doubles the Medium excess. Both are sensitivity assumptions.
- Zero synthetic reservation placeholders disable demo booking floors.
- Both directions use the same multiplier: source operations include takeoffs and landings. *(Superseded by the direction update below.)*
- Opening inventory refreshed to 13.0 aircraft using the existing 1.1-day dwell assumption.
- All standard, ordinary, delay and carryover P3 outputs regenerated together.
- Existing producer columns, filenames, metadata keys and exact 20-file dashboard manifest retained.
- Additional evidence hashes in a separate event_evidence_manifest.json linked to the release run ID.
- nazar/ and original data files unchanged.

## Medium event multipliers

These are derived scenario values, not observed daily LAX/FBO ratios.

| Date | Multiplier, each direction |
| --- | ---: |
| 2027-02-11 | 1.084872 |
| 2027-02-12 | 1.230809 |
| 2027-02-13 | 1.059200 |
| 2027-02-14 | 1.098559 |
| 2027-02-15 | 1.301283 |
| 2027-02-16 | 1.000000 |
| 2027-02-17 | 1.000000 |

The five-day FAA findings distinguish 8.5% control-adjusted regional excess, 15.5% control-adjusted LAX excess and a 33% raw regional Monday same-weekday increase. The latter counts all air-taxi operations; it is not a measured departure-only increase. Mapping regional timing and air-taxi behavior to a fictional GA+air-taxi FBO remains an assumption.

## Interpretation

Ordinary arrivals are approximately 11.8 per day. Allocation-based MAE and coverage are diagnostics only, not real daily predictive accuracy. Test coverage remains approximately 46.82% against the nominal 90% target; event coverage is unvalidated.

Current conditional simulation peak P50 parking demand is 27.7 / 30.2 / 33.1 space units for Low / Medium / High. The 24-hour-delay variant yields 45.0 / 50.7 / 57.2. These are scenario results, not validated capacity requirements. Balanced arrivals/departures do not represent a measured event accumulation wave.

## Verification

11 forecasting tests and 9 parking tests passed. The shared pipeline verifier confirmed that all standard, ordinary, delayed and carryover outputs reproduce from the current inputs. Both manifests were checked against saved files.

The full dashboard suite was attempted: 42 of 57 tests passed; 13 server tests were blocked by sandbox socket permissions and two tests depended on old output values:
- NativeAdapterTests.test_unknown_actions_rejected indexes the first Medium action, but the new Medium case has no actions.
- ParkingVariantTests.test_extension_change_invalidates_reviews changes a carryover quantile in a way that makes this release's quantiles unordered.

These need fixture changes by Nazar; nazar/ was not edited. The current producer data loads through the native adapter and exact manifest validation. No full browser/server test is claimed.

## Next steps

1. Alan: review the regional-to-LAX/FBO transfer, balanced direction assumption, sensitivity scales and the 25% versus 20% share discrepancy.
2. Team: provide direction/size evidence before asserting a departure wave or larger-aircraft mix. Ordinary 47/33/20 mix remains provisional.
3. Nazar: adjust the two data-dependent test fixtures and run server tests in the normal environment. Formats are unchanged.
4. Marvin: develop monthly-scale and independent observed-daily validation; do not headline allocation-based MAE as accuracy.
5. Apply these feature changes to a proper branch, review and publish one matching release.

## Delivery

The ZIP contains changed files in repository-relative paths plus a feature patch against the main snapshot above. The local review copy has archive-based Git history; do not push that history. This update is packaged locally and has not been pushed or merged. It supersedes the older local provisional and post-COVID packages.

Detailed source mapping and assumptions are in marvin/person_2_forecasting/PROVISIONAL_ASSUMPTIONS.md. Reproduce from repository root:

    python marvin/person_2_forecasting/run_provisional.py

## Direction update (Elia, follow-up PR)

Applying one multiplier to both directions on the same day means every extra aircraft arrives and leaves the same day, so the event never accumulates on the ramp (Medium parking peak 30.2 su against 27.7 ordinary). The FAA five-day excess is now split by aircraft conservation: extra arrivals = extra departures = half the excess operations, arrivals on Thursday to Saturday plus half of game day, departures on the other half of game day plus Monday. The five-day operations excess is unchanged (15.5 % in Medium).

| Date | Medium arrivals | Medium departures |
| --- | ---: | ---: |
| 2027-02-11 | 1.1551 | 1.0000 |
| 2027-02-12 | 1.4219 | 1.0000 |
| 2027-02-13 | 1.1082 | 1.0000 |
| 2027-02-14 | 1.0901 | 1.1088 |
| 2027-02-15 | 1.0000 | 1.6653 |
| 2027-02-16 | 1.0000 | 1.0000 |
| 2027-02-17 | 1.0000 | 1.0000 |

Result: P50 parking peaks at 27.7 / 38.9 / 51.4 su for Low / Medium / High on game day, then falls on Monday as event aircraft leave. The 24-hour-delay variant peaks at 45.0 / 56.4 / 69.0 su. No scenario exceeds the 75 su ramp at P50. The timing is an assumption; the FAA table has no directional split.
