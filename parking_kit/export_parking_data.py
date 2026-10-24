"""Export parking_data.json for the 3D parking prototypes: when might demand exceed available aircraft parking?

Everything comes from the team's committed outputs:
- daily ramp demand per scenario and situation (P10 / P50 / P90 space units), capacity, chance of exceeding it,
  risk, and the AI preparation plan with its measured effect (elia/ parking model, 10,000 simulated weeks)
- the ordinary week (same dates, no Super Bowl)
- daily arrivals and departures (marvin/person_2_forecasting)
- hour-of-day shares (PLACEHOLDER, not observed) and the game-day restriction (alan/data/processed)
- parking assumptions (space units, aircraft sizes, ramp area, stays) from elia/assumptions_p3.csv and alan/assumptions.csv
The 3D views generate individual aircraft from these totals; those aircraft are an illustration, the daily answer
comes from the model. Run from the repository root: python parking_kit/export_parking_data.py
"""
import csv
import json
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P3 = ROOT / "elia"
P2 = ROOT / "marvin" / "person_2_forecasting"
PKG = ROOT / "marvin" / "person_2_part91_part135_forecast" / "results"
OUT = Path(__file__).resolve().parent / "parking_data.json"
RAMP_AIRCRAFT = Path(__file__).resolve().parent / "ramp_aircraft.csv"  # from parking_kit/ramp_aircraft.py
VARIANTS = {"standard": ("resource_requirements.csv", "scenario_recommendations.json", "Normal operations"),
            "departure_delay_24h": ("resource_requirements_departure_delay_24h.csv", "scenario_recommendations_departure_delay_24h.json",
                                    "Departures delayed 24 h after the game"),
            "security_restriction": ("resource_requirements_security_restriction.csv", "scenario_recommendations_security_restriction.json",
                                     "Game-day security pause 14:30-20:30 (assumed)"),
            "heavy_rain": ("resource_requirements_heavy_rain.csv", "scenario_recommendations_heavy_rain.json", "Heavy rain on game day")}
PARKING_ACTIONS = {"tow_packing", "overflow_apron", "ppr_and_referrals"}
DAY_KEYS = ("arrivals_p50", "departures_p50", "parking_demand_su_p10", "parking_demand_su_p50", "parking_demand_su_p90",
            "capacity_normal_su", "capacity_prepared_su", "utilization_normal_p50", "prob_over_normal_capacity",
            "prob_over_prepared_capacity", "risk_level")


def rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def num(x):
    try:
        return round(float(x), 4)
    except (TypeError, ValueError):
        return x


def variant(name):
    table, recs_file, label = VARIANTS[name]
    days = defaultdict(dict)
    for r in rows(P3 / table):
        days[r["scenario"]][r["date"]] = {k: num(r[k]) for k in DAY_KEYS}
    recs = json.loads((P3 / recs_file).read_text())["scenarios"]
    plans = {}
    for s, r in recs.items():
        imp = r["impact"]
        plans[s] = {"actions": [{k: a[k] for k in ("id", "action", "dates", "rationale", "cost_usd", "approver")}
                                for a in r["actions"] if a["id"] in PARKING_ACTIONS],
                    "plan_cost_usd": sum(a["cost_usd"] for a in r["actions"] if a["id"] in PARKING_ACTIONS),
                    "aircraft_not_accommodated_mean": {"no_plan": imp["no_preparation"]["unaccommodated_aircraft"]["mean"],
                                                       "with_plan": imp["ai_preparation"]["unaccommodated_aircraft"]["mean"]},
                    "prob_plan_pays_off": imp["prob_preparation_pays_off"],
                    "peak_day": r["summary"]["peak_day"], "overall_risk": r["summary"]["overall_risk"]}
    return {"label": label, "days": days, "plans": plans}


