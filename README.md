# RampReady team project guide

This guide consolidates the team notes and the reviewed product direction. Existing application files are unchanged. The Word version is linked below.

## FBO Parking Readiness Project Plan

Team 9 | SpartHill NCBAA hackathon | 23 October 2026

We are building an AI-assisted parking preparation tool for an FBO manager during Super Bowl LXI week. It will show when parking demand may exceed usable capacity, explain the cause, and recommend preparations for human review. This plan defines a focused 30-hour build for four teammates.

### The product decision

| Decision | Team direction |
| --- | --- |
| Challenge | Parking. Arrivals, departures, aircraft size and stay duration are inputs. |
| Target setting | Pacific Executive FBO, a fictional operator at LAX. |
| Target window | 11–17 February 2027, including the game on 14 February. |
| Shared repository | https://github.com/swyftos/airportsimn |
| Primary user | FBO operations manager, supported by reservations and operations staff. |
| Data | Public context and clearly labeled synthetic operational inputs. |

The existing team code is named RampReady and currently uses Horizon Ridge Aviation at Van Nuys, with a 9–15 February window. Keep the existing codebase and stack. Align the airport, fictional operator, dates, datasets and charts together before the final demo; this document does not change them in code.

### What the submission must demonstrate

- An ordinary-week baseline, event-week forecast and concrete preparation plan.

- How preparations change under lower, expected and higher demand, plus a departure-delay stress test.

- A measurable parking improvement or an honestly evaluated forecast, visible assumptions, uncertainty, privacy and human authority.

The app supports planning. It never authorizes aircraft movements or replaces airport safety procedures. Fuel and staffing are outside the core build; LA 2028 remains a stretch goal.

## How the forecast works

The app produces the expected forecast automatically. Employees provide bookings and operating constraints; they should not have to guess whether demand is low, medium or high. Scenario controls let them test how cautiously to prepare.

### Inputs and evidence

Use a CSV or reproducible sample dataset with anonymous visit IDs, arrival and departure estimates, aircraft category, booking status and source. Include aircraft already parked before the window. Distinguish recorded reservations from estimated additional arrivals. A prior-permission request is not automatically a confirmed booking or guaranteed parking allocation.

### The forecasting sequence

- Start with recorded visits and aircraft already present. Estimate ordinary traffic not already represented; avoid double counting.

- Estimate additional event bookings from a documented booking curve or explicit scenario assumptions. Comparable-event movement data can help shape the estimate, but airport totals are not an individual FBO’s bookings.

- Give predicted visits plausible arrival times, aircraft categories and same-day, overnight or multi-day stays.

- Generate lower, expected and higher demand cases, then calculate parking occupancy from each visit set.

- Update when bookings, cancellations or departure estimates change. Show when the inputs were refreshed and why the forecast changed.

### A transparent worked example

Suppose there are 60 confirmed event visits 14 days before the game. If a documented booking curve says 75% of eventual bookings are usually recorded by that point, the estimate is 80 total event visits, including 20 not yet booked. These numbers are illustrative. The 75% must come from relevant observations or be labeled an assumption, with cancellation rules stated.

### What low and high mean

Lower and higher cases vary unbooked arrivals, aircraft mix or stay durations around the expected case. They are demand alternatives, not capacity statuses: low demand can still overload a small FBO. Test delayed departures separately from arrival growth.

Do not call arbitrary scenario bounds confidence intervals. If Monte Carlo simulation is implemented, calculate occupancy separately for every simulated week and then take percentiles. P10–P90 describes the model’s distribution under its assumptions; real-world coverage still needs evaluation. More reservations do not automatically eliminate uncertainty about cancellations or departures.

## Parking calculations and measurable value

### Calculate overlapping stays

For each hour, include every aircraft that has arrived and has not yet departed. Sum its footprint units. Include stays crossing midnight, aircraft already present at the start, and departures beyond the seven-day window. Show the daily peak and the first hour above capacity. Aircraft arrivals alone do not describe occupied space.

The current team configuration uses light, midsize and large aircraft weights of 1.0, 1.5 and 2.5 parking units, with 40 main-ramp units and up to 25 overflow units. These are synthetic planning assumptions, not measured LAX capacity or verified physical parking spots. Update the ledger if the team changes them.

### Use capacity responsibly

Usable parking depends on layout, aircraft dimensions, access and operating clearances. Runway length, airport acreage and based-aircraft counts are not enough to establish an FBO’s capacity. Document resident-aircraft occupancy and protected reserves, define gross versus net capacity, and avoid subtracting the same reserve twice. Never reduce a required operational reserve to make a scenario fit.

### Produce a preparation plan

- State the shortfall, affected dates, proposed additional capacity and any residual gap.

- Ask reservations staff to check uncertain arrival, departure and overnight-stay estimates.

- Ask the manager to investigate suitable partner capacity and verify dates, access, suitability and price.

