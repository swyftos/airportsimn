"""P3 Parking & Resource Optimization for the fictional LAX FBO, Super Bowl LXI week.

Turns daily demand forecasts (P2) into parking occupancy, staffing, fuel workload,
risk levels and a preparation plan per scenario, then measures the plan against
operating with the normal plan.

The optimizer only RECOMMENDS. Every action carries requires_human_approval and an
approver role; nothing here accepts, rejects or cancels an individual reservation.

Input contract (one row per date x scenario):
    date, scenario, arrivals_p10, arrivals_p50, arrivals_p90,
    departures_p10, departures_p50, departures_p90
Optional columns share_light, share_midsize, share_heavy override the default aircraft mix.

Usage: python parking_optimizer.py [demand_csv]
Defaults to ../marvin/demand_predictions.csv, else the synthetic stub.
"""
import json
import math
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
QUANTILES = ("p10", "p50", "p90")
CATS = ("light", "midsize", "heavy")
SHIFTS = ("morning", "day", "night")


def load_assumptions(path=HERE / "assumptions_p3.csv") -> dict:
    df = pd.read_csv(path)
    return dict(zip(df["parameter"], df["value"].astype(float)))


def load_demand(path=None) -> pd.DataFrame:
    if path is None:
        real = HERE.parent / "marvin" / "demand_predictions.csv"
        path = real if real.exists() else HERE / "stub_demand_predictions.csv"
        if not Path(path).exists():
            import stub_demand
            stub_demand.build().to_csv(path, index=False)
    df = pd.read_csv(path)
    required = {"date", "scenario"} | {f"{f}_{q}" for f in ("arrivals", "departures") for q in QUANTILES}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path} is missing columns {sorted(missing)}")
    df.attrs["source_file"] = str(path)
    return df.sort_values(["scenario", "date"]).reset_index(drop=True)


def su_per_aircraft(a: dict, row=None) -> float:
    """Average parking footprint of one transient aircraft, in space units."""
    mix = {c: a[f"mix_{c}"] for c in CATS}
    if row is not None and all(f"share_{c}" in row and pd.notna(row[f"share_{c}"]) for c in CATS):
        mix = {c: row[f"share_{c}"] for c in CATS}
    return sum(mix[c] * a[f"su_{c}"] for c in CATS)


def gallons_per_departure(a: dict) -> float:
    return a["fuel_uplift_rate"] * sum(a[f"mix_{c}"] * a[f"gal_{c}"] for c in CATS)


def simulate(arr, dep, capacity_su, avg_su, a):
    """Day-by-day ramp simulation for one demand path.

    Within a day, a share of departures leaves before the arrival peak, the rest after.
    Arrivals that do not fit at the peak are counted as unaccommodated (they would be
    referred elsewhere by a human, never refused by the system).
    """
    occ = a["initial_transient_aircraft"]
    out = []
    for ar, de, cap in zip(arr, dep, capacity_su):
        early = min(de * a["dep_share_before_peak"], occ)
        fits = max(0.0, cap / avg_su - (occ - early))
        accepted = min(ar, fits)
        peak = occ - early + accepted
        late = min(de - early, peak)
        occ = peak - late
        out.append({"peak_aircraft": peak, "peak_su": peak * avg_su,
                    "unaccommodated": ar - accepted, "end_aircraft": occ})
    return pd.DataFrame(out)


def shift_workload(movements: float, a: dict) -> dict:
    return {s: movements * a[f"shift_share_{s}"] for s in SHIFTS}


def staffing_need(movements: float, a: dict, buffer=0.0) -> dict:
    return {s: math.ceil(w * (1 + buffer) / a["movements_per_tech_shift"])
            for s, w in shift_workload(movements, a).items()}


def trucks_need(departures: float, a: dict, buffer=0.0) -> int:
    busiest = max(a[f"shift_share_{s}"] for s in SHIFTS)
    gal_shift = departures * gallons_per_departure(a) * busiest * (1 + buffer)
    return math.ceil(gal_shift / (a["truck_capacity_gal"] * a["truck_loads_per_shift"]))


def delayed_turns(movements: float, techs: dict, a: dict) -> float:
    return sum(max(0.0, w - techs[s] * a["movements_per_tech_shift"])
               for s, w in shift_workload(movements, a).items())


def risk_level(util: float, a: dict) -> str:
    if util >= a["risk_high_threshold"]:
        return "High"
    return "Medium" if util >= a["risk_medium_threshold"] else "Low"


