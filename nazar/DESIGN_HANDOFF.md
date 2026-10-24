# RampReady — approved design implementation

This version translates all seven supplied `.dc.html` layouts into native HTML templates. It retains their typography, colors, spacing, navigation, charts and responsive structure. No `support.js`, `DCLogic`, framework, build step or browser API key is shipped. The forecast and parking producer code and outputs in `marvin/`, `elia/` and `alan/` are unchanged.

## Run and use

Run `python3 nazar/app.py` from the repository root and open http://127.0.0.1:4180. The current local preview can use another port with `--port 4182`.

- **Sign in:** choose Maya (manager), Jordan (reservations) or Sam (operations). These are demo roles. Email sign-in is explicitly unconnected.
- **Overview:** Quiet / Expected / Busy load the existing Low / Medium / High model cases. The delay switch loads P3’s separately simulated disruption case. Pick a day, then open its hourly view. The headline, normal-week bars, event peaks and simulated uncertainty come from the loaded outputs.
- **Day:** shows P3’s daily figures alongside a separately labeled hourly illustration. Filter arriving/leaving aircraft and load more generated stays.
- **Plan:** review producer recommendations plus routine preparation checks. Approve, request changes or decline with a note. Approval requires explicit checks of assumptions, resources and cost. Reviews persist in SQLite with reviewer, time and exact input version. Stress comparisons hold the selected plan’s capacity fixed.
- **Bookings:** filter, search and review estimated stays, or upload pseudonymous visits. A check does not create a reservation. Uploaded visits remain separate from P2 until its owners regenerate the producer forecast.
- **Ramp:** inspect modeled main/overflow capacity and aircraft footprint weights; save six operational preparation checks. Unknown reserve counts and unconfirmed partner space are explicit.
- **Numbers:** inspect assumptions and provenance, refresh the team release, export the model or reviewed plan, load the seven-file contract, or open the daily what-if calculator. Change one day’s case, arrivals or departures, add hypothetical overflow or Presidents Day uplift, and recalculate all seven days. Experiments do not modify the producer output or approvals.

## Data boundaries

Daily peaks and costs are **actual outputs of the existing model**, not observations of a real FBO. The current matched P2/P3 release is labeled provisional pending Alan’s review. It uses GA/air-taxi proxies plus FBO-share and aircraft-mix assumptions; these categories are not verified private-jet customers.

The default expected case has a 38.9-unit daily peak against 75 modeled usable units, displayed conservatively as **39 / 75**. The UI therefore does not repeat the reference’s fictitious 32-space shortage. High is displayed as 52 units; high with the supplied departure-delay variant peaks at 69. Producer precision remains in exports.

No individual reservations or hourly occupancy paths were supplied. The illustration rounds daily category arrivals/departures using largest remainders, starts from modeled opening inventory, assumes arrivals at 10:00–17:00 and departures at 06:00–09:00 / 18:00–21:00, and allocates stays FIFO. Its E-codes are fictitious and never shown as booked. Independent daily rounding can differ from rounding the full week once. The hourly peak is not P3’s Monte Carlo median. Unmatched departures and assumptions are disclosed.

P3’s delay case starts on game day according to its assumption ledger. The existing daily what-if calculator instead shifts the entire seven-day departure sequence; its control explicitly states this difference. Neither feature is a weather forecast. Holiday uplift is a user sensitivity, not a measured holiday coefficient. Drop-and-go and overnight ratios have not been inferred from airport operation categories.

The UI shows no invented hourly savings, partner quotes, reserve counts, booking-completion percentages or historical cancellation activity. The booking-share slider is disabled because P2 does not use that model. Summary text is a fixed template grounded in model figures; no AI text service is connected.

## Booking CSV

Use exactly these columns, UTF-8, at most 2 MB / 5,000 rows:

```csv
visit_id,category,arrival,departure,status
V-0001,light_jet,2027-02-14T10:00:00-08:00,2027-02-15T10:00:00-08:00,Booked
```

This example is a test fixture, not a real reservation. Unique visit codes must be `V-` followed by 3–8 digits. Categories: `light_jet`, `midsize_jet`, `large_jet`. Status: `Booked` or `Estimated`. Departures must follow arrivals. Local timestamps are interpreted in Los Angeles time. Names, tail numbers and extra columns are rejected. Uploading changes the review version but never rewrites P2/P3 outputs.

## Implementation and verification

- `static/templates/`: translated supplied layouts, using native `<template>` elements so table rows render correctly.
- `static/design.js`: safe DOM binding and model-to-page presentation.
- `static/design-tools.js`: daily what-if, seven-file import and export controls using existing validated endpoints.
- `readiness/design_view.py`: separate hourly illustration and preparation checklist adapter.
- `app.py` / `readiness/storage.py`: authenticated role checks, CSRF, freshness checks and durable UI state.
- `scripts/import_rampready_design.py`: repeatable translation from the original design directory, authoring only.

Validation: **97 Python tests passed**, both browser scripts passed Node syntax checks, and browser tests exercised sign-in, scenarios, delayed departures, saved plan approval, booking upload/checks, ramp checks and a one-day surge with carryover. Tests confirm adapters do not mutate producer data and old APIs remain available.

All seven pages were captured at **1440 × 1000** and **390 × 844** CSS viewports (full-page image height varies), visually compared with rendered supplied templates, then corrected. Final page scroll width equals viewport width in every case and Mona Sans was loaded. Wide data tables scroll inside their panels and have a phone hint. The original booking reference itself overflows the mobile document; this implementation fixes that defect.

Intentional visual differences are model-driven wording, generated versus booked status, longer provenance notes, more rows with pagination, provisional labels, missing-value states, and the new collapsed planning tools. No claim of pixel-identical sample content is made. Local screenshot gallery and comparison images are saved in the task’s `outputs/design-qa/` directory, separate from the app source.

No branch was pushed and no PR was created for this design change.
