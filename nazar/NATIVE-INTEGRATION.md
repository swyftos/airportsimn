# Current P2/P3 integration

The first dashboard contract was prepared against an empty repository. While work was underway, Persons 2 and 3 committed their modules. This adapter connects to those **existing** outputs, leaving every teammate’s folder unchanged. Use **Load current P2/P3 outputs**. The separate seven-file contract remains an optional future interface and the format for manual bundle import.

## Files read

| Producer | Native file | Use |
| --- | --- | --- |
| Marvin | `marvin/Person2-Forecasting/demand_predictions.csv` | Category/direction point forecasts and ordinary baseline |
| Marvin | `marvin/Person2-Forecasting/uncertainty_results.csv` | Category-specific 90% predictive ranges |
| Marvin | `marvin/Person2-Forecasting/model_report.json` | Assumptions, issue date, provenance, historical test metrics |
| Elia | `elia/resource_requirements.csv` | Parking P10/P50/P90, capacities, exceedance probabilities, staffing and fuel |
| Elia | `elia/scenario_recommendations.json` | Proposed actions, action costs, weekly preparation total and method |
| Elia | `elia/assumptions_p3.csv` | Space, staffing, fuel and cost assumptions |

The adapter reads fixed relative paths, requires a complete set, validates scenario/date/category combinations, reconciles P2 point estimates against uncertainty rows, checks parking quantile order and probability ranges, reconciles weekly action costs, and rejects actions without human approval. It keeps only specified aggregate fields in the display bundle. Producer prose still requires human review and must contain no identifying data.

No forecasts or simulations are re-run on load. Regenerate P2, then P3 against those P2 outputs, then refresh the dashboard. **The producers currently provide no common run ID or input hash, so the adapter cannot prove the files come from the same run.** Recommend adding `p2_input_hash` / `run_id` to P3’s metadata next. The dashboard hashes all six input files to attach reviews to the exact loaded set, but that does not establish upstream coherence.

## Exact interpretation

- Daily arrivals and departures are sums of P2 category **point estimates**. They can differ from P3’s medians of simulated totals; these are different quantities.
- Ordinary arrivals/departures use P2’s `normal_fbo_baseline`, requiring it to agree across scenarios. It is a model comparison, not a measured ordinary-week count.
- Ordinary **parking** is absent and stays `null`. The parking chart omits its bar and labels it unavailable. The Arrivals chart provides the available ordinary/event comparison. Alan and Elia need to supply an ordinary parking simulation for that additional comparison.
- Parking chart and gap arithmetic use P3’s daily `parking_demand_su_p50` values. “Peak” means the maximum of those daily medians, not the median of each simulation’s whole-week maximum.
- P10–P90 is an **80% central model quantile range** for each daily parking peak. It is distinct from P2’s **90%** category predictive ranges. Neither establishes validated Super Bowl event coverage. A zero P50 gap would not imply zero risk.
- Daily capacity exceedance probability comes directly from P3. It is not an empirical probability established from observed Super Bowl outcomes.
- P2 category interval endpoints are never summed. Per-category ranges appear in selected-day details; an aggregate arrival interval remains unavailable.
- Cost is the supplied **weekly preparation action total**, reconciled with action costs. No fabricated daily cost allocation is used. It is not a quote, realized saving or full business P&L.
- Staffing support shows the maximum proposed technician count over the three shifts; daily details retain morning/day/night counts. This includes P3’s staffing buffer, not unique people employed over the week.
- Fuel is the sum of P3 daily median fuel volumes. It is labelled a weekly estimate, not the median of the simulated weekly total or tank inventory. Fuel availability is unavailable and stays `null`.
- No native `departure_delay_24h` output exists, so only `standard` is exposed. P3’s within-day early-departure assumption is not a 24-hour delay scenario.

## Recommendations and human authority

Native action IDs map to review-oriented titles. For example, `tow_packing` appears as **Review the proposed ramp layout**, accompanied by an explicit requirement for qualified human validation of geometry, clearances and procedures. The original action and rationale are labelled as a proposal. No layout, tow, staffing assignment, lease or reservation is executed.

The displayed due date is the earliest supplied action date, used as a review-by marker; the producer does not supply a separate planning lead time. The underlying affected dates are retained and the peak evidence date is included for traceability. A manager demo review records a planning decision; it does not replace the named real-world approver or physical safety checks.

All native evidence chips are copied from validated resource rows. Producer narrative numbers and cost assumptions still need human review. Source text is not treated as an instruction by the application.

## Remaining team work

1. **Alan + Marvin:** connect documented real/estimated inputs with correct provenance; never relabel synthetic model validation as observed accuracy.
2. **Elia + Alan:** export an ordinary parking simulation using the same space-unit convention and initial-occupancy assumptions.
3. **Elia:** add a separately simulated departure-delay variant, with daily resource outputs and recommendations.
4. **Marvin + Elia:** add an upstream input hash/run ID to prove P3 used the current P2 output set.
5. **All:** verify prepared capacity and physical layout assumptions, cost components and event uncertainty before using the model beyond the demo.
6. **Nazar:** extend the adapter to those new outputs when available, run the complete demo and keep the UI labels aligned with actual model semantics.

The standard seven-file import format in `INTEGRATION.md` is an alternative, not a demand that the current team rewrite its models. Coordinate changes with Nazar before changing native filenames or columns.