def plan_scenario(sdf: pd.DataFrame, a: dict) -> dict:
    """Build the prepared plan for one scenario. Parking is sized on P90, staffing on P50 + buffer."""
    avg_su = su_per_aircraft(a, sdf.iloc[0])
    dates = sdf["date"].tolist()
    ramp = a["ramp_capacity_su"]
    packed = ramp * (1 + a["tow_packing_gain"])
    unlimited = [1e9] * len(sdf)
    p90 = simulate(sdf["arrivals_p90"], sdf["departures_p90"], unlimited, avg_su, a)

    actions, capacity = [], [ramp] * len(sdf)
    over_ramp = p90["peak_su"] > ramp
    if over_ramp.any():
        capacity = [packed if o else ramp for o in over_ramp]
        actions.append({
            "id": "tow_packing", "category": "parking",
            "action": "Switch to tight tow-in packing on the main ramp for multi-night stays",
            "dates": [d for d, o in zip(dates, over_ramp) if o],
            "rationale": f"P90 peak reaches {p90['peak_su'].max():.0f} su vs {ramp:.0f} su ramp",
            "cost_usd": 0, "requires_human_approval": True, "approver": "Line service manager"})
    over_packed = p90["peak_su"] > packed
    if over_packed.any():
        idx = [i for i, o in enumerate(over_packed) if o]
        lo, hi = max(0, idx[0] - 1), idx[-1]  # open one day early to stage cones and staff
        days = dates[lo:hi + 1]
        for i in range(lo, hi + 1):
            capacity[i] = packed + a["overflow_capacity_su"]
        actions.append({
            "id": "overflow_apron", "category": "parking",
            "action": f"Lease the remote overflow apron (+{a['overflow_capacity_su']:.0f} su)",
            "dates": days, "rationale": f"P90 peak exceeds packed ramp ({packed:.0f} su) on {len(idx)} day(s)",
            "cost_usd": a["overflow_cost_per_day_usd"] * len(days),
            "requires_human_approval": True, "approver": "FBO general manager"})
    total = packed + a["overflow_capacity_su"]
    if (p90["peak_su"] > total).any():
        first = dates[int((p90["peak_su"] > total).idxmax())]
        actions.append({
            "id": "ppr_and_referrals", "category": "contingency",
            "action": "Require prior reservations (PPR) for arrivals and prepare a referral list of partner FBOs "
                      "at VNY and BUR. Staff decide case by case; the system never refuses an aircraft",
            "dates": [d for d in dates if d <= first], "rationale":
                f"P90 peak {p90['peak_su'].max():.0f} su exceeds all prepared capacity ({total:.0f} su)",
            "cost_usd": 0, "requires_human_approval": True, "approver": "FBO general manager"})

    techs, trucks = [], []
    for _, r in sdf.iterrows():
        mov = r["arrivals_p50"] + r["departures_p50"]
        need = staffing_need(mov, a, a["staffing_buffer"])
        techs.append({s: max(int(a["normal_techs_per_shift"]), n) for s, n in need.items()})
        trucks.append(max(int(a["normal_fuel_trucks"]), trucks_need(r["departures_p50"], a, a["staffing_buffer"])))
    extra_shifts = sum(t[s] - a["normal_techs_per_shift"] for t in techs for s in SHIFTS)
    if extra_shifts:
        actions.append({
            "id": "extra_line_staff", "category": "staffing",
            "action": f"Schedule {extra_shifts:.0f} additional technician shifts over the week (see daily table)",
            "dates": [d for d, t in zip(dates, techs) if max(t.values()) > a["normal_techs_per_shift"]],
            "rationale": "P50 movements plus buffer exceed normal crew of "
                         f"{a['normal_techs_per_shift']:.0f} per shift",
            "cost_usd": extra_shifts * a["extra_tech_shift_cost_usd"],
            "requires_human_approval": True, "approver": "FBO general manager"})
    extra_truck_days = sum(t - a["normal_fuel_trucks"] for t in trucks)
    if extra_truck_days:
        actions.append({
            "id": "extra_refuelers", "category": "fuel",
            "action": "Rent additional refuelers and pre-order Jet-A for the peak days",
            "dates": [d for d, t in zip(dates, trucks) if t > a["normal_fuel_trucks"]],
            "rationale": "Busiest-shift fuel volume exceeds normal truck fleet",
            "cost_usd": extra_truck_days * a["extra_truck_cost_per_day_usd"],
            "requires_human_approval": True, "approver": "FBO general manager"})

    return {"avg_su": avg_su, "capacity": capacity, "techs": techs, "trucks": trucks,
            "actions": actions, "prep_cost": sum(x["cost_usd"] for x in actions)}


def evaluate(sdf, plan, a, prepared: bool, q: str) -> dict:
    """Outcome of one plan (normal or prepared) if demand follows quantile path q."""
    n = len(sdf)
    normal_techs = {s: int(a["normal_techs_per_shift"]) for s in SHIFTS}
    cap = plan["capacity"] if prepared else [a["ramp_capacity_su"]] * n
    techs = plan["techs"] if prepared else [normal_techs] * n
    sim = simulate(sdf[f"arrivals_{q}"], sdf[f"departures_{q}"], cap, plan["avg_su"], a)
    mov = (sdf[f"arrivals_{q}"] + sdf[f"departures_{q}"]).tolist()
    delayed = sum(delayed_turns(m, t, a) for m, t in zip(mov, techs))
    unacc = sim["unaccommodated"].sum()
    cost = unacc * a["revenue_per_aircraft_usd"] + delayed * a["delayed_turn_cost_usd"]
    cost += plan["prep_cost"] if prepared else 0
    return {"unaccommodated_aircraft": round(unacc, 1), "delayed_turns": round(delayed, 1),
            "peak_utilization": round(max(s / c for s, c in zip(sim["peak_su"], cap)), 3),
            "total_cost_usd": round(cost)}


