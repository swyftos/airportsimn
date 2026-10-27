# Super Bowl LXI — AI Airport Readiness Planner (team guidelines, source of truth)

Fictional FBO at LAX · Super Bowl LXI Feb 14 2027 (SoFi) · Planning window Feb 11–17 2027.

**Central objective:** predict additional aircraft demand during Super Bowl week and determine how the FBO should prepare parking capacity, ground operations, fuel services and staffing. Main optimization focus = **aircraft parking**; arrivals, fuel and staffing are supporting variables.

## Judging
Innovation · Accuracy (real data, transparent assumptions, evaluation, intervals) · Practical preparation (parking, staffing, fuel workload, contingencies) · Privacy (no passenger/owner data) · Uncertainty (Low/Medium/High with ranges) · Humans in command (AI recommends, humans decide).

## Roles
- **P1 Data:** LAX 2016–2025 excl. 2020–2022, GA/air taxi, Super Bowl LVI (Feb 2022) activity, seasonal baseline, documented synthetic data. → historical_traffic.csv, baseline.csv, data_sources.md, assumptions.csv
- **P2 Forecast:** explainable daily arrivals/departures model, intervals, Low/Med/High, backtest vs seasonal baseline (MAE, interval coverage). → forecast_model.py, demand_predictions.csv, uncertainty_results.csv
- **P3 Parking & resources:** forecasts → parking occupancy (aircraft size, duration, capacity); ground staffing; fuel workload; shortages & bottlenecks; recommendations per scenario; improvement vs no advance plan. Fuel/staffing stay simple supporting calcs. → **parking_optimizer.py, resource_requirements.csv, scenario_recommendations.json**
- **P4 Dashboard & responsible AI:** dashboard, scenario switch, uncertainty & assumptions display, recommendations, human approval workflow, demo.

## Data strategy
Three classes, always labeled: **verified public** (FAA, LAWA, weather), **estimated/benchmark** (FBO share, parking durations), **synthetic** (reservations, spaces, PPR). Airport-wide movements ≠ FBO demand. Synthetic results never presented as real forecasting performance. Reference: LAWA March 2025 = 1,075 GA, 2,002 air taxi, 49,185 total movements.

## Output per day
Expected arrivals, departures, parking utilization vs capacity, staffing by shift, fuel workload, risk Low/Med/High, AI recommendation, human approval flag. Low = capacity sufficient; Medium = extra preparation; High = exceeds capacity → contingency.

## Evaluation
Forecast accuracy (MAE, interval coverage vs seasonal baseline). Operational impact: with vs without AI preparation — utilization, unaccommodated requests, staffing efficiency, shortages avoided; savings only from explicit cost assumptions.

## Humans in command — the system never autonomously
authorizes aircraft movements; accepts/rejects an individual reservation; cancels a confirmed reservation; activates facilities or commits money; processes passenger information.

## Timeline
H0–3 scope/schemas/contracts (all) · H3–10 data+baseline (P1,P2) · H10–18 forecast+parking (P2,P3) · H18–27 dashboard/scenarios/approval (P3,P4) · H27–30 validation & impact (all) · H30–36 deploy, pitch.
Stack: Python, pandas, scikit-learn, light optimization; Streamlit (or React/Next.js).

## Demo sequence
1 baseline → 2 forecast with intervals → 3 parking/staffing/fuel → 4 plan with human approval → 5 No Preparation vs AI Preparation.
