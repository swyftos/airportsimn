"""Data-integrity checks requested in review of PR #57 (dashboard/TEST_REPORT.md,
"Not tested yet" / the data team): the FAA-derived historical series has no missing
days and no duplicate rows, and the 2022 Super Bowl LVI LAX surge used for
the Low/Medium scenario labels ("+3.1% LAX general aviation", "+15.5% LAX
air taxi") is reproducible from the raw FAA OPSNET daily counts, not just
copied from the committed intermediate file.

Standard library only (no pandas/pytest dependency), so it runs anywhere
sources/tests/test_build_historical_traffic.py does.
"""
import csv
import datetime as dt
import statistics
import unittest
from pathlib import Path

DATA = Path(__file__).resolve().parents[1]
ROOT = DATA.parent

HISTORICAL_FILES = {
    "general_aviation (Part 91)": DATA / "data" / "processed" / "historical_traffic_interim.csv",
    "air_taxi (Part 135)": DATA / "data" / "processed" / "historical_traffic_air_taxi_interim.csv",
}

OPSNET_SUPERBOWL = DATA / "airport_traffic" / "data" / "processed" / "opsnet_daily_superbowl.csv"
SURGE_FILE = DATA / "airport_traffic" / "data" / "processed" / "superbowl_lvi_surge.csv"

GAME_SUNDAY = {2022: dt.date(2022, 2, 13), 2019: dt.date(2019, 2, 10),
               2023: dt.date(2023, 2, 12), 2024: dt.date(2024, 2, 11)}
EVENT_OFFSETS = range(-3, 2)  # Thursday through Monday, inclusive


def load_dates(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [dt.date.fromisoformat(r["date"]) for r in csv.DictReader(f)]


def lax_excess_from_raw(metric):
    """Re-derive the 2022 LAX excess for one metric straight from the raw
    OPSNET daily counts, using the same method as
    sources/airport_traffic/scripts/analyze_superbowl_lvi.py (baseline = median of
    the same weekday outside the Thu-Mon event window; excess_2022 =
    2022 ratio / mean of the 2019/2023/2024 control-year ratios - 1)."""
    with open(OPSNET_SUPERBOWL, newline="", encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if r["locid"] == "LAX"]

    by_year = {}
    for r in rows:
        d = dt.date.fromisoformat(r["date"])
        by_year.setdefault(d.year, []).append((d, float(r[metric])))

    ratios = {}
    for year, sunday in GAME_SUNDAY.items():
        year_rows = by_year.get(year, [])
        in_event = lambda d: (d - sunday).days in EVENT_OFFSETS
        by_weekday = {}
        for d, v in year_rows:
            if not in_event(d):
                by_weekday.setdefault(d.weekday(), []).append(v)
        baseline_by_weekday = {wd: statistics.median(vs) for wd, vs in by_weekday.items()}

        event_total, baseline_total = 0.0, 0.0
        for d, v in year_rows:
            if in_event(d):
                event_total += v
                baseline_total += baseline_by_weekday[d.weekday()]
        ratios[year] = event_total / baseline_total

    control_mean = statistics.mean(ratios[y] for y in (2019, 2023, 2024))
    return ratios[2022] / control_mean - 1


class NoMissingOrDuplicateDaysTests(unittest.TestCase):
    def test_no_duplicate_dates(self):
        for name, path in HISTORICAL_FILES.items():
            with self.subTest(series=name):
                dates = load_dates(path)
                self.assertEqual(len(dates), len(set(dates)),
                                  f"{name}: duplicate date rows in {path.name}")

    def test_no_missing_days(self):
        for name, path in HISTORICAL_FILES.items():
            with self.subTest(series=name):
                dates = sorted(load_dates(path))
                expected = (dates[-1] - dates[0]).days + 1
                self.assertEqual(len(dates), expected,
                                  f"{name}: {expected - len(dates)} day(s) missing between "
                                  f"{dates[0]} and {dates[-1]} in {path.name}")


class SuperBowlLviSurgeReproducibilityTests(unittest.TestCase):
    """Confirms the +3.1% / +15.5% scenario labels trace back to the raw
    FAA OPSNET counts, not just to the committed superbowl_lvi_surge.csv."""

    def test_lax_general_aviation_excess_matches_raw(self):
        self.assertAlmostEqual(lax_excess_from_raw("general_aviation"), 0.031, places=3)

    def test_lax_air_taxi_excess_matches_raw(self):
        self.assertAlmostEqual(lax_excess_from_raw("air_taxi"), 0.155, places=3)

    def test_raw_derived_values_match_committed_surge_file(self):
        """The committed superbowl_lvi_surge.csv (read by the forecast model)
        must still equal what re-running the method on raw data gives."""
        with open(SURGE_FILE, newline="", encoding="utf-8-sig") as f:
            committed = {(r["metric"], r["locid"]): float(r["excess_2022"]) for r in csv.DictReader(f)}
        for metric in ("general_aviation", "air_taxi"):
            with self.subTest(metric=metric):
                self.assertAlmostEqual(lax_excess_from_raw(metric), committed[(metric, "LAX")], places=3)


if __name__ == "__main__":
    unittest.main()
