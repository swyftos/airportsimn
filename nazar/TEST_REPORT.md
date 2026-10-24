# Test report: FBO agent app and its data (2026-10-24)

Run on `main` at 1417f4f (PR #53 merged).

## How to run

```
python3 -m pytest -q nazar/tests/test_agent_data.py nazar/tests/test_agent_app.py   # 38 tests, ~15 s
python3 -m pytest -q --continue-on-collection-errors                                  # whole repo
```

The JavaScript checks need `node`; the browser check also needs Google Chrome (or `CHROME=/path/to/chrome`). Each is skipped when missing.

## What is tested

| File | What it checks |
|---|---|
| `nazar/tests/test_agent_data.py` (19) | `agent_data.json` is exactly what `site_kit/export_agent_data.py` produces from the team's files; both copies are identical; daily numbers match Marvin's `daily_totals.csv`, parking matches Elia's `resource_requirements.csv`, the pause matches Alan's restriction file, weather and accuracy match the measured files; every range contains its forecast; Low <= Medium <= High; hourly curves add up to a full day; no movements in the pause; no personal data; every number in the presentation |
| `nazar/tests/test_agent_app.py` (19) | Every page element `app.js` uses exists in `index.html`; the page serves; the real `app.js` math on the real data (clear weather = forecast, hours add up to the day, game-day pause, heavy rain moves flights to Monday without losing any, Part 91/135 weighting, peak windows, booked vs forecast, CSV import rejects bad rows, HTML escaping); the presentation demo clicked through in headless Chrome (no JS errors, 7 days, flights saved and kept after reload, booked count, game-day page, proposal acknowledged, backtest shown) |

## Results

- New tests: **38 passed.**
- Whole repo: **200 passed, 1 file could not be collected** (see Marvin below). That file passes on its own (12 passed).
- Elia's `elia/test_sensitivity.py` errors seen earlier are gone on main: all pass.

## Data is correct

- `agent_data.json` matches the team's outputs exactly and is not stale.
- Presentation numbers confirmed: Friday 7.3 landings (+44%, peak 09:00-12:00); Monday 10.0 departures (+55%, peak 07:00-10:00); 40% of Sunday departures after 20:30; heavy rain on Sunday moves Monday departures 10.0 -> 10.3; backtest 14.9% vs 16.6 / 17.8 / 18.4 / 21.5%; 87.9% inside the 90% range; Super Bowl effect +3.1 / +15.5 / +31%; eight-city test -32.3% to +81.3%.

## Feedback: things to fix or decide

1. **Next-3-hours box contradicts itself in the demo (fix before presenting).** Friday 10:00 after logging the demo flights shows "1.8 Exp Landings (3 Booked)". The forecast is lower than what is already booked. Expected should never be below booked: show max(booked, forecast), or "3 booked + ~0 more". A judge will notice. (Nazar)
2. **Raw key on the game-day page.** It shows "Weather: heavy_rain" instead of "Heavy rain". (Nazar)
3. **Fog increases traffic in the app.** Measured heavy-fog effect: Part 91 -4.3%, Part 135 **+3.7%** (95% CI +0.2% to +7.3%), so the app adds +0.7% on a fog day and nothing carries over. Is this real (diversions from other airports?) or should fog be 0 when not significant? (Marvin)
4. **Rain on Wednesday 17 Feb loses flights.** Lost movements move to the next day, but the week ends, so they disappear. Fine, but say so in the app or the Q&A. (Nazar)
5. **Two test files with the same name.** `marvin/person_2_forecasting/test_forecast_model.py` and `marvin/person_2_part91_part135_forecast/test_forecast_model.py` collide, so `pytest` from the repo root stops with "import file mismatch". Rename one (e.g. `test_part_forecast_model.py`) or add `__init__.py` files. (Marvin)
6. **The game-day hours 14:00 and 20:00 are drawn as paused** although half of each hour is open (14:00-14:30, 20:30-21:00). The numbers are right; only the shading covers the whole hour. Minor. (Nazar)

## Not tested yet (for the others)

- Alan: raw FAA data (no missing days, no duplicates, 2022 Super Bowl +3.1% / +15.5% reproduced from raw).
- Marvin: rerunning the backtest reproduces 14.9%; forecasts never negative.
- Elia: the slot advisor never suggests a time inside the pause; scenario totals are conserved.
- Everyone: show the app to 3 people outside the team for 5 seconds and ask "what is this for?".
