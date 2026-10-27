"""Super Bowl LVI (Sun 13 Feb 2022, SoFi) surge signal from FAA OPSNET daily tower counts.

Input: sources/airport_traffic/data/processed/opsnet_daily_superbowl.csv (from fetch_opsnet.py)
Method: for each airport and year, event window = Thursday to Monday around the game Sunday
(anchored on the second Sunday of February in control years). Baseline for each event day = median of
the same weekday over the rest of the 4-week window. Ratio = event ops / baseline ops. The 2022 excess is
the 2022 ratio divided by the mean ratio of control years 2019, 2023, 2024 (no Super Bowl in LA),
which removes the normal mid-February pattern (Valentine's weekend, Presidents' Day week).

Outputs (sources/airport_traffic/data/processed/):
  superbowl_lvi_surge.csv          ratio per metric x airport x year, plus 2022 excess over controls
  superbowl_lvi_daily_profile.csv  2022 air-taxi ops per day offset (all six airports) vs baseline
"""
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent.parent / "data" / "processed"
GAME_SUNDAY = {2022: "2022-02-13", 2019: "2019-02-10", 2023: "2023-02-12", 2024: "2024-02-11"}
EVENT_DAYS = (-3, 1)  # Thursday to Monday
METRICS = ("air_taxi", "general_aviation")


def with_baseline(x: pd.DataFrame, metric: str) -> pd.DataFrame:
    in_event = x["offset"].between(*EVENT_DAYS)
    dow = x["date"].dt.day_of_week
    base = x[~in_event].groupby(["locid", dow[~in_event]])[metric].median()
    return x.assign(baseline=[base.get((l, d)) for l, d in zip(x["locid"], dow)])


def main():
    d = pd.read_csv(OUT / "opsnet_daily_superbowl.csv", parse_dates=["date"])
    rows, profile = [], None
    for metric in METRICS:
        for year, sunday in GAME_SUNDAY.items():
            x = d[d["date"].dt.year == year].copy()
            x["offset"] = (x["date"] - pd.Timestamp(sunday)).dt.days
            x = with_baseline(x, metric)
            ev = x[x["offset"].between(*EVENT_DAYS)]
            g = ev.groupby("locid")[[metric, "baseline"]].sum()
            g.loc["ALL6"] = g.sum()
            for loc, r in g.iterrows():
                rows.append({"metric": metric, "year": year, "locid": loc, "event_ops": r[metric],
                             "baseline_ops": r["baseline"], "ratio": r[metric] / r["baseline"]})
            if metric == "air_taxi" and year == 2022:
                profile = x[x["offset"].between(-5, 3)].groupby("offset")[["air_taxi", "baseline"]].sum()
                profile["ratio"] = (profile["air_taxi"] / profile["baseline"]).round(3)

    r = pd.DataFrame(rows)
    wide = r.pivot_table(index=["metric", "locid"], columns="year", values="ratio")
    wide["control_mean"] = wide[[y for y in GAME_SUNDAY if y != 2022]].mean(axis=1)
    wide["excess_2022"] = wide[2022] / wide["control_mean"] - 1
    wide.columns = [f"ratio_{c}" if isinstance(c, int) else c for c in wide.columns]
    wide.round(3).reset_index().to_csv(OUT / "superbowl_lvi_surge.csv", index=False)
    profile.reset_index().to_csv(OUT / "superbowl_lvi_daily_profile.csv", index=False)
    print(wide.round(3).to_string())
    print(profile.to_string())


if __name__ == "__main__":
    main()
