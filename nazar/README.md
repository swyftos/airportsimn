# RampReady — Nazar’s dashboard & integration module

A working local readiness desk for a fictional **Pacific Executive FBO at LAX**. It helps a manager see parking pressure during February 11–17, 2027, compare preparations, inspect assumptions, and record a human planning review.

**Owner: Nazar Meniailo / z1ppyyy — Person 4.** Everything in this contribution lives in `nazar/`. The dashboard is ready for the other three modules to connect; their forecasting and parking logic remain their responsibility.

## Run it

From the shared repository root, with Python **3.10 or newer**:

```sh
python3 nazar/app.py
```

Open **http://127.0.0.1:4180**, choose the manager demo account, and click **Open readiness desk**. On Windows, `py -3 nazar/app.py` is an alternative. No packages, API key, build step or internet connection are required. If the port is taken, use `--port 4181` and open that port. Stop with Ctrl+C.

Do not open `static/index.html` directly: the app needs its local Python server. Each teammate runs their own local copy. Sharing the repository shares code and input files, not a central live database.

## What works now

- Seven-day ordinary/event parking comparison and selectable daily details.
- Lower / Expected / Higher demand scenarios and an optional supplied 24-hour departure-delay variant.
- Before/after capacity gaps, days above capacity, and supplied preparation cost.
- Recommendations with owners, review dates and numerical evidence linked to the resource output.
- Manager review: approve for planning, request changes, or reject; approvals require three checks and a note.
- Persistent SQLite review log tied to dataset version, scenario and variant. Changed inputs make earlier reviews visibly stale.
- Explicit sample / team / imported data sources. Invalid data never silently becomes sample data.
- Source and assumption ledger; JSON plan export.
- Three demo employee views with server-enforced role checks for writes. **These are selectable, unverified demo identities, not real authentication.**

## Connect the team

Read [INTEGRATION.md](INTEGRATION.md) before generating outputs. The seven files in [sample-data](sample-data/) are complete examples of the proposed contract. Coordinate any schema changes before coding to avoid incompatible modules.

| Person | Responsibility | Dashboard inputs |
| --- | --- | --- |
| Alan | History, baseline, assumptions | `alan/baseline.csv`, `alan/assumptions.csv` |
| Marvin | Forecast and uncertainty | `marvin/demand_predictions.csv`, `marvin/uncertainty_results.csv` |
| Elia | Parking/resource model and preparation output | `elia/resource_requirements.csv`, `elia/scenario_recommendations.json`, `elia/manifest.json` |
| Nazar | Dashboard, integration, responsible AI, demo | This folder |

Alan’s historical data and source documentation and teammates’ Python models stay in their modules. The dashboard consumes their exported aggregates; it does not run model code on an HTTP request. Elia coordinates the manifest with the other producers to describe the **whole bundle**, including synthetic assumptions.

After the teammates commit those outputs and you pull their changes, select **Data & assumptions → Load team outputs**. File presence is shown separately from validation. To import outputs from elsewhere, choose **Import a complete output bundle** and select all seven files together. **Refresh current source** reloads the active source, not whichever source happens to have files available.

## Sample data is a demonstration, not a forecast

The initial dataset contains handcrafted fixtures, labelled synthetic throughout. It is not fitted to historical traffic, calibrated, or calculated from aircraft visits. `sample-data/generate_samples.py` reproduces the fixtures; it is **not a prediction model**.

Illustrative expected case: peak 92 parking units versus 64 on-site; proposed extra capacity reduces the peak gap from 28 to 0 and days over capacity from 3 to 0, at $3,780 of assumed overflow cost. Higher demand leaves a 14-unit gap; higher demand plus delayed departures leaves 27. These are conditional arithmetic comparisons, **not measured real-world improvements or accuracy claims**. Costs only cover the components supplied by the resource module; sample costs cover overflow alone.

Selecting a scenario asks “what if?” It does not make the employee the forecaster, retrain a model, or assert which outcome will occur. The model owner provides the central estimate and explains how alternatives and intervals were constructed.

## Responsible AI boundary

This module displays the preparation output supplied by the resource/planner module. The shipped advice is templated sample text, **not live AI-generated advice**. If the team adds an LLM, keep the key in the backend, have it reference validated evidence, disclose the generation method in `source`, and check its prose. The dashboard checks numerical evidence fields against resource values; it does **not** fact-check arbitrary narrative claims or verify external sources.

AI must never authorize aircraft movements, select a physically safe aircraft position, clear towing/taxiing/takeoff/landing, override airport procedures, or autonomously commit resources or money. Approving a card only records a planning review. It sends no operational instruction, booking, purchase or message. Scalar parking units do not demonstrate aircraft compatibility, clearances or safe geometry.

Only aggregate inputs belong here. No passenger names, manifests, tail numbers, contact details, or secret keys. Extra CSV columns are rejected, but free-text fields are not a PII detector: producers must remove identifying information. Keep review notes free of personal data.

## Local storage and deployment limits

`.state/reviews.sqlite3` stores the selected source, imported bundle and review history locally and is ignored by Git. Sessions are in memory and end when the server restarts. Restarting preserves imported inputs and reviews. If the selected team files disappear or become invalid, the app shows an error rather than replacing them with samples.

This is a localhost hackathon app. **Do not bind it publicly or present its demo roles as real identity/security.** A shared production deployment would need verified authentication, actual role assignment, HTTPS, a managed database, retention controls and deployment hardening. Any local user can choose the manager demo role. Review history displays at most the latest 500 records; the local database retains older records. Do not use it as a regulated operational audit system.

## Verify and rehearse

```sh
python3 -m unittest discover -s nazar/tests -v
```

Tests cover data contracts, missing/invalid files, evidence mismatches, finite values, summaries, persisted reviews, stale-version rejection, role checks, CSRF/origin checks, export and source restoration. See [DEMO.md](DEMO.md) for the presentation walkthrough and integration acceptance checklist.

## Folder map

- `app.py`: local HTTP API and session/role boundary.
- `readiness/contracts.py`: schema validation and deterministic summary arithmetic.
- `readiness/data.py`: fixed teammate paths and explicit source loading.
- `readiness/storage.py`: local source/review persistence.
- `static/`: dashboard HTML, CSS and browser interactions.
- `sample-data/`: fixtures and reproducible fixture generator.
- `tests/`: standard-library automated checks.

The shared file formats are the part to agree on **now**. Connect outputs and test one complete journey early; use the remaining time to improve model quality, operational realism and visual polish together.
