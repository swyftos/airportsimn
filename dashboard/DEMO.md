# The Intelligent FBO: three-minute team demo

## Start from the shared repository

Use Python 3.10+ and run `python3 dashboard/app.py` (Windows: `py -3 dashboard/app.py`). Open http://127.0.0.1:4180 and choose Maya, the manager demo account. Fresh installs load the current team outputs; if an older installation shows samples, click **Use current team outputs**. No API key is needed. These are demo identities, not verified accounts.

Run `python3 -m unittest discover -s dashboard/tests -v` beforehand. With numpy/pandas available, also run `python3 dashboard/scripts/verify_team_pipeline.py`. The latter must report `matched`. Read the current values from the screen; do not memorize an earlier release’s numbers.

## Demonstration script

1. **0:00 — The manager’s problem.** “We help one fictional FBO at LAX prepare parking for seven days around the Super Bowl.” Point to the first shortage date, median peak demand, available capacity and remaining gap. Explain that parking units account for aircraft size, not individual marked stands.
2. **0:30 — Where the numbers come from.** Show the provisional banner. “Our forecast uses estimated FBO allocations from public airport data, plus assumed event multipliers and illustrative reservations. These are conditional scenarios, not confirmed bookings.”
3. **0:50 — Explore the week.** Compare ordinary and event parking, then select the busiest day. Show its uncertainty range and remaining simulated exceedance risk. A zero median gap does not mean zero risk. Arrivals is an optional supporting view.
4. **1:15 — Stress-test preparation.** Choose Higher and enable delayed departures. Explain the displayed start date and affected share. Show that remaining shortages persist when the supplied preparation is insufficient. Expand aircraft carryover if asked; it is unconstrained demand beyond the window, not confirmed inventory.
5. **1:40 — A concrete preparation decision.** Click **Review preparations**. Show overflow, layout and referral proposals with owners and evidence. Expand simulated service impact and cost tradeoffs; describe benefits as conditional estimates and retain negative outcomes.
6. **2:10 — Keep humans in command.** Review the overflow proposal and choose **Request changes**. Enter “Confirm usable area, availability and a quote before committing resources.” Open Review history to show the exact scenario and variant. Nothing is booked, ordered or authorized. Planning review does not approve the forecast itself.
7. **2:35 — Evidence and handoff.** Show Data & assumptions, the data team’s separately labelled baseline and the forecast holdout scores. Return to the overview and export the selected plan. The JSON retains release status, scenario, variant, resources, impact and version-matched reviews.

Answer to the judges: **AI must never authorize aircraft movements or override airport safety procedures.** Qualified humans must validate geometry, clearances, availability and spending.

## Refresh after teammates finish their models

1. Agree the model assumptions with the data team and the forecast team. The parking team updates opening inventory as necessary.
2. Producers regenerate with `python dashboard/scripts/release_team.py` (numpy/pandas required) and commit the complete release together.
3. Pull the merged changes, run tests and the pipeline verifier, then click **Refresh current source**.
4. Changed files cause a visible stale-plan warning and block review/export. Missing or mismatched release files cannot silently fall back to samples. Fix the complete release before refreshing again.

The optional seven-file contract under Advanced is not the team’s current integration route. Its three missing exports must be produced in the matching schema before that path can load. The data team’s parked-aircraft estimates must not be substituted for P3 space units.

## Final team acceptance

- All scenario/variant numbers reproduce from the producer files; the verifier reports matched.
- Forecast assumptions are agreed, or visibly presented as provisional.
- Uncertainty, estimated/synthetic provenance and cost assumptions are explained honestly.
- Manager-only review, missing/changed-input rejection, export and role switching work.
- Each teammate can start the app from a clean pull; local review databases are not shared through Git.
- The presenter rehearses the full sequence and can explain why preparation still leaves risk.

This is a local hackathon decision-support demo, not a deployed operational system. No live LLM is required: the learned forecast and Monte Carlo/resource rules supply the recommendations. LA 2028 remains outside the core demonstration.

Coordinated release: see [the release guide](RELEASE.md). The default stops on the current the data team/the forecast team policy mismatch; only `--allow-provisional-mismatch` explicitly permits reproducing that provisional demo.
