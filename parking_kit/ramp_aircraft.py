"""How many aircraft of each size the parking model puts on the ramp at each day's peak.

The 3D site needs plane counts, while parking/resource_requirements*.csv only report space units. This script re-runs
the parking model's own 10,000 demand paths (same seed, same functions, same order as parking/parking_optimizer.run)
and records, per situation, scenario and day, the median number of light / midsize / large aircraft parked at the
daily peak and the median arrivals and departures per size. It checks that it reproduces the published
parking_demand_su_p50 exactly before writing anything. The parking team's files are not modified.

Run from the repository root (needs numpy and pandas): python parking_kit/ramp_aircraft.py
Writes parking_kit/ramp_aircraft.csv.
"""
import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "parking"))
import parking_optimizer as po  # noqa: E402

OUT = Path(__file__).resolve().parent / "ramp_aircraft.csv"
VARIANTS = {"standard": "resource_requirements.csv",
            "departure_delay_24h": "resource_requirements_departure_delay_24h.csv",
            "security_restriction": "resource_requirements_security_restriction.csv",
            "heavy_rain": "resource_requirements_heavy_rain.csv"}


def peak_aircraft(arr, dep, a):
    """po.ramp_sim with unlimited capacity, keeping the aircraft count per size at each daily peak [run, day, size]."""
    occ = np.tile([a["initial_transient_aircraft"] * a[f"mix_{c}"] for c in po.CATS], (arr.shape[0], 1))
    peaks = np.zeros(arr.shape)
    for t in range(arr.shape[1]):
        early = np.minimum(dep[:, t] * a["dep_share_before_peak"], occ)
        peak = occ - early + arr[:, t]
        peaks[:, t] = peak
        occ = peak - np.minimum(dep[:, t] - early, peak)
    return peaks


def variant_rows(demand, a, variant):
    """Same draws and transformations as po.run(demand, a, variant)."""
    rng = np.random.default_rng(int(a["mc_seed"]))
    restriction = po.load_restriction() if variant == "security_restriction" else None
    rain = po.load_heavy_rain() if variant == "heavy_rain" else None
    su = np.array([a[f"su_{c}"] for c in po.CATS])
    rows = []
    for scenario, sdf in demand.groupby("scenario", sort=False):
        dates, mid, lo, hi = po.scenario_arrays(sdf)
        draws = po.sample_demand(mid, lo, hi, a, rng)
        arr, dep = draws[:, 0], draws[:, 1]
        profile, blocked = po.shift_profile(dates, a, restriction)
        if variant == "departure_delay_24h":
            dep, _ = po.shift_departures(dep, a)
        elif variant == "security_restriction":
            dep, _ = po.restrict_departures(dep, list(dates).index(restriction["date"]), blocked, a)
        elif variant == "heavy_rain":
            arr, dep, _ = po.heavy_rain_shift(arr, dep, int(a["heavy_rain_day"]), rain["effect"])
        peaks = peak_aircraft(arr, dep, a)
        for t, date in enumerate(dates):
            row = {"situation": variant, "scenario": scenario, "date": date,
                   "parking_demand_su_p50": round(float(np.percentile(peaks[:, t] @ su, 50)), 1),
                   "aircraft_at_peak_p50": round(float(np.median(peaks[:, t].sum(1))), 2)}
            for i, c in enumerate(po.CATS):
                row[f"{c}_at_peak_p50"] = round(float(np.median(peaks[:, t, i])), 2)
                row[f"{c}_arrivals_p50"] = round(float(np.median(arr[:, t, i])), 2)
                row[f"{c}_departures_p50"] = round(float(np.median(dep[:, t, i])), 2)
            rows.append(row)
    return rows


def main():
    a = po.load_assumptions()
    demand = po.load_demand()
    rows = []
    for variant, published in VARIANTS.items():
        got = variant_rows(demand, a, variant)
        with open(ROOT / "parking" / published, newline="") as f:
            ref = {(r["scenario"], r["date"]): float(r["parking_demand_su_p50"]) for r in csv.DictReader(f)}
        bad = [(r["scenario"], r["date"], r["parking_demand_su_p50"], ref[(r["scenario"], r["date"])])
               for r in got if abs(r["parking_demand_su_p50"] - ref[(r["scenario"], r["date"])]) > 1e-9]
        if bad:
            raise SystemExit(f"{variant}: does not reproduce {published}: {bad[:3]}")
        rows += got
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT} ({len(rows)} rows); parking_demand_su_p50 reproduced for all {len(VARIANTS)} situations")


if __name__ == "__main__":
    main()
