# Brief: a new planning website for the fictional FBO at LAX, Super Bowl LXI

## The question the site answers
Predict the additional private-aircraft demand during Super Bowl LXI week (game Sunday 14 February 2027 at SoFi Stadium; planning window 11 to 17 February 2027) and show how the FBO should prepare its **parking** for it.

**Scope: landings (arrivals), departures and parking only.** No staffing, no fuel. Parking costs (the cost of the parking plan) are in scope.

The FBO manager must be able to predict, access all the data and plan accordingly, with a human approving every action.

## Data
Everything is in `site_kit/fbo_data.json` (copy it into your site folder). It comes from the team's real model outputs. Main keys:
- `meta`: title, planning window, game day, Presidents' Day, scope, units, `human_in_command`, `never_allowed`, `data_classes`.
- `scenarios`: Low / Medium / High definitions (measured Super Bowl effect sizes).
- `forecast_daily`: per date and scenario, `baseline_*` (ordinary week) and `expected_*` (Super Bowl week) arrivals and departures, `*_range90` [low, high], and `by_aircraft_size`.
- `ordinary_week_parking`: parking for an ordinary week (same dates, no Super Bowl).
- `parking[variant]` for `standard`, `departure_delay_24h`, `security_restriction`, `heavy_rain`: `label`, `method`, `days` (per scenario and date: arrivals/departures P50, parking P10/P50/P90 in su, normal and prepared capacity, utilization, probability over capacity, risk level) and `plans` (per scenario: summary, parking `actions` with dates, rationale, cost, `requires_human_approval`, `approver`; `parking_cost_usd`; `aircraft_not_accommodated` with no plan vs with plan; `net_benefit_usd`; `prob_plan_pays_off`).
- `slot_advisor`: price incentives. Drop-and-go credit vs cheap early arrival, at 0 to 30% take-up (`rows`), and `recommendations` per scenario (actions and the finding that cheap early arrival does not free parking).
- `accuracy`: rolling backtest of the forecast (model WAPE 14.9% vs four simple baselines) and the holdout split.
- `super_bowl_test`: measured Super Bowl effects at eight host cities, with position vs the Low/Medium/High range.
- `weather`: measured effect of rain, heavy rain and fog on LAX operations, and February frequencies.
- `share_robustness`: ramp use is identical whatever the FBO share, because the ramp is sized to the share.
- `key_assumptions`, `history_daily_faa` (2023-2025 daily FAA counts), `sources`.

## What the site must offer
1. **Week at a glance**: for the chosen scenario, KPIs (extra landings over the week, peak parking day and level vs capacity, aircraft not accommodated without vs with the plan, plan cost) and the seven-day chart of landings and departures, ordinary vs Super Bowl, with 90% ranges.
2. **Predict**: scenario switch (Low / Medium / High) and situation switch (normal, 24 h departure delay, security restriction, heavy rain). Daily landings and departures with ranges, by aircraft size; parking occupancy vs capacity per day. Add one simple what-if of your own design (for example a ramp-capacity slider or an extra-demand slider) computed in the browser, clearly labelled as an approximation of the full model.
3. **Plan**: the recommended parking actions for the chosen scenario and situation, with dates, rationale, cost and effect (aircraft not accommodated: no plan vs plan, chance the plan pays off). Each action has Approve / Request changes / Reject with the approver's name and a note, stored in localStorage, with an export of the decisions as JSON. Show the price-incentive advice (drop-and-go credit; why cheap early arrival does not help). State clearly that the system never accepts or refuses an aircraft.
4. **Trust**: forecast accuracy (backtest vs baselines), the Super Bowl test across eight cities, weather effects, the FAA history chart, key assumptions with measured / estimated / assumed badges, and sources with links.
5. A visible answer to: "What decision should the AI never be allowed to make?" (use `meta.never_allowed`).

## Rules
- Follow `site_kit/FRONTEND_SKILL.md`.
- Work only inside your own site folder. Do not edit anything else in the repository.
- Static site, no backend. It must run with `cd <your folder> && python3 -m http.server 8000`.
- English UI. No staff, no fuel anywhere.
- Before finishing, serve it locally, check there are no console errors (for example with a headless check or by fetching every file), and write `<your folder>/STATUS.md` (max 10 lines: pages, features, how to run, known gaps).
