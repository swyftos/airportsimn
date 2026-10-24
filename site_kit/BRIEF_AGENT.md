# Brief: an app for the FBO agent, Super Bowl LXI week at LAX

## The one question
**Aircraft arrivals: when should the FBO expect its busiest periods?** Landings and departures only. No staffing, no fuel. Parking may appear as one small secondary indicator, nothing more.

## Who uses it
An FBO customer-service / operations agent at the desk of a fictional FBO at LAX, during their shift, on a laptop or a tablet. In real life they track inbound and outbound aircraft (tail number, aircraft type, ETA/ETD), relay arrivals to the line crew, and keep an arrivals/departures board up to date. They are busy and interrupted: the screen must answer "what is coming, when, and how busy will it get" in a few seconds.

## Data (use ONLY this file; do not invent numbers)
`agent_data.json` (copy it from `site_kit/` into your folder). Everything in it comes from the team's own data:
- `days[]`: the seven planning days (Thu 11 to Wed 17 Feb 2027), with `game_day`, `presidents_day`, `security_restriction` flags and, per scenario (Low / Medium / High): ordinary-week and Super Bowl-week expected arrivals and departures, their 90% ranges, the Part 91 / Part 135 split, and a small parking indicator (ramp space in su vs capacity).
- `hourly_profile.shares`: hour-of-day shares for weekday/weekend arrivals/departures. **This is a placeholder curve, not observed data: label it as such.** Movements the agent enters replace it for the hours they cover.
- `game_day_restriction`: no private movements on Sun 14 Feb 14:30-20:30 (Super Bowl LVI precedent, an assumption), with ready-made `hour_shares` where blocked movements are released after 20:30.
- `weather`: measured effects of rain, heavy rain and heavy fog on Part 91 and Part 135 movements (with 95% ranges), the February probability of each, and the rule: lost movements happen the next day.
- `accuracy` (rolling backtest: the model's average daily error is 14.9%, better than four simple baselines), `super_bowl_test` (eight host cities), `scenarios`, `key_assumptions`, `sources`, `meta` (question, privacy, human-in-command, `never_allowed`).

## What the agent must be able to do
1. **See today hour by hour.** Pick a day of the week (and a demo "now" time, since the dates are in 2027). Show a 24-hour timeline of expected landings and departures: the forecast spread by the hour profile, adjusted for the scenario, the weather setting and the game-day restriction, with the agent's own entered movements overlaid. Highlight the busiest hours. Show what is coming in the next 3 hours.
2. **Plug in real movements.** A fast form to add an arrival or a departure: time, optional tail number, aircraft size (light / midsize / large), status (expected, confirmed, landed, departed). Edit, delete, mark landed or departed. Keyboard-friendly. Stored in localStorage; import and export as CSV. Compare booked vs forecast: "6 arrivals booked, about 7.3 expected: plan for about 1 more unannounced arrival".
3. **Plan the week, Thursday to Wednesday.** One view of the seven days, each with expected arrivals and departures (with range) vs an ordinary week, the busiest day for arrivals and the busiest day for departures, peak hour windows, and **day-specific proposals** generated from the data (for example the busiest arrival day, the game-day pause and the departure wave after 20:30, Presidents' Day departures, the day after bad weather). Proposals are about handling arrivals and departures (timing, slots/PPR confirmations, readiness windows), never about staff or fuel.
4. **Set the weather per day.** For each day: clear, rain, heavy rain or heavy fog, with its February probability shown. Apply the measured effect (weighted by that day's Part 91 / Part 135 split) and move the lost movements to the next day, visibly ("+0.4 movements moved from Sunday").
5. **Switch scenario** Low / Medium / High at any time, and always be able to compare with the ordinary week.
6. **Trust.** Show forecast accuracy, the Super Bowl test across eight cities, every assumption with a badge (measured / estimated / assumed / placeholder) and the sources.
7. **Humans in command and privacy.** Proposals are suggestions the agent can acknowledge or dismiss, with a note. The tool never accepts, refuses or cancels an aircraft and never authorizes a movement (`meta.human_in_command`). No passenger data is ever entered or stored; say so on the entry form. Visible answer to "What decision should your AI never be allowed to make?" (`meta.never_allowed`).

## Rules
- Follow `site_kit/FRONTEND_SKILL.md` (fbo-frontend skill).
- Work only inside your own folder. Plain HTML/CSS/JS, no build step; runs with `python3 -m http.server` from your folder.
- Use only numbers from `agent_data.json` or computed from it in the browser (state the formula next to computed values).
- English UI. Readable at arm's length on a tablet. No horizontal scroll at 390 px.
- Finish with `<your folder>/STATUS.md` (max 10 lines: views, features, how to run, known gaps).
