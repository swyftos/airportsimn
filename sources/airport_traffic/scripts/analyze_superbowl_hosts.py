"""Super Bowl surge at other host cities, same method as analyze_superbowl_lvi.py, to test the forecast scenarios.

Input: sources/airport_traffic/data/processed/opsnet_daily_superbowl_hosts.csv (python fetch_opsnet.py hosts)
Method: for each event and year, event window = Thursday to Monday around the anchor Sunday. Baseline for each
event day = median of the same weekday and airport over the rest of the 4-week window. Ratio = event ops / baseline
ops, summed over the host airports. Excess = game-year ratio / mean control-year ratio - 1. Metrics: air_taxi (Part
135), general_aviation (Part 91) and their sum (private, the forecast's scope).

Output: superbowl_hosts_excess.csv, one row per event x metric, with Super Bowl LVI (LAX and six LA airports) added
from superbowl_lvi_surge.csv, and whether each excess falls inside the forecast's Low-High range (+3.1% to +31%).
"""
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent.parent / "data" / "processed"
EVENT_DAYS = (-3, 1)  # Thursday to Monday
LOW, MEDIUM, HIGH = 0.031, 0.155, 0.31  # forecast scenarios (forecast/main_forecast/build_event_inputs.py)


def ratios(d: pd.DataFrame, metric: str) -> pd.DataFrame:
    rows = []
    for (event, anchor), x in d.groupby(["event", "anchor_sunday"]):
        x = x.assign(offset=(x["date"] - pd.Timestamp(anchor)).dt.days, dow=x["date"].dt.day_of_week)
        inside = x["offset"].between(*EVENT_DAYS)
        base = x[~inside].groupby(["locid", "dow"])[metric].median()
        ev = x[inside]
        baseline = sum(base.get((l, w), 0) for l, w in zip(ev["locid"], ev["dow"]))
        rows.append({"event": event, "anchor_sunday": anchor, "is_game_year": bool(x["is_game_year"].iloc[0]),
                     "ratio": ev[metric].sum() / baseline if baseline else float("nan")})
    return pd.DataFrame(rows)


def main():
    d = pd.read_csv(OUT / "opsnet_daily_superbowl_hosts.csv", parse_dates=["date"])
    d["private"] = d["air_taxi"] + d["general_aviation"]
    airports = d.groupby("event")["locid"].apply(lambda s: "+".join(sorted(s.unique())))
    out = []
    for metric in ("private", "air_taxi", "general_aviation"):
        r = ratios(d, metric)
        for event, x in r.groupby("event"):
            game, controls = x[x["is_game_year"]], x[~x["is_game_year"]]
            excess = game["ratio"].iloc[0] / controls["ratio"].mean() - 1
            out.append({"event": event, "game_sunday": game["anchor_sunday"].iloc[0], "airports": airports[event],
                        "metric": metric, "ratio_game": round(game["ratio"].iloc[0], 3),
                        "control_mean": round(controls["ratio"].mean(), 3),
                        "control_min": round(controls["ratio"].min(), 3), "control_max": round(controls["ratio"].max(), 3),
                        "excess": round(excess, 3)})
    lvi = pd.read_csv(OUT / "superbowl_lvi_surge.csv")
    for locid, name in (("LAX", "LAX"), ("ALL6", "BUR+HHR+LAX+LGB+SMO+VNY")):
        for metric in ("air_taxi", "general_aviation"):
            r = lvi[(lvi["metric"] == metric) & (lvi["locid"] == locid)].iloc[0]
            out.append({"event": f"LVI_{locid}", "game_sunday": "2022-02-13", "airports": name, "metric": metric,
                        "ratio_game": r["ratio_2022"], "control_mean": r["control_mean"],
                        "control_min": min(r["ratio_2019"], r["ratio_2023"], r["ratio_2024"]),
                        "control_max": max(r["ratio_2019"], r["ratio_2023"], r["ratio_2024"]), "excess": r["excess_2022"]})
    t = pd.DataFrame(out)
    t["within_low_high"] = t["excess"].between(LOW, HIGH)
    t["position"] = pd.cut(t["excess"], [-10, LOW, MEDIUM, HIGH, 10], labels=["below_low", "low_to_medium", "medium_to_high", "above_high"])
    t["data_classification"] = "verified_public"
    t["source"] = "FAA ATADS/OPSNET daily tower operations, https://www.aspm.faa.gov/opsnet/sys/Airport.asp"
    t.to_csv(OUT / "superbowl_hosts_excess.csv", index=False)
    print(t[["event", "metric", "ratio_game", "control_mean", "excess", "position"]].to_string(index=False))


if __name__ == "__main__":
    main()
