# Data sources — The Intelligent FBO (Super Bowl LXI parking readiness)

Consolidated from the team's three Step 2 contributions. Each source keeps
its original ID prefix (ALAN-, NAZAR-, no prefix for Elia's L/B/F series)
so references in code, `assumptions.csv`, and commit history stay valid.
Classification follows the project's four-way vocabulary: **public data**,
**benchmark estimate**, **synthetic**, or **assumption**.

Full detail, reproduction commands, and validation reports live in each
owner's own doc — this file is the merged index:
- `alan/docs/data_sources_alan.md` — FAA 5010 master record
- `alan/docs/data_sources_nazar.md` — LAX apron/ramp area
- `alan/elia_output/data_sources_lawa_bts.md` — LAWA TCOM + FAA OPSNET + BTS
- `alan/docs/super_bowl_surge_benchmark.md` — Super Bowl LVI/LVII/LVIII surge benchmark (Step 4)
- `alan/docs/lax_private_capacity_and_cost_research.md` — LAX private-aircraft capacity and landing cost research (Items 1 & 2)
- `alan/docs/vip_tfr_operational_impact.md` — VIP/high-security TFR operational impact (Item 5)

---

## 1. FAA Airport Master Record (5010) — Alan

| ID | Source | What it supports | Confidence |
|---|---|---|---|
| ALAN-S01 | FAA Airport Master Record (5010), effective 2026-10-01, via ADIP | Ownership, acreage, elevation, all 4 runway specs (length/width/surface/PCN), control tower status | High |
| ALAN-S02 | AirNav LAX page (secondary aggregator, cross-check only) | Confirms runway specs exactly; confirms no based-aircraft count published | High (as a corroboration, not an independent source) |

**Key finding**: LAX's based-aircraft count is **not available** in either source — both leave it blank/self-reported-empty. Checked and ruled out as a gap-filling path: FAA's National Based Aircraft Inventory Program (login-gated, no public lookup), the CA Public Use Airport List (no based-aircraft field), and a LAWA FBO lease PDF (unreadable scan). Treated as a documented gap, not filled with a guessed number.

Archived sources: `alan/data/raw/alan_5010/`.

## 2. LAX apron/ramp area — Nazar

| ID | Source | What it supports | Confidence |
|---|---|---|---|
| NAZAR-S01 | LAWA Board report, 2020-11-19 | Atlantic leased land: 666,502.84 sq ft; Signature: 527,795 sq ft land / 128,400 sq ft building | High for historical lease facts; neither figure is apron-only |
| NAZAR-S02 | Atlantic hangar/office initial study, 2013-09-12 | Proposed building area, partial site plan | High for the documented proposal; not proof of as-built |
| NAZAR-S03 | LA city administrative report, 2014-04-01 | Atlantic leasehold cross-check: 666,503 sq ft / 15.3008 acres | High, historical cross-check only |
| NAZAR-S04 | FAA airport diagram, cycle 2610 | FBO vicinity context | High for context; no surveyed FBO boundary |
| NAZAR-S05 | LAWA Movement Area Map 2026 v5 | Identifies Atlantic/Signature FBO locations | High for identification; schematic only |
| NAZAR-S06 | Signature LAX operator page (FAQ) | Claims 200,000-300,000 sq ft ramp | Low — FAQ context is ambiguous (mentions Las Vegas nearby) |
| NAZAR-S07 | AIN historical report, 2008-02-08 | Reports a 13-acre Atlantic ramp at LAX | Medium as historical statement, low as a present-day proxy |
| NAZAR-S08 | Atlantic LAX operator page | Operator identity, PPR advisories | Qualitative context only |
| NAZAR-S09 | Atlantic-hosted FAA diagram | Stale chart; superseded by NAZAR-S04 | Low |

**Key finding**: no precise current apron-only area was established. **Recommended reference facility: Atlantic Aviation LAX** (stronger public evidence than Signature). Historical ramp benchmark: **13 acres / 566,280 sq ft (NAZAR-S07, 2008)** — carried forward only as a low-confidence optional proxy, not current measured capacity.

Archived sources: `alan/data/raw/nazar_apron/`.

## 3. LAWA monthly/annual movements + FAA OPSNET + BTS — Elia

| ID | Source | What it supports | Confidence |
|---|---|---|---|
| L1 | LAWA Traffic Comparison (TCOM), monthly | LAX private-aviation movements (air taxi, GA; air carrier and military excluded), Jan 2015-Aug 2026 | High |
| L2 | LAWA Ten Year Summary of FAA Aircraft Movements | Annual totals 2008-2025, validates L1 | High |
| L3 | LAWA FBO rental car services page | Checked, not used — car-rental data, not aircraft activity | n/a |
| B1 | BTS T-100 Air Carrier Statistics | Checked, not usable — covers certificated airlines only, not GA/air-taxi | n/a |
| F1 | FAA ATADS/OPSNET standard report | LAX monthly tower ops 2015-2025; **daily** ops at LAX, VNY, BUR, HHR, LGB, SMO for Jan 30-Feb 26 of 2019, 2022, 2023, 2024 | High |

**Validation**: L1 reconciles exactly to L2's official annual totals in 10 of 11 years; the one gap (2018) is explained exactly by OPSNET's revised preliminary-data correction. 123 of 132 months match OPSNET exactly.

**Key findings**:
- Current level (2025): 22,041 air taxi + 12,234 GA movements/year at LAX (~94/day combined).
- **Structural COVID-era break**: GA+air-taxi fell from ~265/day (2015) to ~100/day (2024-2025). Pre-2020 and post-2022 levels are not comparable without a level shift — see `assumptions.csv` row `ALAN-baseline_training_window`.
- **Monthly data cannot see the Super Bowl LVI surge** (Feb 2022 only +6.8% vs adjacent months, within normal year-to-year noise). This motivated the daily OPSNET pull (F1).

**Super Bowl LVI, measured via daily OPSNET data (F1)** — this is the strongest Step 4 evidence the team has, and should be read alongside `alan/docs/super_bowl_surge_benchmark.md`:
- Six LA-area airports combined: air-taxi operations ran **+8% excess** above weekday/control-year baseline over the 5-day event window (Thu-Mon).
- **LAX alone: +15% excess.** BUR +18%, HHR +14%, LGB +118% (small base), VNY -10%, SMO -42%.
- Daily shape, all six airports: **+25% Friday, +6% Saturday, +11% game day, +33% Monday** (post-game departure wave).
- Limitation: one event, during post-COVID recovery; counts tower operations (takeoffs/landings), not parked aircraft; no aircraft-size split. This measured order of magnitude is well below the "2-3x normal" business-jet benchmark reported for a 2026 Bay Area mega-event (different event type, business jets only).

Reproduce: `python alan/elia_output/scripts/fetch_opsnet.py`, `python alan/elia_output/scripts/analyze_superbowl_lvi.py`. Outputs in `alan/elia_output/data/processed/`: `opsnet_lax_monthly.csv`, `opsnet_daily_superbowl.csv`, `opsnet_vs_lawa_crosscheck.csv`, `superbowl_lvi_surge.csv`, `superbowl_lvi_daily_profile.csv`.

---

## Cross-cutting limitations (apply across all three contributions)

- All FAA/LAWA/OPSNET movement counts are **airport-wide**, not FBO-specific or parking-occupancy data. Converting to FBO-scoped parking estimates requires the market-share and dwell-time assumptions documented in `assumptions.csv`.
- FAA's operational categories (air taxi, GA) do not split by aircraft size; the light/midsize/large jet mix used downstream is a benchmark assumption, not an FAA-reported breakdown.
- 2020-2022 is excluded from ordinary-week trend training throughout (COVID), and 2016-2019 is further excluded from the live baseline specifically due to the structural pre/post-COVID level break (see `assumptions.csv`).
