# AGENTS.md — RampReady: The Intelligent FBO, Super Bowl LXI

> Read in full before any action. Single source of truth. If information is missing, ask your human instead of inventing.
> This is the English working version of the team's PROJECT_PLAN.md, with the post-review decisions (D1–D6) already merged in.
> Also read `coordination/PROTOCOL.md` (how to report) and `coordination/BOARD.md` (current tasks).

## 0. Context

- **Event:** SpartHill Hacks, NCBAA track "The Intelligent FBO". **One day.** Team of 4, each piloting an AI agent.
- **Brief:** an AI tool that helps an FBO at an LA-area airport prepare for demand during **Super Bowl LXI** week (Sunday **Feb 14, 2027**, SoFi Stadium, Inglewood).
- **Chosen focus: PARKING.** When does aircraft parking demand exceed the FBO's capacity?
- **Sponsor principle:** *AI assists. People decide.*

### Jury checklist
The prototype must show: (1) an ordinary-week **baseline**, (2) a Super Bowl week **forecast**, (3) a **recommended preparation plan**, (4) how the plan **changes under low / medium / high** scenarios.
Also required:
- Clearly identified assumptions on **arrivals, fuel purchases, parking duration, available resources**.
- Stadium attendance alone does **not** establish aircraft demand. We model demand drivers.
- **Impact:** forecast accuracy and/or improvement in parking capacity, staffing, delays.
- **Humans in command:** privacy, explained uncertainty. The tool **plans**; it authorizes **no** aircraft movement and replaces **no** safety procedure.
- Stretch goal: LA 2028 Olympics adaptation.
- Jury question: "What decision should your AI never be allowed to make?"

Judging: *Innovation + accuracy / Practical preparation / Privacy, uncertainty and humans in command.*
Deliverables: *Working prototype (planning workflow) / 3-minute pitch (user, problem, value) / Impact + disruption (baseline comparison and a demand spike or delay).*

## 1. Product

**RampReady** helps an FBO operations manager see, hour by hour, when the ramp will saturate during Super Bowl week, with an uncertainty range, three scenarios and an action plan that **only the manager** approves.

- **Persona:** Maria, Operations Manager at an FBO in Van Nuys. In January she must decide how much overflow parking to book, how many ramp agents to add, when to switch to mandatory reservations. Today: gut feel plus memory of Super Bowl 2022.
- **FBO:** *Horizon Ridge Aviation (fictional)* at Van Nuys Airport (KVNY). Never use a real FBO's name or brand. All capacities are invented and documented as assumptions.

| Day | Date | Role in the week |
|---|---|---|
| Tue | Feb 9, 2027 | Ramp-up begins |
| Wed | Feb 10 | Ramp-up (media, sponsors) |
| Thu | Feb 11 | Strong arrivals |
| Fri | Feb 12 | Arrival peak |
| Sat | Feb 13 | Arrival peak + **occupancy peak** |
| Sun | Feb 14 | **Game.** Few arrivals, departures from the evening |
| Mon | Feb 15 | **Departure wave** |

Baseline = the same calendar week (Tue → Mon) without the event.

## 2. Model (simple, explainable, defensible). No deep learning.

### 2.1 Arrivals
```
arrivals(day, hour, scenario) = baseline_day(day) × event_multiplier(day, scenario) × hourly_profile(hour, day)
event_multiplier(day, scenario) = 1 + (regional_extra_peak(scenario) × extra_demand_day_shape(day) × fbo_market_share(scenario)) / baseline_day(day)
```
The multiplier is **not** derived from attendance. Demand drivers:

| Driver | Explanation | Effect |
|---|---|---|
| High-value clientele | Corporate guests, sponsors, celebrities, media | Base of the multiplier |
| Qualifying teams' origin | Distant fans → more jets. Teams known only ~2 weeks before | Main scenario lever |
| FBO market share | Demand splits across VNY, Hawthorne, Long Beach, Santa Monica, Burbank, etc., and several FBOs per airport | We capture a small share |
| External constraints | Slot reservation programs / airspace restrictions usual for such events | Caps and shifts demand |

