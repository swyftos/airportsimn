"""Export agent_data.json for the FBO agent apps: when are the busiest periods (landings and departures)?

Everything comes from the team's committed outputs, nothing from outside the repository:
- daily forecast per scenario with 90% ranges and the ordinary week (marvin/person_2_forecasting)
- Part 91 / Part 135 split per day (marvin/person_2_part91_part135_forecast/results/part_daily_totals.csv)
- measured weather effects and February frequencies (NOAA x FAA, weather_effect_measured.csv)
- game-day security restriction (alan/data/processed/security_restriction_model_input.csv) and the release
  window used by the parking model (elia/assumptions_p3.csv security_release_hours)
- hour-of-day shares (hourly_profile_weights.csv): a PLACEHOLDER profile, not observed; the agent's own
  entered movements take priority over it
- accuracy (backtest), Super Bowl evidence (eight host cities), parking as a secondary indicator.
Run from the repository root: python site_kit/export_agent_data.py
"""
import csv
import json
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P2 = ROOT / "marvin" / "person_2_forecasting"
PKG = ROOT / "marvin" / "person_2_part91_part135_forecast" / "results"
P3 = ROOT / "elia"
OUT = Path(__file__).resolve().parent / "agent_data.json"
SCENARIOS = ("Low", "Medium", "High")
WEATHER = ("rain", "heavy_rain", "heavy_fog")


def rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def r3(x):
    return round(float(x), 3)


def hourly_profile():
    prof = defaultdict(lambda: [0.0] * 24)
    for r in rows(PKG / "hourly_profile_weights.csv"):
        prof[r["day_type"], r["target"]][int(r["local_hour"])] = round(float(r["fitted_hour_share"]), 5)
    return {f"{d}_{t}": v for (d, t), v in prof.items()}


def game_day_shares(profile, start, end, release_hours):
    """Game-day hour shares with no movements inside the restriction window. Blocked departures are released
    evenly over release_hours after it ends (the parking model's security_restriction rule); blocked arrivals
    land before the window instead, in proportion to the earlier hours (aircraft come in before the game)."""
    release_hours = min(release_hours, 24 - end)  # keep the released movements on game day (before midnight)
    out = {}
    for t in ("arrivals", "departures"):
        base = profile[f"weekend_{t}"]
        shares, blocked = [0.0] * 24, 0.0
        for h in range(24):
            inside = max(0.0, min(h + 1, end) - max(h, start))  # hours of [h, h+1) inside the window
            shares[h] = base[h] * (1 - inside)
            blocked += base[h] * inside
        if t == "departures":
            for h in range(24):
                shares[h] += blocked * max(0.0, min(h + 1, end + release_hours) - max(h, end)) / release_hours
        else:
            before = [shares[h] * max(0.0, min(h + 1, start) - h) for h in range(24)]  # share sitting before the window
            total_before = sum(before)
            for h in range(24):
                shares[h] += blocked * before[h] / total_before
        out[t] = [round(x, 5) for x in shares]
    return out


