"""Export one JSON bundle for the FBO planning websites: landings, departures and parking only.

Reads the committed team outputs (forecast, parking model, slot advisor, backtest, Super Bowl evidence,
weather) and writes site_kit/fbo_data.json. Staffing and fuel are left out on purpose: the sites focus on
arrivals (landings), departures and parking. Run from the repository root: python site_kit/export_site_data.py
"""
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P2 = ROOT / "marvin" / "person_2_forecasting"
P3 = ROOT / "elia"
DATA = ROOT / "alan" / "elia_output" / "data" / "processed"
PKG = ROOT / "marvin" / "person_2_part91_part135_forecast" / "results"
OUT = Path(__file__).resolve().parent / "fbo_data.json"
VARIANTS = {"standard": "Normal operations", "departure_delay_24h": "Departures delayed 24 h after the game",
            "security_restriction": "Game-day security restriction 14:30-20:30", "heavy_rain": "Heavy rain on game day"}
PARKING_ACTIONS = {"tow_packing", "overflow_apron", "ppr_and_referrals"}  # staff and fuel actions are dropped


def rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def num(x):
    try:
        v = float(x)
        return int(v) if v.is_integer() and "." not in str(x) else round(v, 4)
    except (TypeError, ValueError):
        return x


def forecast():
    daily = [{k: num(v) for k, v in r.items()} for r in rows(P2 / "daily_totals.csv")]
    ranges = defaultdict(lambda: {"arrivals": [0, 0], "departures": [0, 0]})
    by_size = defaultdict(dict)
    for r in rows(P2 / "uncertainty_results.csv"):
        key = (r["date"], r["scenario"])
        ranges[key][r["target"]][0] += float(r["lower"])
        ranges[key][r["target"]][1] += float(r["upper"])
        by_size[key].setdefault(r["aircraft_category"], {})[r["target"]] = round(float(r["expected"]), 3)
    for d in daily:
        key = (d["date"], d["scenario"])
        d["arrivals_range90"] = ranges[key]["arrivals"]
        d["departures_range90"] = ranges[key]["departures"]
        d["by_aircraft_size"] = by_size[key]
    return daily


def parking_variant(name):
    suffix = "" if name == "standard" else f"_{name}"
    keep = ("scenario", "date", "arrivals_p50", "departures_p50", "parking_demand_su_p10", "parking_demand_su_p50",
            "parking_demand_su_p90", "capacity_normal_su", "capacity_prepared_su", "utilization_normal_p50",
            "prob_over_normal_capacity", "prob_over_prepared_capacity", "risk_level")
    days = [{k: num(r[k]) for k in keep} for r in rows(P3 / f"resource_requirements{suffix}.csv")]
    recs = json.loads((P3 / f"scenario_recommendations{suffix}.json").read_text())
    plans = {}
    for scenario, r in recs["scenarios"].items():
        actions = [{k: a[k] for k in ("id", "category", "action", "dates", "rationale", "cost_usd",
                                       "requires_human_approval", "approver")}
                   for a in r["actions"] if a["id"] in PARKING_ACTIONS]
        imp = r["impact"]
        no, ai = imp["no_preparation"]["unaccommodated_aircraft"], imp["ai_preparation"]["unaccommodated_aircraft"]
        plans[scenario] = {
            "summary": r["summary"], "actions": actions,
            "parking_cost_usd": sum(a["cost_usd"] for a in actions),
            "aircraft_not_accommodated": {"no_plan": no, "with_plan": ai},
            "prob_any_not_accommodated": {"no_plan": imp["no_preparation"]["prob_any_unaccommodated"],
                                          "with_plan": imp["ai_preparation"]["prob_any_unaccommodated"]},
            "net_benefit_usd": imp["net_benefit_usd"], "prob_plan_pays_off": imp["prob_preparation_pays_off"]}
    method = recs["meta"]["method"].replace(", staffing and fuel for P50 plus buffer", "")
    return {"label": VARIANTS[name], "method": method, "days": days, "plans": plans}


