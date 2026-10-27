# Daily what-if in the original dashboard

The original dashboard (`python3 dashboard/app.py`) now includes a **What-if planner**
tab. It accepts one low/medium/high week case, optional per-day cases and explicit
arrival/departure counts, a Monday holiday sensitivity, a 24-hour departure shift,
and proposed extra units. The experiment is separate from the validated P3 release.

The deterministic daily inventory model uses the producer's opening inventory,
size mix and before-peak departure share. Departures cannot exceed available
aircraft in that category; unmatched departure requests remain visible. Arrivals
are never discarded for exceeding capacity. Closing inventory carries forward
and departure requests shifted beyond the seven-day window are disclosed.

It is a daily sensitivity calculation, not an hourly simulator or a new trained
forecast. The newer Streamlit integration at `wt-int/app.py` instead demonstrates
hourly overlap from synthetic or uploaded visit intervals. The two interfaces
label their different methods and data sources explicitly.

The read-only `POST /api/what-if` endpoint requires the current source version,
the normal session and CSRF/origin checks. Its body is `{version, settings}`;
unknown settings, invalid dates, non-finite numbers and stale versions are rejected.
All demo roles may experiment; no experiment edits the source or grants an
operational permission. Editing the form hides obsolete results until recalculated.
Export recalculates against the current version.

The original release checker now also validates the optional 12-file FAA-event
evidence manifest against the matching release ID. The release coordinator carries
that evidence output with the standard release and installs the main manifest last.
