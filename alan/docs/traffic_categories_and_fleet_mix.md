# Traffic categories, fleet mix, and FBO share

Prepared by Alan, per Nazar's request: "Document which traffic categories
we include, what other activity they may contain, and the evidence for
aircraft-size mix and our FBO's share. Keep airport operations separate
from aircraft visits... Mark unsupported values as assumptions."

This doc describes the project **as it currently stands**, including a
known scope inconsistency (section 1.4) — it does not resolve that
inconsistency or force a single team decision.

## 1. Traffic categories

FAA/LAWA/OPSNET movement data classifies every tower operation into one of
four categories. Military is excluded from this project throughout and is
not discussed further.

### 1.1 Part 121 — air_carrier

**FAA definition**: scheduled, large-aircraft commercial air transportation
(14 CFR Part 121) — the airlines. Includes nearly all mainline passenger
and cargo flights at a hub like LAX.

**Project scope**: excluded entirely. LAX's Part 121 traffic has no
plausible path to this fictional FBO's ramp — airlines use terminal gates,
not FBO ramps.

**Contamination beyond the textbook definition**: historically, some
scheduled small-aircraft commuter flights were certificated under Part 135
rather than 121. The FAA's 1997 "Commuter Rule" (14 CFR 119, effective
1997) moved most scheduled passenger operations using aircraft with 10+
seats or turbojet power into Part 121, narrowing what stays in Part 135.
This is relevant context for section 1.2's boundary, not for 121 itself.

### 1.2 Part 135 — air_taxi

**FAA definition** (14 CFR 119.3, 110.2): on-demand charter AND scheduled
commuter operations, specifically scheduled passenger service operating
up to 5 round trips per week between two or more points according to
published schedules, using either non-turbojet aircraft with a maximum of
9 passenger seats, or any rotorcraft. On-demand (charter, air ambulance,
cargo) has no seat/schedule ceiling in the same way.

**What this means for "air_taxi" as a label**: it is not purely "private
charter jets." It legally bundles:
- On-demand charter (the category most people picture)
- Scheduled small commuter/commuter-rotorcraft service (airline-like,
  just below the Part 121 schedule/size threshold)
- Air ambulance and other on-demand operations when flown under Part 135
  certification

**Project scope**: the project initially considered including Part 135
(see the original 47/33/20-style broader scope and Marvin's early
provisional work), then **explicitly narrowed to Part 91 only** ("please
do not include charter flights, only private" — Alan, mid-project). Part
135/air_taxi is excluded from the current baseline (`alan/baseline.csv`)
and from Marvin's `private_only_review/` folder.

**Real Part 135 records do exist in the repo, kept deliberately
separate**: Elia's `alan/elia_output/data/processed/opsnet_lax_daily.csv`
already has a full daily `air_taxi` column (FAA ATADS/OPSNET,
`verified_public`) for the same 2015-2025 window as the GA data,
cross-checked 132/132 months against `opsnet_lax_daily_check.csv`.
`alan/scripts/build_historical_traffic_air_taxi.py` turns this into
`alan/data/processed/historical_traffic_air_taxi_interim.csv` using the
same daily-direct method as the Part 91 pipeline. **This output does not
feed `alan/baseline.csv`** and is not meant to — it exists only for
comparison/context, e.g. grounding the Medium forecast scenario's
air-taxi-derived event-size uplift (+15.5%, confirmed with Marvin) in a
real measured air-taxi baseline instead of an unsourced number.

### 1.3 Part 91 — general_aviation

**FAA definition**: the general operating and flight rules that apply to
virtually all non-commercial flying — there is no single certificate
describing "Part 91 operators" the way Part 121/135 describe airlines and
charter operators. It is the default rule set for anyone not operating
under another part.

**What this means for "general_aviation" as a label** — this is the
single biggest source of contamination in the project's numbers, because
FAA/LAWA movement counts report one `general_aviation` total with no
further split:
- **Personal/business flying** — the use case this project actually cares
  about (an owner or company flying their own aircraft to the Super Bowl)
- **Flight training** — instructional flights, touch-and-goes, practice
  approaches. The FAA's own Student Pilot/private pilot guidance (e.g.
  FAA-H-8083-27A) confirms training flights are flown and logged under
  Part 91 like any other GA flight. A training-heavy local airport's GA
  count can be dominated by touch-and-go patterns that never involve an
  FBO ramp at all.
- **Recreational/personal flying** that never touches an FBO (based
  owner flying their own hangar, local sightseeing, etc.)
- **Business aviation support flights** — positioning, maintenance,
  ferry flights — that generate a movement but not a "visit" with a
  passenger needing FBO services.

