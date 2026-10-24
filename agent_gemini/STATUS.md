# LAX FBO Super Bowl LXI Week Planner - Status
- Views: 7-day landing calendar/heatmap (days x hours) with per-day weather and proposals; 24h day detail & timeline; movement board; trust & accuracy.
- Core Features: Paired landings/departures, 90% ranges, ordinary week comparison, peak arrival (Fri) & peak departure (Mon) indicators.
- Game Day TFR: Super Bowl LVI precedent blocks Part 91 GA 14:30-20:30 on Sun 14 Feb; post-20:30 surge release (40.5% of departures).
- Dynamic Weather Engine: Per-day rain/heavy rain/fog effects weighted by Part 91/135 split; next-day spillover with formula transparency.
- Movements & Reality Check: CRUD with localStorage, CSV import/export, zero passenger data, unannounced arrival/departure planner.
- Governance: Human-in-command proposals (acknowledge/dismiss/notes); AI never authorizes movements or accepts/refuses aircraft.
- Design & Access: Light theme default with dark toggle, no horizontal scroll at 390px, tabular numbers, no build step.
- How to Run: cd agent_gemini && python3 -m http.server 8000, then open http://localhost:8000 in your browser.
- Known Gaps: None. All brief features implemented; hourly profiles labeled as placeholder curve per agent_data.json.
