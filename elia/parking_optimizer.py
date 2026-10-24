"""P3 Parking & Resource Optimization for the fictional LAX FBO, Super Bowl LXI week.

Turns P2's daily demand forecasts into parking occupancy, staffing, fuel workload,
risk levels and a preparation plan per scenario, then measures that plan against the
normal operating plan over thousands of Monte Carlo demand paths.

The optimizer only RECOMMENDS. Every action carries requires_human_approval and an
approver role; nothing here accepts, rejects or cancels an individual reservation.

Input (P2, ../marvin/person_2_forecasting/uncertainty_results.csv):
    date, scenario, aircraft_category, target (arrivals|departures), expected, lower, upper
The earlier P2 layout (Person2-Forecasting/, direction, expected_movements, lower90/upper90_prediction)
is still accepted. Category names are mapped to light / midsize / large.
Monte Carlo: each (day, category, direction) is drawn from a split lognormal whose median is
the expected value and whose 5th/95th percentiles are P2's planning range. A shared
shock (mc_common_shock_share) makes the whole event run bigger or smaller together, since
P2 warns that its category intervals must not be summed independently.

Usage: python parking_optimizer.py [p2_output_dir]
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
P2_DIRS = (HERE.parent / "marvin" / "person_2_forecasting", HERE.parent / "marvin" / "Person2-Forecasting")
CATS = ("light", "midsize", "large")
CATEGORY_ALIASES = {"light_jet": "light", "midsize_jet": "midsize", "super_midsize": "midsize", "large_jet": "large"}
DIRS = ("arrivals", "departures")
SHIFTS = ("morning", "day", "night")
Z90 = 1.6449  # standard normal 95th percentile, edge of a central 90 % range


def load_assumptions(path=HERE / "assumptions_p3.csv") -> dict:
    df = pd.read_csv(path)
    return dict(zip(df["parameter"], df["value"].astype(float)))


def load_demand(p2_dir=None) -> pd.DataFrame:
    p2_dir = Path(p2_dir) if p2_dir else next((d for d in P2_DIRS if d.exists()), P2_DIRS[0])
    df = pd.read_csv(p2_dir / "uncertainty_results.csv").rename(columns={
        "target": "direction", "expected": "expected_movements",
        "lower": "lower90_prediction", "upper": "upper90_prediction"})
    if "expected_movements" not in df:  # earlier P2 layout kept the point forecast in demand_predictions.csv
        keys = ["date", "scenario", "aircraft_category", "direction"]
        d = pd.read_csv(p2_dir / "demand_predictions.csv")[keys + ["expected_movements"]]
        df = df.merge(d, on=keys, validate="one_to_one")
    df["aircraft_category"] = df["aircraft_category"].replace(CATEGORY_ALIASES)
    unknown = set(df["aircraft_category"]) - set(CATS)
    if unknown:
        raise ValueError(f"unknown aircraft categories from P2: {sorted(unknown)}")
    df.attrs["source"] = str(p2_dir)
    prov = next((c for c in ("historical_data_class", "input_provenance") if c in df), None)
    df.attrs["provenance"] = sorted(df[prov].unique()) if prov else []
    return df


def scenario_arrays(sdf: pd.DataFrame):
    """(dates, mid, lo, hi) with arrays shaped [direction, day, category]."""
    dates = sorted(sdf["date"].unique())
    out = []
    for col in ("expected_movements", "lower90_prediction", "upper90_prediction"):
        p = sdf.pivot_table(index=["direction", "date"], columns="aircraft_category", values=col)
        out.append(np.stack([p.loc[d].reindex(index=dates, columns=list(CATS)).to_numpy() for d in DIRS]))
    return dates, *out


def sample_demand(mid, lo, hi, a, rng):
    """Monte Carlo draws, shape [run, direction, day, category]."""
    n = int(a["mc_runs"])
    s = a["mc_common_shock_share"]
    z = np.sqrt(s) * rng.standard_normal((n, 1, 1, 1)) + np.sqrt(1 - s) * rng.standard_normal((n,) + mid.shape)
    sig_up = np.log(np.maximum(hi, mid) / mid) / Z90
    # a lower bound of 0 (P2 floors ranges at zero) has no lognormal equivalent: mirror the upper spread
    sig_dn = np.where(lo > 0, np.log(mid / np.clip(lo, 1e-6, mid)) / Z90, sig_up)
    return mid * np.exp(np.where(z > 0, sig_up, sig_dn) * z)


def ramp_sim(arr, dep, capacity_su, a):
    """Day-by-day ramp over all runs. arr/dep [run, day, category], capacity_su [day].

    Within a day a share of departures leaves before the arrival peak, the rest after.
    Arrivals that do not fit at the peak are counted as unaccommodated (a human would refer
    them elsewhere; the system never refuses an aircraft).
    """
    su = np.array([a[f"su_{c}"] for c in CATS])
    occ = np.tile([a["initial_transient_aircraft"] * a[f"mix_{c}"] for c in CATS], (arr.shape[0], 1))
    peak_su = np.zeros(arr.shape[:2])
    unacc = np.zeros(arr.shape[:2])
    for t, cap in enumerate(capacity_su):
        early = np.minimum(dep[:, t] * a["dep_share_before_peak"], occ)
        base = occ - early
        want = arr[:, t] @ su
        frac = np.clip((cap - base @ su) / np.where(want > 0, want, 1), 0, 1)
        accepted = arr[:, t] * frac[:, None]
        peak = base + accepted
        peak_su[:, t] = peak @ su
        unacc[:, t] = (arr[:, t] - accepted).sum(1)
        occ = peak - np.minimum(dep[:, t] - early, peak)
    return peak_su, unacc


def gallons(dep_by_cat, a):
    return dep_by_cat @ np.array([a["fuel_uplift_rate"] * a[f"gal_{c}"] for c in CATS])


def delayed_turns(movements, techs, a):
    """movements [run, day], techs [day, shift] -> delayed turns per run."""
    share = np.array([a[f"shift_share_{s}"] for s in SHIFTS])
    work = movements[:, :, None] * share
    return np.clip(work - techs[None] * a["movements_per_tech_shift"], 0, None).sum((1, 2))


def risk_level(util, a):
    if util >= a["risk_high_threshold"]:
        return "High"
    return "Medium" if util >= a["risk_medium_threshold"] else "Low"


def plan_scenario(dates, need_su, movements_p50, gallons_p50, a):
    """Prepared plan: parking sized on the planning quantile, staffing and fuel on P50 + buffer."""
    ramp = a["ramp_capacity_su"]
    packed = ramp * (1 + a["tow_packing_gain"])
    total = packed + a["overflow_capacity_su"]
    q = int(a["planning_quantile"] * 100)
    capacity = np.full(len(dates), ramp)
    actions = []

    over_ramp = need_su > ramp
    if over_ramp.any():
        capacity[over_ramp] = packed
        actions.append({
            "id": "tow_packing", "category": "parking",
            "action": "Switch to tight tow-in packing on the main ramp for multi-night stays",
            "dates": [d for d, o in zip(dates, over_ramp) if o],
            "rationale": f"P{q} parking demand peaks at {need_su.max():.0f} su vs {ramp:.0f} su ramp",
            "cost_usd": 0, "requires_human_approval": True, "approver": "Line service manager"})
    over_packed = np.flatnonzero(need_su > packed)
    if over_packed.size:
        lo, hi = max(0, over_packed[0] - 1), over_packed[-1]  # open one day early to stage cones and staff
        capacity[lo:hi + 1] = total
        actions.append({
            "id": "overflow_apron", "category": "parking",
            "action": f"Lease the remote overflow apron (+{a['overflow_capacity_su']:.0f} su)",
            "dates": dates[lo:hi + 1],
            "rationale": f"P{q} parking demand exceeds packed ramp ({packed:.0f} su) on {over_packed.size} day(s)",
            "cost_usd": a["overflow_cost_per_day_usd"] * (hi + 1 - lo),
            "requires_human_approval": True, "approver": "FBO general manager"})
    over_total = np.flatnonzero(need_su > total)
    if over_total.size:
        actions.append({
            "id": "ppr_and_referrals", "category": "contingency",
            "action": "Require prior reservations (PPR) for arrivals and prepare a referral list of partner FBOs "
                      "at VNY and BUR. Staff decide case by case; the system never refuses an aircraft",
            "dates": dates[:over_total[0] + 1],
            "rationale": f"P{q} parking demand {need_su.max():.0f} su exceeds all prepared capacity ({total:.0f} su)",
            "cost_usd": 0, "requires_human_approval": True, "approver": "FBO general manager"})

    share = np.array([a[f"shift_share_{s}"] for s in SHIFTS])
    need_techs = np.ceil(movements_p50[:, None] * share * (1 + a["staffing_buffer"]) / a["movements_per_tech_shift"])
    techs = np.maximum(need_techs, a["normal_techs_per_shift"]).astype(int)
    extra_shifts = int((techs - a["normal_techs_per_shift"]).sum())
    if extra_shifts:
        actions.append({
            "id": "extra_line_staff", "category": "staffing",
            "action": f"Schedule {extra_shifts} additional technician shifts over the week (see daily table)",
            "dates": [d for d, t in zip(dates, techs) if t.max() > a["normal_techs_per_shift"]],
            "rationale": f"P50 movements plus {a['staffing_buffer']:.0%} buffer exceed the normal crew of "
                         f"{a['normal_techs_per_shift']:.0f} per shift",
            "cost_usd": extra_shifts * a["extra_tech_shift_cost_usd"],
            "requires_human_approval": True, "approver": "FBO general manager"})

    truck_gal = a["truck_capacity_gal"] * a["truck_loads_per_shift"]
    busiest = max(a[f"shift_share_{s}"] for s in SHIFTS)
    trucks = np.maximum(np.ceil(gallons_p50 * busiest * (1 + a["staffing_buffer"]) / truck_gal),
                        a["normal_fuel_trucks"]).astype(int)
    extra_truck_days = int((trucks - a["normal_fuel_trucks"]).sum())
    if extra_truck_days:
        actions.append({
            "id": "extra_refuelers", "category": "fuel",
            "action": "Rent additional refuelers and pre-order Jet-A for the peak days",
            "dates": [d for d, t in zip(dates, trucks) if t > a["normal_fuel_trucks"]],
            "rationale": "Busiest-shift fuel volume exceeds the normal truck fleet",
            "cost_usd": extra_truck_days * a["extra_truck_cost_per_day_usd"],
            "requires_human_approval": True, "approver": "FBO general manager"})

    return {"capacity": capacity, "techs": techs, "trucks": trucks, "actions": actions,
            "prep_cost": sum(x["cost_usd"] for x in actions)}


def outcome(arr, dep, capacity, techs, prep_cost, a):
    """Per-run unaccommodated aircraft, delayed turns and total cost for one plan."""
    _, unacc = ramp_sim(arr, dep, capacity, a)
    unacc = unacc.sum(1)
    delayed = delayed_turns((arr + dep).sum(2), techs, a)
    cost = unacc * a["revenue_per_aircraft_usd"] + delayed * a["delayed_turn_cost_usd"] + prep_cost
    return {"unaccommodated": unacc, "delayed": delayed, "cost": cost}


def dist(x):
    return {"mean": round(float(x.mean()), 1), "p10": round(float(np.percentile(x, 10)), 1),
            "p50": round(float(np.percentile(x, 50)), 1), "p90": round(float(np.percentile(x, 90)), 1)}


def run(demand: pd.DataFrame, a: dict):
    rng = np.random.default_rng(int(a["mc_seed"]))
    rows, recs = [], {}
    for scenario, sdf in demand.groupby("scenario", sort=False):
        dates, mid, lo, hi = scenario_arrays(sdf)
        draws = sample_demand(mid, lo, hi, a, rng)
        arr, dep = draws[:, 0], draws[:, 1]
        free_peak, _ = ramp_sim(arr, dep, np.full(len(dates), np.inf), a)
        need_su = np.percentile(free_peak, a["planning_quantile"] * 100, axis=0)
        movements = (arr + dep).sum(2)
        gal = gallons(dep, a)
        plan = plan_scenario(dates, need_su, np.median(movements, 0), np.median(gal, 0), a)

        ramp = a["ramp_capacity_su"]
        for t, date in enumerate(dates):
            p10, p50, p90 = np.percentile(free_peak[:, t], [10, 50, 90])
            rows.append({
                "scenario": scenario, "date": date,
                "arrivals_p50": round(float(np.median(arr[:, t].sum(1))), 1),
                "departures_p50": round(float(np.median(dep[:, t].sum(1))), 1),
                "parking_demand_su_p10": round(p10, 1), "parking_demand_su_p50": round(p50, 1),
                "parking_demand_su_p90": round(p90, 1),
                "capacity_normal_su": ramp, "capacity_prepared_su": round(float(plan["capacity"][t]), 1),
                "utilization_normal_p50": round(p50 / ramp, 3),
                "prob_over_normal_capacity": round(float((free_peak[:, t] > ramp).mean()), 3),
                "prob_over_prepared_capacity": round(float((free_peak[:, t] > plan["capacity"][t]).mean()), 3),
                "risk_level": risk_level(p50 / ramp, a),
                **{f"techs_{s}": int(plan["techs"][t, i]) for i, s in enumerate(SHIFTS)},
                "techs_normal_per_shift": int(a["normal_techs_per_shift"]),
                "fuel_gallons_p50": round(float(np.median(gal[:, t]))),
                "fuel_trucks": int(plan["trucks"][t]), "fuel_trucks_normal": int(a["normal_fuel_trucks"])})

        normal_techs = np.full(plan["techs"].shape, int(a["normal_techs_per_shift"]))
        base = outcome(arr, dep, np.full(len(dates), ramp), normal_techs, 0, a)
        prep = outcome(arr, dep, plan["capacity"], plan["techs"], plan["prep_cost"], a)
        net = base["cost"] - prep["cost"]
        day = pd.DataFrame([r for r in rows if r["scenario"] == scenario])
        peak = day.loc[day["parking_demand_su_p50"].idxmax()]
        recs[scenario] = {
            "summary": {
                "peak_day": peak["date"], "peak_parking_demand_su_p50": peak["parking_demand_su_p50"],
                "peak_parking_demand_su_p90": peak["parking_demand_su_p90"], "normal_capacity_su": ramp,
                "max_prepared_capacity_su": float(plan["capacity"].max()),
                "risk_days": day.loc[day["risk_level"] != "Low", "date"].tolist(),
                "overall_risk": risk_level(day["utilization_normal_p50"].max(), a)},
            "actions": plan["actions"], "preparation_cost_usd": plan["prep_cost"],
            "impact": {
                "runs": int(a["mc_runs"]),
                "no_preparation": {"unaccommodated_aircraft": dist(base["unaccommodated"]),
                                   "delayed_turns": dist(base["delayed"]), "total_cost_usd": dist(base["cost"]),
                                   "prob_any_unaccommodated": round(float((base["unaccommodated"] > 0.5).mean()), 3)},
                "ai_preparation": {"unaccommodated_aircraft": dist(prep["unaccommodated"]),
                                   "delayed_turns": dist(prep["delayed"]), "total_cost_usd": dist(prep["cost"]),
                                   "prob_any_unaccommodated": round(float((prep["unaccommodated"] > 0.5).mean()), 3)},
                "net_benefit_usd": dist(net),
                "prob_preparation_pays_off": round(float((net > 0).mean()), 3)}}
    return pd.DataFrame(rows), recs


def main():
    a = load_assumptions()
    demand = load_demand(sys.argv[1] if len(sys.argv) > 1 else None)
    table, recs = run(demand, a)
    table.to_csv(HERE / "resource_requirements.csv", index=False)
    out = {"meta": {
        "demand_source": demand.attrs["source"], "demand_provenance": demand.attrs["provenance"],
        "assumptions_file": "assumptions_p3.csv",
        "method": f"{int(a['mc_runs'])} Monte Carlo demand paths per scenario drawn from P2 point forecasts and assumed "
                  "planning ranges mapped to 5th/95th percentiles, with a shared event shock. P2 expected counts are treated as medians. Parking prepared for the planning quantile, "
                  "staffing and fuel for P50 plus buffer. Impact compares normal plan vs prepared plan on the same paths.",
        "limitations": "P2 historical input provenance: " + ", ".join(demand.attrs["provenance"]) + ". "
                       "FBO allocation, reservations and event assumptions are provisional; results are conditional simulations, not observed FBO performance. "
                       "P2 event-week ranges are not validated against observed Super Bowl outcomes.",
        "human_in_command": "Recommendations only. Every action needs approval by the named role. The system never "
                            "accepts, rejects or cancels an individual aircraft reservation."},
        "scenarios": recs}
    (HERE / "scenario_recommendations.json").write_text(json.dumps(out, indent=2))
    for s, r in recs.items():
        i = r["impact"]
        print(f"{s:7} peak P50 {r['summary']['peak_parking_demand_su_p50']:6.1f} su  P90 "
              f"{r['summary']['peak_parking_demand_su_p90']:6.1f}  risk {r['summary']['overall_risk']:6} "
              f"actions {[x['id'] for x in r['actions']]}  prep ${r['preparation_cost_usd']:,.0f}")
        print(f"        unaccommodated mean {i['no_preparation']['unaccommodated_aircraft']['mean']} -> "
              f"{i['ai_preparation']['unaccommodated_aircraft']['mean']}, delayed turns "
              f"{i['no_preparation']['delayed_turns']['mean']} -> {i['ai_preparation']['delayed_turns']['mean']}, "
              f"net benefit P50 ${i['net_benefit_usd']['p50']:,.0f}, pays off in {i['prob_preparation_pays_off']:.0%} of runs")


if __name__ == "__main__":
    main()
