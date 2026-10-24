"""Check the public sidecars before interpreting their derived ratios."""

import csv
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
YEARS = (2019, 2023, 2024, 2025)


def rows(name):
    with (HERE / name).open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def main():
    feb = rows("opsnet_lax_feb2026.csv")
    assert len(feb) == 28
    assert [r["date"] for r in feb] == [
        (date(2026, 2, 1) + timedelta(days=n)).isoformat() for n in range(28)
    ]
    assert {r["airport"] for r in feb} == {"LAX"}
    assert all(r["data_classification"] == "observed_airport" for r in feb)

    # Independent monthly source: LAWA Volume of Air Traffic, February 2026.
    with (ROOT / "alan/elia_output/data/processed/lax_monthly_movements.csv").open(
        newline="", encoding="utf-8-sig"
    ) as stream:
        monthly = [r for r in csv.DictReader(stream)
                   if r["year"] == "2026" and r["month"] == "2"]
    assert len(monthly) == 1
    assert sum(int(r["air_taxi"]) for r in feb) == int(monthly[0]["air_taxi"])
    assert sum(int(r["general_aviation"]) for r in feb) == int(monthly[0]["general_aviation"])

    event = rows("opsnet_super_bowl_analog_daily.csv")
    keys = [(r["event"], r["comparison_year"], r["airport"], r["date"]) for r in event]
    assert len(keys) == len(set(keys)), "Duplicate airport-date in event source"
    assert all(r["data_classification"] == "observed_airport" for r in event)
    assert all(int(r[m]) >= 0 for r in event for m in
               ("general_aviation", "air_taxi", "local_ga"))
    grouped = defaultdict(list)
    for r in event:
        grouped[r["event"], r["comparison_year"], r["airport"]].append(r)
    for (name, year, airport), group in grouped.items():
        assert int(year) in YEARS
        sunday = date.fromisoformat(group[0]["game_sunday"])
        assert all(r["game_sunday"] == sunday.isoformat() for r in group)
        assert all(abs((date.fromisoformat(r["date"]) - sunday).days) <= 14 for r in group)
        # FAA may have no record for a listed airport in a comparison year;
        # those airports must be excluded from matched-year comparisons.
        assert len(group) <= 29, (name, year, airport)

    coverage = rows("super_bowl_analog_airport_coverage.csv")
    for r in coverage:
        counts = [len(grouped[r["event"], str(y), r["airport"]]) for y in YEARS]
        assert counts == [int(r[f"days_{y}"]) for y in YEARS]
        assert (r["included_in_comparison"] == "True") == all(n == 29 for n in counts)
    assert len(rows("super_bowl_analog_year_ratios.csv")) == 3 * 4 * 2
    assert len(rows("super_bowl_analog_summary.csv")) == 3 * 2
    assert len(rows("presidents_day_frozen_model_check.csv")) == 4
    print(f"Validated {len(feb)} LAX days against LAWA monthly totals and "
          f"{len(event)} unique FAA event-region airport-days")


if __name__ == "__main__":
    main()
