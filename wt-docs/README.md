# RampReady ✈️
### The Intelligent FBO — Super Bowl LXI parking planner

> **AI assists. People decide.**
> Built at SpartHill Hacks 2026 for the NCBAA *Intelligent FBO* track.

RampReady helps the operations manager of a business-aviation FBO see, hour by hour, **when aircraft parking demand will exceed capacity** during Super Bowl LXI week in Los Angeles, with an explicit uncertainty range, low / medium / high scenarios, and a preparation plan that **only a human can approve**.

---

## The problem

Super Bowl LXI is played on **Sunday, February 14, 2027** at SoFi Stadium in Inglewood. In the days before, business jets pour into LA-area airports, and most of them **stay on the ground for days** before leaving together on Sunday night and Monday.

For an FBO, the ramp is the bottleneck. Every aircraft needs a spot, and a large long-range jet takes far more room than a light jet. Managers have to commit weeks in advance to overflow space, extra ramp staff and fuel capacity, usually from experience and gut feel.

Stadium attendance does not tell you how many jets will show up. Demand depends on who is playing, where their fans fly from, which airports they choose, and how long they stay.

## Who it's for

**The FBO operations manager.** RampReady is a planning tool. It never assigns, accepts, refuses or moves an aircraft.

## Scope

| | |
|---|---|
| **Focus** | Aircraft **parking** (with arrivals as the driver, and staffing and fuel as derived views) |
| **FBO** | *Horizon Ridge Aviation*, a **fictional** FBO at Van Nuys Airport (KVNY) |
| **Window** | Tuesday Feb 9 → Monday Feb 15, 2027 (7 days) |
| **Data** | Synthetic, generated from documented assumptions |

---

## What the prototype shows

1. **Ordinary-week baseline** of arrivals and ramp occupancy.
2. **Super Bowl week forecast** with P10 / P50 / P90 bands.
3. **Recommended preparation plan**: overflow parking, reservation policy, staffing by hour, fuel volume.
4. **Low / medium / high scenarios**, side by side, showing how the plan changes.
5. **Impact**: naive plan vs RampReady plan, plus forecast accuracy on a hidden synthetic week.
6. **Disruption testing**: weather delays, extended stays, temporary airspace restrictions.
7. **Human approval gate**: every recommendation is *Proposed* until a person approves, modifies or rejects it. Every decision is logged.
8. **Plain-language briefing** written by an LLM from computed numbers only, with a template fallback when no API key is set.

---

## Quick start

```bash
git clone <repo-url>
cd rampready
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python data/generate.py          # builds the synthetic datasets (the app also does it if missing)
streamlit run app/streamlit_app.py
```

Or simply `./run.sh`.

Optional, for the LLM briefing:
```bash
export ANTHROPIC_API_KEY=your_key_here
```
Without a key, the app uses a template briefing. Everything else works the same.

Run the tests:
```bash
pytest
```

---

## How it works

### 1. Arrivals
```
arrivals(day, hour, scenario) = baseline_day(day) × event_multiplier(day, scenario) × hourly_profile(hour, day)
```
The event multiplier is built from **demand drivers**, not attendance:
- High-value attendee mix (corporate hospitality, sponsors, media)
- Where the two qualifying teams are based (distant teams bring more jets)
- The FBO's share of regional demand across competing LA-area airports and FBOs
- External constraints such as slot reservation programs and airspace restrictions typically used for events of this size

### 2. Parking occupancy
```
occupancy(h) = occupancy(h-1) + arrivals(h) − departures(h)
```
Departures come from a **length-of-stay distribution** that depends on arrival day. Aircraft arriving Thursday to Saturday mostly stay until Sunday night or Monday. Demand above available capacity is tracked separately as **unserved demand**: aircraft the manager would need to redirect.

Occupancy is measured in **parking units (PU)**: light jet = 1.0, midsize = 1.5, large long-range = 2.5.

### 3. Uncertainty
A Monte Carlo simulation (1,000 runs) varies the demand multiplier, length of stay and aircraft mix. Occupancy is accumulated run by run, then summarized. Every number is shown as a **P10 / P50 / P90** range.

### 4. Recommendations
Transparent rules, not a black box. Each recommendation shows the rule that triggered it:
- P90 occupancy above capacity → reserve overflow space
- P50 occupancy above 85% of capacity → switch to mandatory reservations
- P90 movements per hour → ramp agents needed
- Departures × average gallons by aircraft class → fuel volume, checked against truck delivery capacity
- Critical windows: 2-hour windows with occupancy > 95% flagged

