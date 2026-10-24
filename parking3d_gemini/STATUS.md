# Status: LAX FBO 3D Parking Simulator (Gemini)
- **Answer**: Peak demand on Sun Feb 14 Game Day (P50 17.4 su, P90 21.3 su vs 15.0 su ramp, 81.3% chance over). First overflow Fri Feb 12 (81.7%).
- **Plan**: Tight tow-packing (+10% ramp gain) + 5 su overflow apron lease ($3,500 cost, 62% payoff probability, unaccommodated aircraft reduced 2.3 -> 0.1).
- **3D Ramp**: Explorable Three.js airfield with free orbit camera, 15 su marked stands, remote overflow apron, and manager holding area.
- **Day/Night Lighting**: Directional sun trajectory, sky tones, and high-mast floodlight towers that dynamically illuminate stands at dusk/night.
- **Week Timeline**: 7-day strip colored by model over-capacity risk (green/amber/red); clicking any day scrubs simulation clock to that date.
- **2D Visibility**: Executive KPI cards, interactive SVG forecast chart (P10-P90 band), and accessible table with formulas operate independently of 3D.
- **Governance**: Recommends only; named managers approve actions. Overflow aircraft wait for manager decisions and are never refused.
- **Tech**: Zero-build, vanilla HTML/CSS/JS with Three.js 0.160.0 pinned CDN import map, tabular numerals, mobile-responsive (no scroll at 390px).

## Review (Claude, headless Chromium with WebGL)
- Loads with no console errors; WebGL context OK; 390 px phone width OK; numbers match parking_data.json.
- Interactions checked: Low / Medium / High, the four situations, day cards, plan toggles, play/pause.
- Fixed, hard-coded values now read from parking_data.json: ramp and prepared capacity, the ordinary-week maximum chance (was 5.0%, data says 21%), the security window, the heavy-rain and game-night dates, situation labels, the capacity derivation, opening aircraft sizes, the game-day chart marker.
- Fixed: "Game Day" was printed on whichever day peaked (Monday under the 24 h delay).
- Fixed: the 3D ramp did not hold the model's daily demand (game day Medium peaked at 9.5 su against a model P50 of 17.4). Each day is now topped up with carry-over aircraft until its busiest moment matches the P50; the inspector labels them as model stock, not forecast arrivals. Days whose generated flights already exceed P50 are not trimmed (Thu under the 24 h delay: 16.0 vs 14.1).
