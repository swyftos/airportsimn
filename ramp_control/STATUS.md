# V3 situations — implemented
- 1: Opens on outlook base case × default demand; read-only model outlook, day risk labels and skyline labels; no situation/scenario selectors.
- 2: Outlook date/window drive the security pause and minute-level banner; taxi, pushback and tow intervals stay outside it.
- 3: Data-generated impact grid previews all combinations, with a fixed what-if banner and return-to-model button (including fullscreen).
- 4: Seven flow rows show rounded size counts, peak ranges/capacity, dated actions, offers/effects/approvers, discouraged incentives and human authority.
- Retained detailed jets, continuous movement, camera presets, stand views, named approvals/Undo, overflow gating and label decluttering; reinforced stacked HUD CSS.
- Model values come from unchanged parking_data.json; timing, airframe identities, geometry and stand assignments remain illustrations. Offers never dispatch/refuse aircraft.
- verify.mjs retains every existing assertion: PASS, 12 combinations / 12,096 frames; added 84 exact flow rows, impact/default checks, 92 pause-safe intervals and offer/boundary checks.
- verify-app.mjs: PASS for all previews, return, synchronized views, pause banner, scoped named approvals/Undo. Existing delay-game-day discrepancy remains visible (14 vs 15); max peak error 2.20 su, within original rounding tolerance.
- Visual/WebGL/mobile QA could not run: sandbox denied HTTP listen and headless Chromium launch; syntax checks and Node/DOM-adapter checks passed.
