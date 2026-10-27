# Dashboard input contract — proposed v1.0

This is a concrete integration proposal for the four team members, not a claim that their empty modules already use these schemas. Use the sample files as executable examples. If an owner needs another format, agree on an adapter/change before merging. Paths below are relative to the shared repository root. All changes in this PR are inside `dashboard/`.

## Rules for all producers

- UTF-8 CSV with headers; ordinary JSON for the manifest and recommendations.
- Exactly the listed fields; extra columns are rejected, including identifying fields.
- All numerical values must be finite and nonnegative, at most 1 billion. Expected aircraft counts may be fractional; do not claim they are confirmed bookings.
- Seven local calendar dates: `2027-02-11` through `2027-02-17`, inclusive, in `America/Los_Angeles`.
- Scenarios: `low`, `medium`, `high`. The dashboard labels them Lower, Expected, Higher.
- Resource variants: mandatory `standard`; optional `departure_delay_24h`. Supply all three scenarios and all seven dates for every included variant. The app disables the delay toggle when the variant is absent.
- No duplicate keys/rows. No missing days. CSV row limit 5,000; each input file below 2 MB. Browser imports must fit a 5 MB JSON request, including encoding overhead.
- Resource model and baseline must share the same aircraft footprint unit convention. Put it in the assumption ledger. A unit is a planning abstraction, not a safe aircraft position.
- No API fetches, forecast training, visit simulation or airport instructions are executed by the dashboard.

## The data team: baseline and assumptions

`sources/baseline.csv` — exactly 7 rows:

```csv
date,arrivals,departures,parking_units
2027-02-11,8,7,19
```

Dates are **planning dates aligned to the ordinary-week comparison**, not the original historical observation dates. `parking_units` is the ordinary daily peak. Explain the reference week, weekday alignment, historical/synthetic sources, opening occupancy and aggregation method in assumptions/source documentation.

`sources/assumptions.csv` — at least 1 row:

```csv
id,label,value,unit,classification,source,note
capacity,Usable capacity,64,parking units,synthetic,Team demonstration,Not measured LAX capacity
```

All fields are required nonempty text, up to 1,200 characters each. IDs are unique. Classification is `public`, `synthetic`, `assumption`, or `benchmark`. Document the aircraft footprint conversion, capacity, dwell time, fuel purchases, staffing productivity, prices and all event adjustments actually used. Coordinate resource assumptions with the parking team and forecast assumptions with the forecast team. Quote CSV fields that contain commas.

`historical_traffic.csv` and `data_sources.md` remain the data team’s provenance/model inputs; they are not directly ingested here. Do not infer aircraft demand from event attendance alone.

## The forecast team: demand and uncertainty

`forecast/demand_predictions.csv` — exactly 21 rows:

```csv
scenario,date,arrivals,departures
medium,2027-02-11,14,8
```

Supply all 3 × 7 combinations, with daily arrival/departure estimates. These are **the standard departure assumptions**, also shown with that label when a resource delay test is selected. The delay toggle changes supplied resource results, not this original forecast file. Do not send identical standard departure counts as if they were the delayed result.

`forecast/uncertainty_results.csv` — exactly 21 corresponding rows:

```csv
scenario,date,arrivals_lower,arrivals_upper
medium,2027-02-11,10,20
```

Require `arrivals_lower <= arrivals <= arrivals_upper`. These are **arrival** ranges, not parking confidence bands. Explain whether each is an assumed range, model quantiles, or a calibrated prediction interval in the manifest. For actual prediction intervals, state coverage, construction and validation in the description and source documentation. The UI does not invent confidence percentages.

Expected/medium is the central scenario supplied by the model owner; it is not automatically the statistically most probable scenario. Alternative scenarios must have explicit assumptions. Backtest/holdout results belong in the model documentation; this version does not compute a forecast accuracy metric.

## The parking team: parking and resources

