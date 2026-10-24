"""Step 3/5 (Alan): build the 7-row alan/baseline.csv the dashboard (Nazar's
INTEGRATION.md contract) expects, plus alan/assumptions.csv.

Input:  alan/data/processed/historical_traffic_interim.csv
        (airport-wide, daily, air_taxi + general_aviation only, 50/50
        arrivals/departures split -- built by build_historical_traffic.py)

Output: alan/baseline.csv       -- exactly 7 rows, one per planning date
        alan/assumptions.csv    -- the assumption ledger behind those rows

Per INTEGRATION.md: "Dates are planning dates aligned to the ordinary-week
comparison, not the original historical observation dates." So each of the
7 planning dates (2027-02-11 .. 2027-02-17) gets the historical average for
ITS OWN WEEKDAY, in February, across ordinary (non-COVID, non-event) years.
This preserves weekday seasonality (e.g. weekend vs weekday GA patterns)
instead of just averaging across "any February day."

Three additional assumptions, beyond the monthly->daily and 50/50
arrivals/departures split already applied in the interim file, are needed
to get from "all of LAX" down to "this fictional FBO's parking baseline":

  1. FBO_MARKET_SHARE: this fictional FBO's share of LAX's total GA +
     air-taxi traffic. LAX realistically has two real FBOs (Atlantic
     Aviation, Signature -- see Nazar's apron research). A new, smaller
     fictional entrant capturing an even 1/3 split is optimistic; 20% is
     used as a conservative starting assumption, easy to change via the
     named constant below.

  2. AVG_DWELL_DAYS: parking_units (how many aircraft are ON THE GROUND on
     a given day) is NOT the same as arrivals that day -- it also depends
     on how long aircraft stay. Using the three occupancy categories named
     in the project brief (same-day turn, overnight, multi-day) with an
     illustrative ordinary-week mix of 40% / 45% / 15% and dwell times of
     roughly 0.5 / 1 / 3 days gives a weighted average dwell of:
         0.40*0.5 + 0.45*1 + 0.15*3 = 1.10 days
     This is a benchmark estimate, not a measured figure -- refine with
     better evidence if time allows.

  3. Steady-state occupancy (Little's Law): for a queue/system in steady
     state, average number present = average arrival rate x average time
     each one stays. Applied here: parking_units(day) ~= arrivals_fbo(day)
     x AVG_DWELL_DAYS. This assumes the ordinary week is already in
     steady state (opening occupancy = the steady-state average itself,
     not zero / not ramping up from an empty ramp).
"""
import calendar
import csv
from pathlib import Path

HERE = Path(__file__).parent
IN_PATH = HERE.parent / "data" / "processed" / "historical_traffic_interim.csv"
BASELINE_OUT = HERE.parent / "baseline.csv"
ASSUMPTIONS_OUT = HERE.parent / "assumptions.csv"

FBO_MARKET_SHARE = 0.20
AVG_DWELL_DAYS = 1.10

# Training window for the ordinary-week baseline. LAX GA + air-taxi traffic
# shows a large structural break across COVID: February daily averages run
# ~175/day pre-COVID (2016-2019) vs. ~98/day post-COVID (2023-2025) -- a
# ~45% drop, not noise. The forecast target (Feb 2027) is a post-COVID year,
# so blending pre- and post-COVID years without a level-shift adjustment
# would overstate today's actual traffic by roughly 45%. Restricting to
# post-COVID years only is the simpler, more defensible fix versus applying
# an unvalidated level-shift correction factor to the older years.
# Pre-COVID years (2016-2019) stay in historical_traffic_interim.csv as
# reference/audit data; they are just excluded from this average.
BASELINE_YEARS = {2023, 2024, 2025}

# Day-of-week multiplier applied to the flat monthly average (the interim
# historical file has no day-of-week signal -- it was built by spreading
# each month's total evenly across its days). This is an ILLUSTRATIVE
# BENCHMARK, not measured for this FBO: typical general aviation / business
# jet traffic skews weekday-heavy with a Saturday trough and a partial
# Sunday rebound (return travel). Multipliers are normalized to average
# exactly 1.0 across the week, so the weekly total is unchanged -- only its
# daily distribution shifts.
WEEKDAY_MULTIPLIERS = {
    "Monday": 1.08,
    "Tuesday": 1.12,
    "Wednesday": 1.12,
    "Thursday": 1.08,
    "Friday": 1.00,
    "Saturday": 0.65,
    "Sunday": 0.95,
}
assert abs(sum(WEEKDAY_MULTIPLIERS.values()) / 7 - 1.0) < 1e-9, "weekday multipliers must average to 1.0"

# Planning week and its weekday sequence (fixed by the team's dashboard contract)
PLANNING_DATES = [
    "2027-02-11", "2027-02-12", "2027-02-13",
    "2027-02-14", "2027-02-15", "2027-02-16", "2027-02-17",
]


def weekday_name(date_str):
    y, m, d = (int(p) for p in date_str.split("-"))
    return calendar.day_name[calendar.weekday(y, m, d)]


