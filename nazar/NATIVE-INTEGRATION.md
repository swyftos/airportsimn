# Current P2/P3 integration

The first dashboard contract was prepared against an empty repository. While work was underway, Persons 2 and 3 committed their modules. This adapter connects to those **existing** outputs, leaving every teammate’s folder unchanged. Use **Load current P2/P3 outputs**. The separate seven-file contract remains an optional future interface and the format for manual bundle import.

## Files read

| Producer | Native file | Use |
| --- | --- | --- |
| Marvin | `marvin/person_2_forecasting/demand_predictions.csv` | Wide category rows with arrival/departure point forecasts, baseline and event assumptions |
| Marvin | `marvin/person_2_forecasting/uncertainty_results.csv` | Category-specific event planning ranges; nominal 90% baseline coverage, unvalidated event coverage |
| Marvin | `marvin/person_2_forecasting/run_metadata.json` | Model configuration, exclusion policy and historical provenance |
| Marvin | `marvin/person_2_forecasting/evaluation_metrics.csv` | Six category/direction holdout evaluations with input provenance |
| Elia | `elia/resource_requirements.csv` | Parking P10/P50/P90, capacities, exceedance probabilities, staffing and fuel |
| Elia | `elia/scenario_recommendations.json` | Proposed actions, action costs, weekly preparation total, paired simulation impact and method |
| Elia | `elia/assumptions_p3.csv` | Space, staffing, fuel and cost assumptions |

The adapter reads fixed relative paths, requires a complete set, validates scenario/date/category combinations, reconciles P2 point estimates against uncertainty rows, checks parking quantile order and probability ranges, reconciles weekly action costs, and rejects actions without human approval. It keeps only specified aggregate fields in the display bundle. Producer prose still requires human review and must contain no identifying data.

No forecasts or simulations are re-run on load. Regenerate P2, then P3 against those P2 outputs, then refresh the dashboard. **The producers currently provide no common run ID or input hash, so the adapter cannot prove the files come from the same run.** Recommend adding `p2_input_hash` / `run_id` to P3’s metadata next. The dashboard hashes all loaded input files (seven base files plus four comparison files when present) to attach reviews to the exact loaded set, but that does not establish upstream coherence.

## Optional parking comparison release

The following four files are accepted only as a complete group:

| Key | Path | Use |
| --- | --- | --- |
| `p3_ordinary` | `elia/ordinary_week_parking.csv` | Seven ordinary daily peaks, in P3 space units |
| `p3_delay_resources` | `elia/resource_requirements_departure_delay_24h.csv` | 21 separately simulated delayed resource rows |
| `p3_delay_recommendations` | `elia/scenario_recommendations_departure_delay_24h.json` | Delayed actions, costs and impact for three scenarios |
| `p3_carryover` | `elia/parking_carryover.csv` | Ordinary plus three scenarios × two variants after Feb 17 |

With none present, the seven-file native mode remains supported. If any is present, all must validate. Missing/duplicate rows, mismatched ordinary flows/capacity, invalid quantiles, contradictory provenance or opening inventory fail loading. Partial or invalid refreshes keep the previously loaded dataset visible with an error. Structural validation does not prove numerical coherence; run the verifier below.

All eleven files contribute to the review version. Reviews remain scoped to scenario and variant; approving a standard proposal never approves its delayed counterpart. Exports contain the selected variant’s seven resource rows, impact, recommendations, matching reviews, the ordinary baseline and matching carryover. Sample/import contracts are unchanged.

## Verify before refreshing

```sh
python3 -m unittest discover -s nazar/tests -v
python3 nazar/scripts/verify_team_pipeline.py
```

The second command requires numpy/pandas and invokes Elia’s existing model in memory. It compares 21 standard resource rows and three scenario recommendations/impact distributions; when extensions are present it additionally compares 21 delayed resource rows, three delayed recommendation/impact results, seven ordinary parking rows and seven carryover rows, then prints the loaded dataset version and SHA-256 hashes. It fails on inconsistent outputs or changes during verification, without rewriting any teammate file. A successful result establishes reproducibility for that exact file set, not source reliability or model accuracy. This is a separate handoff check, not an automatic dashboard load gate.

The current native schema expects `light_jet`, `midsize_jet`, `large_jet`; Low/Medium/High; Feb 11–17, 2027; and 90% nominal baseline coverage because P3 interprets interval endpoints as 5th/95th percentiles. A schema or coverage change needs coordination with both consumers. Evaluation rows must carry the same historical provenance as demand; estimated/synthetic history requires `non_observed_demonstration`. Output generation time is explicitly unavailable.

## Exact interpretation