def situation_outlook(sec, dates):
    """Which situations the model expects, from evidence: the site applies the expected ones and shows the rest as risks."""
    weather = json.loads((ROOT / "site_kit" / "agent_data.json").read_text())["weather"]
    p_heavy = weather["february_probability"]["heavy_rain"]
    game = "2027-02-14"
    return {
        "decided_by": "model",
        "base_case": "security_restriction",
        "base_case_note": ("The model's base case is the forecast demand with the game-day security pause applied, because every "
                           "Super Bowl has had a security flight restriction. Daily parking totals equal normal operations; the "
                           "pause changes when aircraft can move on game day."),
        "items": [
            {"situation": "security_restriction", "status": "expected", "dates": [sec["date"]],
             "window": [sec["start_time_local"], sec["end_time_local"]], "probability": None,
             "basis": ("Every Super Bowl has a security flight restriction; under the 2022 (LVI) precedent LAX sat inside the inner "
                       "ring, so private (Part 91) flights are grounded for the window. No 2027 notice is published yet."),
             "source": sec["source"]},
            {"situation": "heavy_rain", "status": "possible", "dates": [game], "probability": p_heavy,
             "probability_week_any_day": round(1 - (1 - p_heavy) ** len(dates), 3),
             "basis": (f"{p_heavy:.0%} of February days at LAX had heavy rain ({weather['source']}). The model tests it on game day."),
             "source": "marvin/person_2_part91_part135_forecast/results/weather_effect_measured.csv"},
            {"situation": "departure_delay_24h", "status": "stress test", "dates": [game], "probability": None,
             "basis": "No measured likelihood. Tests what happens if departures slip a full day after the game.",
             "source": "elia/assumptions_p3.csv (delay_24h_first_day, delay_24h_share)"},
            {"situation": "standard", "status": "reference", "dates": [], "probability": None,
             "basis": "Same demand without any situation, for comparison.", "source": ""},
        ],
    }


def levers():
    """Slot advisor results (elia/slot_advisor.py): offers that change when aircraft come and go, per scenario."""
    recs = json.loads((P3 / "slot_recommendations.json").read_text())
    out = {"decided_by": "model", "human_in_command": recs["meta"]["human_in_command"],
           "take_up_status": recs["meta"]["take_up_status"], "by_scenario": {}}
    for sc, r in recs["scenarios"].items():
        out["by_scenario"][sc] = {
            "no_action": r["no_action"],
            "recommended": [{k: x.get(k) for k in ("id", "action", "rationale", "cost_usd", "approver", "dates")} for x in r["actions"]],
            "not_recommended": r.get("early_arrival_finding"), "note": r.get("pricing_note")}
    return out


