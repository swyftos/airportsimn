"""Generate reproducible, synthetic hourly CSV stubs for the frozen data contract."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta
from pathlib import Path
import random

import yaml


ROOT = Path(__file__).resolve().parents[1]
CFG_PATH = ROOT / "config" / "assumptions.yaml"
DATA_DIR = ROOT / "data"
CSV_COLUMNS = (
    "timestamp",
    "scenario",
    "arrivals_p10",
    "arrivals_p50",
    "arrivals_p90",
    "departures_p50",
    "arrivals_light",
    "arrivals_mid",
    "arrivals_large",
)


def _event_stay_group(day_name: str) -> str:
    if day_name in ("tuesday", "wednesday"):
        return "tuesday_wednesday"
    if day_name in ("thursday", "friday", "saturday"):
        return "thursday_saturday"
    return day_name


def _arrival_series(cfg: dict, rng: random.Random) -> tuple[dict, dict]:
    """Create ordinary hourly arrivals and normalized day profiles."""
    start = datetime.fromisoformat(cfg["calendar"]["start_date"])
    end = datetime.fromisoformat(cfg["calendar"]["end_date"])
    ordinary = {}
    profiles = {}
    sigma = cfg["uncertainty"]["stub_hourly_jitter_sigma"]
    earliest = start - timedelta(days=cfg["ordinary_length_of_stay"]["three_plus_departure_day_offset"])
    day = earliest
    while day <= end:
        raw = [max(0.0, weight * rng.gauss(1.0, sigma)) for weight in cfg["arrival_hourly_profile"]]
        total = sum(raw)
        weights = [weight / total for weight in raw]
        profiles[day.date()] = weights
        daily = cfg["baseline_daily_arrivals"][day.strftime("%A").lower()]
        for hour, weight in enumerate(weights):
            ordinary[day + timedelta(hours=hour)] = daily * weight
        day += timedelta(days=1)
    return ordinary, profiles


def _ordinary_departures(hour: datetime, arrivals: dict, cfg: dict) -> float:
    stay = cfg["ordinary_length_of_stay"]
    same_day = arrivals.get(hour - timedelta(hours=cfg["ordinary_same_day_departure_lag_hours"]), 0.0)
    one_night = arrivals.get(hour - timedelta(days=stay["one_night_departure_day_offset"]), 0.0)
    long_stay = arrivals.get(hour - timedelta(days=stay["three_plus_departure_day_offset"]), 0.0)
    return (
        stay["same_day"] * same_day
        + stay["one_night"] * one_night
        + stay["three_plus_days"] * long_stay
    )


def _scenario_rows(cfg: dict, scenario: str, ordinary: dict, profiles: dict) -> list[dict]:
    start = datetime.fromisoformat(cfg["calendar"]["start_date"])
    end = datetime.fromisoformat(cfg["calendar"]["end_date"])
    hours = [start + timedelta(hours=index) for index in range((end - start).days * len(cfg["arrival_hourly_profile"]) + len(cfg["arrival_hourly_profile"]))]
    extras = {}
    if scenario == "baseline":
        mix = cfg["ordinary_aircraft_mix"]
    else:
        settings = cfg["scenarios"][scenario]
        mix = {
            "light": cfg["event_aircraft_mix_light_plus_large_share"] - settings["large_jet_share"],
            "mid": cfg["event_aircraft_mix_mid_share"],
            "large": settings["large_jet_share"],
        }
        for hour in hours:
            day_name = hour.strftime("%A").lower()
            day_extra = (
                settings["regional_extra_peak_aircraft_per_day"]
                * cfg["extra_demand_day_shape"][day_name]
                * settings["fbo_market_share"]
            )
            extras[hour] = day_extra * profiles[hour.date()][hour.hour]

    wave_start = datetime.fromisoformat(cfg["departure_wave"]["start"])
    wave_weights = cfg["departure_wave"]["hourly_profile"]
    wave = {wave_start + timedelta(hours=index): weight for index, weight in enumerate(wave_weights)}
    sunday = "sunday"
    sunday_wave_weight = sum(weight for hour, weight in wave.items() if hour.date() > wave_start.date())
    early_wave_total = sum(
        value * cfg["event_length_of_stay"][_event_stay_group(hour.strftime("%A").lower())]["departure_wave"]
        for hour, value in extras.items()
        if hour.date() < wave_start.date()
    )
    sunday_wave_total = sum(value for hour, value in extras.items() if hour.strftime("%A").lower() == sunday)
    sunday_wave_total *= cfg["event_length_of_stay"][sunday]["departure_wave"]

    rows = []
    spread = cfg["uncertainty"]
    base_mix = cfg["ordinary_aircraft_mix"]
    for hour in hours:
        baseline_arrivals = ordinary[hour]
        extra_arrivals = extras.get(hour, 0.0)
        arrivals = baseline_arrivals + extra_arrivals
        extra_same_day = 0.0
        if extras:
            earlier = hour - timedelta(hours=cfg["event_same_day_departure_lag_hours"])
            day_name = earlier.strftime("%A").lower()
            if earlier in extras:
                stay = cfg["event_length_of_stay"][_event_stay_group(day_name)]
                extra_same_day = extras[earlier] * stay["same_day"]
        wave_departures = early_wave_total * wave.get(hour, 0.0)
        if hour.date() > wave_start.date() and sunday_wave_weight:
            wave_departures += sunday_wave_total * wave.get(hour, 0.0) / sunday_wave_weight
        departures = _ordinary_departures(hour, ordinary, cfg) + extra_same_day + wave_departures
        rows.append(
            {
                "timestamp": hour.strftime("%Y-%m-%dT%H:00"),
                "scenario": scenario,
                "arrivals_p10": baseline_arrivals * spread["stub_arrivals_p10_fraction"]
                + extra_arrivals * spread["stub_arrivals_p10_fraction"],
                "arrivals_p50": arrivals,
                "arrivals_p90": baseline_arrivals * spread["stub_arrivals_p90_fraction"]
                + extra_arrivals * spread["stub_arrivals_p90_fraction"],
                "departures_p50": departures,
                "arrivals_light": baseline_arrivals * base_mix["light"] + extra_arrivals * mix["light"],
                "arrivals_mid": baseline_arrivals * base_mix["mid"] + extra_arrivals * mix["mid"],
                "arrivals_large": baseline_arrivals * base_mix["large"] + extra_arrivals * mix["large"],
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    with CFG_PATH.open(encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=cfg["uncertainty"]["generator_seed"])
    args = parser.parse_args()
    ordinary, profiles = _arrival_series(cfg, random.Random(args.seed))
    _write_csv(DATA_DIR / "baseline_week.csv", _scenario_rows(cfg, "baseline", ordinary, profiles))
    event_rows = []
    for scenario in cfg["scenarios"]:
        event_rows.extend(_scenario_rows(cfg, scenario, ordinary, profiles))
    _write_csv(DATA_DIR / "event_hourly.csv", event_rows)


if __name__ == "__main__":
    main()
