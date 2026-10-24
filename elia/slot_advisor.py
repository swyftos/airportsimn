"""Arrival-slot and price-incentive advisor for the fictional LAX FBO, Super Bowl LXI week.

Tests two levers on the same Monte Carlo demand paths as parking_optimizer.run (same seed, same order):

- drop_and_go: an incentive (credit) offered to event arrivals Thursday to Sunday to drop passengers,
  reposition to a partner field and come back for pickup. Each event aircraft that accepts leaves the ramp the day it
  arrives instead of on its original departure day (Sunday or Monday, in proportion to departures); the pickup
  is a short turn that adds two handling movements but no parking.
- early_arrival: a cheaper rate for arriving Thursday or Friday instead of Saturday or Sunday. Departures
  do not move, so these aircraft stay longer.

How many owners accept an offer is not known, so every lever is shown at several take-up shares. The ramp is
the plain ramp (ramp_capacity_su), without tow-in packing or the overflow apron, so the levers are compared
with doing nothing. Every recommendation is an offer that a named manager approves; the system never refuses
or reassigns an aircraft.

Outputs: slot_advisor.csv (one row per scenario, lever and take-up) and slot_recommendations.json.
Usage: python slot_advisor.py [p2_output_dir]
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import parking_optimizer as po

TAKE_UP = (0.0, 0.1, 0.2, 0.3)
EVENT_ARRIVAL_DAYS = (0, 1, 2, 3)  # Thu 2027-02-11 to Sun 2027-02-14
DEPARTURE_DAYS = (3, 4)  # Sunday and Monday, when event aircraft leave
WEEKEND_DAYS, EARLY_DAYS = (2, 3), (0, 1)


def event_shares(p2_dir, scenario):
    """Share of each day's arrivals and departures that is Super Bowl extra traffic, [day, category] each,
    from P2's multipliers (extra = 1 - 1/multiplier)."""
    d = pd.read_csv(Path(p2_dir) / "demand_predictions.csv")
    d = d[d["scenario"] == scenario].assign(cat=lambda x: x["aircraft_category"].map(po.CATEGORY_ALIASES))
    out = []
    for t in po.DIRS:
        m = d.pivot_table(index="date", columns="cat", values=f"{t}_multiplier").reindex(columns=list(po.CATS))
        out.append(1 - 1 / m.to_numpy())
    return out


def drop_and_go(arr, dep, share, extra_arr, extra_dep):
    """Share of the event aircraft arriving Thu-Sun leaves the ramp the same day; their later departure (Sunday or
    Monday, in proportion to event departures) no longer happens from the ramp.
    Returns (arr, dep, accepted aircraft per run, extra handling movements per run)."""
    dep = dep.copy()
    moved = arr[:, EVENT_ARRIVAL_DAYS] * extra_arr[list(EVENT_ARRIVAL_DAYS)] * share
    later = dep[:, DEPARTURE_DAYS] * extra_dep[list(DEPARTURE_DAYS)]
    weights = later / np.where(later.sum(1, keepdims=True) > 0, later.sum(1, keepdims=True), 1)
    dep[:, EVENT_ARRIVAL_DAYS] += moved
    dep[:, DEPARTURE_DAYS] = np.clip(dep[:, DEPARTURE_DAYS] - moved.sum(1)[:, None] * weights, 0, None)
    accepted = moved.sum((1, 2))
    return arr, dep, accepted, 2 * accepted


def early_arrival(arr, dep, share):
    """Share of weekend arrivals arrives on Thursday or Friday instead (split evenly). Returns (arr, dep)."""
    arr = arr.copy()
    moved = arr[:, WEEKEND_DAYS].sum(1) * share
    arr[:, WEEKEND_DAYS] *= 1 - share
    arr[:, EARLY_DAYS] += moved[:, None] / len(EARLY_DAYS)
    return arr, dep


def evaluate(arr, dep, a, extra_movements=0):
    """Peaks from unconstrained demand; unaccommodated aircraft against the plain ramp."""
    peak, _ = po.ramp_sim(arr, dep, np.full(arr.shape[1], np.inf), a)
    _, unacc = po.ramp_sim(arr, dep, np.full(arr.shape[1], a["ramp_capacity_su"]), a)
    return {"peak_su_p50": float(np.median(peak.max(1))), "peak_su_p90": float(np.percentile(peak.max(1), 90)),
            "game_day_su_p50": float(np.median(peak[:, 3])),
            "unaccommodated_mean": float(unacc.sum(1).mean()),
            "max_daily_arrivals_p50": float(np.median(arr.sum(2).max(1))),
            "movements_p50": float(np.median((arr + dep).sum((1, 2)) + extra_movements))}


