# Ramp Control — review fixes
- Full-width 3D hero, responsive HTML outlook/clock/capacity/waiting HUD, fullscreen, camera flights, follow selection and optional idle orbit; every previous 2D planning section remains.
- Richer primitive world: terminal/hangar glazing, runway exit/taxiway lights, floodlights, clock-driven sky/fog, larger source-scaled jets, beacons and attached tugs.
- Selectable world skyline shows daily P10–P90/P50, ordinary-week ghosts, probabilities and labeled ramp/prepared planes; selects the busiest illustrated hour.
- Shared-budget flex positions and minimum-move repacking eliminate false waiting; current geometry is shared by 3D/map/inspector and every reposition has a tow event.
- Modelled: demand/ranges, probabilities, capacities, flows, plan dates/costs/approvers and outcomes come from unchanged parking_data.json; daily P50 anchoring error is at most 0.70 su.
- Illustrated: positions, routes, clock shape, carry-over stays and world geometry. Flex envelopes share capacity, and are not a real stand plan or an executed aircraft decision.
- Date-valid named approvals alone activate packed/remote space and lights; the lease opens the barrier. Full-proposal comparison does not grant approval.
- Verification: verify.mjs passes all 12 combinations and 12,096 approval/hour frames, zero under-capacity waiting, at most 0.50 su waiting discrepancy; JS syntax and HTML structure checks pass.
- Browser QA remains unverified: sandbox denies HTTP binding and Chromium Mach-port startup, with no connected browser. Visual/mobile/WebGL rendering and measured frame rate need browser review.
