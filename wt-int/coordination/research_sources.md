# Public sources for calibration (from team research, unverified until opened)

Use for calibrating parameters, not for training. Aggregate counts only: never tail numbers.

| Use | Source | What to extract |
|---|---|---|
| Baseline + observed event multiplier (priority 1) | FAA ATADS daily ops, https://www.aspm.faa.gov/opsnet/sys/airport.asp | VNY (also BUR, SMO, HHR, LGB) daily movements Feb 8–15 2022 (Super Bowl LVI, LA) vs same weekdays Feb 2021/2023 |
| Regional airports in reservation program, LA 2022 | https://notams.aim.faa.gov/lta/main/viewlta?lookupid=2763385205610780572 | LAX, SMO, HHR, VNY, BUR, LGB, SNA, ONT, SBD: justifies market-share split + external constraints |
| Departure wave shape | Flightradar24, https://www.flightradar24.com/blog/flight-tracking-news/just-for-fun/the-super-bowl-lx-private-jet-exodus/ | 136 bizjet departures 19:00–02:00 after game (SFO/OAK/SJC/LVK/HWD) vs 11 week before |
| Single-airport capture order of magnitude | SJC, https://dev.flysanjose.com/news-release/super-bowl-week | 900+ private jet movements Feb 4–9 2026 |
| Reservation programs other editions | FAA notices 2023–2026 (dom24001, dom24038, dom26007) | Context for "external constraints" driver |

Not relevant to aircraft parking: TSA/CBP wait times, car parking, BTS on-time, T-100.
Limit: ATADS counts airport-level movements, not ramp occupancy or per-FBO split. Length of stay and market share stay assumptions.
