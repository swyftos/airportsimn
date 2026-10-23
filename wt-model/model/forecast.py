"""Seeded hourly arrival Monte Carlo for the planning week."""

import numpy as np
import pandas as pd

from model import _require_assumptions


_CLASSES = ("light", "mid", "large")


def forecast(scenario: str, cfg: dict, n_sims: int = 1000, seed: int = 42) -> pd.DataFrame:
    """Return hourly percentiles and integer arrival draws (runs × hours × class)."""
    cfg = _require_assumptions(cfg)
    if scenario != "baseline" and scenario not in cfg["scenarios"]:
        raise ValueError(f"Unknown scenario: {scenario}")
    if n_sims <= 0:
        raise ValueError("n_sims must be positive")

    uncertainty = cfg["uncertainty"]
    calendar = cfg["calendar"]
    profile = np.asarray(cfg["arrival_hourly_profile"], dtype=float)
    end = pd.Timestamp(calendar["end_date"]) + pd.Timedelta(hours=len(profile) - 1)
    hours = pd.date_range(calendar["start_date"], end=end, freq="h")
    weekdays = hours.day_name().str.lower()
    baseline = np.array([cfg["baseline_daily_arrivals"][day] for day in weekdays], dtype=float)
    if len(profile) != hours.hour.max() + 1 or not np.isclose(profile.sum(), 1):
        raise ValueError("arrival_hourly_profile must cover every hour and sum to one")
    expected = baseline * profile[hours.hour]
    if scenario == "baseline":
        mix = np.array([cfg["ordinary_aircraft_mix"][name] for name in _CLASSES])
    else:
        settings = cfg["scenarios"][scenario]
        extra = np.array([cfg["extra_demand_day_shape"][day] for day in weekdays])
        expected += (settings["regional_extra_peak_aircraft_per_day"]
                     * settings["fbo_market_share"] * extra * profile[hours.hour])
        mix = np.array([
            cfg["event_aircraft_mix_light_plus_large_share"] - settings["large_jet_share"],
            cfg["event_aircraft_mix_mid_share"], settings["large_jet_share"],
        ])
    if not np.isclose(mix.sum(), 1) or np.any(mix < 0):
        raise ValueError("aircraft mix must be nonnegative and sum to one")

    rng = np.random.default_rng(seed)
    sigma = uncertainty["multiplier_lognormal_sigma"]
    day_index = pd.factorize(hours.normalize())[0]
    day_count = len(np.unique(day_index))
    multiplier = rng.lognormal(-sigma * sigma / 2, sigma, size=(n_sims, day_count))
    totals = rng.poisson(expected[None, :] * multiplier[:, day_index])

    variation = uncertainty["aircraft_mix_variation_points"]
    mid = np.clip(mix[1] + rng.uniform(-variation, variation, size=(n_sims, 1)), 0, 1)
    large = np.clip(mix[2] + rng.uniform(-variation, variation, size=(n_sims, 1)), 0, 1 - mid)
    light = 1 - mid - large
    probabilities = np.concatenate((light, mid, large), axis=1)
    sims = np.empty((n_sims, len(hours), len(_CLASSES)), dtype=np.int32)
    for run in range(n_sims):
        remaining = totals[run].copy()
        sims[run, :, 0] = rng.binomial(remaining, probabilities[run, 0])
        remaining -= sims[run, :, 0]
        conditional_mid = probabilities[run, 1] / (probabilities[run, 1] + probabilities[run, 2])
        sims[run, :, 1] = rng.binomial(remaining, conditional_mid)
        sims[run, :, 2] = remaining - sims[run, :, 1]

    levels = [uncertainty[f"percentile_{name}"] for name in ("low", "median", "high")]
    quantiles = np.percentile(sims.sum(axis=2), levels, axis=0)
    med_classes = quantiles[1, :, None] * mix[None, :]
    frame = pd.DataFrame({
        "timestamp": hours.strftime("%Y-%m-%dT%H:00"),
        "scenario": scenario,
        "arrivals_p10": quantiles[0],
        "arrivals_p50": quantiles[1],
        "arrivals_p90": quantiles[2],
        "departures_p50": np.zeros(len(hours)),
        **{f"arrivals_{name}": med_classes[:, index] for index, name in enumerate(_CLASSES)},
    })
    frame.attrs["sims"] = sims
    frame.attrs["seed"] = seed
    from model.occupancy import _simulate_departures

    departures = _simulate_departures(frame, cfg)
    frame.attrs["departure_sims"] = departures
    frame["departures_p50"] = np.percentile(
        departures.sum(axis=2), uncertainty["percentile_median"], axis=0
    )
    return frame
