# Brief: 3D parking simulator for the fictional FBO at LAX, Super Bowl LXI week

## The one question
**Parking: when might demand exceed available aircraft parking space?** Planning window Thu 11 to Wed 17 Feb 2027, game Sunday 14 Feb.

## Data (use ONLY parking_data.json; never invent numbers)
- `parking[situation].days[scenario][date]`: the parking model's answer, from 10,000 simulated weeks: ramp demand P10 / P50 / P90 in space units (su), normal and prepared capacity, `prob_over_normal_capacity` (chance demand exceeds the ramp that day), risk level, arrivals and departures P50. Situations: `standard`, `departure_delay_24h`, `security_restriction`, `heavy_rain`. Scenarios Low / Medium / High, **Medium is the forecast** (`default_scenario`); Low and High are the plausible range, not a user preference.
- `parking[situation].plans[scenario]`: the AI preparation plan (tow-in packing, overflow apron lease), its cost, aircraft not accommodated without vs with the plan, chance it pays off, and the approver of each action.
- `ordinary_week`: the same dates without the Super Bowl, for comparison.
- `capacity` (15 su ramp, how it was derived, tow-packing gain, overflow apron), `aircraft` (sizes in su with real examples, assumed mix, assumed stay mix, opening aircraft), `hourly_profile` (PLACEHOLDER hour shares), `game_day_restriction`, `flows` (daily arrivals/departures), `meta`, `sources`.

The daily answer is the model's. Individual aircraft in the 3D scene must be generated from these totals (seeded, reproducible): arrivals and departures per hour from the daily numbers and the hour shares, sizes from the mix, stay lengths from the stay mix, starting with the opening aircraft. Label that scene as an illustration consistent with the model, and show the model's P50 / P90 and probability next to it.

## What the prototype must show
1. **The answer first, in plain 2D**: for the selected scenario and situation, the days when demand is likely to exceed the ramp (probability and P50 / P90 vs capacity), the first and the worst day, and the ordinary week for comparison.
2. **A 3D ramp**: the 15 su main ramp with stands to scale, a separate remote overflow apron, and aircraft of three sizes. A clock runs through the seven days (play, pause, speed, scrub to a day and hour): aircraft taxi in, park, and leave. A gauge shows space used vs capacity. When demand exceeds the ramp, the extra aircraft wait in a highlighted "needs a manager decision" area. **They are never refused automatically.**
3. **The plan**: toggle "plan approved" (tow-in packing +10% and the overflow lease) to see the effect in the scene and in the numbers (aircraft not accommodated without vs with the plan, cost, chance it pays off). Each action can be approved / rejected by a named person with a note (localStorage).
4. **Situations**: switch normal / 24 h departure delay / security pause / heavy rain. Scenario defaults to Medium (the forecast), with Low and High as the plausible range.
5. **Honesty**: capacity is an estimate (not a stand count), the hour shape and stay mix are assumptions, and the 3D aircraft are illustrative. Answer "What decision should your AI never be allowed to make?" (`meta.human_in_command`).

## Rules
- Follow `parking_kit/FRONTEND_SKILL.md` (including the 3D section). Plain HTML/CSS/JS with Three.js from a pinned CDN; no build step; runs with `python3 -m http.server` from your folder.
- Parking only (with arrivals/departures as its drivers). No staffing, no fuel, no passenger data.
- Never mention air traffic control actions, clearances or authorities that are not in the data.
- Work only inside your own folder. Finish with `<your folder>/STATUS.md` (max 10 lines).
