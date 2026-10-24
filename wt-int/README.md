# RampReady: parking preparation desk

Streamlit integration entry point for a fictional Pacific Executive FBO at LAX,
11–17 February 2027. Start with the parking gap, inspect the seven-day chart,
then preview a preparation plan. The previous seven-file dashboard remains at
`nazar/app.py`; its contracts and producer function signatures are preserved.

## Run

From the repository root, with Python 3.10 or newer:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r wt-int/requirements.txt
python -m streamlit run wt-int/app.py
```

Windows: activate `.venv\Scripts\activate` instead. Open http://localhost:8501.
Select a demo identity, then **Open planning desk**. This is local demo identity
selection, not production sign-in. The service binds to localhost by default.
No API key is needed. The briefing is a deterministic template, explicitly
labeled “Template briefing (AI service unavailable)”; no LLM integration is
claimed by this interface.

## Demo route

1. Open **Expected forecast**. Read the first shortage and peak gap.
2. Click **Preview preparation plan**, then **Preparation plan** for measured
   before/after results on identical demand. Overflow changes capacity, not demand.
3. Compare **Higher demand**. Residual shortage stays visible when overflow is
   insufficient. Inspect **Bookings and overlapping stays** to see why.
4. Increase departure delay. Try **Weather disruption test** and unavailable
   units. These are explicit user assumptions, not weather predictions.
5. Save a planning review with a note. Change an input; the history marks the
   prior review out of date. Reviews persist locally in `wt-int/.state`, ignored
   by Git. Set `FBO_REVIEW_DIR` to override the local storage directory for tests.
6. Under **Data & assumptions**, select **Marvin’s latest private-only case**.
   It reads the merged `private_only_review/daily_private_only_plan.csv` directly.
   This smaller case fits the illustrative ramp; the app does not invent a gap.
7. Upload a pseudonymous visit CSV or export the current modeled visits and
   preparation JSON. Upload errors never silently select demo data.

## Data provenance and boundaries

Default: **Synthetic demo data**, deterministic hourly private-aircraft visits.
It is deliberately a busy-week rehearsal so every plan interaction is usable.
It is not advertised as Marvin's forecast or observed FBO demand.

Marvin source: PR #31, merged into main at `b6d6976` when integrated here.
Daily requested arrivals come from his private-only review package. Its FAA GA
category observations are a proxy, with assumed 50% private eligibility and 20%
capture. Those are not observed private-fleet shares. The new source excludes
air-taxi counts; the older producer contract remains separate. Source metadata
and exact file fingerprints are exposed in the UI and export. The loader reads
current local files after the team pulls Git; it does not poll GitHub.

**Hourly adapter:** departure times, arrival hours, size and dwell are synthetic
assumptions. It uses Marvin's requested arrivals, not his `can_land` field or
daily departures. Occupancy is recomputed from the generated intervals and is
not presented as Elia's Monte Carlo simulation. Decimal daily baselines are
rounded to integer visits. Opening stock uses baseline arrivals × an assumed
1.1-day dwell, rounded, consistently across scenarios. No real reservations are
supplied. Changing the demand case does not modify uploaded recorded visits.

`assumptions.yaml` is the single source of operator, airport, dates, size weights,
rehearsal arrivals, dwell, capacity and demo roles. Capacity is **40 synthetic
main-ramp units**, with **4 protected reserve units** excluded: 36 usable units.
Up to 25 proposed overflow units yields 61 usable units. These replace the source
package's 75-unit assumption explicitly; none is claimed as verified physical
LAX stand capacity. The UI can edit main capacity and proposed overflow without
reducing reserve. Weather restrictions subtract additional usable units.

The event sweep computes exact overlap with half-open stays `[arrival, departure)`.
It handles opening inventory, midnight, identical arrival/departure times,
fractional-hour uploads and beyond-window stays. The chart shows hourly peaks;
shortage unit-hours integrate actual event intervals. They are not rejected
aircraft counts, delay savings or accuracy measurements. No aircraft is removed
from demand because it exceeds capacity.

Costs are illustrative: proposed units × $85/unit/day × all seven days. No
availability or quote is asserted. Any approval, modification or rejection is
a planning review attached to the complete source/config/visits/engine version.
It does not execute the proposed action. Source or assumption changes invalidate
earlier reviews. Avoid passenger/crew/owner data and tail numbers; CSV imports
accept only pseudonymous `V-####` IDs and the documented five columns.

## Weather handoff

See [the copy-ready team message](WEATHER-HANDOFF.md). Weather is a timing and
capacity stress test in this prototype. A live weather feed and a calibrated
weather-to-demand model are not implemented. No February conditions are invented.

## Verify

```sh
python -m unittest discover -s wt-int/tests -v
python -m unittest discover -s nazar/tests -v
```

Tests cover a hand-calculated three-aircraft midnight example, boundary times,
exact shortage integrals, weather/delay monotonicity, unchanged demand under
overflow, arrival-count reconciliation with Marvin, CSV validation, source
selection, review notes and stale reviews. Streamlit tests use temporary review
storage. The UI uses Plotly, Barlow fonts with system fallback, and no image or
external AI service dependency.
