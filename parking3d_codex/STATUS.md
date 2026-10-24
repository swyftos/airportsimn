# Ramp Control status
- Built a plain HTML/CSS/JS 3D parking simulator with a fixed isometric Three.js ramp, seven-day time lapse, capacity gauge, and manager-decision waiting area.
- The 2D answer shows daily P10/P50/P90, overflow probability, first and highest-risk days, ordinary-week comparison, and illustrative pressure hours.
- Scenario, situation, date, plan view, playback, theme, and per-action named decisions with notes are interactive; decisions persist in localStorage.
- Hourly aircraft are seeded from the supplied opening count, flows, hourly shares, size mix, and stay mix, then aligned to each day's modeled P50; the UI states this formula and its limits.
- Run from this folder with `python3 -m http.server` and open `index.html`; no build step. Three.js is pinned to 0.160.0 on jsDelivr.
- Verified JavaScript syntax, source links, contrast, and all 12 scenario/situation model combinations; browser visual QA was unavailable because local HTTP binding and Safari computer use were denied.

## Review (Claude, headless Chromium with WebGL)
- Loads with no console errors; WebGL context OK; numbers match parking_data.json (17.4 su, 82% / 81%, $3,500, 2.3 to 0.1).
- Interactions checked: Low / Medium / High, the 24 h delay situation, day click, prepared-capacity toggle, play/pause.
- No data values are hard-coded; each day's busiest illustrated hour is anchored to the model P50.
- Fixed: page was 803 px wide on a 390 px phone (the evidence table forced the grid wider); the table now scrolls inside its own box.