- Daily arrivals and departures are sums of P2 category **point estimates**. They can differ from P3’s medians of simulated totals; these are different quantities.
- Ordinary arrivals/departures use P2’s `baseline_arrivals` / `baseline_departures`, requiring it to agree across scenarios. It is a model comparison, not a measured ordinary-week count.
- Ordinary **parking** uses `parking_demand_su_p50` from P3’s ordinary simulation, with P10/P90 retained. Its baseline arrival/departure totals must match P2 within the producer’s one-decimal rounding tolerance, and normal capacity must match event runs. It does not read Alan’s aircraft-count `parking_units` as space units. If the four comparison files are absent, ordinary parking remains `null`.
- Parking chart and gap arithmetic use P3’s daily `parking_demand_su_p50` values. “Peak” means the maximum of those daily medians, not the median of each simulation’s whole-week maximum.
- P10–P90 is an **80% central model quantile range** for each daily parking peak. It is distinct from P2’s **90%** category event planning ranges. Neither establishes validated Super Bowl event coverage. A zero P50 gap would not imply zero risk.
- Daily capacity exceedance probability comes directly from P3. It is not an empirical probability established from observed Super Bowl outcomes.
- P2 category interval endpoints are never summed. Per-category ranges appear in selected-day details; an aggregate arrival interval remains unavailable.
- Cost is the supplied **weekly preparation action total**, reconciled with action costs. No fabricated daily cost allocation is used. It is not a quote, realized saving or full business P&L.
- Business impact uses P3’s paired weekly simulations: mean unaccommodated aircraft, mean delayed turns, mean total modeled cost and probability of any unaccommodated aircraft. Net-benefit median/P10/P90 and probability preparation pays off are supplied directly, never calculated by subtracting marginal quantiles. Negative benefits are retained. Mean net benefit must reconcile with the difference in mean costs within rounding tolerance. These are conditional model results, not measured savings or guaranteed improvements.
- Selected-day arrival details retain each category’s event multiplier, reservation floor, reservation provenance and assumption source.
- Staffing support shows the maximum proposed technician count over the three shifts; daily details retain morning/day/night counts. This includes P3’s staffing buffer, not unique people employed over the week.
- Fuel is the sum of P3 daily median fuel volumes. It is labelled a weekly estimate, not the median of the simulated weekly total or tank inventory. Fuel availability is unavailable and stays `null`.
- `departure_delay_24h` selects separate resource, recommendation, cost and impact results. The UI reads its start date and delayed share from P3 assumptions (currently all departures from Feb 14). Daily departures show P3 simulated P50 values for the selected variant, alongside the original P2 point estimate. Arrivals retain their original P2 estimate.
- Carryover is unconstrained demand assuming unlimited parking. It is not the inventory after rejected/referred arrivals under the prepared plan. Display remaining aircraft, their P10–P90 range, size-weighted space units and departures shifted beyond the window separately. The latter is a scheduled flow, not another inventory to add to remaining aircraft.

## Recommendations and human authority

Native action IDs map to review-oriented titles. For example, `tow_packing` appears as **Review the proposed ramp layout**, accompanied by an explicit requirement for qualified human validation of geometry, clearances and procedures. The original action and rationale are labelled as a proposal. No layout, tow, staffing assignment, lease or reservation is executed.

The displayed due date is the earliest supplied action date, used as a review-by marker; the producer does not supply a separate planning lead time. The underlying affected dates are retained and the peak evidence date is included for traceability. A manager demo review records a planning decision; it does not replace the named real-world approver or physical safety checks.

All native evidence chips are copied from validated resource rows. Producer narrative numbers and cost assumptions still need human review. Source text is not treated as an instruction by the application.

## Release integrity and remaining team work

The native loader verifies the 21-file `marvin/person_2_forecasting/release_manifest.json` against exact file bytes and its run ID. All four comparison artifacts are included. A mismatched manifest fails loading; no manifest is labelled unreviewed. A matching manifest establishes file identity, not numerical coherence, approved assumptions, observed forecast accuracy or safe ramp geometry. Run the independent pipeline verifier after producer changes.

The release status participates in the dashboard version. Reviews and exports are rejected if current source files no longer match the displayed snapshot. The UI checks every 30 seconds while visible; review/export endpoints check immediately. Refresh accepts only a valid complete release. Existing reviews remain tied to their old dataset/scenario/variant.

Alan’s committed baseline and assumptions appear as a separate reference. Their parking field estimates aircraft via arrivals × dwell; it never replaces P3 ordinary parking in space units. The alternate seven-file contract is optional and currently incomplete; use the native path for the demo.

1. Alan + Marvin: agree on the training window, capture share and event multipliers; the current release remains provisional. Historical holdout scores against allocated estimates are not observed FBO accuracy.
2. Elia: recompute opening inventory and regenerate all parking variants after the agreed forecast changes.
3. All: review capacity, geometry, costs and uncertainty. Scalar space units cannot authorize an aircraft movement or prove a safe layout.
4. Nazar: pull the coherent release, refresh, run the tests/verifier and repeat the walkthrough in `DEMO.md`. The dashboard supports these updates without rewriting the UI as long as contracts remain stable.

Coordinated release: see [the release guide](RELEASE.md). The default stops on the current Alan/Marvin policy mismatch; only `--allow-provisional-mismatch` explicitly permits reproducing that provisional demo.
