"""Sensitivity analysis and capacity stress test for the P3 parking model.

One-at-a-time tornado analysis on the Medium scenario, standard variant.
Capacity stress test across ramp capacities [10, 15, 20, 25, 30, 40, 50, 75]
for 'standard' and 'departure_delay_24h' variants across all scenarios.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import parking_optimizer as po

MC_RUNS = 2000
CSV_NOTE_BASE = f"mc_runs={MC_RUNS}"


def run_tornado(demand: pd.DataFrame = None, a_base: dict = None, mc_runs: int = MC_RUNS) -> pd.DataFrame:
    """Run one-at-a-time tornado sensitivity on the Medium scenario, standard variant.

    Parameters tested:
    1. demand_scale: 0.5 / 1.0 / 1.5 (FBO share 0.05 / 0.10 / 0.15)
    2. opening_dwell_days: 0.8 / 1.1 / 1.5
    3. dep_share_before_peak: 0.3 / 0.5 / 0.7
    4. aircraft_mix: (0.60,0.30,0.10) / (0.47,0.33,0.20) / (0.30,0.35,0.35)
    5. su_large: 2.0 / 2.5 / 3.0
    """
    if demand is None:
        demand = po.load_demand()
    if a_base is None:
        a_base = po.load_assumptions()
    a_base = a_base.copy()
    a_base["mc_runs"] = mc_runs

    # Base baseline run for comparison
    table_base, recs_base = po.run(demand, a_base, variant="standard")
    med_base_p50 = recs_base["Medium"]["summary"]["peak_parking_demand_su_p50"]
    med_base_p90 = recs_base["Medium"]["summary"]["peak_parking_demand_su_p90"]
    med_base_prob = table_base[table_base["scenario"] == "Medium"]["prob_over_normal_capacity"].max()

    rows = []

    # 1. demand_scale
    # Multiply every demand value column by 0.5 / 1.0 / 1.5; scale initial_transient_aircraft by the same factor
    scale_runs = {}
    for scale in [0.5, 1.0, 1.5]:
        d = demand.copy()
        for col in ["expected_movements", "lower90_prediction", "upper90_prediction"]:
            d[col] = d[col] * scale
        if "baseline_radius" in d.columns:
            d["baseline_radius"] = d["baseline_radius"] * scale
        if "baseline_first_day_arrivals" in d.attrs:
            d.attrs["baseline_first_day_arrivals"] = demand.attrs["baseline_first_day_arrivals"] * scale
        a = a_base.copy()
        a["initial_transient_aircraft"] = a_base["initial_transient_aircraft"] * scale
        t, r = po.run(d, a, variant="standard")
        p50 = r["Medium"]["summary"]["peak_parking_demand_su_p50"]
        p90 = r["Medium"]["summary"]["peak_parking_demand_su_p90"]
        prob = t[t["scenario"] == "Medium"]["prob_over_normal_capacity"].max()
        scale_runs[scale] = (p50, p90, prob)

    swing_p50 = round(abs(scale_runs[1.5][0] - scale_runs[0.5][0]), 1)
    rows.append({
        "parameter": "demand_scale",
        "low_value": 0.5,
        "base_value": 1.0,
        "high_value": 1.5,
        "peak_p50_low": scale_runs[0.5][0],
        "peak_p50_base": scale_runs[1.0][0],
        "peak_p50_high": scale_runs[1.5][0],
        "swing_p50": swing_p50,
        "peak_p90_low": scale_runs[0.5][1],
        "peak_p90_high": scale_runs[1.5][1],
        "note": f"{CSV_NOTE_BASE}; FBO share 0.05 / 0.10 / 0.15; max prob_over_normal_capacity low={scale_runs[0.5][2]:.3f}, base={scale_runs[1.0][2]:.3f}, high={scale_runs[1.5][2]:.3f}",
    })

    # 2. opening_dwell_days
    # Recompute initial_transient_aircraft = current value / 1.1 * dwell
    dwell_runs = {}
    for dwell in [0.8, 1.1, 1.5]:
        a = a_base.copy()
        a["opening_dwell_days"] = dwell
        a["initial_transient_aircraft"] = a_base["initial_transient_aircraft"] / 1.1 * dwell
        t, r = po.run(demand, a, variant="standard")
        p50 = r["Medium"]["summary"]["peak_parking_demand_su_p50"]
        p90 = r["Medium"]["summary"]["peak_parking_demand_su_p90"]
        prob = t[t["scenario"] == "Medium"]["prob_over_normal_capacity"].max()
        dwell_runs[dwell] = (p50, p90, prob)

    swing_p50 = round(abs(dwell_runs[1.5][0] - dwell_runs[0.8][0]), 1)
    rows.append({
        "parameter": "opening_dwell_days",
        "low_value": 0.8,
        "base_value": 1.1,
        "high_value": 1.5,
        "peak_p50_low": dwell_runs[0.8][0],
        "peak_p50_base": dwell_runs[1.1][0],
        "peak_p50_high": dwell_runs[1.5][0],
        "swing_p50": swing_p50,
        "peak_p90_low": dwell_runs[0.8][1],
        "peak_p90_high": dwell_runs[1.5][1],
        "note": f"{CSV_NOTE_BASE}; opening dwell days; max prob_over_normal_capacity low={dwell_runs[0.8][2]:.3f}, base={dwell_runs[1.1][2]:.3f}, high={dwell_runs[1.5][2]:.3f}",
    })

    # 3. dep_share_before_peak
    # 0.3 / 0.5 / 0.7
    dep_runs = {}
    for dep_share in [0.3, 0.5, 0.7]:
        a = a_base.copy()
        a["dep_share_before_peak"] = dep_share
        t, r = po.run(demand, a, variant="standard")
        p50 = r["Medium"]["summary"]["peak_parking_demand_su_p50"]
        p90 = r["Medium"]["summary"]["peak_parking_demand_su_p90"]
        prob = t[t["scenario"] == "Medium"]["prob_over_normal_capacity"].max()
        dep_runs[dep_share] = (p50, p90, prob)

    swing_p50 = round(abs(dep_runs[0.7][0] - dep_runs[0.3][0]), 1)
    rows.append({
        "parameter": "dep_share_before_peak",
        "low_value": 0.3,
        "base_value": 0.5,
        "high_value": 0.7,
        "peak_p50_low": dep_runs[0.3][0],
        "peak_p50_base": dep_runs[0.5][0],
        "peak_p50_high": dep_runs[0.7][0],
        "swing_p50": swing_p50,
        "peak_p90_low": dep_runs[0.3][1],
        "peak_p90_high": dep_runs[0.7][1],
        "note": f"{CSV_NOTE_BASE}; departure share before arrival peak; max prob_over_normal_capacity low={dep_runs[0.3][2]:.3f}, base={dep_runs[0.5][2]:.3f}, high={dep_runs[0.7][2]:.3f}",
    })

    # 4. aircraft_mix
    # (0.60,0.30,0.10) / (0.47,0.33,0.20) / (0.30,0.35,0.35)
    # Set mix_light/mix_midsize/mix_large in a AND rescale demand per-category values
    mixes = {
        "low": {"light": 0.60, "midsize": 0.30, "large": 0.10, "label": "(0.60,0.30,0.10)"},
        "base": {"light": 0.47, "midsize": 0.33, "large": 0.20, "label": "(0.47,0.33,0.20)"},
        "high": {"light": 0.30, "midsize": 0.35, "large": 0.35, "label": "(0.30,0.35,0.35)"},
    }
    mix_runs = {}
    for key, m in mixes.items():
        d = demand.copy()
        tot = d.groupby(["scenario", "date", "direction"])["expected_movements"].transform("sum")
        target_exp = tot * d["aircraft_category"].map(m)
        scale = target_exp / d["expected_movements"]
        for col in ["expected_movements", "lower90_prediction", "upper90_prediction"]:
            d[col] = d[col] * scale
        if "baseline_radius" in d.columns:
            d["baseline_radius"] = d["baseline_radius"] * scale

        a = a_base.copy()
        a["mix_light"] = m["light"]
        a["mix_midsize"] = m["midsize"]
        a["mix_large"] = m["large"]
        t, r = po.run(d, a, variant="standard")
        p50 = r["Medium"]["summary"]["peak_parking_demand_su_p50"]
        p90 = r["Medium"]["summary"]["peak_parking_demand_su_p90"]
        prob = t[t["scenario"] == "Medium"]["prob_over_normal_capacity"].max()
        mix_runs[key] = (p50, p90, prob)

    swing_p50 = round(abs(mix_runs["high"][0] - mix_runs["low"][0]), 1)
    rows.append({
        "parameter": "aircraft_mix",
        "low_value": mixes["low"]["label"],
        "base_value": mixes["base"]["label"],
        "high_value": mixes["high"]["label"],
        "peak_p50_low": mix_runs["low"][0],
        "peak_p50_base": mix_runs["base"][0],
        "peak_p50_high": mix_runs["high"][0],
        "swing_p50": swing_p50,
        "peak_p90_low": mix_runs["low"][1],
        "peak_p90_high": mix_runs["high"][1],
        "note": f"{CSV_NOTE_BASE}; fleet mix light/midsize/large; max prob_over_normal_capacity low={mix_runs['low'][2]:.3f}, base={mix_runs['base'][2]:.3f}, high={mix_runs['high'][2]:.3f}",
    })

    # 5. su_large
    # 2.0 / 2.5 / 3.0
    su_runs = {}
    for su in [2.0, 2.5, 3.0]:
        a = a_base.copy()
        a["su_large"] = su
        t, r = po.run(demand, a, variant="standard")
        p50 = r["Medium"]["summary"]["peak_parking_demand_su_p50"]
        p90 = r["Medium"]["summary"]["peak_parking_demand_su_p90"]
        prob = t[t["scenario"] == "Medium"]["prob_over_normal_capacity"].max()
        su_runs[su] = (p50, p90, prob)

    swing_p50 = round(abs(su_runs[3.0][0] - su_runs[2.0][0]), 1)
    rows.append({
        "parameter": "su_large",
        "low_value": 2.0,
        "base_value": 2.5,
        "high_value": 3.0,
        "peak_p50_low": su_runs[2.0][0],
        "peak_p50_base": su_runs[2.5][0],
        "peak_p50_high": su_runs[3.0][0],
        "swing_p50": swing_p50,
        "peak_p90_low": su_runs[2.0][1],
        "peak_p90_high": su_runs[3.0][1],
        "note": f"{CSV_NOTE_BASE}; large jet space unit footprint; max prob_over_normal_capacity low={su_runs[2.0][2]:.3f}, base={su_runs[2.5][2]:.3f}, high={su_runs[3.0][2]:.3f}",
    })

    df = pd.DataFrame(rows)
    df = df.sort_values(by="swing_p50", ascending=False).reset_index(drop=True)
    return df


def run_capacity_stress(
    demand: pd.DataFrame = None,
    a_base: dict = None,
    mc_runs: int = MC_RUNS,
    capacities: list = None,
    variants: list = None,
) -> tuple[pd.DataFrame, dict]:
    """Run capacity stress test across specified capacities and variants for all scenarios.

    Returns:
        (df_results, capacity_thresholds)
    """
    if demand is None:
        demand = po.load_demand()
    if a_base is None:
        a_base = po.load_assumptions()
    a_base = a_base.copy()
    a_base["mc_runs"] = mc_runs

    if capacities is None:
        capacities = [10, 15, 20, 25, 30, 40, 50, 75]
    if variants is None:
        variants = ["standard", "departure_delay_24h"]

    scenarios = ["Low", "Medium", "High"]
    rows = []

    for cap in capacities:
        a = a_base.copy()
        a["ramp_capacity_su"] = float(cap)
        for var in variants:
            table, recs = po.run(demand, a, variant=var)
            for scen in scenarios:
                r = recs[scen]
                sub_t = table[table["scenario"] == scen]
                max_prob = float(sub_t["prob_over_normal_capacity"].max())
                i = r["impact"]
                no_prep_u = float(i["no_preparation"]["unaccommodated_aircraft"]["mean"])
                ai_prep_u = float(i["ai_preparation"]["unaccommodated_aircraft"]["mean"])
                net_ben_p50 = float(i["net_benefit_usd"]["p50"])
                prob_pays = float(i["prob_preparation_pays_off"])
                prep_cost = float(r["preparation_cost_usd"])
                action_ids = "|".join(x["id"] for x in r["actions"])

                rows.append({
                    "ramp_capacity_su": cap,
                    "variant": var,
                    "scenario": scen,
                    "peak_parking_demand_su_p50": r["summary"]["peak_parking_demand_su_p50"],
                    "peak_parking_demand_su_p90": r["summary"]["peak_parking_demand_su_p90"],
                    "overall_risk": r["summary"]["overall_risk"],
                    "max_prob_over_normal_capacity": max_prob,
                    "no_preparation_unaccommodated_mean": no_prep_u,
                    "ai_preparation_unaccommodated_mean": ai_prep_u,
                    "net_benefit_usd_p50": net_ben_p50,
                    "prob_preparation_pays_off": prob_pays,
                    "preparation_cost_usd": prep_cost,
                    "action_ids": action_ids,
                    "note": CSV_NOTE_BASE,
                })

    df = pd.DataFrame(rows)

    # Compute smallest tested capacity at which no-preparation unaccommodated mean < 0.5
    thresholds = {}
    for var in variants:
        for scen in scenarios:
            sub = df[(df["variant"] == var) & (df["scenario"] == scen)]
            ok = sub[sub["no_preparation_unaccommodated_mean"] < 0.5]
            min_cap = int(ok["ramp_capacity_su"].min()) if len(ok) > 0 else None
            thresholds[(var, scen)] = min_cap

    return df, thresholds


def main():
    print("=" * 70)
    print("P3 Parking Model - Sensitivity Analysis & Capacity Stress Test")
    print(f"Monte Carlo runs: {MC_RUNS}")
    print("=" * 70)

    # 1. Tornado sensitivity
    print("\nRunning one-at-a-time tornado on Medium scenario (standard variant)...")
    tornado_df = run_tornado()
    tornado_path = HERE / "sensitivity_tornado.csv"
    tornado_df.to_csv(tornado_path, index=False, lineterminator="\n")
    print(f"Saved tornado results to {tornado_path}")
    print("\nTornado Sensitivity Summary (sorted by swing_p50 descending):")
    print("-" * 70)
    for _, row in tornado_df.iterrows():
        print(f"  {row['parameter']:22} low={row['peak_p50_low']:5.1f}  base={row['peak_p50_base']:5.1f}  "
              f"high={row['peak_p50_high']:5.1f}  swing_p50={row['swing_p50']:4.1f} su")

    # 2. Capacity stress
    print("\nRunning capacity stress across capacities and variants...")
    stress_df, thresholds = run_capacity_stress()
    stress_path = HERE / "capacity_stress.csv"
    stress_df.to_csv(stress_path, index=False, lineterminator="\n")
    print(f"Saved capacity stress results to {stress_path}")

    print("\nCapacity Thresholds (smallest tested capacity where no-prep unaccommodated mean < 0.5):")
    print("-" * 70)
    for (var, scen), cap in thresholds.items():
        print(f"  {var:20} scenario {scen:6}: {cap:2d} su")
    print("=" * 70)


if __name__ == "__main__":
    main()
