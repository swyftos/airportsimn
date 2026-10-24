# Demo and acceptance checklist

## Three-minute story

1. **Open the desk as Maya, FBO manager.** Say: “Our focus is FBO parking preparation at a fictional operator at LAX. These initial inputs are synthetic; the team’s models plug into the same interface.”
2. **Expected outlook.** Start with “Prepare for a 28-unit parking gap.” Point out 92 needed versus 64 available. The manager first learns the size and timing of the problem, not a wall of controls.
3. **Select a day in the chart.** Compare ordinary and event parking. Explain that arrivals do not equal occupied spaces: existing aircraft, dwell time, footprint and delayed departures determine occupancy. Arrival ranges are supplied assumptions in this demo, not confidence claims.
4. **Review preparations.** Proposed additional capacity takes 3 days above capacity to 0, conditionally. $3,780 is an illustrative overflow-only cost. It is not a quote or proof of a real-world saving.
5. **Higher demand, then delayed departures.** Standard higher demand leaves 14 units uncovered; delayed departures leave 27. Show that the tool admits an unresolved problem instead of declaring the airport ready.
6. **Request changes on the overflow action.** Enter a note asking for verified availability, suitability and a quote. Show the review history. Nothing is ordered or authorized.
7. **Inspect Data & assumptions.** Show explicit sources, missing teammate files, the assumption ledger, and the model/version. Explain that invalid input is rejected rather than silently replaced with samples.
8. **Export the plan.** The JSON contains the selected scenario, derived summary, recommendations, version and matched review records for the team to inspect.

Answer “What decision should AI never make?”: **It must never authorize aircraft movements or override airport safety procedures.** A human must validate physical parking suitability and commit resources. This app records planning reviews only.

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

The dashboard and integration module work now. The **real baseline, forecasting/AI component, simulator and validated preparation output** still need to come from Persons 1–3. The sample generator is not that component. An LLM is optional and must not invent numerical results. Demonstrate model skill with honest validation or present conditional resource improvement estimates with their assumptions. UI polish comes after an early end-to-end integration run, not after every model is finished.

LA 2028 is a stretch goal. Keep it outside the core demo until this seven-day story is reliable.