def main():
    a = {r["parameter"]: num(r["value"]) for r in rows(P3 / "assumptions_p3.csv")}
    alan = {r["id"]: r for r in rows(ROOT / "alan" / "assumptions.csv")}
    ordinary = [{k: num(r[k]) for k in ("date", "arrivals_baseline", "departures_baseline", "parking_demand_su_p10",
                                         "parking_demand_su_p50", "parking_demand_su_p90", "capacity_normal_su",
                                         "utilization_normal_p50", "prob_over_normal_capacity", "risk_level")}
                for r in rows(P3 / "ordinary_week_parking.csv")]
    history = [{"date": r["date"], "part91_general_aviation": int(r["general_aviation"]), "part135_air_taxi": int(r["air_taxi"])}
               for r in rows(DATA / "opsnet_lax_daily.csv") if r["date"][:4] in ("2023", "2024", "2025")]
    evidence = json.loads((P2 / "provisional_inputs" / "event_evidence.json").read_text())
    slot_recs = json.loads((P3 / "slot_recommendations.json").read_text())
    bundle = {
        "meta": {
            "title": "Super Bowl LXI readiness, fictional FBO at LAX",
            "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
            "planning_window": ["2027-02-11", "2027-02-17"], "game_day": "2027-02-14",
            "presidents_day": "2027-02-15",
            "scope": "Private aviation: Part 91 (FAA general aviation) + Part 135 (FAA air taxi). Airlines and military excluded.",
            "focus": "Landings (arrivals), departures and parking. Staffing and fuel are out of scope for this site.",
            "units": {"su": "space unit = one light-jet parking position; midsize 1.5 su, large 2.5 su",
                      "movements": "an arrival is a landing, a departure is a takeoff"},
            "human_in_command": ("The system recommends; a named manager approves every action. It never accepts, "
                                 "refuses or cancels an individual aircraft or booking."),
            "never_allowed": ("Accept or refuse an individual aircraft, cancel a confirmed booking, authorize aircraft "
                              "movements, commit money or activate facilities, or process passenger data."),
            "data_classes": {"measured": "public observations (FAA, NOAA)", "estimated": "derived from measurements with stated assumptions",
                             "assumed": "team assumption, not measured"},
        },
        "key_assumptions": [
            {"name": "FBO share of LAX private traffic", "value": float(alan["fbo_market_share"]["value"]), "class": "assumed",
             "note": "50% private-eligible x 20% capture. Ramp is sized to the same share, so ramp use does not depend on it."},
            {"name": "Ramp capacity", "value": a["ramp_capacity_su"], "unit": "su", "class": "estimated",
             "note": f"Atlantic's {a['reference_ramp_su']} su ramp (2008 area) x share / Atlantic's {a['reference_traffic_share']} traffic share"},
            {"name": "Aircraft mix light / midsize / large", "value": [a["mix_light"], a["mix_midsize"], a["mix_large"]], "class": "assumed"},
            {"name": "Space units light / midsize / large", "value": [a["su_light"], a["su_midsize"], a["su_large"]], "unit": "su", "class": "estimated",
             "note": "Checked against CJ3, Challenger 350 and G650 footprints"},
            {"name": "Opening aircraft on the ramp", "value": a["initial_transient_aircraft"], "class": "estimated",
             "note": "Ordinary arrivals x 1.1-day average stay"},
            {"name": "Revenue lost per aircraft not accommodated", "value": a["revenue_per_aircraft_usd"], "unit": "USD", "class": "assumed"},
            {"name": "Overflow apron lease", "value": a["overflow_cost_per_su_day_usd"], "unit": "USD per su per day", "class": "assumed"},
        ],
        "scenarios": {"Low": "+3.1% (LAX GA, Super Bowl LVI 2022)", "Medium": "+15.5% (LAX air taxi, Super Bowl LVI 2022)",
                      "High": "+31% (twice Medium, stress case)"},
        "event_evidence": {k: evidence[k] for k in ("lax_five_day_control_adjusted_excess", "lax_ga_five_day_control_adjusted_excess",
                                                     "six_airport_five_day_control_adjusted_excess", "scenario_excess_scales",
                                                     "direction_assumption", "daily") if k in evidence},
        "forecast_daily": forecast(),
        "ordinary_week_parking": ordinary,
        "parking": {v: parking_variant(v) for v in VARIANTS},
        "slot_advisor": {"rows": [{k: num(v) for k, v in r.items()} for r in rows(P3 / "slot_advisor.csv")],
                         "recommendations": slot_recs["scenarios"], "meta": slot_recs["meta"]},
        "accuracy": {"backtest": [{k: num(v) for k, v in r.items()} for r in rows(P2 / "backtest_metrics.csv")],
                     "holdout": [{k: num(v) for k, v in r.items()} for r in rows(P2 / "evaluation_metrics.csv")][:1],
                     "note": "Rolling backtest: every Monday of 2025, fit on earlier days only, forecast 7 days. WAPE = average daily error as a share of actual traffic."},
        "super_bowl_test": [{k: num(v) for k, v in r.items()} for r in rows(DATA / "superbowl_hosts_excess.csv")],
        "weather": {"effects": [{k: num(v) for k, v in r.items()} for r in rows(PKG / "weather_effect_measured.csv")
                                if r["window"] == "2016-2019+2023-2025"],
                    "february": [{k: num(v) for k, v in r.items()} for r in rows(PKG / "weather_feb_climatology.csv")
                                 if r["metric"] != "feb_11_17_days"]},
        "share_robustness": [{k: num(v) for k, v in r.items()} for r in rows(P3 / "sensitivity_share_robustness.csv")],
        "history_daily_faa": history,
        "sources": [
            {"name": "FAA ATADS/OPSNET daily tower operations", "url": "https://www.aspm.faa.gov/opsnet/sys/Airport.asp"},
            {"name": "NOAA GHCN-Daily, LAX station USW00023174", "url": "https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries&stations=USW00023174"},
            {"name": "LAWA general aviation fees", "url": "https://www.lawa.org/general-aviation-fees-lax"},
            {"name": "FAA Super Bowl LVI flight advisory (security restriction)", "url": "https://www.faasafety.gov/files/notices/2022/Jan/SB_LVI_Flight_Advisory.pdf"},
        ],
    }
    OUT.write_text(json.dumps(bundle, indent=1))
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
