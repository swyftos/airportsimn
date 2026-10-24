"""Step 2 (Elia): clean monthly LAX movement series from the parsed TCOM readings, validated against
LAWA's official 10-year summary of FAA aircraft movements.

Rules, in order of preference for each month:
  1. tcom_current      value printed for the report month itself
  2. tcom_prior_year   same month read from the next year's report (fills months whose link on the LAWA
                       page points to the wrong file, or whose PDF is a scan)
  3. annual_residual   official annual total minus the 11 other months (only if exactly one month is missing)

Outputs (alan/elia_output/data/processed/):
  lawa_annual_10yr.csv       official annual totals scraped from LAWA
  lax_monthly_movements.csv  year, month, air_carrier, air_taxi, general_aviation, military, total,
                             value_source, excluded_covid, data_classification, source_url
  validation_report.csv      per-year sum of months vs official annual total
"""
import re
import html
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent  # alan/elia_output/
OUT = ROOT / "data" / "processed"
ANNUAL_URL = "https://www.lawa.org/lawa-investor-relations/statistics-for-lax/10-year-summary/faa-aircraft-movements"
CATS = ["air_carrier", "air_taxi", "military", "general_aviation", "total"]  # column order on the LAWA page
EXCLUDED = {2020, 2021, 2022}  # team guideline: COVID years excluded from trend fitting
MIN_YEAR = 2015  # first year with all 12 monthly reports on the LAWA page


def annual_totals() -> pd.DataFrame:
    req = urllib.request.Request(ANNUAL_URL, headers={"User-Agent": "Mozilla/5.0"})
    text = html.unescape(re.sub(r"<[^>]+>", " ", urllib.request.urlopen(req, timeout=60).read().decode()))
    text = re.sub(r"\s+", " ", text)
    rows = [{"year": int(m[0]), **{c: int(v.replace(",", "")) for c, v in zip(CATS, m[1:])}}
            for m in re.findall(r"\b(20\d\d) ([\d,]+) ([\d,]+) ([\d,]+) ([\d,]+) ([\d,]+)", text)]
    return pd.DataFrame(rows).drop_duplicates("year").sort_values("year")


def main():
    raw = pd.read_csv(OUT / "lawa_monthly_movements.csv")
    annual = annual_totals()
    annual.to_csv(OUT / "lawa_annual_10yr.csv", index=False)

    best = []
    for col, label in (("current", "tcom_current"), ("prior_year", "tcom_prior_year")):
        part = raw[raw["column"] == col].copy()
        # a month printed by two different reports as "current" means a mislinked file; keep the report whose
        # URL appears once for that month only if values agree, otherwise drop both and let the fallback fill it
        agree = part.groupby(["year", "month"])["total"].transform("nunique") == 1
        part = part[agree].drop_duplicates(["year", "month"])
        part["value_source"] = label
        best.append(part)
    monthly = pd.concat(best).drop_duplicates(["year", "month"], keep="first")

    years = range(MIN_YEAR, int(monthly["year"].max()) + 1)
    for y in years:
        have = set(monthly.loc[monthly["year"] == y, "month"])
        missing = sorted(set(range(1, 13)) - have)
        row = annual[annual["year"] == y]
        if len(missing) == 1 and not row.empty:
            rest = monthly[monthly["year"] == y][CATS].sum()
            fill = {c: int(row[c].iloc[0] - rest[c]) for c in CATS}
            monthly = pd.concat([monthly, pd.DataFrame([{"year": y, "month": missing[0], **fill,
                                                         "report_url": ANNUAL_URL,
                                                         "value_source": "annual_residual"}])])

    monthly = monthly[monthly["year"] >= MIN_YEAR].sort_values(["year", "month"])
    monthly["excluded_covid"] = monthly["year"].isin(EXCLUDED)
    monthly["data_classification"] = "verified_public"
    monthly = monthly.rename(columns={"report_url": "source_url"})
    keep = ["year", "month", "air_carrier", "air_taxi", "general_aviation", "military", "total",
            "value_source", "excluded_covid", "data_classification", "source_url"]
    monthly[keep].to_csv(OUT / "lax_monthly_movements.csv", index=False)

    sums = monthly.groupby("year")[CATS].sum().join(monthly.groupby("year").size().rename("months"))
    val = sums.join(annual.set_index("year"), how="inner", suffixes=("", "_official"))
    for c in ("air_taxi", "general_aviation", "total"):
        val[f"{c}_diff"] = val[c] - val[f"{c}_official"]
    val["matches_official"] = (val["months"] == 12) & (val[[f"{c}_diff" for c in ("air_taxi", "general_aviation", "total")]] == 0).all(axis=1)
    val.reset_index()[["year", "months", "air_taxi_diff", "general_aviation_diff", "total_diff", "matches_official"]] \
        .to_csv(OUT / "validation_report.csv", index=False)
    print(val[["months", "air_taxi_diff", "general_aviation_diff", "total_diff", "matches_official"]].to_string())
    print(monthly["value_source"].value_counts().to_string())


if __name__ == "__main__":
    main()
