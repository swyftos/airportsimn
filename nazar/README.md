# The Intelligent FBO — Nazar’s dashboard & integration module

A working local readiness desk for a fictional **Pacific Executive FBO at LAX**. It helps a manager see parking pressure during February 11–17, 2027, compare preparations, inspect assumptions, and record a human planning review.

**Owner: Nazar Meniailo / z1ppyyy — Person 4.** Everything in this contribution lives in `nazar/`. The dashboard connects directly to Marvin’s and Elia’s committed outputs through a native adapter. Their forecasting and parking logic remain their responsibility; Alan’s source work and estimated baseline are merged. His baseline appears separately in Data & assumptions because its parked-aircraft counts differ from P3’s size-weighted space units.

## Run it

From the shared repository root, with Python **3.10 or newer**:

```sh
python3 nazar/app.py
```

Open **http://127.0.0.1:4180**, choose the manager demo account, and click **Open readiness desk**. On Windows, `py -3 nazar/app.py` is an alternative. No packages, API key, build step or internet connection are required to run the dashboard. A fresh install opens the current team outputs; an existing installation preserves its previously selected source. If it shows samples, use **Use current team outputs** on the overview. Missing or invalid team files produce an error, never a silent switch to sample data. If the port is taken, use `--port 4181` and open that port. Stop with Ctrl+C.

Do not open `static/index.html` directly: the app needs its local Python server. Each teammate runs their own local copy. Sharing the repository shares code and input files, not a central live database.

## What works now

- Seven-day ordinary/event parking comparison and selectable daily details.
- Lower / Expected / Higher demand scenarios and an optional supplied 24-hour departure-delay variant.
- Before/after capacity gaps, days above capacity, and supplied preparation cost.
- Recommendations with owners, review dates and numerical evidence linked to the resource output.
- Manager review: approve for planning, request changes, or reject; approvals require three checks and a note.
- Persistent SQLite review log tied to dataset version, scenario and variant. Changed inputs make earlier reviews visibly stale.
- Explicit sample / team / imported data sources. Invalid data never silently becomes sample data.
- Source and assumption ledger, plus Alan’s separate estimated baseline; JSON plan export including release status.
- Prominent provisional-review status with SHA-256 verification of the supplied 20-file release manifest. Matching hashes do not approve assumptions or establish forecast accuracy.
- Live source checks every 30 seconds while visible, and on every review/export. Changed, missing or mismatched files block review/export until a coherent release is loaded; the old snapshot stays visible with a warning.
- Three demo employee views with server-enforced role checks for writes. **These are selectable, unverified demo identities, not real authentication.**

## Connect the current team code — works now

The native adapter reads the existing P2/P3 formats without requiring teammates to rename their files. Open **Data & assumptions → Load current P2/P3 outputs**. It loads Marvin’s category forecasts, ranges, run metadata and evaluation metrics from `marvin/person_2_forecasting/`, plus Elia’s resources, recommendations and assumptions from `elia/`.

The current merged release uses estimated FBO demand and provisional parking assumptions. Read the current numbers from the screen rather than reusing values from an older demo. The overview shows the median parking gap, its first date, proposed remaining gap and simulated exceedance risk at the peak-demand day. Expand the service-impact section for costs and simulated benefits, including losses.

Click **Arrivals** above the chart for an ordinary/event comparison using P2’s learned baseline. Parking displays P3 daily P50 peaks and P10–P90 ranges. When all four P3 comparison files are present, the chart also displays ordinary parking in the same space units and daily-P50 basis. The delay toggle selects a separate simulation and updates parking, departures, staffing, fuel, costs, impact and recommendations together. Carryover shows unconstrained aircraft demand after February 17, including departures pushed beyond the window. Without the comparison files, ordinary parking and the delay option remain unavailable; a partial set is rejected. Category arrival intervals are shown individually and never added into a false total interval. The data tab shows P2’s historical holdout metrics with the producer’s observed/estimated/synthetic classification. Scores against estimated inputs are not observed FBO accuracy. Selected-day details expose event multipliers, reservation floors and their sources. The preparation panel compares simulated unaccommodated aircraft, delayed turns and modeled costs, including negative net benefits; exports retain these results.