### 5. Impact
The same simulated week is replayed under two plans:

| | Naive plan | RampReady plan |
|---|---|---|
| Parking | Normal capacity + flat 20% margin | Overflow sized on P90 |
| Staffing | Normal crew + 2 | Hourly reinforcement from forecast |
| Reservations | None | Mandatory past threshold |

Metrics: hours over capacity, aircraft that could not be served, staff-hours short and in excess, peak occupancy. Forecast accuracy is measured on a hidden synthetic week (MAPE, P10–P90 coverage, peak error).

---

## Key assumptions

All numbers live in [`config/assumptions.yaml`](config/assumptions.yaml) and are editable from the app. Full justification in [`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md).

| Area | Assumption (synthetic) |
|---|---|
| **Arrivals** | Regional extra demand at peak of 300 / 550 / 850 aircraft per day (low / medium / high), of which the FBO captures 1.5–1.7%; peak on Friday and Saturday |
| **Parking duration** | Thu–Sat arrivals: 10% same day, 80% leave Sunday night or Monday, 10% stay 3+ days |
| **Aircraft mix** | Ordinary: 45% light / 40% mid / 15% large. Super Bowl: 25–45% large depending on scenario |
| **Fuel purchases** | 150 / 450 / 1,200 gallons per departure by class |
| **Resources** | 40 PU main ramp, up to +25 PU overflow, 6–12 ramp agents per shift, 3–5 fuel trucks |

These are **illustrative values for a prototype**, not real operational data. The method is designed so a real FBO can replace them with its own history.

---

## Humans in command

RampReady supports planning. It **does not authorize aircraft movements or replace airport safety procedures.**

- **Never decides** which aircraft is accepted, refused, repositioned or allowed to move.
- **Never assigns** a parking spot to a specific aircraft.
- **No personal data.** Aircraft are counted by class only: no tail numbers, owners, passengers or individual flight plans.
- **Uncertainty is always visible.** No single-number forecasts.
- **Every recommendation goes through a human approval gate**, with a logged decision and note.
- The LLM only **explains** numbers it is given. It cannot create figures or make operational calls.

> **What decision should our AI never be allowed to make?**
> Any decision that touches a specific aircraft, crew or passenger. RampReady can tell the manager *"Saturday between 2 PM and 8 PM, you will likely be 8 to 15 spots short."* Who gets accommodated, who gets redirected and how, stays with the manager, within the airport's safety procedures.

More in [`docs/RESPONSIBLE_AI.md`](docs/RESPONSIBLE_AI.md).

---

## Stretch goal: LA 2028 Olympics

The model is parameter-driven, so adapting it is a configuration change, not a rewrite: a longer window (17 days), several venues, multiple demand peaks and longer stays. See [`docs/LA2028.md`](docs/LA2028.md).

---

## Project structure

```
run.sh                    one-command setup and launch script
config/assumptions.yaml   all numeric assumptions, single source of truth
data/                     synthetic data generator and datasets
model/                    forecast, occupancy, recommendations, impact, disruption
app/                      Streamlit app and briefing
docs/                     assumptions, data contract, responsible AI, LA 2028
tests/                    pytest suite
pitch/                    pitch script
coordination/             how the four AI agents were coordinated
```

---

## Limitations

- All data is **synthetic**. Accuracy figures validate the method, not real-world performance.
- Demand drivers are simplified. Real deployment would calibrate on historical events such as Super Bowl LVI (LA, 2022).
- Airspace programs and airport rules for 2027 are not yet published; they are modeled as adjustable constraints.
- One FBO, one airport. Regional competition is modeled as a market-share parameter.

---

## Team

Built in one day by a team of four, each person working with an AI coding agent. Claude Code dispatched tasks and checked each agent's output against the data contract; every merge was reviewed by a human: *AI assists, people decide* applied to how we built it too.

| Member | Role | Agent |
|---|---|---|
| _name_ | Data & assumptions | OpenCode (Gemini) |
| _name_ | Model & impact | Codex |
| _name_ | App, integration & coordination | Claude Code |
| _name_ | Docs, quality & pitch | OpenCode (GitHub Copilot) |

---

*SpartHill Hacks × NCBAA — October 2026*
