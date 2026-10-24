# LAX FBO Super Bowl LXI Planner - PR #53 Status
- Week Overview (Boss): 7 days Thu-Wed with large landings/departures, busiest hours, plain busy levels, short action lines & glanceable heatmap.
- Central Forecast: Medium (+15.5%) default; Low/High plausible range; scenario toggle removed from header; collapsed Compare Cases section.
- 90% Ranges: Displayed as 90% range using agent_data.json totals with range_note info tooltips; no category summing.
- Security & Validation: CSV import validates tail (max 10, chars/digits/-), HH:MM time, date & enums; skipped rows reported; XSS-safe DOM.
- Next 3 Hours Radar: Exact simulated minute window, partial hour prorating, midnight next-day continuation, outside-week handling.
- Weather Engine & Bug Fix: Changing weather immediately updates day's landings, departures, ranges (low'=low*factor+in) and next day's carryover.
- Governance & Role: Strict FBO agent scope (confirm ETAs/ETDs, keep board current); no ATC/holds/tower/fuel/staffing/passengers; light theme default.
- Mobile Layout: Clean responsive view with zero horizontal scroll at 390px wide.