Baseline daily arrivals at our FBO (assumption): Tue–Fri 14, Sat 10, Sun 12, Mon 14.
`extra_demand_day_shape` (assumption, **D3**): Tue 0.2, Wed 0.4, Thu 0.7, Fri 1.0, Sat 1.0, Sun 0.1, Mon 0.0.

### 2.2 Length of stay → occupancy (core of the parking focus)
```
occupancy(h) = occupancy(h-1) + arrivals(h) − departures(h)
```
Departures follow a length-of-stay distribution by arrival day:

| Arrival | Leaves same day | Leaves Sun night / Mon | Stays 3+ days |
|---|---|---|---|
| Ordinary week | 50% | n/a | 10% (other 40%: one night) |
| Tue–Wed (event) | 15% | 60% | 25% |
| Thu–Sat (event) | 10% | 80% | 10% |
| Sun (event) | 30% | 70% | 0% |

The departure wave is concentrated **Sun 20:00 → Mon 14:00**. `departure_wave_hourly_profile` (**D3**) has two humps: Sun 22:00–Mon 01:00 and Mon 09:00–12:00.

**D4 — served vs unserved:** demand above available capacity is not parked. Occupancy output also carries `occupancy_unserved_up_p50` / `_p90` = parking units of demand that would have to be redirected.

### 2.3 Aircraft size (parking AND fuel), in parking units (PU)

| Class | Examples | PU | Avg gallons bought at departure |
|---|---|---|---|
| Light | Citation CJ, Phenom 300 | 1.0 | 150 |
| Midsize / super-mid | Challenger 350, Citation Latitude | 1.5 | 450 |
| Large / long-range | Gulfstream G650, Global 7500 | 2.5 | 1,200 |

Ordinary mix: 45% light / 40% mid / 15% large. Super Bowl mix: depends on scenario (2.5). **D3 split rule:** mid stays 40%, light = 60% − large.
**D5:** display unit is "PU"; column suffix stays `_up`.

### 2.4 Uncertainty
Never a single number. Per hour: **P10 / P50 / P90** from ~1,000 Monte Carlo draws, varying the multiplier (lognormal around the scenario value), the length-of-stay split (±10 points) and the aircraft mix.

**D2:** occupancy percentiles must be computed **per draw then aggregated**, never by summing arrival percentiles. `forecast()` attaches the raw draws as `df.attrs["sims"]` (numpy array, runs × hours × classes); `compute_occupancy` cumulates per draw, then takes percentiles.

### 2.5 Scenarios

| Parameter | Low | Medium | High |
|---|---|---|---|
| Regional extra demand at peak (aircraft/day, whole region) | 300 | 550 | 850 |
| FBO market share (**D1**) | 1.5% | 1.6% | 1.7% |
| Qualifying teams | 1 local + 1 nearby | 1 local + 1 distant | 2 distant |
| Large-jet share | 25% | 35% | 45% |

Calibration target (P50 peak): low ≈ 90% of 40 PU; medium ≈ 55–60 PU; high > 65 PU (overflow insufficient). Values are invented, must appear in `docs/ASSUMPTIONS.md` and in the app's Assumptions tab, and be editable (sliders).

### 2.6 FBO resources (assumptions)

| Resource | Ordinary | Reinforcement option |
|---|---|---|
| Main ramp | 40 PU | none |
| Overflow (agreement with airport / neighbouring FBO) | 0 PU | up to +25 PU, booked in advance |
| Ramp agents per shift | 6 | up to 12 |
| Fuel trucks | 3 | +2 rented |
| Fuel delivery per truck (**D3**) | 8,000 gal/day | |
| Staffing rule | 1 agent per 3 movements/hour | |

