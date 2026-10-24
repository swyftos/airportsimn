# Demo and acceptance checklist

## Three-minute story using the handcrafted sample

1. **Open the desk as Maya, FBO manager.** Say: “Our focus is FBO parking preparation at a fictional operator at LAX. These initial inputs are synthetic; the team’s models plug into the same interface.”
2. **Expected outlook.** Start with “Prepare for a 28-unit parking gap.” Point out 92 needed versus 64 available. The manager first learns the size and timing of the problem, not a wall of controls.
3. **Select a day in the chart.** Compare ordinary and event parking. Explain that arrivals do not equal occupied spaces: existing aircraft, dwell time, footprint and delayed departures determine occupancy. Arrival ranges are supplied assumptions in this demo, not confidence claims.
4. **Review preparations.** Proposed additional capacity takes 3 days above capacity to 0, conditionally. $3,780 is an illustrative overflow-only cost. It is not a quote or proof of a real-world saving.
5. **Higher demand, then delayed departures.** Standard higher demand leaves 14 units uncovered; delayed departures leave 27. Show that the tool admits an unresolved problem instead of declaring the airport ready.
6. **Request changes on the overflow action.** Enter a note asking for verified availability, suitability and a quote. Show the review history. Nothing is ordered or authorized.
7. **Inspect Data & assumptions.** Show explicit sources, missing teammate files, the assumption ledger, and the model/version. Explain that invalid input is rejected rather than silently replaced with samples.
8. **Export the plan.** The JSON contains the selected scenario, derived summary, recommendations, version and matched review records for the team to inspect.

Answer “What decision should AI never make?”: **It must never authorize aircraft movements or override airport safety procedures.** A human must validate physical parking suitability and commit resources. This app records planning reviews only.

## Presentation with the connected team models

Run `python3 nazar/scripts/verify_team_pipeline.py` (numpy/pandas required), then use **Data & assumptions → Load current P2/P3 outputs** before presenting this version. Do not narrate the handcrafted sample’s numbers over the native model screens.

- Expected demand: peak daily P50 parking need 91.7, current capacity 90, proposed 139. The remaining median shortfall is 0; the preparation does not eliminate risk.
- Compare **Arrivals** to show the supplied ordinary baseline against event estimates. Explain that the missing ordinary parking baseline is still a team deliverable.
- Select game day: the parking P10–P90 range is 54.8–132.6 units and the supplied simulation exceeds proposed capacity in 7.0% of runs. These are unvalidated synthetic-model outputs, not observed probabilities.
- Show the impact comparison: Expected mean unaccommodated aircraft changes 9.4 → 0.9, but median net benefit is −$15,006 and preparation pays off in only 38.7% of simulations. Discuss the risk/cost tradeoff; do not pitch guaranteed savings. These figures belong to the currently committed synthetic output set and must be refreshed when producers change it.
- Show the per-category arrival ranges and P2’s synthetic historical test metrics on the data tab. Historical validation does not validate the assumed event uplift.
- Explain that the 24-hour delay toggle is disabled until Person 3 supplies that variant. Do not describe the current P3 within-day departure-order assumption as a 24-hour delay test.
- Review the overflow proposal; the displayed weekly preparation cost is $24,400, including supplied action costs. Record a request for confirmed capacity, geometry checks and quotes.

## What each teammate should demonstrate before the final rehearsal

- Alan: explain ordinary-week selection, sources, weekday mapping, capacities and synthetic assumptions.
- Marvin: explain the central prediction, how lower/higher were built, uncertainty meaning and holdout evaluation if available. Event attendance is not aircraft demand.
- Elia: reconcile occupancy against visits, demonstrate carry-in/carry-out and delayed departures, verify overflow constraints and costs. Export daily peaks without calling them hourly measurements.
- Nazar: load all seven outputs, reconcile dashboard summaries, show one source failure and one successful human review; explain stale reviews.

## Integration acceptance

- [ ] All owners agree on dates, timezone, footprint units, variants and file fields.
- [ ] Team files load without manually editing dashboard values.
- [ ] Ordinary-week, lower, expected, higher and supported delay outputs reconcile against producer files.
- [ ] Uncertainty is labelled according to how it was actually computed.
- [ ] A missing file, mismatched evidence value or invalid numerical input produces a readable error and keeps the previous dataset.
- [ ] Dataset changes invalidate old approvals; scenario/variant reviews are distinct.
- [ ] Non-manager demo roles can inspect but cannot submit reviews/change data.
- [ ] Approval requires checks and a meaningful note; unresolved capacity remains visible after approval.
- [ ] The team explains proposed-vs-confirmed resources and identifies all synthetic assumptions.
- [ ] No passenger data, real tail numbers, secret keys or `.state` database are committed.
- [ ] Export and startup work on another teammate’s laptop.

## Remaining work before calling it a complete hackathon solution

The dashboard and integration module work now. Marvin’s learned forecasting component and Elia’s Monte Carlo parking component are now integrated from their committed exports. Their current outputs are synthetic. Alan’s real-data baseline, ordinary parking comparison, and a separate delay variant remain incomplete. The sample generator is not the forecasting component. An LLM is optional and must not invent numerical results. Demonstrate model skill with honest validation or present conditional resource improvement estimates with their assumptions. UI polish comes after an early end-to-end integration run, not after every model is finished.

LA 2028 is a stretch goal. Keep it outside the core demo until this seven-day story is reliable.