`parking/resource_requirements.csv` — 21 rows per variant:

```csv
scenario,variant,date,parking_units,capacity_units,prepared_capacity_units,staff_required,staff_available,prepared_staff,fuel_gallons,fuel_available_gallons,preparation_cost
medium,standard,2027-02-13,75,64,92,5,5,5,7560,8000,1260
```

| Field | Meaning |
| --- | --- |
| `parking_units` | Daily maximum occupancy from the parking simulation, using agreed footprint units |
| `capacity_units` | Existing usable capacity for that date |
| `prepared_capacity_units` | **Total** capacity under the proposed preparation, not just extra units; must be >= existing |
| `staff_required` | Supporting peak personnel requirement for that date, under the documented shift model |
| `staff_available` | Ordinary available personnel for the same period |
| `prepared_staff` | Proposed personnel, must be >= ordinary availability |
| `fuel_gallons` | Total daily fuel demand estimate |
| `fuel_available_gallons` | Daily serviceable fuel availability under the producer’s stated convention |
| `preparation_cost` | Incremental USD cost attributable to this date; dashboard sums the seven dates |

Person 3 owns occupancy accounting, aircraft size, dwell time, capacity constraints, delayed departures and overflow assumptions. If the simulator works hourly, aggregate its **daily maxima** here, retaining hourly results in its own module. The dashboard reports **days with a shortage**, not shortage hours or aircraft waiting time. The delay variant must come from a separate simulation; a UI multiplier is not a substitute.

Proposed capacity is treated as a conditional resource assumption. It is not verified or reserved. Include applicability and cost components in assumptions. Charge one-time costs on one date; do not repeat the entire weekly cost on every row. A zero cost means the producer supplied zero, not “unknown.” Do not substitute zero for missing information; resolve/document it before export.

## The parking team, coordinating with the team: manifest

`parking/manifest.json` — one object with exactly these fields (see full sample):

```json
{
  "schema_version": "1.0",
  "dataset_name": "Team parking model output",
  "fbo_name": "Pacific Executive FBO",
  "airport": "LAX",
  "timezone": "America/Los_Angeles",
  "window_start": "2027-02-11",
  "window_end": "2027-02-17",
  "data_classification": "synthetic",
  "interval_kind": "assumed_range",
  "interval_description": "Describe how the arrival ranges were constructed and validated.",
  "model_version": "team-model-v1",
  "generated_at": "2026-10-23T12:00:00-07:00",
  "notes": "Fictional operator. Describe sources, limitations and synthetic components."
}
```

All values are nonempty strings. `data_classification`: `synthetic`, `mixed`, or `observed`; classify the **bundle**, not just its historical input. The dashboard displays this declaration; it does not independently verify it. Future demand normally contains forecasts and assumptions, so do not label the full future bundle “observed” merely because historical input was real. `interval_kind`: `assumed_range`, `model_quantiles`, or `prediction_interval`. `generated_at` should be an ISO timestamp including timezone. Do not update it without regenerating a coherent output bundle.

This version deliberately fixes LAX and the seven-day event. A different airport/window requires a coordinated contract and UI change; it is not a hidden configuration toggle.

## The parking team: preparation recommendations

`parking/scenario_recommendations.json` — list of up to 100 actions:

```json
[
  {
    "id": "confirm_overflow",
    "scenario": "medium",
    "variant": "standard",
    "action_type": "confirm_overflow",
    "reason": "Investigate the proposed extra capacity; verify suitability, availability and a supplier quote.",
    "owner": "manager",
    "due_date": "2027-02-12",
    "affected_dates": ["2027-02-13"],
    "source": "Parking optimizer v1; rule-based preparation advice",
    "evidence": [
      {"date": "2027-02-13", "field": "parking_units", "value": 75},
      {"date": "2027-02-13", "field": "prepared_capacity_units", "value": 92}
    ]
  }
]
```