See [NATIVE-INTEGRATION.md](NATIVE-INTEGRATION.md) for exact mappings, limitations and remaining team work. The models are **not** re-run on load: regenerate P2 and P3 outputs coherently, then refresh. The app’s source badge always distinguishes team outputs from the handcrafted sample.

## Review status and coherent updates

For the native path, the dashboard validates the producer schemas and all 20 declared manifest files, including ordinary parking, delayed departures and carryover. A missing manifest is explicitly unreviewed; an existing malformed/mismatched manifest blocks loading. An unsigned producer status cannot establish verified human approval. A manager planning review never removes the provisional banner.

The file list is deliberately fixed in `readiness/release_status.py`. Coordinate a contract change with Nazar if a producer adds/removes manifest entries; do not weaken validation to make a broken release load. Producers should run `python nazar/scripts/release_team.py` with numpy/pandas installed after updating agreed inputs. It regenerates and verifies the complete release. Pull it, then use **Refresh current source**. Loading does not run simulations or silently activate changed files.

Imported bundles are frozen snapshots; re-import them to update. Alan’s reference is read independently and is not part of the active forecast or planning approvals.

## Optional standardized seven-file contract

If the team wants a unified export format later, read [INTEGRATION.md](INTEGRATION.md). The native integration above does not require migrating to it. The seven files in [sample-data](sample-data/) are complete examples of the proposed contract. Coordinate any schema changes before coding to avoid incompatible modules.

| Person | Responsibility | Dashboard inputs |
| --- | --- | --- |
| Alan | History, baseline, assumptions | `alan/baseline.csv`, `alan/assumptions.csv` |
| Marvin | Forecast and uncertainty | `marvin/demand_predictions.csv`, `marvin/uncertainty_results.csv` |
| Elia | Parking/resource model and preparation output | `elia/resource_requirements.csv`, `elia/scenario_recommendations.json`, `elia/manifest.json` |
| Nazar | Dashboard, integration, responsible AI, demo | This folder |

Alan’s historical data and source documentation and teammates’ Python models stay in their modules. The dashboard consumes their exported aggregates; it does not run model code on an HTTP request. Elia coordinates the manifest with the other producers to describe the **whole bundle**, including synthetic assumptions.

The alternative contract remains incomplete in this repository: `elia/manifest.json`, `marvin/demand_predictions.csv` and `marvin/uncertainty_results.csv` are not supplied in that format. Existing native files are not interchangeable with these schemas. The advanced loader reports missing/incompatible files and keeps the previous dataset. If the team later supplies a complete compatible export, select **Data & assumptions → Advanced → Load seven-file contract**. File presence is shown separately from validation. To import outputs from elsewhere, choose **Import a complete output bundle** and select all seven files together. **Refresh current source** reloads the active source, not whichever source happens to have files available.

## Sample data is a demonstration, not a forecast

The initial dataset contains handcrafted fixtures, labelled synthetic throughout. It is not fitted to historical traffic, calibrated, or calculated from aircraft visits. `sample-data/generate_samples.py` reproduces the fixtures; it is **not a prediction model**.

Illustrative expected case: peak 92 parking units versus 64 on-site; proposed extra capacity reduces the peak gap from 28 to 0 and days over capacity from 3 to 0, at $3,780 of assumed overflow cost. Higher demand leaves a 14-unit gap; higher demand plus delayed departures leaves 27. These are conditional arithmetic comparisons, **not measured real-world improvements or accuracy claims**. Costs only cover the components supplied by the resource module; sample costs cover overflow alone.