def main():
    totals = {(r["date"], r["scenario"]): r for r in rows(P2 / "daily_totals.csv")}
    # Aggregate 90% range. The three size categories are fixed shares of one daily series, so their errors are
    # perfectly correlated and the total radius is the sum of the category radii (summing the rounded category
    # bounds would inflate it). Range = [max(0, ordinary - R) x m, (ordinary + R) x m], m = expected / ordinary.
    radius = defaultdict(float)
    for r in rows(P2 / "uncertainty_results.csv"):
        radius[r["date"], r["scenario"], r["target"]] += float(r["baseline_radius"])
    def total_range(t, d, s):
        base, exp = float(totals[d, s][f"baseline_{t}"]), float(totals[d, s][f"expected_{t}"])
        m, R = (exp / base if base else 1.0), radius[d, s, t]
        return [round(max(0.0, base - R) * m, 2), round((base + R) * m, 2)]
    parts = defaultdict(dict)
    for r in rows(PKG / "part_daily_totals.csv"):
        parts[r["date"], r["scenario"]][r["operation_part"]] = float(r["expected_arrivals"]) + float(r["expected_departures"])
    parking = {(r["date"], r["scenario"]): r for r in rows(P3 / "resource_requirements.csv")}
    a = {r["parameter"]: r["value"] for r in rows(P3 / "assumptions_p3.csv")}
    sec = rows(ROOT / "alan" / "data" / "processed" / "security_restriction_model_input.csv")[0]
    clock = lambda s: int(s[:2]) + int(s[3:5]) / 60
    start, end, release = clock(sec["start_time_local"]), clock(sec["end_time_local"]), float(a["security_release_hours"])

    days = []
    for d in sorted({k[0] for k in totals}):
        dt = date.fromisoformat(d)
        day = {"date": d, "weekday": dt.strftime("%A"), "day_type": "weekend" if dt.weekday() >= 5 else "weekday",
               "game_day": d == "2027-02-14", "presidents_day": d == "2027-02-15",
               "security_restriction": d == sec["date"], "scenarios": {}}
        for s in SCENARIOS:
            t, p, pk = totals[d, s], parts[d, s], parking[d, s]
            total = sum(p.values())
            day["scenarios"][s] = {
                "ordinary_arrivals": r3(t["baseline_arrivals"]), "ordinary_departures": r3(t["baseline_departures"]),
                "expected_arrivals": r3(t["expected_arrivals"]), "expected_departures": r3(t["expected_departures"]),
                "arrivals_range90": total_range("arrivals", d, s), "departures_range90": total_range("departures", d, s),
                "share_part91": round(p["part91"] / total, 4), "share_part135": round(p["part135"] / total, 4),
                "parking_su_p50": float(pk["parking_demand_su_p50"]), "parking_su_p90": float(pk["parking_demand_su_p90"]),
                "ramp_capacity_su": float(pk["capacity_normal_su"]), "prob_ramp_full": float(pk["prob_over_normal_capacity"])}
        days.append(day)

    effects = {r["weather_type"]: {} for r in rows(PKG / "weather_effect_measured.csv")}
    for r in rows(PKG / "weather_effect_measured.csv"):
        if r["window"] == "2016-2019+2023-2025" and r["weather_type"] in WEATHER:
            part = "part91" if r["category"].startswith("part91") else "part135"
            effects[r["weather_type"]][part] = {"effect": r3(r["effect"]), "ci95": [r3(r["ci_low"]), r3(r["ci_high"])],
                                                "days_observed": int(r["n_days"])}
    feb = {r["weather_type"]: r3(r["value"]) for r in rows(PKG / "weather_feb_climatology.csv")
           if r["metric"] == "february_day_share"}
    profile = hourly_profile()
    backtest = [r for r in rows(P2 / "backtest_metrics.csv") if r["target"] == "arrivals" and r["window"] == "all_2025_origins"]

    bundle = {
        "meta": {
            "question": "Aircraft arrivals: when should the FBO expect its busiest periods?",
            "fbo": "Fictional FBO at LAX (Los Angeles International)", "timezone": "America/Los_Angeles",
            "planning_window": [days[0]["date"], days[-1]["date"]], "game_day": "2027-02-14", "presidents_day": "2027-02-15",
            "scope": "Private aviation: Part 91 (FAA general aviation) + Part 135 (FAA air taxi). Airlines and military excluded.",
            "units": "aircraft movements per day: an arrival is a landing, a departure is a takeoff",
            "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
            "human_in_command": ("The tool supports planning. It never authorizes aircraft movements, never accepts, refuses "
                                 "or cancels an aircraft or booking, and does not replace airport safety procedures."),
            "never_allowed": "Accept or refuse an individual aircraft, cancel a booking, or authorize an aircraft movement.",
            "privacy": "No passenger names or personal data. Movements are recorded by optional tail number, aircraft size and time only.",
        },
        "scenarios": {"Low": "+3.1% over Thu-Mon (LAX general aviation, Super Bowl LVI 2022)",
                      "Medium": "+15.5% (LAX air taxi, Super Bowl LVI 2022)", "High": "+31% (twice Medium, stress case)"},
        "days": days,
        "hourly_profile": {"shares": profile, "class": "placeholder",
                           "note": "Hour-of-day shares are a placeholder (no observed hourly FBO data in the repository). Movements the agent enters replace them for the hours they cover."},
        "game_day_restriction": {"date": sec["date"], "start": sec["start_time_local"], "end": sec["end_time_local"],
                                 "release_hours_after": release, "rule": sec["inner_ring_rule"],
                                 "shares_rule": "Blocked departures leave in the hours after the window; blocked arrivals land before it.",
                                 "source": sec["source"], "status": "precedent-based assumption (Super Bowl LVI TFR); no 2027 TFR published",
                                 "hour_shares": game_day_shares(profile, start, end, release)},
        "weather": {"effects": {k: v for k, v in effects.items() if k in WEATHER},
                    "february_probability": {k: feb[k] for k in WEATHER},
                    "rule": "On a bad-weather day, completed movements change by the measured effect, weighted by the day's Part 91 / Part 135 split; the movements that did not happen happen the next day.",
                    "definitions": {"rain": "at least 0.10 in of rain", "heavy_rain": "at least 0.50 in of rain", "heavy_fog": "NOAA heavy-fog flag (low visibility)"},
                    "source": "NOAA GHCN-Daily LAX x FAA daily operations, 2016-2019 and 2023-2025, vs dry days of the same weekday and month"},
        "range_note": ("90% ranges come from the model's held-out errors on real airport days (rolling 2025 backtest: 87.9% "
                       "of days inside; frozen 2026 test: 98.5%). Super Bowl scaling of the range is not validated."),
        "accuracy": {"rolling_backtest_2025_wape": {r["model"]: r3(r["wape"]) for r in backtest},
                     "coverage_90": r3(next(r["coverage_90"] for r in backtest if r["model"] == "model")),
                     "note": "Every Monday of 2025: fit on earlier days only, forecast the next 7 days. WAPE = average daily error as a share of actual traffic."},
        "super_bowl_test": [{k: r[k] for k in ("event", "game_sunday", "airports", "metric", "excess", "position")}
                            for r in rows(ROOT / "alan" / "elia_output" / "data" / "processed" / "superbowl_hosts_excess.csv")],
        "key_assumptions": [
            {"name": "FBO share of LAX private traffic", "value": "10%", "class": "assumed"},
            {"name": "Arrivals vs departures on ordinary days", "value": "50 / 50", "class": "assumed"},
            {"name": "Hour-of-day profile", "value": "placeholder curve", "class": "placeholder"},
            {"name": "Game-day restriction 14:30-20:30", "value": "Super Bowl LVI precedent", "class": "assumed"},
            {"name": "Super Bowl effect sizes", "value": "+3.1 / +15.5 / +31%", "class": "measured (2022) / assumed (High)"},
            {"name": "Weather effects", "value": "NOAA x FAA", "class": "measured"},
        ],
        "sources": [
            {"name": "FAA ATADS/OPSNET daily tower operations", "url": "https://www.aspm.faa.gov/opsnet/sys/Airport.asp"},
            {"name": "NOAA GHCN-Daily, LAX station USW00023174", "url": "https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries&stations=USW00023174"},
            {"name": "FAA Super Bowl LVI flight advisory", "url": "https://www.faasafety.gov/files/notices/2022/Jan/SB_LVI_Flight_Advisory.pdf"},
        ],
    }
    OUT.write_text(json.dumps(bundle, indent=1))
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB, {len(days)} days)")


if __name__ == "__main__":
    main()