## 3. Recommended plan (transparent rules)

1. **Overflow:** if `occupancy_P90 > capacity` at any hour → book `max(occupancy_P90) − capacity` PU of overflow, rounded up to 5 (capped at max overflow; flag the remainder).
2. **Mandatory reservations:** if `occupancy_P50 > 85% of capacity` → switch to mandatory reservations from that day.
3. **Staffing:** agents per hour = `ceil(movements_P90(h) / 3)`, capped at 12. Flag hours above the planned crew.
4. **Fuel:** daily volume = `Σ departures × avg_gallons(class)`, P50 and P90. Flag if the peak exceeds truck delivery capacity.
5. **Critical windows:** list 2-hour windows with occupancy > 95%.

Each recommendation shows the **rule that produced it** ("because P90 exceeds capacity by 14 PU on Sat 18:00"), a **confidence level**, and a status **D6:** `PROPOSED` → `APPROVED` / `MODIFIED` / `REJECTED` by a human.

## 4. Impact

### 4.1 Forecast accuracy (synthetic backtest)
A hidden "actual" week is generated with parameters **unknown to the model** (+ noise). Metrics: **MAPE** on daily arrivals, **% of hours where actual falls inside P10–P90** (target ≈ 80%), **peak occupancy error**. Be honest: validation on synthetic data; with real history (Super Bowl LVI, LA 2022) the same method applies.

### 4.2 Naive plan vs RampReady plan (same simulated week)

| | Naive | RampReady |
|---|---|---|
| Parking | 40 PU + flat 20% margin | Overflow sized on P90 |
| Staffing | Normal crew + 2 | Hourly reinforcement from forecast |
| Mandatory reservations | No | Yes, past threshold |

Metrics: hours over capacity, aircraft to redirect (unserved PU), staff-hours short and in excess, peak occupancy rate. Key visual: both occupancy curves vs the capacity line.

### 4.3 Disruption (required)
At least 2 cases: **fog** (Saturday arrivals shifted by 6 h, Sunday departures shifted); **extended stay** (30% of Sunday-night departures stay until Monday noon); optional **airspace restriction** (no movement for 3 h). The plan recomputes and the app shows **what changed**.

## 5. Humans in command & responsible AI

Absolute rules (coded AND displayed):
- The tool **never refuses, accepts, moves or authorizes any aircraft.** It flags risks.
- It **never assigns spots** to specific aircraft.
- **No passenger data.** Aircraft counted by class only. Never tail numbers, names, owners, individual flight plans.
- **Always show uncertainty** (P10/P50/P90) and assumptions.
- Every recommendation passes a **human approval gate** (APPROVED / MODIFIED / REJECTED + note), logged.

**LLM briefing:** plain-language summary written **only from computed numbers** (JSON in the prompt). Forbidden: inventing figures, recommending to refuse a specific aircraft, mentioning people. No API key → template fallback. The app must work without an LLM.

**Answer to the jury question:** "Our tool never decides which aircraft is accommodated, refused, moved or allowed to move. It tells Maria: *Saturday between 2 PM and 8 PM, you will likely be 8 to 15 spots short.* She decides who is accommodated, who is redirected and how, within the airport's safety procedures. Any decision touching an aircraft, a crew or passengers stays human."

## 6. Stack & structure

Python 3.11+, `pandas`, `numpy`, `plotly`, `streamlit`, `pyyaml`, `pytest`; optional `anthropic`. No database: CSV + one YAML.

```
rampready/
├── AGENTS.md  CLAUDE.md  README.md  requirements.txt  run.sh
├── coordination/        BOARD.md, PROTOCOL.md, status/<role>.md
├── config/assumptions.yaml
├── data/generate.py  baseline_week.csv  event_hourly.csv  holdout_actual.csv
├── model/forecast.py  occupancy.py  recommend.py  impact.py  disruption.py
├── app/streamlit_app.py  briefing.py
├── docs/ASSUMPTIONS.md  DATA_CONTRACT.md  RESPONSIBLE_AI.md  LA2028.md
├── tests/
└── pitch/pitch_script.md
```