- Identify an owner, deadline, reason and confirmation status for every action. Report infeasibility when the allowed overflow is insufficient.

Any cost must use a documented rate and availability period. No verified partner quote exists in this prototype. A proposed plan does not reserve space, spend money, change a booking or authorize repositioning.

### Measure the improvement

Compare identical demand before and after the proposed capacity plan. Report first shortage time, peak shortage, hours over capacity, shortage unit-hours, residual shortage and illustrative cost. Shortage unit-hours sum unmet parking demand over time; they are not a count of rejected aircraft or actual service delays.

For forecast evaluation, reserve independent cases that were not used to tune the model. Use real time-separated history if available; otherwise label the result synthetic evaluation. Report arrival error, peak occupancy error and interval coverage when applicable. Do not claim real-world accuracy, avoided delays or staffing savings without supporting evidence.

## The employee experience and AI boundaries

### Make the first screen simple

After sign-in, show the employee’s name, role and FBO. Lead with the parking shortage and dates, followed by a seven-day baseline versus event chart and a Preview preparation plan button. Keep detailed bookings, assumptions and advanced settings expandable.

Use Expected forecast as the default, with Lower demand and Higher demand as stress-test options. Add Why this forecast to explain recorded reservations, estimated additional arrivals, stay durations and source quality. A departure-delay control should visibly show whether the plan still works.

| Role | Main task |
| --- | --- |
| Manager | Review capacity arrangements, cost and the proposed plan. |
| Reservations coordinator | Check booking status, arrival estimates, departure estimates and stays. |
| Operations supervisor | Verify usable capacity, aircraft suitability and readiness. |

For real accounts, use verified organization invitations or manager-approved membership. Assign roles on the server. Keep a clearly labeled demo account path for the hackathon; a client-side role picker is not authentication. Avoid building elaborate account administration before the core planning journey works.

### Separate calculation from AI explanation

The numerical engine calculates demand, shortages and conditional cost. The AI receives those results and an allowed resource list, explains the causes, and proposes preparation actions. Validate its output against supplied facts; a prompt alone does not guarantee correctness. Keep keys server-side and provide a deterministic fallback when the AI service fails.

### Keep decisions with people

- AI must never authorize movements, takeoffs, landings, taxiing or operating schedule changes.

- AI must not override safety limits, commit spending, invent partner availability, or cancel or prioritize an individual booking.

- Avoid passenger, crew, owner and VIP information. Use synthetic or pseudonymous visit IDs; real tail numbers are not automatically anonymous.

- Record proposed, approved, modified or rejected planning actions with a note, time, reviewer and exact plan version. Changing inputs invalidates the old review.

Our answer to the judges: The AI may identify a parking shortage and propose preparations. It must never decide which specific aircraft may move or independently allocate or withdraw a customer’s parking.

## Four people building one shared product

Use the existing Python and Streamlit repository. Do not rewrite it in React merely because React appeared in earlier notes. Each person owns one workstream and a branch; assign the actual teammates together rather than assuming that a GitHub username determines their role.

| Workstream | Deliverable |
| --- | --- |
| 1  App and integration | Simple manager journey, charts, employee experience, review UI and integration. |
| 2  Data and forecasting | Validated inputs, synthetic generator, baseline, booking estimate, scenario cases and assumptions ledger. |
| 3  Parking model | Hourly occupancy, overflow constraints, delay simulation, impact metrics and numerical tests. |
| 4  AI planner and quality | Grounded briefing, action explanations, review validation, documentation and pitch evidence. |

Workstream 1 owns session and account integration if real sign-in is built; workstream 4 helps validate permissions and review behavior. Prefer managed authentication and keep the demo scope small.

### Agree on the interfaces before splitting up

Keep the existing public model signatures stable. Agree on visits or hourly inputs, category units, timestamps, scenario identifiers, occupancy results and recommendation fields. Track source, model and plan versions. The repository currently stores copied work areas under wt-app, wt-data, wt-model, wt-docs and wt-int; these folders are not themselves Git branches. Use wt-int as the current integration entry point and agree how changes reach it.

### The 30 hour schedule

| Hours | Milestone |
| --- | --- |
| 0–2 | Freeze scope, owners and contracts; everyone runs the same starter. |
| 2–10 | Build in parallel; integrate one complete forecast-to-plan journey. |
| 10–18 | Improve evidence, scenario behavior, AI explanation and review handling. |
| 18–24 | Test boundaries and failures; evaluate impact on held-out scenarios. |
| 24–27 | Freeze features, polish and record a backup demo. |
| 27–30 | Rehearse, fix reliability issues and submit. |

Use small pull requests with one human review before merging. Pull main regularly and coordinate shared-file changes. Never commit secrets or private bookings. The first milestone is one scenario working end to end; do not wait until the final hours to combine separate implementations.

## Build status and final submission

### What is in the team repository now

