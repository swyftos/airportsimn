"""Summarize public airport proxies without altering the shared FBO forecast."""

import csv
import statistics
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from fetch_public_counts import EVENTS

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LAX_DAILY = ROOT / "sources/airport_traffic/data/processed/opsnet_lax_daily.csv"
METRICS = ("general_aviation", "air_taxi")


def read(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def write(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def presidents_day(year):
    first = date(year, 2, 1)
    first_monday = first + timedelta(days=(0 - first.weekday()) % 7)
    return first_monday + timedelta(days=14)


def holiday_checks():
    historical = read(LAX_DAILY)
    recent = read(HERE / "opsnet_lax_feb2026.csv")
    by_date = {r["date"]: r for r in historical + recent}
    if len(by_date) != len(historical) + len(recent):
        raise ValueError("Duplicate LAX dates")
    rows = []
    for year in range(2015, 2027):
        holiday = presidents_day(year)
        days = [holiday + timedelta(days=7 * week) for week in (-2, -1, 1, 2)]
        controls = [d for d in days if d.month == 2]
        if holiday.isoformat() not in by_date or any(d.isoformat() not in by_date for d in controls):
            raise ValueError(f"Incomplete holiday comparison for {year}")
        for metric in METRICS:
            count = int(by_date[holiday.isoformat()][metric])
            reference = statistics.median(int(by_date[d.isoformat()][metric]) for d in controls)
            rows.append(dict(year=year, holiday_date=holiday.isoformat(), metric=metric,
                observed_airport_operations=count, comparison_monday_median=reference,
                ratio_to_other_feb_mondays=round(count / reference, 4) if reference else "",
                other_feb_monday_count=len(controls),
                regime="recent_2023_2026" if year >= 2023 else
                       "pandemic_event_reference_2020_2022" if year >= 2020 else "pre_2020_reference",
                scope="LAX_airport_itinerant_category", data_classification="derived_public_benchmark"))
    write(HERE / "presidents_day_airport_checks.csv", rows)
    return rows


def frozen_holiday_check():
    """Recreate the branch's 60% training split and month/weekday baseline at GA scope."""
    history = read(LAX_DAILY)
    dates = sorted(date.fromisoformat(r["date"]) for r in history
                   if 2023 <= int(r["date"][:4]) <= 2025)
    train_end = dates[int(len(dates) * .6) - 1]
    train = [r for r in history if date(2023, 1, 1) <= date.fromisoformat(r["date"]) <= train_end]
    weekday = defaultdict(list)
    seasonal = defaultdict(list)
    for row in train:
        day = date.fromisoformat(row["date"])
        value = int(row["general_aviation"])
        weekday[day.weekday()].append(value)
        seasonal[day.month, day.weekday()].append(value)

    def ordinary(day):
        parent = statistics.mean(weekday[day.weekday()])
        matching = seasonal[day.month, day.weekday()]
        return (sum(matching) + 14 * parent) / (len(matching) + 14)

    by_date = {r["date"]: r for r in history + read(HERE / "opsnet_lax_feb2026.csv")}
    training_holidays = [presidents_day(y) for y in (2023, 2024)]
    factor = statistics.mean(int(by_date[d.isoformat()]["general_aviation"]) / ordinary(d)
                             for d in training_holidays)
    rows = []
    for year in (2023, 2024, 2025, 2026):
        day = presidents_day(year)
        observed = int(by_date[day.isoformat()]["general_aviation"])
        baseline = ordinary(day)
        rows.append(dict(year=year, holiday_date=day.isoformat(),
            train_end=train_end.isoformat(), training_holiday_count=len(training_holidays),
            observed_lax_ga_operations=observed, frozen_ordinary_model=round(baseline, 4),
            observed_to_ordinary_ratio=round(observed / baseline, 4),
            learned_holiday_factor=round(factor, 4),
            factor_relative_error=round(observed / (baseline * factor) - 1, 4),
            role="fit" if day <= train_end else "held_out_holiday_check",
            scope="LAX_airport_itinerant_GA", data_classification="derived_public_diagnostic"))
    write(HERE / "presidents_day_frozen_model_check.csv", rows)
    return rows


def event_checks():
    rows = read(HERE / "opsnet_super_bowl_analog_daily.csv")
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["event"], int(row["comparison_year"]), row["airport"]].append(row)
    years = (2019, 2023, 2024, 2025)
    airports = []
    eligible = {}
    for event in sorted(EVENTS):
        all_airports = sorted(EVENTS[event][1])
        complete = []
        for airport in all_airports:
            counts = {year: len(grouped[event, year, airport]) for year in years}
            is_complete = all(n == 29 for n in counts.values())
            airports.append(dict(event=event, airport=airport, **{f"days_{y}":counts[y] for y in years},
                included_in_comparison=is_complete))
            if is_complete:
                complete.append(airport)
        if not complete:
            raise ValueError(f"No complete comparison airports for {event}")
        eligible[event] = complete
    write(HERE / "super_bowl_analog_airport_coverage.csv", airports)

    ratios = []
    for event, included in eligible.items():
        event_year = int(event.split("_")[1])
        for year in years:
            selected = [r for airport in included for r in grouped[event, year, airport]]
            sunday = date.fromisoformat(selected[0]["game_sunday"])
            for metric in METRICS:
                baseline = {}
                for airport in included:
                    other = [r for r in grouped[event, year, airport]
                             if not -3 <= (date.fromisoformat(r["date"]) - sunday).days <= 1]
                    for weekday in range(7):
                        vals = [int(r[metric]) for r in other if date.fromisoformat(r["date"]).weekday() == weekday]
                        if not vals:
                            raise ValueError(f"Missing control weekday: {event} {year} {airport} {weekday}")
                        baseline[airport, weekday] = statistics.median(vals)
                event_rows = [r for r in selected if -3 <= (date.fromisoformat(r["date"]) - sunday).days <= 1]
                actual = sum(int(r[metric]) for r in event_rows)
                expected = sum(baseline[r["airport"], date.fromisoformat(r["date"]).weekday()]
                               for r in event_rows)
                ratios.append(dict(event=event, event_year=event_year, comparison_year=year,
                    metric=metric, airports="|".join(included), airport_count=len(included),
                    event_window="Thursday-Monday", airport_event_operations=actual,
                    matched_weekday_baseline_operations=expected,
                    event_to_nearby_weekday_ratio=round(actual / expected, 6),
                    scope="airport_itinerant_category", data_classification="derived_public_benchmark"))
    write(HERE / "super_bowl_analog_year_ratios.csv", ratios)

    summary = []
    for event in sorted(eligible):
        event_year = int(event.split("_")[1])
        for metric in METRICS:
            series = {r["comparison_year"]: r["event_to_nearby_weekday_ratio"]
                      for r in ratios if r["event"] == event and r["metric"] == metric}
            observed = series[event_year]
            all_controls = [v for y, v in series.items() if y != event_year]
            recent_controls = [v for y, v in series.items() if y not in (2019, event_year)]
            summary.append(dict(event=event, metric=metric, airports="|".join(eligible[event]),
                airport_count=len(eligible[event]), event_year_ratio=observed,
                control_mean_2019_and_recent=round(statistics.mean(all_controls), 6),
                excess_vs_all_controls=round(observed / statistics.mean(all_controls) - 1, 4),
                control_mean_recent_only=round(statistics.mean(recent_controls), 6),
                excess_vs_recent_controls=round(observed / statistics.mean(recent_controls) - 1, 4),
                scope="airport_itinerant_category", data_classification="derived_public_benchmark",
                transfer_to_selected_fleet_validated="no"))
    write(HERE / "super_bowl_analog_summary.csv", summary)
    return summary


def main():
    holidays = holiday_checks()
    frozen = frozen_holiday_check()
    events = event_checks()
    recent_ga = [float(r["ratio_to_other_feb_mondays"]) for r in holidays
                 if r["metric"] == "general_aviation" and r["regime"] == "recent_2023_2026"]
    print("Recent Presidents Day LAX GA ratios:", recent_ga,
          "median", round(statistics.median(recent_ga), 3))
    print("Frozen model Presidents Day factor:", frozen[0]["learned_holiday_factor"],
          "held-out ratios", [r["observed_to_ordinary_ratio"] for r in frozen if r["role"] != "fit"])
    for row in events:
        print(row["event"], row["metric"], "airports", row["airport_count"],
              "recent-control excess", row["excess_vs_recent_controls"])


if __name__ == "__main__":
    main()
