# Ramp / 27 status
- Page: one responsive English dashboard (`index.html`) with Overview, Predict, Plan, and Trust & Data sections.
- Features: three demand cases, four situations, day focus, movement and parking charts with ranges and tables, aircraft mix, and a clearly labelled ramp-space what-if.
- Planning: dated parking proposals and optional price offer; named Approve / Request changes / Reject records with notes in localStorage, plus JSON export. No aircraft decisions are automated.
- Data: loads `fbo_data.json` with `fetch`; includes backtest, host-event and weather evidence, FAA history, assumptions, sources, raw-data explorer, and full JSON download.
- Run: `cd site_codex && python3 -m http.server 8000`, then open `http://localhost:8000/`.
- Checks: JavaScriptCore rendered 36 case/situation/day states and trust content; decision storage, links, data shape, CSS rules, and tested text contrast passed.
- Known gaps: sandbox denied local socket binding and browser access, so live HTTP, responsive screenshots, and browser-console QA could not run here. Situation-specific movement ranges are unavailable in the data; the chart labels the base ranges and the daily panel shows situation medians.