- Use a unique `id` within each scenario/variant, stable across equivalent outputs.
- Allowed `action_type`: `verify_bookings`, `confirm_overflow`, `staffing_review`, `fuel_review`, `monitor_capacity`. The dashboard supplies safe, fixed titles.
- Owner: `manager`, `reservations`, or `operations`; manager demo role records reviews for all owners.
- `due_date`: ISO calendar date. It may precede the planning window.
- `affected_dates`: nonempty list of dates in the planning window. Evidence dates must be in this list.
- Evidence field must be a numerical resource field above. Value must match the resource row for the same scenario/variant/date within 0.000001. No invented metrics or unsupported evidence.
- `reason` and `source` are producer text; they are safely rendered but **not semantically fact-checked**. Narrative numbers still need producer review. Explain whether advice is rule-based or AI-generated. No keys or secrets in these files.
- Empty recommendation lists are accepted and shown as “No recommendations supplied”; they are not evidence that no preparation is needed.
- Recommendation approval never executes the recommendation. Numerical before/after comparisons show the supplied proposed capacity regardless of approval status; approval does not change the simulation.

## Summary arithmetic

For each date `d`:

```
before_gap[d] = max(0, parking_units[d] - capacity_units[d])
after_gap[d] = max(0, parking_units[d] - prepared_capacity_units[d])
```

Peak gap = maximum daily gap, which need not occur on the maximum-demand date when capacity varies. Days above capacity = count of dates with positive gap. Peak demand = maximum daily occupancy; on-site capacity in the hero is taken on that same peak-demand date. Cost = sum of daily incremental preparation costs. Supporting staff = maximum daily `staff_required`; weekly fuel = sum of `fuel_gallons`.

These are modelled comparisons holding demand fixed. They do not establish causal improvements, exact parking layouts or service-delay reductions.

## API and review integration

The browser calls a same-origin localhost JSON API. `GET /api/session` returns the demo session; `POST /api/login` accepts `{ "role": "manager" }` (or another demo role). The response includes a CSRF token; the session uses an HttpOnly SameSite=Strict cookie. All authenticated POST calls require `X-CSRF-Token` plus JSON content type.

- `GET /api/dashboard`: validated bundle, server summaries, source status, teammate file presence and latest 500 reviews.
- `POST /api/source`: `{ "source": "team" }` / `sample` / `import` (refresh last import).
- `POST /api/import`: `{ "files": { "manifest.json": "file text", ... } }` with exactly seven files.
- `POST /api/review`: exact active `version`, `scenario`, `variant`, `recommendation_id`, `decision`, `note`, `checks`. Decisions: `approved`, `changes_requested`, `rejected`. Approval requires boolean checks `assumptions`, `availability`, `cost` all true. Note 5–600 characters. Manager role only.
- `GET /api/export?scenario=medium&variant=standard`: downloaded JSON plan, matched current-version reviews and limitations.
- `POST /api/logout`: empty object, removes session.

Input version is a SHA-256 digest of the validated bundle, not a commit identifier. Reviews for different input versions remain visible but do not count as current. Reviews are also scoped to scenario/variant. Canonical object key ordering is stable; producers should keep CSV/recommendation ordering stable to avoid unnecessary new versions. The source selection and imported text persist locally; teammate files reload on app restart or explicit refresh, not via continuous watching.

## Integrating without overwriting each other

1. Agree on this contract or propose concrete edits before generating large outputs.
2. Work on personal branches and within your own folders.
3. Commit sample-compatible outputs first; merge via reviewed PRs.
4. Pull the shared branch, start the app, and load team outputs explicitly.
5. Reconcile displayed numbers against Person 3’s output, then replace fixtures with validated results and rehearse.

The dashboard team owns adapters and dashboard changes. Coordinate changes to shared formats, airport, dates and units as a team. Do not commit local `.state/`, `.env`, secrets, personal data or real operational instructions.
