# The Intelligent FBO

A seven-day parking preparation desk for a fictional FBO at LAX during Super Bowl LXI. Compare ordinary and event demand, explore lower/expected/higher scenarios and delayed departures, inspect preparation proposals, and record a human planning review.

## Run the shared app

Python 3.10 or newer is enough for the dashboard. From the repository root:

```sh
python3 nazar/app.py
```

On Windows use `py -3 nazar/app.py`. Open **http://127.0.0.1:4180** and select the manager demo account. If the port is busy, add `--port 4181`. No API key, frontend build or third-party package is required to view the committed outputs.

Fresh installs open the team release. Existing installations keep their selected source; choose **Use current team outputs** if the sample is active. Use **Data & assumptions → Refresh current source** after pulling a complete producer update.

Start with the parking gap and its first date, compare scenarios, then click **Review preparations**. See [the three-minute demo](nazar/DEMO.md) and [dashboard documentation](nazar/README.md).

## Team ownership

| Owner | Module | Responsibility |
|---|---|---|
| Alan | `alan/` | Historical sources, estimated baseline and assumption evidence |
| Marvin | `marvin/person_2_forecasting/` | Forecast, scenarios, ranges and evaluation |
| Elia | `elia/` | Parking, delayed departures, carryover and preparation impact |
| Nazar | `nazar/` | Dashboard, integration, human review and demo |

Coordinate schema changes before altering shared exports. Commit coherent releases together; review logs in `.state/` stay local and are ignored by Git.

## Verification and producer refresh

```sh
python3 -m unittest discover -s nazar/tests -v
python3 nazar/scripts/verify_team_pipeline.py
```

The verifier requires numpy and pandas; the dashboard does not. To regenerate the provisional forecast and all parking outputs, use `python3 nazar/scripts/release_team.py` with those dependencies installed. Review model assumptions before regenerating; this command does not resolve them automatically.

## What the results mean

Current forecasts and capacity assumptions are **provisional pending team review**. Public airport observations are allocated into estimated FBO demand; reservations and event multipliers include assumptions. Matching release hashes and passing tests do not prove forecasting accuracy or physical capacity. Alan’s independent parked-aircraft baseline is displayed separately from P3’s size-weighted parking units.

The dashboard checks the 20-file release manifest, flags changed inputs, and blocks stale-plan review/export. Reviews are attached to the precise dataset, scenario and variant. A planning approval does not authorize movement, towing, a booking, spending or an airport safety decision.

This is a local hackathon application with selectable demo identities, not production authentication or a public deployment. Only aggregate data belongs in the repository; never commit passenger details, credentials or local review databases.

Coordinated release: see [the release guide](nazar/RELEASE.md). The default stops on the current Alan/Marvin policy mismatch; only `--allow-provisional-mismatch` explicitly permits reproducing that provisional demo.
