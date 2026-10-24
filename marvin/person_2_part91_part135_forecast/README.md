# Person 2: Part 91 and Part 135 forecast with observed weather effects

Fictional FBO at LAX, Super Bowl week February 11–17, 2027. Open `results/report.html` for the readable report.

## What is observed and what is assumed

| Piece | Status | Source |
|---|---|---|
| Daily history 2023–2025 | **Observed** FAA tower counts at LAX: general aviation for Part 91, air taxi for Part 135 | FAA ATADS/OPSNET, `alan/elia_output/data/processed/opsnet_lax_daily.csv` |
| Private-eligible share (50% of each category) | Placeholder. GA also holds training and positioning; air taxi also holds cargo feeders and small commuter flights | none |
| FBO capture (20%) | Team assumption; 0.50 × 0.20 = `fbo_market_share` 0.10 in `alan/assumptions.csv` | team |
| Super Bowl scenarios | Measured: Low +3.1% (LAX GA), Medium +15.5% (LAX air taxi), High +31% (2× Medium), five-day excess around Super Bowl LVI | FAA, `superbowl_lvi_surge.csv` |
| Presidents Day (Mon 2027-02-15) | Learned from the 2023 and 2024 holidays: Part 91 ×1.05, Part 135 ×1.29 | FAA daily counts |
| Weather effects | **Observed**: NOAA daily weather at LAX joined with FAA counts, 2016–2019 and 2023–2025 | NOAA GHCN-Daily USW00023174, `weather_effect.py` |
| Hourly curve, service times, parking prices, VIP pause | Synthetic placeholders | none |
| Parking capacity | Read from `elia/assumptions_p3.csv` (P3 owns parking) | P3 estimate |

Ordinary demand: 1.8 Part 91 and 3.1 Part 135 arrivals a day. Accuracy on the 2025 holdout days (observed counts): Part 135 errors 10% below a plain average, Part 91 7% below; about 85% of days inside the nominal 90% range. This measures the daily airport pattern, not observed FBO accuracy.

## Weather (observed)

On LAX days with at least 0.5 in of rain, Part 91 operations were 9.8% lower than on comparable dry days (95% range −18% to −1%), Part 135 4.1% lower (range −10% to +2%, not significant). Ordinary rain (0.1 in) and heavy fog show smaller or unclear effects. In February, 12% of LAX days have rain and 9% heavy fog; the week of February 11–17 had 0.75 rain days on average (at most 3) over 2015–2026. These are effects on completed operations; they do not separate cancelled flights from shifted ones. No weather forecast exists for 2027.

Heavy fog is an exploratory sensitivity, not a causal forecast. In the 166 historical heavy-fog days used here, LAX air-taxi operations averaged 3.7% above comparable dry days (95% bootstrap interval +0.2% to +7.3%), while general aviation averaged 4.3% below (interval -9.3% to +1.0%). The more recent 2023-2025 air-taxi interval includes zero. These airport totals do not identify diversions or explain the difference. The app defaults to clear weather and applies the observed association only when a user selects heavy fog; it should not be presented as extra confirmed FBO demand. See `results/weather_effect_measured.csv`.

## Run

    python run_demo.py
    python -m unittest test_part_forecast_model test_operations_extension test_weather_effect

`python fetch_noaa_weather.py` refreshes the NOAA file (network). Everything else is offline, standard library only. The model never accepts, refuses or cancels an aircraft; parking overflow is a flag for a manager.