## 7. Data contract (DO NOT CHANGE without telling the whole team)

All times LA local, ISO `YYYY-MM-DDTHH:00`.

**`config/assumptions.yaml`**: every parameter of sections 2 and 2.6. **No numeric constant hard-coded anywhere else.**

**`data/baseline_week.csv`, `data/event_hourly.csv`**

| column | type | description |
|---|---|---|
| `timestamp` | str | local hour |
| `scenario` | str | `baseline` / `low` / `medium` / `high` |
| `arrivals_p10` / `arrivals_p50` / `arrivals_p90` | float | forecast arrivals |
| `departures_p50` | float | forecast departures |
| `arrivals_light` / `arrivals_mid` / `arrivals_large` | float | P50 split |

**`model/occupancy.py` → DataFrame**

| column | type |
|---|---|
| `timestamp`, `scenario` | str |
| `occupancy_up_p10` / `_p50` / `_p90` | float (PU) |
| `occupancy_unserved_up_p50` / `_p90` (D4) | float (PU) |
| `capacity_up` | float |
| `movements_p90` | float |
| `staff_needed` | int |
| `fuel_gal_p50` / `fuel_gal_p90` | float |

**`model/recommend.py` → list of dicts**

| field | type | example |
|---|---|---|
| `id` | str | `REC-003` |
| `category` | str | `parking` / `staffing` / `fuel` / `policy` |
| `action` | str | "Book 15 PU of overflow from Feb 11 to Feb 15" |
| `rule` | str | "P90 occupancy exceeds 40 PU by 14 PU on 02/13 18:00" |
| `confidence` | str | `low` / `medium` / `high` |
| `scenario` | str | |
| `status` | str | `PROPOSED` / `APPROVED` / `MODIFIED` / `REJECTED` |
| `human_note` | str | empty by default |

**Frozen public signatures**
```python
# model/forecast.py
def forecast(scenario: str, cfg: dict, n_sims: int = 1000, seed: int = 42) -> pd.DataFrame: ...  # attrs["sims"] (D2)
# model/occupancy.py
def compute_occupancy(forecast_df: pd.DataFrame, cfg: dict) -> pd.DataFrame: ...
# model/recommend.py
def recommend(occupancy_df: pd.DataFrame, cfg: dict) -> list[dict]: ...
# model/impact.py
def compare_plans(scenario: str, cfg: dict) -> dict: ...
def backtest(cfg: dict) -> dict: ...  # {"mape": float, "coverage_p10_p90": float, "peak_error_up": float}
# model/disruption.py
def apply_disruption(forecast_df: pd.DataFrame, kind: str, cfg: dict) -> pd.DataFrame: ...  # kind: fog | extended_stay | airspace
```

## 8. Roles. Golden rule: each agent edits ONLY its own paths. One branch per role. A human reviews every merge.

**`data` — OpenCode + Gemini.** Owns `config/`, `data/`, `docs/ASSUMPTIONS.md`, `docs/DATA_CONTRACT.md`.
YAML with every value; seeded, reproducible `data/generate.py` producing the 3 CSVs; public orders of magnitude (LA business aviation traffic, Super Bowl LVI 2022 reports) to justify assumptions, with sources in ASSUMPTIONS.md; **stub CSVs in contract format by H+1**.

**`model` — Codex.** Owns `model/`, `tests/`.
The 5 modules with frozen signatures. Tests: occupancy never negative; P10 ≤ P50 ≤ P90; conservation (arrivals − departures = change in occupancy); high ≥ medium ≥ low.

