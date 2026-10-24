"""Weekday profile and daily variability of GA + air-taxi operations at LAX, from FAA OPSNET daily counts.

Input: alan/elia_output/data/processed/opsnet_lax_daily.csv (python fetch_opsnet.py lax-daily)
Method: business-aviation proxy = itinerant air_taxi + general_aviation operations (LAX has no local GA).
Each day is divided by the mean of its calendar month, so the index removes seasonality and the
structural level shift between 2016-2019 and 2023-2025.

Outputs (alan/elia_output/data/processed/):
  opsnet_lax_weekday_profile.csv  weekday index (mean, std, days) for 2023-2025 and 2016-2019
  opsnet_lax_daily_check.csv      daily sums vs monthly OPSNET totals, one row per month
"""
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent.parent / "data" / "processed"
WINDOWS = {"2023-2025": (2023, 2024, 2025), "2016-2019": (2016, 2017, 2018, 2019)}
ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def main():
    d = pd.read_csv(OUT / "opsnet_lax_daily.csv", parse_dates=["date"])
    m = pd.read_csv(OUT / "opsnet_lax_monthly.csv")

    sums = d.groupby([d["date"].dt.year.rename("year"), d["date"].dt.month.rename("month")])[
        ["air_taxi", "general_aviation", "total"]].sum().reset_index()
    check = sums.merge(m[["year", "month", "air_taxi", "general_aviation", "total"]],
                       on=["year", "month"], suffixes=("_daily_sum", "_monthly"))
    check["matches"] = (check[[f"{c}_daily_sum" for c in ("air_taxi", "general_aviation", "total")]].to_numpy()
                        == check[[f"{c}_monthly" for c in ("air_taxi", "general_aviation", "total")]].to_numpy()).all(axis=1)
    check.to_csv(OUT / "opsnet_lax_daily_check.csv", index=False)

    d["ga_air_taxi"] = d["air_taxi"] + d["general_aviation"]
    rows = []
    for label, years in WINDOWS.items():
        x = d[d["date"].dt.year.isin(years)].copy()
        x["index"] = x["ga_air_taxi"] / x.groupby(x["date"].dt.to_period("M"))["ga_air_taxi"].transform("mean")
        g = x.groupby(x["date"].dt.day_name())["index"].agg(["mean", "std", "count"]).reindex(ORDER)
        for day, r in g.iterrows():
            rows.append({"window": label, "weekday": day, "index_mean": round(r["mean"], 3),
                         "index_std": round(r["std"], 3), "days": int(r["count"]),
                         "data_classification": "verified_public", "source": "FAA ATADS/OPSNET, LAX daily tower operations"})
    profile = pd.DataFrame(rows)
    profile.to_csv(OUT / "opsnet_lax_weekday_profile.csv", index=False)
    print(f"months matching monthly totals: {check['matches'].sum()} / {len(check)}")
    print(profile.pivot(index="window", columns="weekday", values="index_mean")[ORDER].to_string())


if __name__ == "__main__":
    main()