Selecting a scenario asks “what if?” It does not make the employee the forecaster, retrain a model, or assert which outcome will occur. The model owner provides the central estimate and explains how alternatives and intervals were constructed.

## Responsible AI boundary

This module displays the preparation output supplied by the resource/planner module. The native path uses P2’s learned month/weekday shrinkage forecasts plus P3’s Monte Carlo/rule-based resource advice. The separate sample uses handcrafted text. Neither path calls a live LLM. If the team adds an LLM, keep the key in the backend, have it reference validated evidence, disclose the generation method in `source`, and check its prose. The dashboard checks numerical evidence fields against resource values; it does **not** fact-check arbitrary narrative claims or verify external sources.

AI must never authorize aircraft movements, select a physically safe aircraft position, clear towing/taxiing/takeoff/landing, override airport procedures, or autonomously commit resources or money. Approving a card only records a planning review. It sends no operational instruction, booking, purchase or message. Scalar parking units do not demonstrate aircraft compatibility, clearances or safe geometry.

Only aggregate inputs belong here. No passenger names, manifests, tail numbers, contact details, or secret keys. Extra CSV columns are rejected, but free-text fields are not a PII detector: producers must remove identifying information. Keep review notes free of personal data.

## Local storage and deployment limits

`.state/reviews.sqlite3` stores the selected source, imported bundle and review history locally and is ignored by Git. Sessions are in memory and end when the server restarts. Restarting preserves imported inputs and reviews. If the selected team files disappear or become invalid, the app shows an error rather than replacing them with samples.

This is a localhost hackathon app. **Do not bind it publicly or present its demo roles as real identity/security.** A shared production deployment would need verified authentication, actual role assignment, HTTPS, a managed database, retention controls and deployment hardening. Any local user can choose the manager demo role. Review history displays at most the latest 500 records; the local database retains older records. Do not use it as a regulated operational audit system.

## Verify and rehearse

```sh
python3 -m unittest discover -s nazar/tests -v
```

For a read-only numerical check that Elia’s committed results match the current forecast inputs (requires numpy and pandas):

```sh
python3 nazar/scripts/verify_team_pipeline.py
```

The verifier reproduces P3 in memory, compares standard and delayed resources/recommendations/impact, ordinary parking and all carryover rows, and prints input SHA-256 hashes. It does not overwrite producer files or validate physical capacity. Run it after every P2/P3 update; normal dashboard loading does not run simulations.

Tests cover data contracts, missing/invalid files, evidence mismatches, finite values, summaries, persisted reviews, stale-version rejection, role checks, CSRF/origin checks, export and source restoration. See [DEMO.md](DEMO.md) for the presentation walkthrough and integration acceptance checklist.

## Folder map

- `app.py`: local HTTP API and session/role boundary.
- `readiness/contracts.py`: schema validation and deterministic summary arithmetic.
- `readiness/data.py`: fixed teammate paths and explicit source loading.
- `readiness/storage.py`: local source/review persistence.
- `readiness/team_adapter.py`: validates and normalizes the existing P2/P3 exports without changing their code.
- `readiness/parking_variants.py`: validates the optional four-file ordinary/delay/carryover release; keeps variant-specific costs, impacts and recommendations separate.
- `static/`: dashboard HTML, CSS and browser interactions.
- `sample-data/`: fixtures and reproducible fixture generator.
- `tests/`: standard-library automated checks, including mandatory current-repository integration tests. Missing native files fail instead of skipping.
- `scripts/verify_team_pipeline.py`: read-only P2-to-P3 numerical coherence check.

The shared file formats are the part to agree on **now**. Connect outputs and test one complete journey early; use the remaining time to improve model quality, operational realism and visual polish together.

Coordinated release: see [the release guide](RELEASE.md). The default stops on the current Alan/Marvin policy mismatch; only `--allow-provisional-mismatch` explicitly permits reproducing that provisional demo.
