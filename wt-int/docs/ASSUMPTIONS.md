# Assumptions

All demand and capacity figures in this prototype are synthetic planning assumptions for Horizon Ridge Aviation, a fictional FBO. They are not measurements of aircraft activity at Van Nuys or any other airport. Stadium attendance is not used as a direct predictor of aircraft arrivals. The team-origin descriptions are scenario narratives, not known 2027 qualifiers.

`config/assumptions.yaml` is the machine-readable source for all parameters below. Times are Los Angeles local time for February 9–15, 2027. A parking unit (PU) is the space required by one light aircraft.

| Group | Assumption |
|---|---|
| Ordinary arrivals | 14 per day Tue–Fri and Mon, 10 Sat, 12 Sun at the fictional FBO |
| Event demand shape | Tue 0.2, Wed 0.4, Thu 0.7, Fri 1.0, Sat 1.0, Sun 0.1, Mon 0.0 of regional peak extra demand |
| Scenario demand | Low 300 regional aircraft/day and 1.5% FBO share; medium 550 and 1.6%; high 850 and 1.7% |
| Team-origin narratives | Low: one local and one nearby; medium: one local and one distant; high: two distant |
| Aircraft size and fuel | Light: 1 PU, 150 gal; mid: 1.5 PU, 450 gal; large: 2.5 PU, 1,200 gal at departure |
| Aircraft mix | Ordinary: 45% light, 40% mid, 15% large. Event: mid 40%; large 25%, 35%, or 45% by scenario; light is the remainder (35%, 25%, or 15%). |
| Ordinary stays | 50% depart same day, 40% after one night, 10% after at least three days |
| Event extra-demand stays | Tue–Wed: 15% same day, 60% Sun night/Mon wave, 25% at least three days. Thu–Sat: 10%, 80%, 10%. Sun: 30%, 70%, 0%. |
| Ramp and staffing | 40 PU main ramp; 0 ordinary overflow, up to 25 PU booked overflow; six ordinary ramp agents, up to 12; one agent per three movements/hour |
| Fuel service | Three ordinary trucks, up to two rentals, 8,000 gal/day delivery per truck |
| Monte Carlo model settings | 1,000 draws; 0.15 lognormal multiplier sigma; length-of-stay share variation of 10 percentage points; aircraft mix variation of 5 percentage points; P10/P50/P90 output |
| Peak targets | Low around 90% of 40 PU; medium 55–60 PU; high above 65 PU. These are calibration goals, not measured outcomes. |

## Provisional stub choices

The project plan specifies the shape of the departure wave but not the precise hourly weights. The YAML records an explicit 24-hour arrival profile and 19-hour departure profile from Sun 20:00 through Mon 14:00. The arrival weights favor daytime and early evening. The departure weights have humps at Sun 22:00–Mon 01:00 and Mon 09:00–12:00. Both profiles sum to one.

For the CSV stub, an ordinary aircraft's same-day departure is placed six hours after arrival; an event-extra aircraft's is placed four hours after arrival. The ordinary 10% long-stay group is represented by a departure three days later. The Monday event-extra group, unspecified in the plan's stay table, uses 50% same-day departure and 50% beyond the displayed week. The seeded generator adds a 0.06 standard-deviation perturbation to hourly arrival weights and normalizes them within each day. Stub P10/P90 arrivals are 75%/125% of P50. These spreads are placeholders, not Monte Carlo percentiles; the model agent will produce draw-based P10/P50/P90.

The stub separates ordinary traffic from event-extra traffic for departures: ordinary traffic follows the ordinary stay split and extra demand follows the event stay split. This keeps the event's incremental parking pressure visible without treating routine transient aircraft as multi-day event visitors.

**Source:** team `AGENTS.md` sections 2 and 2.6 supplies the scenario and resource values. The provisional stub choices above are documented here because they are invented. External traffic references and calibration remain future validation work; this synthetic prototype should not present these values as observed aviation statistics.
