"""Step 3/5 (the data team): build the 7-row sources/baseline.csv the dashboard (the dashboard team's
INTEGRATION.md contract) expects, plus sources/assumptions.csv.

Input:  sources/data/processed/historical_traffic_interim.csv
        (airport-wide, daily, Part 91 general_aviation, 50/50
        arrivals/departures split -- built by build_historical_traffic.py
        from the forecast team's verified daily GA extract, not a monthly spread)
        plus sources/data/processed/historical_traffic_air_taxi_interim.csv
        (same layout, Part 135 air_taxi, build_historical_traffic_air_taxi.py),
        summed per day: the team scope is Part 91 + Part 135.

Output: sources/baseline.csv       -- exactly 7 rows, one per planning date
        sources/assumptions.csv    -- the assumption ledger behind those rows

Per INTEGRATION.md: "Dates are planning dates aligned to the ordinary-week
comparison, not the original historical observation dates." So each of the
7 planning dates (2027-02-11 .. 2027-02-17) gets the historical average for
ITS OWN WEEKDAY, in February, across ordinary (non-COVID, non-event) years.
This preserves weekday seasonality (e.g. weekend vs weekday GA patterns)
instead of just averaging across "any February day."

Three additional assumptions, beyond the daily GA-only extraction and
50/50 arrivals/departures split already applied in the interim file, are
needed to get from "all of LAX's GA category" down to "this fictional
FBO's parking baseline":

  1. EFFECTIVE_SHARE: this fictional FBO's share of LAX's Part 91 GA
     traffic, built from two factors the team was previously applying
     inconsistently (one pipeline used a flat 20% on the combined
     GA+air-taxi total, the other used 50% eligibility x 20% capture =
     10% on GA alone):
       - PRIVATE_ELIGIBLE_FRACTION (0.50): fraction of the raw FAA
         general_aviation category that is actually private/FBO-eligible
         traffic (excludes flight training, positioning flights, etc --
         see sources/docs/traffic_categories_and_fleet_mix.md section 1.3).
         This is the forecast team's number (private_eligibility_sensitivity.csv).
       - FBO_CAPTURE_SHARE (0.20): of that already-filtered private
         traffic, the fictional FBO's capture share. LAX realistically
         has two real FBOs (Atlantic Aviation, Signature -- see the dashboard team's
         apron research); 20% is a conservative starting assumption for a
         smaller, newer third entrant.
     EFFECTIVE_SHARE = PRIVATE_ELIGIBLE_FRACTION x FBO_CAPTURE_SHARE = 0.10
     is now the ONE number both the data team's baseline and the forecast team's forecast
     should share, instead of two silently-different figures. A low/high
     range (0.05-0.15) comes from the forecast team's own eligibility sensitivity
     table at the 25%/75% eligibility points (capture share held fixed,
     since no comparable sensitivity exists for it yet).

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
# Part 135 (FAA air taxi) daily history, added to Part 91 GA per the team's Part 91 + 135 scope
AIR_TAXI_PATH = HERE.parent / "data" / "processed" / "historical_traffic_air_taxi_interim.csv"
BASELINE_OUT = HERE.parent / "baseline.csv"
ASSUMPTIONS_OUT = HERE.parent / "assumptions.csv"

PRIVATE_ELIGIBLE_FRACTION = 0.50
PRIVATE_ELIGIBLE_FRACTION_LOW = 0.25
PRIVATE_ELIGIBLE_FRACTION_HIGH = 0.75
FBO_CAPTURE_SHARE = 0.20
EFFECTIVE_SHARE = PRIVATE_ELIGIBLE_FRACTION * FBO_CAPTURE_SHARE
EFFECTIVE_SHARE_LOW = PRIVATE_ELIGIBLE_FRACTION_LOW * FBO_CAPTURE_SHARE
EFFECTIVE_SHARE_HIGH = PRIVATE_ELIGIBLE_FRACTION_HIGH * FBO_CAPTURE_SHARE
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

# No separate day-of-week multiplier: the interim histories are observed daily
# counts, so the weekday-matched average below already carries the real weekday
# pattern. (The earlier illustrative multipliers were for a monthly-spread file
# and would now count the weekday effect twice.)

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
    with open(AIR_TAXI_PATH, newline="") as f:
        air_taxi = {r["date"]: r for r in csv.DictReader(f)}
    if set(air_taxi) != {r["date"] for r in rows}:
        raise ValueError("GA and air-taxi histories cover different dates")
    rows = [dict(r, arrivals=float(r["arrivals"]) + float(air_taxi[r["date"]]["arrivals"]),
                 departures=float(r["departures"]) + float(air_taxi[r["date"]]["departures"])) for r in rows]

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

        arrivals_fbo = avg_arrivals_airportwide * EFFECTIVE_SHARE
        departures_fbo = avg_departures_airportwide * EFFECTIVE_SHARE
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
            # NOTE: id kept as "fbo_market_share" (not renamed) -- the dashboard team's
            # dashboard/scripts/release_team.py and dashboard/readiness/release_status.py
            # read this exact key out of sources/assumptions.csv. Only the VALUE
            # and its derivation changed (unified with the forecast team's eligibility x
            # capture figure); keeping the id avoids breaking that pipeline.
            "id": "fbo_market_share",
            "label": "Combined private-eligible x FBO-capture share of LAX Part 91 GA + Part 135 air-taxi traffic",
            "value": EFFECTIVE_SHARE,
            "unit": "fraction",
            "classification": "assumption",
            "source": "PRIVATE_ELIGIBLE_FRACTION (the forecast team, private_eligibility_sensitivity.csv) x FBO_CAPTURE_SHARE (team judgment, the dashboard team's apron research: 2 real incumbent FBOs, Atlantic/Signature)",
            "note": f"Single shared number replacing two previously-divergent pipeline figures (the data team's old flat 0.20 on GA+air-taxi vs the forecast team's 0.50x0.20=0.10 on GA alone). Low/high range {EFFECTIVE_SHARE_LOW:.2f}-{EFFECTIVE_SHARE_HIGH:.2f} from the forecast team's eligibility sensitivity table at the 25%/75% eligibility points (capture share held fixed at 0.20; no comparable sensitivity exists for it). Change PRIVATE_ELIGIBLE_FRACTION / FBO_CAPTURE_SHARE in build_baseline.py to revise.",
        },
        {
            "id": "fbo_capacity_su",
            "label": "Atlantic Aviation's own full facility capacity (hangar + whole reference ramp)",
            "value": 87.5,
            "unit": "space units",
            "classification": "benchmark",
            "source": "Hangar: Atlantic Aviation LAX corporate hangar, confirmed built 2016 (sources/docs/lax_private_capacity_and_cost_research.md Item 1a), 5 large-cabin jets x 2.5 su/large jet (the parking team's su_large) = 12.5 su. Ramp: the parking team's P3 ramp model (parking/assumptions_p3.csv, ramp_capacity_su), Atlantic's 2008 13-acre ramp benchmark = 75 su (range 61-91).",
            "note": "NOT this fictional FBO's own capacity ceiling -- describes Atlantic's entire reference facility (correctly flagged by the parking team's parking/PARKING_ASSUMPTIONS.md: \"that describes Atlantic's facility, not a share-sized one, and is not used\"). This fictional FBO's actual, share-sized ramp is parking/assumptions_p3.csv's ramp_capacity_su = reference_ramp_su x fbo_market_share / reference_traffic_share (15 su at the current 10% share) -- use that figure for this FBO's capacity, not this row. Kept here only as the underlying reference-facility benchmark those two factors are derived from. Range 73.5-103.5 su using the parking team's documented ramp range (61-91) with the hangar held fixed; does not include the parking team's optional +40 su overflow apron or +10% tow-packing gain.",
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
            "value": "FAA ATADS/OPSNET LAX GA + air-taxi daily operations, Feb (ordinary years)",
            "unit": "n/a",
            "classification": "benchmark",
            "source": "FAA ATADS/OPSNET daily LAX operations: general aviation (Part 91) via build_historical_traffic.py plus air taxi (Part 135) via build_historical_traffic_air_taxi.py, summed per day (daily-direct, 50/50 arrivals/departures)",
            "note": "Weekday-matched February average across ordinary (non-COVID, non-2022) years; see sources/scripts/build_baseline.py docstring for full methodology. Daily-resolution FAA counts; Part 135 air taxi added back to Part 91 GA when the team scope became Part 91 + 135 -- see sources/docs/traffic_categories_and_fleet_mix.md section 1.4.",
        },
    ]

    assumptions_rows.append(
        {
            "id": "baseline_training_window",
            "label": "Years used for the ordinary-week baseline average",
            "value": str(sorted(BASELINE_YEARS)),
            "unit": "years",
            "classification": "assumption",
            "source": "data's analysis of sources/airport_traffic lax_monthly_movements.csv",
            "note": "Restricted to post-COVID years only. Feb daily mean: ~175/day in 2016-2019 vs ~98/day in 2023-2025 (~45% drop, structural break not noise). Blending both without a level-shift would overstate 2027 ordinary traffic. 2016-2019 remain in historical_traffic_interim.csv as reference data, excluded only from this baseline average. See issue #10.",
        }
    )

    assumptions_rows.append(
        {
            "id": "security_restriction_window",
            "label": "Game-day VIP/security TFR ground-stop window applied to the model",
            "value": "2027-02-14 14:30-20:30 America/Los_Angeles",
            "unit": "n/a",
            "classification": "assumption",
            "source": "Super Bowl LVI FAA Flight Advisory (99.7 Special Security Instruction TFR): https://www.faasafety.gov/files/notices/2022/Jan/SB_LVI_Flight_Advisory.pdf",
            "note": "Modeled by applying the LVI precedent's exact clock window to this project's game day (2027-02-14, Sunday); no TFR has actually been published for Super Bowl LXI, so this is a precedent-based assumption, not a confirmed restriction. Structured model input: sources/data/processed/security_restriction_model_input.csv. Full derivation: sources/docs/vip_tfr_operational_impact.md.",
        }
    )

    assumptions_rows.append(
        {
            "id": "weekday_multiplier",
            "label": "Day-of-week traffic pattern",
            "value": "observed (no separate multiplier)",
            "unit": "ratio per weekday",
            "classification": "public data",
            "source": "Weekday-matched averages of observed FAA daily counts",
            "note": "The interim histories are daily FAA counts, so the weekday pattern is observed. The earlier illustrative multipliers (Sat 0.65 etc.) were for monthly-spread data and are no longer applied, to avoid counting the weekday effect twice.",
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
