"""SYNTHETIC stand-in for P2's demand_predictions.csv, used until Marvin's forecast exists.

Same columns as the agreed contract. Numbers are illustrative, not a forecast:
baseline of 14 FBO arrivals/day = LAWA March 2025 GA + air taxi movements
(1,075 + 2,002 over 31 days, about 50 arrivals/day airport-wide) times an assumed 28 % FBO share.
"""
from pathlib import Path

import pandas as pd

BASELINE_ARRIVALS = 14
DATES = pd.date_range("2027-02-11", "2027-02-17")  # Thu -> Wed, game on Sun 14
# Medium-scenario multipliers on the baseline. Arrivals peak Sat, departures peak Mon.
ARR_MULT = [1.3, 1.8, 2.6, 2.2, 0.9, 0.8, 0.9]
DEP_MULT = [1.0, 1.1, 1.2, 1.0, 3.2, 2.0, 1.1]
# Event surge (multiplier - 1) is scaled per scenario
SCENARIO_SCALE = {"low": 0.5, "medium": 1.0, "high": 1.6}
BAND = {"p10": 0.80, "p90": 1.25}  # asymmetric interval around P50


def build() -> pd.DataFrame:
    rows = []
    for scenario, k in SCENARIO_SCALE.items():
        for date, am, dm in zip(DATES, ARR_MULT, DEP_MULT):
            arr = BASELINE_ARRIVALS * (1 + (am - 1) * k)
            dep = BASELINE_ARRIVALS * (1 + (dm - 1) * k)
            rows.append({
                "date": date.date().isoformat(), "scenario": scenario,
                "arrivals_p10": round(arr * BAND["p10"], 1), "arrivals_p50": round(arr, 1),
                "arrivals_p90": round(arr * BAND["p90"], 1),
                "departures_p10": round(dep * BAND["p10"], 1), "departures_p50": round(dep, 1),
                "departures_p90": round(dep * BAND["p90"], 1),
                "source": "synthetic_stub",
            })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    out = Path(__file__).with_name("stub_demand_predictions.csv")
    build().to_csv(out, index=False)
    print(f"wrote {out}")