**`app` — Claude Code (also supervisor and integrator).** Owns `app/`, `requirements.txt`, `coordination/`, final integration.
Streamlit tabs: 1 Week view (baseline vs Super Bowl, P10–P90 band, capacity line, scenario selector) · 2 Recommended plan (approve / modify / reject + note, decision log) · 3 Scenarios side by side · 4 Impact (naive vs RampReady, backtest) · 5 Disruption (before / after) · 6 Assumptions & limits (YAML table + sliders) · 7 Briefing (LLM or template). Permanent banner: *"Planning aid only. Authorizes no aircraft movement. Final decision: the manager."* Codes against stub CSVs until the model is ready.

**`docs` — OpenCode + Copilot.** Owns `README.md`, `run.sh`, `docs/RESPONSIBLE_AI.md`, `docs/LA2028.md`, `pitch/`.
README kept accurate; `run.sh`; check `pip install -r requirements.txt && streamlit run app/streamlit_app.py` on a clean venv; RESPONSIBLE_AI.md from section 5; LA2028.md (17-day window, several venues, longer stays, multiple peaks → parameter changes only); pitch script (section 10) + backup screenshots.

## 9. Schedule

| Time | All | data | model | app | docs |
|---|---|---|---|---|---|
| H0–H1 | Read plan, repo, branches | YAML + stub CSVs | Function skeletons | Streamlit skeleton | README + run.sh |
| H1–H4 | | Full generator + sources | Forecast + occupancy + tests | Tabs 1 and 6 | RESPONSIBLE_AI.md |
| **H4** | **Integration merge #1** | | | | |
| H4–H7 | | Holdout + disruption data | Recommend + impact + disruption | Tabs 2–5 + briefing | LA2028 + pitch |
| **H7** | **FEATURE FREEZE. Merge #2.** | | | | |
| H7–end | Fixes, screenshots, **3 timed pitch rehearsals** | | | | |

## 10. 3-minute pitch

| Time | Content |
|---|---|
| 0:00–0:30 | **Problem.** Maria, FBO manager. On Super Bowl Saturday her 40 spots won't be enough. How many short, and when? |
| 0:30–0:50 | **Why it's hard.** Attendance says nothing about jets. Demand depends on teams, aircraft mix, multi-day stays. |
| 0:50–1:50 | **Demo.** Baseline vs Super Bowl curve → occupancy over capacity on Saturday → recommended plan → Maria approves → switch low/medium/high → fog disruption. |
| 1:50–2:20 | **Impact.** Naive vs RampReady: X saturation hours avoided, Y aircraft that couldn't have been served, staffing adjusted. Backtest accuracy. |
| 2:20–2:45 | **Humans in command.** What the AI never decides. No passenger data. Uncertainty always visible. |
| 2:45–3:00 | **Next.** Same parameters → LA 2028. Thank you. |

## 11. Definition of Done

- [ ] `streamlit run app/streamlit_app.py` works on a clean machine
- [ ] Baseline, forecast, plan, 3 scenarios visible
- [ ] P10/P50/P90 shown everywhere
- [ ] Assumptions on arrivals, fuel, parking duration and resources visible in the app
- [ ] Naive vs RampReady comparison with numbers
- [ ] Backtest metrics shown
- [ ] At least one simulated disruption
- [ ] Working human approval gate + log
- [ ] No personal data anywhere
- [ ] App works without an LLM key
- [ ] pytest green
- [ ] README + RESPONSIBLE_AI + LA2028 written
- [ ] Pitch rehearsed 3 times under 3 minutes

## 12. Rules for agents

1. Read this file fully before coding. 2. Edit only your paths; need a change elsewhere → write it under `requests:` in your status file. 3. Never change the data contract (section 7) alone. 4. No hard-coded numeric constant: everything from `config/assumptions.yaml`. 5. Never use real tail numbers, people's names or real FBO names. 6. Simple that works beats sophisticated that breaks. 7. Code comments in English, clear commit messages. 8. Every invented assumption goes in `docs/ASSUMPTIONS.md`.
