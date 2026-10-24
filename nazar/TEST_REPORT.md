# Test report: FBO agent app and its data (2026-10-24)

Baseline: `main` at 1417f4f (PR #53 merged). This report includes the Marvin follow-up on PR #57.

## How to run

```
python3 -m pytest -q nazar/tests/test_agent_data.py nazar/tests/test_agent_app.py   # 38 tests, ~15 s
python3 -m pytest -q                                                                 # whole repo
```

The JavaScript checks need `node`; the browser check also needs Google Chrome (or `CHROME=/path/to/chrome`). Each is skipped when missing.

## What is tested

| File | What it checks |
|---|---|
| `nazar/tests/test_agent_data.py` (19) | `agent_data.json` is exactly what `site_kit/export_agent_data.py` produces from the team's files; both copies are identical; daily numbers match Marvin's `daily_totals.csv`, parking matches Elia's `resource_requirements.csv`, the pause matches Alan's restriction file, weather and accuracy match the measured files; every range contains its forecast; Low <= Medium <= High; hourly curves add up to a full day; no movements in the pause; no personal data; every number in the presentation |
| `nazar/tests/test_agent_app.py` (19) | Every page element `app.js` uses exists in `index.html`; the page serves; the real `app.js` math on the real data (clear weather = forecast, hours add up to the day, game-day pause, heavy rain moves flights to Monday without losing any, Part 91/135 weighting, peak windows, booked vs forecast, CSV import rejects bad rows, HTML escaping); the presentation demo clicked through in headless Chrome (no JS errors, 7 days, flights saved and kept after reload, booked count, game-day page, proposal acknowledged, backtest shown) |

## Results

- New tests: **38 passed.**
- Whole repo after the Marvin follow-up: **198 passed, 17 skipped, 331 subtests passed** on Windows. The skips require Node or Chrome on the Python test runner's PATH; there are no collection errors.
- Elia's `elia/test_sensitivity.py` errors seen earlier are gone on main: all pass.

## Data is correct

- `agent_data.json` matches the team's outputs exactly and is not stale.
- Presentation numbers confirmed: Friday 7.3 landings (+44%, peak 09:00-12:00); Monday 10.0 departures (+55%, peak 07:00-10:00); 40% of Sunday departures after 20:30; heavy rain on Sunday moves Monday departures 10.0 -> 10.3; rolling backtest 14.9% WAPE vs 16.6 / 17.8 / 18.4 / 21.5%; 87.9% inside the 90% range; Super Bowl effect +3.1 / +15.5 / +31%; eight-city test -32.3% to +81.3%.

## Feedback: things to fix or decide

1. **FIXED in this PR. Next-3-hours box contradicted itself in the demo.** Friday 10:00 after logging the demo flights showed "1.8 Exp Landings (3 Booked)". It now shows max(forecast, booked), and a browser test checks expected >= booked.
2. **FIXED in this PR. Raw key on the game-day page.** It showed "Weather: heavy_rain"; it now shows "Heavy rain" (tested).
3. **Clarified in this PR. Fog is a sensitivity, not a diversion claim.** In the full historical sample, heavy fog is associated with Part 91 -4.3% and Part 135 +3.7% (95% bootstrap interval +0.2% to +7.3%). The recent 2023-2025 Part 135 interval includes zero. The app defaults to clear weather and shows about +0.7% only if heavy fog is selected. The source cannot identify diversions or predict 2027 fog; the app now says so.
4. **Rain on Wednesday 17 Feb loses flights.** Lost movements move to the next day, but the week ends, so they disappear. Fine, but say so in the app or the Q&A. (Nazar)
5. **Fixed in this PR.** The Part 91/135 test is now `test_part_forecast_model.py` and loads its own `forecast_model.py` by path, so root-level pytest cannot reuse the other package's module. The release evidence hash was refreshed for the changed Marvin test.
6. **The game-day hours 14:00 and 20:00 are drawn as paused** although half of each hour is open (14:00-14:30, 20:30-21:00). The numbers are right; only the shading covers the whole hour. Minor. (Nazar)

## Not tested yet (for the others)

- Alan: raw FAA data (no missing days, no duplicates, 2022 Super Bowl +3.1% / +15.5% reproduced from raw).
- Elia: the slot advisor never suggests a time inside the pause; scenario totals are conserved.
- Everyone: show the app to 3 people outside the team for 5 seconds and ask "what is this for?".