def run(demand, a, p2_dir=None):
    p2_dir = p2_dir or next((d for d in po.P2_DIRS if d.exists()), po.P2_DIRS[0])
    rng = np.random.default_rng(int(a["mc_seed"]))
    rows = []
    for scenario, sdf in demand.groupby("scenario", sort=False):
        dates, mid, lo, hi = po.scenario_arrays(sdf)
        draws = po.sample_demand(mid, lo, hi, a, rng)
        arr, dep = draws[:, 0], draws[:, 1]
        base = evaluate(arr, dep, a)
        extra_arr, extra_dep = event_shares(p2_dir, scenario)
        for share in TAKE_UP:
            a2, d2, accepted, extra = drop_and_go(arr, dep, share, extra_arr, extra_dep)
            r = evaluate(a2, d2, a, extra)
            credits = float(accepted.mean()) * a["slot_dropgo_credit_usd"]
            saved = (base["unaccommodated_mean"] - r["unaccommodated_mean"]) * a["revenue_per_aircraft_usd"]
            rows.append({"scenario": scenario, "lever": "drop_and_go", "take_up": share, **r,
                         "aircraft_accepting_mean": round(float(accepted.mean()), 2),
                         "incentive_cost_usd": round(credits), "net_vs_no_action_usd": round(saved - credits)})
            a3, d3 = early_arrival(arr, dep, share)
            r = evaluate(a3, d3, a)
            saved = (base["unaccommodated_mean"] - r["unaccommodated_mean"]) * a["revenue_per_aircraft_usd"]
            moved = float(arr[:, WEEKEND_DAYS].sum((1, 2)).mean()) * share
            rows.append({"scenario": scenario, "lever": "early_arrival", "take_up": share, **r,
                         "aircraft_accepting_mean": round(moved, 2),
                         "incentive_cost_usd": round(moved * a["slot_early_discount_usd"]),
                         "net_vs_no_action_usd": round(saved - moved * a["slot_early_discount_usd"])})
    return [{k: round(v, 2) if isinstance(v, float) else v for k, v in r.items()} for r in rows]


def recommend(rows, a):
    """Recommend the drop-and-go offer where it is worth more than it costs at the tested take-up."""
    recs = {}
    for scenario in dict.fromkeys(r["scenario"] for r in rows):
        drop = [r for r in rows if r["scenario"] == scenario and r["lever"] == "drop_and_go"]
        early = [r for r in rows if r["scenario"] == scenario and r["lever"] == "early_arrival"]
        base, best = drop[0], max(drop, key=lambda r: r["net_vs_no_action_usd"])
        actions = []
        if best["net_vs_no_action_usd"] > 0:
            low = drop[1]
            actions.append({
                "id": "drop_and_go_offer", "category": "pricing",
                "action": (f"Offer a ${a['slot_dropgo_credit_usd']:.0f} drop-and-go credit to Super Bowl arrivals Thu-Sun: "
                           "drop passengers, reposition to a partner field, return for pickup"),
                "rationale": (f"Without action {base['unaccommodated_mean']:.1f} aircraft a run do not fit the "
                              f"{a['ramp_capacity_su']:.0f} su ramp. If {low['take_up']:.0%} of event arrivals accept: "
                              f"{low['unaccommodated_mean']:.1f}, net ${low['net_vs_no_action_usd']:,}; if "
                              f"{best['take_up']:.0%} accept: {best['unaccommodated_mean']:.1f}, net "
                              f"${best['net_vs_no_action_usd']:,}. Complements the ramp plan (tow-in packing, "
                              "overflow lease); take-up is unknown"),
                "requires_human_approval": True, "approver": "FBO general manager"})
        early_top = early[-1]
        recs[scenario] = {
            "no_action": {k: base[k] for k in ("peak_su_p50", "peak_su_p90", "unaccommodated_mean")},
            "actions": actions,
            "early_arrival_finding": (f"At {early_top['take_up']:.0%} take-up, a cheap Thu-Fri slot moves the game-day "
                                      f"P50 from {base['game_day_su_p50']:.1f} to {early_top['game_day_su_p50']:.1f} su "
                                      f"and unaccommodated aircraft from {base['unaccommodated_mean']:.1f} to "
                                      f"{early_top['unaccommodated_mean']:.1f}: aircraft arrive earlier but leave at the "
                                      "same time, so they stay longer. It does not free parking."),
            "pricing_note": ("Past Super Bowls filled parking without raising prices (alan/docs/"
                             "lax_private_capacity_and_cost_research.md); reservations (PPR) stay the primary tool, "
                             "incentives are offers, and the system never refuses an aircraft.")}
    return recs


def main():
    a = po.load_assumptions()
    demand = po.load_demand(sys.argv[1] if len(sys.argv) > 1 else None)
    rows = run(demand, a, sys.argv[1] if len(sys.argv) > 1 else None)
    import csv
    with open(po.HERE / "slot_advisor.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    recs = recommend(rows, a)
    meta = {"method": __doc__.split("\n\n")[1].replace("\n", " "), "take_up_tested": list(TAKE_UP),
            "take_up_status": "unknown; shown as a range, not a forecast",
            "ramp_capacity_su": a["ramp_capacity_su"], "mc_runs": int(a["mc_runs"]),
            "human_in_command": "Offers only. Every action needs approval by the named role. The system never "
                                "accepts, rejects or cancels an individual aircraft."}
    (po.HERE / "slot_recommendations.json").write_text(json.dumps({"meta": meta, "scenarios": recs}, indent=2))
    for s, r in recs.items():
        print(f"{s:7} no action: {r['no_action']['unaccommodated_mean']:.1f} unaccommodated; "
              f"actions {[x['id'] for x in r['actions']]}")
        print(f"        {r['early_arrival_finding']}")


if __name__ == "__main__":
    main()