def run(demand: pd.DataFrame, a: dict):
    rows, recs = [], {}
    for scenario, sdf in demand.groupby("scenario", sort=False):
        sdf = sdf.reset_index(drop=True)
        plan = plan_scenario(sdf, a)
        sims = {q: simulate(sdf[f"arrivals_{q}"], sdf[f"departures_{q}"], [1e9] * len(sdf), plan["avg_su"], a)
                for q in QUANTILES}
        for i, r in sdf.iterrows():
            util = sims["p50"].loc[i, "peak_su"] / a["ramp_capacity_su"]
            row = {"scenario": scenario, "date": r["date"],
                   "arrivals_p50": r["arrivals_p50"], "departures_p50": r["departures_p50"]}
            for q in QUANTILES:
                row[f"parking_demand_su_{q}"] = round(sims[q].loc[i, "peak_su"], 1)
            row.update({
                "capacity_normal_su": a["ramp_capacity_su"], "capacity_prepared_su": round(plan["capacity"][i], 1),
                "utilization_normal_p50": round(util, 3),
                "utilization_prepared_p90": round(sims["p90"].loc[i, "peak_su"] / plan["capacity"][i], 3),
                "risk_level": risk_level(util, a)})
            row.update({f"techs_{s}": plan["techs"][i][s] for s in SHIFTS})
            row.update({"techs_normal_per_shift": int(a["normal_techs_per_shift"]),
                        "fuel_gallons_p50": round(r["departures_p50"] * gallons_per_departure(a)),
                        "fuel_trucks": plan["trucks"][i], "fuel_trucks_normal": int(a["normal_fuel_trucks"])})
            rows.append(row)

        impact = {}
        for q in QUANTILES:
            base, prep = evaluate(sdf, plan, a, False, q), evaluate(sdf, plan, a, True, q)
            impact[q] = {"no_preparation": base, "ai_preparation": prep,
                         "aircraft_accommodated_gain": round(base["unaccommodated_aircraft"]
                                                             - prep["unaccommodated_aircraft"], 1),
                         "net_benefit_usd": base["total_cost_usd"] - prep["total_cost_usd"]}
        day = pd.DataFrame([x for x in rows if x["scenario"] == scenario])
        peak = day.loc[day["parking_demand_su_p50"].idxmax()]
        recs[scenario] = {
            "summary": {"peak_day": peak["date"], "peak_parking_demand_su_p50": peak["parking_demand_su_p50"],
                        "peak_parking_demand_su_p90": peak["parking_demand_su_p90"],
                        "normal_capacity_su": a["ramp_capacity_su"],
                        "max_prepared_capacity_su": round(max(plan["capacity"]), 1),
                        "risk_days": day.loc[day["risk_level"] != "Low", "date"].tolist(),
                        "overall_risk": risk_level(day["utilization_normal_p50"].max(), a)},
            "actions": plan["actions"], "preparation_cost_usd": plan["prep_cost"], "impact": impact}
    return pd.DataFrame(rows), recs


def main():
    a = load_assumptions()
    demand = load_demand(sys.argv[1] if len(sys.argv) > 1 else None)
    table, recs = run(demand, a)
    table.to_csv(HERE / "resource_requirements.csv", index=False)
    out = {"meta": {
        "demand_source": demand.attrs["source_file"],
        "demand_is_synthetic": bool((demand.get("source") == "synthetic_stub").any()),
        "assumptions_file": "assumptions_p3.csv",
        "planning_rules": "Parking sized on P90 demand path, staffing and fuel on P50 plus buffer. "
                          "Impact compares the normal plan with the prepared plan under P10, P50 and P90 outcomes.",
        "human_in_command": "Recommendations only. Every action needs approval by the named role. The system never "
                            "accepts, rejects or cancels an individual aircraft reservation."},
        "scenarios": recs}
    (HERE / "scenario_recommendations.json").write_text(json.dumps(out, indent=2, default=float))
    for s, r in recs.items():
        i = r["impact"]["p50"]
        print(f"{s:7} peak {r['summary']['peak_parking_demand_su_p50']:6.1f} su (P90 "
              f"{r['summary']['peak_parking_demand_su_p90']:.1f}) risk {r['summary']['overall_risk']:6} "
              f"actions {len(r['actions'])}  prep ${r['preparation_cost_usd']:,.0f}  P50: unaccommodated "
              f"{i['no_preparation']['unaccommodated_aircraft']} -> {i['ai_preparation']['unaccommodated_aircraft']}, "
              f"delayed turns {i['no_preparation']['delayed_turns']} -> {i['ai_preparation']['delayed_turns']}, "
              f"net ${i['net_benefit_usd']:,.0f}")


if __name__ == "__main__":
    main()