def main():
    with open(IN_PATH, newline="") as f:
        rows = list(csv.DictReader(f))

    # Ordinary February days: month == 2, not flagged excluded_covid (covers
    # 2020/2021/2022, which also removes the Super Bowl LVI event month),
    # AND restricted to BASELINE_YEARS to avoid blending pre-/post-COVID
    # traffic levels (see constant comment above).
    feb_ordinary = [
        r for r in rows
        if r["date"][5:7] == "02"
        and r["excluded_covid"] == "False"
        and int(r["date"][:4]) in BASELINE_YEARS
    ]

    by_weekday = {}
    for r in feb_ordinary:
        wd = weekday_name(r["date"])
        by_weekday.setdefault(wd, []).append(r)

    planning_weekdays = [weekday_name(d) for d in PLANNING_DATES]
    missing = [wd for wd in set(planning_weekdays) if wd not in by_weekday]
    if missing:
        raise ValueError(f"No historical February data for weekday(s): {missing}")

    baseline_rows = []
    for date, wd in zip(PLANNING_DATES, planning_weekdays):
        matches = by_weekday[wd]
        avg_arrivals_airportwide = sum(float(r["arrivals"]) for r in matches) / len(matches)
        avg_departures_airportwide = sum(float(r["departures"]) for r in matches) / len(matches)

        dow_mult = WEEKDAY_MULTIPLIERS[wd]
        arrivals_fbo = avg_arrivals_airportwide * dow_mult * FBO_MARKET_SHARE
        departures_fbo = avg_departures_airportwide * dow_mult * FBO_MARKET_SHARE
        parking_units = arrivals_fbo * AVG_DWELL_DAYS

        baseline_rows.append(
            {
                "date": date,
                "arrivals": round(arrivals_fbo),
                "departures": round(departures_fbo),
                "parking_units": round(parking_units),
            }
        )

    with open(BASELINE_OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "arrivals", "departures", "parking_units"])
        w.writeheader()
        w.writerows(baseline_rows)

    assumptions_rows = [
        {
            "id": "fbo_market_share",
            "label": "Fictional FBO's share of LAX GA + air-taxi traffic",
            "value": FBO_MARKET_SHARE,
            "unit": "fraction",
            "classification": "assumption",
            "source": "Team judgment, informed by Nazar's apron research (2 real incumbent FBOs: Atlantic, Signature)",
            "note": "Conservative share for a smaller/newer third entrant, not an even 1/3 split. Change the FBO_MARKET_SHARE constant in build_baseline.py to revise.",
        },
        {
            "id": "avg_dwell_days",
            "label": "Average parking dwell time, ordinary week",
            "value": AVG_DWELL_DAYS,
            "unit": "days",
            "classification": "benchmark",
            "source": "Weighted from illustrative occupancy mix: 40% same-day turn (0.5d), 45% overnight (1d), 15% multi-day (3d)",
            "note": "Occupancy-mix shares are illustrative per project brief Section 4, not measured for this FBO. Refine if real dwell-time evidence is found.",
        },
        {
            "id": "parking_units_method",
            "label": "Parking occupancy estimation method",
            "value": "Little's Law: parking_units = arrivals_fbo x avg_dwell_days",
            "unit": "method",
            "classification": "assumption",
            "source": "Standard steady-state queueing relationship",
            "note": "Assumes the ordinary week is already in steady state (opening occupancy = computed average), not ramping up from empty.",
        },
        {
            "id": "historical_base",
            "label": "Underlying airport-wide movement data",
            "value": "LAWA TCOM monthly movements, Feb (ordinary years), disaggregated to daily",
            "unit": "n/a",
            "classification": "benchmark",
            "source": "Elia (LAWA TCOM, verified_public) via Alan's build_historical_traffic.py (monthly->daily, 50/50 arrivals/departures)",
            "note": "Weekday-matched February average across ordinary (non-COVID, non-2022) years; see alan/scripts/build_baseline.py docstring for full methodology.",
        },
    ]

    assumptions_rows.append(
        {
            "id": "baseline_training_window",
            "label": "Years used for the ordinary-week baseline average",
            "value": str(sorted(BASELINE_YEARS)),
            "unit": "years",
            "classification": "assumption",
            "source": "Alan's analysis of alan/elia_output lax_monthly_movements.csv",
            "note": "Restricted to post-COVID years only. Feb daily mean: ~175/day in 2016-2019 vs ~98/day in 2023-2025 (~45% drop, structural break not noise). Blending both without a level-shift would overstate 2027 ordinary traffic. 2016-2019 remain in historical_traffic_interim.csv as reference data, excluded only from this baseline average. See issue #10.",
        }
    )

    assumptions_rows.append(
        {
            "id": "weekday_multiplier",
            "label": "Day-of-week traffic multiplier applied to flat monthly average",
            "value": str(WEEKDAY_MULTIPLIERS),
            "unit": "ratio per weekday",
            "classification": "benchmark",
            "source": "Illustrative general aviation/business-jet weekly pattern (weekday-heavy, Saturday trough, partial Sunday rebound)",
            "note": "Not measured for this FBO or LAX specifically; the underlying historical file has no native day-of-week signal (monthly totals were spread evenly across days). Multipliers average to 1.0, so weekly totals are unchanged. See alan/scripts/build_baseline.py.",
        }
    )

    with open(ASSUMPTIONS_OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "label", "value", "unit", "classification", "source", "note"])
        w.writeheader()
        w.writerows(assumptions_rows)

    print(f"Wrote {len(baseline_rows)} rows to {BASELINE_OUT}")
    for r in baseline_rows:
        print(" ", r)
    print(f"Wrote {len(assumptions_rows)} rows to {ASSUMPTIONS_OUT}")


if __name__ == "__main__":
    main()
