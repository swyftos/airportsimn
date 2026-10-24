# Status: Super Bowl LXI FBO Planning Dashboard (site_gemini)
- **Pages/Views**: 5 accessible tabs (Week at a Glance, Flight Demand Predict, Ramp & What-If Simulation, Action Plan & Slot Advisor, Model Trust & Verification).
- **Core Features**: Live scenario (Low/Med/High) and operational situation (standard, 24h delay, security restriction, heavy rain) reactive switching.
- **Interactive Visualizations**: Hand-rolled responsive SVG charts with 90% uncertainty bands, event markers, size-mix breakdown, and 3-year FAA history.
- **What-If Engine**: Real-time browser simulation modeling ramp capacity (su), demand shocks, tow-packing, and apron leasing with instant feedback.
- **Human-in-Command**: Prominent AI safeguard (`meta.never_allowed`); action authorization workflow (Approve/Changes/Reject) with localStorage and JSON export.
- **Economics & Slot Advisor**: Drop-and-go credit sensitivity table; evidence-based finding showing why cheap early arrival fails to relieve ramp crowding.
- **Model Trust**: Out-of-sample backtest (14.9% WAPE vs 4 baselines), 8-city Super Bowl benchmark, NOAA weather sensitivity, and assumption badges.
- **How to Run**: Run `cd site_gemini && python3 -m http.server 8000`, then open `http://localhost:8000/` in any modern web browser.
- **Known Gaps**: Static prototype; what-if simulation is a client-side approximation of the 10,000-run Monte Carlo model.
