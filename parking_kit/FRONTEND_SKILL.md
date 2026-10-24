---
name: fbo-frontend
description: Front-end design and build rules for the FBO Super Bowl planning website. Use for every HTML/CSS/JS decision, chart and layout in this project.
---

# Front-end skill: operational planning dashboard

The reader is an FBO (private-jet terminal) manager planning one week. They need to see, in seconds: how many aircraft land and depart each day, whether the ramp overflows, what to prepare and what it costs, and how sure we are. Design for that decision, not for decoration.

## Build
- Plain HTML, CSS and JavaScript (ES modules allowed). No build step, no npm install. It must run with `python3 -m http.server` from the site folder and load `fbo_data.json` with `fetch`.
- One external library at most, from a pinned CDN URL (for example Chart.js 4.4.1 from cdnjs). Hand-rolled SVG charts are welcome and often cleaner. No trackers, no analytics, no external fonts required (system font stack is fine; one Google Font is allowed).
- Keep files small and readable: `index.html`, `styles.css`, `app.js`, plus a few modules if useful.

## Visual system
- Define colours, spacing, radii and font sizes as CSS custom properties on `:root`. Provide a dark theme with `@media (prefers-color-scheme: dark)` and a toggle.
- Neutral background, one brand accent, and a separate semantic set: ok (enough capacity), warning (extra preparation), critical (over capacity). Never use the accent for status. Check contrast: text at least 4.5:1, chart marks at least 3:1 against the background.
- Typography: one family, 3 to 4 sizes, tabular numbers (`font-variant-numeric: tabular-nums`) for every figure. Big numbers for the few KPIs that matter, small muted labels.
- Spacing on an 4/8 px scale. Generous white space. Cards only where grouping helps.

## Layout
- Mobile first. Works at 360 px wide with no horizontal scroll (16 px side gutter), then grows to a two- or three-column layout on desktop.
- Top: a sticky control bar with the scenario (Low / Medium / High), the situation variant (normal, 24 h delay, security restriction, heavy rain) and the date. Every view below reacts to it.
- Put the answer first (KPIs and the week chart), detail below (tables, evidence). Navigation by sections or tabs, keyboard accessible.

## Charts (most important)
- Every forecast shows its range: a band for the 90% range around the expected line or bars. Never show a forecast as a single exact number without the range nearby.
- Arrivals and departures: paired bars or two lines per day, the same two colours everywhere in the site. Mark game day (Sun 14 Feb) and Presidents' Day (Mon 15 Feb).
- Parking: occupancy band (P10 to P90) with the P50 line, plus a horizontal capacity line (normal ramp) and a dashed line (prepared capacity). Fill above capacity in the critical colour.
- Ordinary week vs Super Bowl week: show both on the same axis so the difference is visible.
- Label axes with units (aircraft, su = space units). Direct labels beat legends. No 3D, no pie charts, no gradients that carry meaning.
- Tooltips on hover and on tap, plus the same numbers in an accessible table (visually hidden or in a details element).

## Honesty in the interface
- Tag numbers by origin with small badges: measured (FAA, NOAA), estimated, assumed. Data in `fbo_data.json` already tells you which is which (`key_assumptions`, `meta.data_classes`).
- Show uncertainty and limits in plain words near the number they qualify.
- Never present the system as deciding. Recommendations are proposals with an approver; the human approves, asks for changes or rejects.

## Accessibility and quality
- Semantic HTML (header, nav, main, section, table), visible focus states, all controls reachable by keyboard, `aria-live` for values that change with the scenario, `prefers-reduced-motion` respected.
- No console errors. Test at 360 px, 768 px and 1280 px. Check both themes.
- Load fast: no blocking scripts in head, render the first view in under a second on a laptop.

## 3D (for the parking simulation)
- Use Three.js from a pinned CDN with an import map, for example `"three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js"` and `"three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"` (OrbitControls). No build step.
- Low-poly, readable geometry. Aircraft footprints proportional to their space units (light 1.0, midsize 1.5, large 2.5). Ramp and overflow apron drawn to the same scale.
- Keep it fast: instanced or simple meshes, under 200 aircraft, 60 fps on a laptop. Pause rendering when the tab is hidden.
- The 3D view is a visual aid: the answer (which days and hours demand exceeds space, and how likely) must also be readable in plain 2D text and tables, for screen readers and phones.
- Respect `prefers-reduced-motion` (no autoplay). Show a clear fallback message if WebGL is unavailable.