At inspected commit 0eb9038, wt-int contains a Streamlit interface, synthetic-data generator, YAML assumptions, model interfaces and optional AI briefing code. The forecast currently repeats median values rather than running independent stochastic simulations. Occupancy returns missing values, recommendations return an empty list, impact metrics are placeholders, and disruption returns an unchanged copy. The app can therefore show Not available yet. Existing contract tests do not establish a working numerical forecast.

The briefing can use an AI provider when configured, with a template fallback. A live model call and operational accuracy have not been verified. The current decision log is local and is not tied to authenticated reviewers or exact input versions. Completing the model and connecting the journey is the immediate priority.

### Completion checklist

- Show an ordinary baseline and event forecast for one consistent FBO and seven-day window.

- Explain reservations versus estimates and show lower, expected and higher demand.

- Calculate overlapping stays and expose a departure-delay shortage.

- Recommend a feasible conditional plan, or explicitly show remaining unmet capacity.

- Demonstrate measured improvement and label all synthetic evaluation.

- Show human review, uncertainty, assumptions and AI fallback; prepare a backup recording.

### Assumptions and sources

For every numerical input, record its value, units, public or synthetic or assumed status, source, update time and uncertainty. This includes arrivals, size mix, stays, capacities, reserves and any illustrative prices. Fuel purchases and staffing may be documented as contextual assumptions where the brief requests them; they are not independently optimized in this parking project.

Public starting points: discoverlosangeles.com/superbowl for event context; signatureaviation.com/locations/LAX for real FBO-service context; FAA airport data for facility context. None establishes the fictional FBO’s usable capacity or demand. Do not present generated event benchmarks as observed history or unverified judging weights as official rules.

### Keep the scope focused

Exclude the SFO airport-wide proposal, runway and gate scheduling, live broker integrations, passenger profiling, regional routing, deep fuel or staffing models, and enterprise audit infrastructure. Do not infer demand directly from stadium attendance or cut protected reserves to make capacity fit.

After the core works, LA 2028 can reuse the framework for a selected seven-day period with new evidence and different arrival and stay assumptions. Configurable dates help, but an Olympics forecast requires new demand evidence rather than relabeling the Super Bowl data.

Demo sequence: manager opens expected forecast, sees the shortage, inspects overlapping stays, previews preparations, delays departures, updates the plan and records human review. Change an assumption to demonstrate that the previous review becomes stale.

## Run the current team scaffold

The integrated application is under `wt-int/`, not the repository root. Use Python 3.11 or newer. These commands start the scaffold; placeholder model functions still need implementation.

```sh
git clone https://github.com/swyftos/airportsimn.git
cd airportsimn/wt-int
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python data/generate.py
python -m streamlit run app/streamlit_app.py
```

On Windows, activate with `.venv\Scripts\activate`. To run the existing contract checks from `wt-int/`, use `python -m pytest tests`. These checks are not forecast-accuracy validation.

The optional AI briefing reads `ANTHROPIC_API_KEY` and `RAMPREADY_BRIEFING_MODEL` from the environment. Configure a provider-supported model available to your account; the hard-coded default has not been verified. Without a key or on a provider error, the briefing falls back to a template.

Do not use the copied `wt-docs/run.sh` as the root launcher: it expects application and data folders alongside it, which are not present in that work area.

## Repository map

| Path | Current contents |
| --- | --- |
| `wt-int/` | Combined application, generator, assumptions, model skeleton and tests |
| `wt-app/` | App work area |
| `wt-data/` | Data and assumptions work area |
| `wt-model/` | Model and contract-test work area |
| `wt-docs/` | Documentation work area and launcher script |

Each work area has its own `AGENTS.md` and coordination files. Read the applicable instructions before editing it. Keep model contracts stable and coordinate changes across copies. The coordination boards can lag behind the code; inspect implementation before marking work complete.

## Start working together

1. Accept the invitation to this existing repository and clone it.
2. Create a branch such as `feat/app`, `feat/data`, `feat/model`, or `feat/planner`.
3. Confirm your owned paths and shared contracts with the integration owner.
4. Push small commits, open a pull request, and get a human review before merging.
5. Pull main regularly. Do not push directly to main or duplicate the repository.

Do not commit API keys, `.env` files, virtual environments, private bookings or local decision logs. Real authentication and access control remain implementation work.

## Project references

- [Corrected shareable project plan](team-plan/Team-9-Corrected-FBO-Project-Plan.docx)
- [Current assumptions](wt-int/config/assumptions.yaml)
- [Existing assumption notes](wt-int/docs/ASSUMPTIONS.md)
- [Existing responsible AI notes](wt-docs/docs/RESPONSIBLE_AI.md)
- [Existing integration contracts and agent instructions](wt-int/AGENTS.md)

The older work-area documents describe some intended features as implemented. Use the build-status section above when explaining the inspected starter; update it as functionality is completed and verified.