**Concrete sourced example of positioning-flight contamination**: Atlantic
Aviation's own 2013 LAX hangar project filing
(`alan/data/processed/alan_5010/` chain of custody; see Item 1a in
`alan/docs/lax_private_capacity_and_cost_research.md`) states the explicit
purpose of basing more aircraft at LAX was to let owners **stop flying
in empty to position the aircraft before a passenger trip** — cutting
operations from 4 per customer trip (fly in empty, fly out, fly in, fly
out with passengers) down to 2 (based at LAX, fly out and back with
passengers only). This is a real, government-filed example of exactly the
positioning-flight contamination described above, not a hypothetical.

**Project scope**: this is the category the project's narrowed, private-
only baseline is built on (`alan/scripts/build_historical_traffic.py`,
`alan/scripts/build_baseline.py`). The project does **not** have a way to
strip training/positioning/non-FBO flights out of the raw `general_
aviation` movement counts — LAWA/OPSNET do not report that sub-split
publicly. This means the baseline's `general_aviation` input is a ceiling
on true private, FBO-relevant traffic, not a clean measurement of it. This
is a known limitation, carried forward from `data_sources.md`'s
cross-cutting limitations section, stated here explicitly rather than
implicitly.

### 1.4 Known scope inconsistency across the project

**Update**: Alan's side of this inconsistency is now fixed. `alan/scripts/
build_historical_traffic.py` and `build_baseline.py` were switched to
Marvin's verified daily Part 91 `general_aviation`-only extract
(`private_only_review/ga_only_daily_source.csv`), dropping `air_taxi`
entirely, and now share the same combined
private-eligible-fraction x FBO-capture-share figure as Marvin's
`private_only_review/` work (`EFFECTIVE_SHARE` in `build_baseline.py`;
`ALAN-fbo_market_share` in `assumptions.csv`) instead of a
separately-chosen flat share applied to a combined GA+air-taxi total.

One inconsistency remains, and this doc does not fix it (outside this
doc's scope — a team/Marvin decision):

| File | Scope used |
|---|---|
| `alan/baseline.csv`, `alan/scripts/build_baseline.py` | **Fixed**: Part 91 (general_aviation) only, combined private-eligible x FBO-capture share |
| `marvin/person_2_forecasting/private_only_review/*` | Part 91 only, via `private_eligible_ga_fraction` applied on top of the raw `general_aviation` count |
| `marvin/person_2_forecasting/demand_predictions.csv` (live dashboard-facing file) | Still uses the **older mixed Part 91 + Part 135 scope** ("25% air-taxi eligibility"-style assumption), not the private-only numbers from Marvin's own `private_only_review/` folder |

Resolving that last row is a team decision outside this doc's scope (see
the repo audit finding from earlier in the project, "issue number 1/2"
context).

## 2. Aircraft-size mix (47% light / 33% midsize / 20% large)

**Evidence search performed**: the FAA/TetraTech "General Aviation and
Part 135 Activity Survey" (the official annual survey of U.S. GA fleet
activity — the right government source family for this question) was
checked directly. Its publicly posted tables (checked: CY2005/CY2006
chapters, and the survey's general methodology) break turbine aircraft
down by engine count and, in some years, by seat count (e.g. "1-12 seats"
vs "13+ seats" for twin turboprops) — **not** by a light/midsize/large
weight class. Separately, the FAA's ATC weight-class terminology (Small
≤41,000 lb / Large 41,000-300,000 lb / Heavy ≥300,000 lb, from air traffic
control separation rules) uses different category names and boundaries
than the project's light/midsize/large business-jet categories, and isn't
a fleet-mix survey in the first place — it would be the wrong source even
if the names matched.

**Conclusion**: no official light/midsize/large (or equivalent) weight-
class breakdown for the GA fleet was found in this pass, consistent with
the team's earlier findings (`ELIA-mix_light/midsize/large`, `MARVIN-mix-
light/midsize/large` are already labeled "not FAA aircraft observations").

**Per Nazar's instruction, this is marked as an unsupported assumption and
not pursued further.** The 47/33/20 split should continue to be treated
as a team-chosen illustrative mix, not a measured one.

## 3. FBO market share (currently 20%)

**Evidence search performed**: the project already has real, government-
sourced data comparing the two actual incumbent FBOs at LAX (from Nazar's
apron research, `NAZAR-S01`, a 2020-11-19 LAWA Board report):

- Atlantic Aviation leased land: **666,502.84 sq ft**
- Signature Flight Support leased land: **527,795 sq ft** (128,400 sq ft
  building)

This gives Atlantic roughly **55.8%** and Signature roughly **44.2%** of
the two real incumbents' combined leased footprint — real evidence, but
it answers a different question than "what share would a new, third,
fictional FBO capture," since the fictional FBO has no comparable lease
record to measure.

A further search for Signature's own LAX-specific square footage (to
sharpen this ratio) and for any FAA/LAWA source on *traffic* share (as
opposed to land share) by FBO came up empty — searches returned only
Signature's Van Nuys (~1,170,000 sq ft, a 2013 figure) and Stewart, NY
figures, neither comparable to LAX. No public source reports FBO-level
traffic share (operations or based-aircraft count by FBO) at LAX at all.

**Conclusion**: the real Atlantic/Signature land-share ratio above is
useful context (it shows the two real incumbents are not evenly split
either — roughly 56/44, not 50/50), but it cannot be converted into a
hard number for a fictional third entrant's traffic share without a
further assumption about that FBO's relative size, which is exactly the
kind of extra assumption Nazar's instruction says not to force. **The FBO
capture share is marked as an unsupported assumption** and not pursued
further, now with the added context above on what evidence does and
doesn't exist.

**Update — the two shares are now unified**: this used to be two
materially different numbers (Alan's flat 20% applied to the combined
GA+air-taxi total vs. Marvin's 50% eligibility x 20% capture = 10% applied
to GA alone). They are now one shared figure:
`ALAN-fbo_market_share` in `assumptions.csv`
(`EFFECTIVE_SHARE` in `build_baseline.py`) = `PRIVATE_ELIGIBLE_FRACTION`
(0.50, Marvin's number) x `FBO_CAPTURE_SHARE` (0.20) = **0.10**, with a
**0.05-0.15 low/high range** taken from Marvin's own
`private_eligibility_sensitivity.csv` at the 25%/75% eligibility points
(the capture share itself has no comparable sensitivity table yet, so it
is held fixed). Both factors remain labeled `assumption`, unsupported by
independent evidence, per the conclusion above — this update removes the
*inconsistency* between pipelines, it does not newly evidence either
factor.

## 4. Operations vs. aircraft visits

**FAA/LAWA/OPSNET movement counts are operations, not aircraft visits.**
One aircraft landing and later departing generates **two** recorded
operations (one arrival, one departure) — not one "visit." This applies
to every raw count used anywhere in this project (`lax_monthly_movements.
csv`, OPSNET pulls, LAWA TCOM reports).

**Conversion**, under the simplest possible assumption (every aircraft
that arrives also departs within the same observation window, i.e. no
multi-day stays crossing a period boundary):

```
aircraft_visits ≈ operations / 2
            ≈ (arrivals + departures) / 2
```

Caveats:
- This undercounts true visit duration information — it tells you how
  many aircraft came and went, not how many were present on any given
  day (occupancy).
- It breaks down at period boundaries for multi-day stays: an aircraft
  that arrives on day N and departs on day N+3 contributes one arrival
  operation to day N's count and one departure operation to day N+3's
  count — the two halves of that visit are not even in the same daily
  bucket, so simple same-day division understates visits at a daily
  grain and must not be used to estimate daily occupancy.
- **Occupancy (parking_units) is a different, correct calculation already
  used in this project**: `alan/scripts/build_baseline.py` computes
  `parking_units = arrivals_fbo x avg_dwell_days` (Little's Law), which
  correctly derives how many aircraft are present on an average day from
  the arrival rate and average length of stay — it does not divide
  operations by two or treat operations as visits. This is the right
  approach, not an error to fix.

### 4.1 Audit of existing files for operations/visits conflation

Checked: `alan/scripts/build_historical_traffic.py`,
`alan/scripts/build_baseline.py`, every CSV header under
`alan/elia_output/data/processed/`, `marvin/person_2_forecasting/` (all
files, including `private_only_review/`), and the project's docs
(`alan/docs/*.md`, `data_sources.md`).

**No conflation found.** Every file consistently uses `arrivals` and
`departures` as separate operation counts (never a combined "visits"
column), and the one place occupancy is computed
(`build_baseline.py`'s `parking_units`) uses the correct Little's Law
relationship rather than dividing operations by two. Marvin's
`aircraft_remaining_end_day` column (in `daily_private_only_plan.csv`)
is also a correctly-distinct occupancy figure, not an operations count
mislabeled as a visit count.

Since no conflation was found, no code or data fix was needed for this
section — the audit requested in the spec is recorded here as a result
(clean), not skipped.

## 5. Summary of findings

| Item | Resolution |
|---|---|
| Traffic categories (121/135/91) | Documented, including Part 91's training/positioning contamination and Part 135's commuter-vs-charter split — new detail beyond what was previously in the repo |
| Scope inconsistency (91-only vs mixed) | **Fixed on Alan's side** (build_historical_traffic.py / build_baseline.py now Part 91-only, via Marvin's verified daily GA extract); Marvin's live `demand_predictions.csv` remains mixed-scope — outside this doc's scope, see section 1.4 |
| Aircraft-size mix (47/33/20) | No official evidence found (FAA GA Survey checked directly); confirmed as an unsupported assumption, not pursued further |
| FBO market share | Real Atlantic/Signature land-share evidence exists (~56/44) but doesn't resolve a fictional entrant's share; still an unsupported assumption, but Alan's and Marvin's two previously-divergent figures are now unified into one shared number (`ALAN-fbo_market_share` = 0.10, range 0.05-0.15) — see section 3 |
| Operations vs. visits | Explained with conversion math and caveats; full-repo audit found no existing conflation, so no fix was required |