def main():
    a = {r["parameter"]: num(r["value"]) for r in rows(P3 / "assumptions_p3.csv")}
    p3 = a
    alan = {r["id"]: r for r in rows(ROOT / "alan" / "assumptions.csv")}
    sec = rows(ROOT / "alan" / "data" / "processed" / "security_restriction_model_input.csv")[0]
    hourly = defaultdict(lambda: [0.0] * 24)
    for r in rows(PKG / "hourly_profile_weights.csv"):
        hourly[f"{r['day_type']}_{r['target']}"][int(r["local_hour"])] = round(float(r["fitted_hour_share"]), 5)
    flows = defaultdict(dict)
    for r in rows(P2 / "daily_totals.csv"):
        flows[r["scenario"]][r["date"]] = {k: num(r[k]) for k in ("baseline_arrivals", "expected_arrivals",
                                                                    "baseline_departures", "expected_departures")}
    ordinary = {r["date"]: {k: num(r[k]) for k in ("arrivals_baseline", "departures_baseline", "parking_demand_su_p10",
                                                    "parking_demand_su_p50", "parking_demand_su_p90", "capacity_normal_su",
                                                    "prob_over_normal_capacity", "risk_level")}
                for r in rows(P3 / "ordinary_week_parking.csv")}
    dates = sorted(ordinary)
    ramp_aircraft = defaultdict(lambda: defaultdict(dict))
    for r in rows(RAMP_AIRCRAFT):
        ramp_aircraft[r["situation"]][r["scenario"]][r["date"]] = {
            "aircraft_at_peak_p50": num(r["aircraft_at_peak_p50"]),
            "at_peak_p50": {c: num(r[f"{c}_at_peak_p50"]) for c in ("light", "midsize", "large")},
            "arrivals_p50": {c: num(r[f"{c}_arrivals_p50"]) for c in ("light", "midsize", "large")},
            "departures_p50": {c: num(r[f"{c}_departures_p50"]) for c in ("light", "midsize", "large")}}
    bundle = {
        "meta": {
            "question": "Parking: when might demand exceed available aircraft parking space?",
            "fbo": "Fictional FBO at LAX", "planning_window": [dates[0], dates[-1]], "game_day": "2027-02-14",
            "presidents_day": "2027-02-15", "timezone": "America/Los_Angeles",
            "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
            "how_to_read": ("Daily ramp demand comes from the parking model: 10,000 simulated weeks per scenario on the FAA-based "
                            "forecast. P50 is the median day, P10-P90 the likely range, prob_over_normal_capacity the share of "
                            "simulated weeks in which demand exceeds the ramp that day."),
            "human_in_command": ("The model recommends; a named manager approves every action. It never accepts, refuses or "
                                 "reassigns an individual aircraft. Overflow is a flag for a person to resolve."),
            "privacy": "No passenger or owner data.",
        },
        "days": [{"date": d, "weekday": date.fromisoformat(d).strftime("%A"),
                  "day_type": "weekend" if date.fromisoformat(d).weekday() >= 5 else "weekday",
                  "game_day": d == "2027-02-14", "presidents_day": d == "2027-02-15"} for d in dates],
        "scenarios": {"Low": "+3.1% (measured, LAX GA 2022)", "Medium": "+15.5% (measured, LAX air taxi 2022): the forecast",
                      "High": "+31% (stress case)"},
        "default_scenario": "Medium",
        "situations": {k: v["label"] for k, v in ((n, variant(n)) for n in VARIANTS)},
        "parking": {n: variant(n) for n in VARIANTS},
        "ordinary_week": ordinary,
        "situation_outlook": situation_outlook(sec, dates),
        "levers": levers(),
        "demand_levels": {
            "decided_by": "model", "basis": "ramp utilization at the daily P50 peak (risk_level in elia/resource_requirements.csv)",
            "medium_from": num(p3["risk_medium_threshold"]), "high_from": num(p3["risk_high_threshold"]),
            "labels": {"Low": "below 85% of the ramp", "Medium": "85 to 100% of the ramp", "High": "above the ramp"}},
        "ramp_aircraft": {
            "class": "model output",
            "note": ("Median number of aircraft of each size on the ramp at each day's peak, and median arrivals and departures "
                     "per size, from the same 10,000 simulated weeks as the parking model (parking_kit/ramp_aircraft.py, "
                     "which reproduces parking_demand_su_p50 exactly). Use these counts for the planes shown."),
            "by_situation": ramp_aircraft},
        "flows": flows,
        "capacity": {
            "ramp_su": a["ramp_capacity_su"], "tow_packing_gain": a["tow_packing_gain"],
            "overflow_apron_su": a["overflow_capacity_su"], "overflow_cost_per_su_day_usd": a["overflow_cost_per_su_day_usd"],
            "derivation": (f"Atlantic's ramp: {a['ramp_area_m2']:.0f} m2 x {a['usable_parking_share']} usable / "
                           f"{a['m2_per_su']} m2 per su = {a['reference_ramp_su']:.0f} su, scaled to this FBO's "
                           f"{float(alan['fbo_market_share']['value']):.0%} share vs Atlantic's {a['reference_traffic_share']:.0%}: "
                           f"{a['ramp_capacity_su']:.0f} su. Estimated, not a measured stand count."),
            "class": "estimated"},
        "aircraft": {
            "space_unit": "1 su = one light-jet parking position (about 600 m2 including clearance and half a taxilane)",
            "sizes": {"light": {"su": a["su_light"], "share": a["mix_light"], "example": "Citation CJ3 (16.3 m span x 15.6 m)"},
                      "midsize": {"su": a["su_midsize"], "share": a["mix_midsize"], "example": "Challenger 350 (21.0 m x 20.9 m)"},
                      "large": {"su": a["su_large"], "share": a["mix_large"], "example": "Gulfstream G650 (30.4 m x 30.4 m)"}},
            "mix_class": "assumed", "opening_aircraft": a["initial_transient_aircraft"],
            "stays": {"same_day": 0.40, "overnight": 0.45, "multi_day_3": 0.15, "average_days": float(alan["avg_dwell_days"]["value"]),
                      "class": "assumed (illustrative stay mix from the team ledger)"},
        },
        "hourly_profile": {"shares": dict(hourly), "class": "placeholder",
                           "note": "Hour-of-day shares are a placeholder curve, not observed data."},
        "game_day_restriction": {"date": sec["date"], "start": sec["start_time_local"], "end": sec["end_time_local"],
                                 "status": "assumption from the Super Bowl LVI precedent; no 2027 notice published",
                                 "source": sec["source"]},
        "sources": [
            {"name": "FAA ATADS/OPSNET daily operations (forecast input)", "url": "https://www.aspm.faa.gov/opsnet/sys/Airport.asp"},
            {"name": "Atlantic Aviation LAX ramp area, AIN 2008 (capacity reference)",
             "url": "https://www.ainonline.com/aviation-news/business-aviation/2008-02-08/atlantic-completes-los-angeles-and-santa-barbara-fbos"},
        ],
    }
    OUT.write_text(json.dumps(bundle, indent=1), newline="\n")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
