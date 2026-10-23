"""Per-draw departures, unconstrained parking demand, and resource loads."""

import numpy as np
import pandas as pd

from model import _require_assumptions


_CLASSES = ("light", "mid", "large")
_COLUMNS = (
    "timestamp", "scenario", "occupancy_up_p10", "occupancy_up_p50",
    "occupancy_up_p90", "occupancy_unserved_up_p50",
    "occupancy_unserved_up_p90", "capacity_up", "movements_p90",
    "staff_needed", "fuel_gal_p50", "fuel_gal_p90",
)


def _simulate_departures(forecast_df: pd.DataFrame, cfg: dict) -> np.ndarray:
    """Schedule departures without ever taking an aircraft before its arrival."""
    arrivals = forecast_df.attrs["sims"]
    runs, count, classes = arrivals.shape
    if classes != len(_CLASSES):
        raise ValueError("arrival draws must have light, mid, and large classes")
    timestamps = pd.DatetimeIndex(pd.to_datetime(forecast_df["timestamp"]))
    if timestamps.has_duplicates or not timestamps.is_monotonic_increasing:
        raise ValueError("forecast hours must be unique and sorted")
    departures = np.zeros_like(arrivals)
    rng = np.random.default_rng(forecast_df.attrs.get("seed", cfg["uncertainty"]["generator_seed"]))
    variation = cfg["uncertainty"]["length_of_stay_variation_points"]
    scenario = forecast_df["scenario"].iloc[0]
    ordinary = scenario == "baseline"
    day_hours = len(cfg["arrival_hourly_profile"])
    wave_start = pd.Timestamp(cfg["departure_wave"]["start"])
    wave_profile = np.asarray(cfg["departure_wave"]["hourly_profile"], dtype=float)
    if not np.isclose(wave_profile.sum(), 1):
        raise ValueError("departure_wave hourly_profile must sum to one")
    wave_index = int(timestamps.searchsorted(wave_start))
    wave_pool = np.zeros((runs, classes), dtype=np.int32)
    for hour, stamp in enumerate(timestamps):
        cohort = arrivals[:, hour, :]
        if ordinary:
            distribution = cfg["ordinary_length_of_stay"]
            lag = cfg["ordinary_same_day_departure_lag_hours"]
        else:
            weekday = stamp.day_name().lower()
            if weekday in ("tuesday", "wednesday"):
                group = "tuesday_wednesday"
            elif weekday in ("thursday", "friday", "saturday"):
                group = "thursday_saturday"
            else:
                group = weekday
            distribution = cfg["event_length_of_stay"][group]
            lag = cfg["event_same_day_departure_lag_hours"]

        same_p = np.clip(distribution["same_day"] + rng.uniform(-variation, variation, size=(runs, 1)), 0, 1)
        long_p = np.clip(distribution["three_plus_days"] + rng.uniform(-variation, variation, size=(runs, 1)), 0, 1 - same_p)
        same = rng.binomial(cohort, same_p)
        remaining = cohort - same
        long = rng.binomial(remaining, np.divide(long_p, 1 - same_p,
                                                out=np.zeros_like(long_p), where=(1 - same_p) > 0))
        middle = remaining - long

        same_hour = min(hour + lag, (hour // day_hours + 1) * day_hours - 1, count - 1)
        departures[:, same_hour, :] += same
        if ordinary:
            middle_hour = hour + distribution["one_night_departure_day_offset"] * day_hours
        else:
            middle_hour = None
            wave_pool += middle
        long_offset = cfg["ordinary_length_of_stay"]["three_plus_departure_day_offset"]
        long_hour = hour + long_offset * day_hours
        if middle_hour is not None and middle_hour < count:
            departures[:, middle_hour, :] += middle
        if long_hour < count:
            departures[:, long_hour, :] += long

        wave_position = hour - wave_index
        if not ordinary and 0 <= wave_position < len(wave_profile):
            remaining_weight = wave_profile[wave_position:].sum()
            probability = wave_profile[wave_position] / remaining_weight
            departing = rng.binomial(wave_pool, probability)
            departures[:, hour, :] += departing
            wave_pool -= departing
    return departures


def compute_occupancy(forecast_df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Aggregate per-draw parking demand and departures into the public contract.

    Occupancy is unconstrained demand. Units above ``capacity_up`` appear in
    ``occupancy_unserved_up_*`` and therefore require human redirection.
    """
    cfg = _require_assumptions(cfg)
    required = {"timestamp", "scenario"}
    missing = required - set(forecast_df.columns)
    if missing:
        raise ValueError(f"forecast_df is missing columns: {sorted(missing)}")
    sims = forecast_df.attrs.get("sims")
    if not isinstance(sims, np.ndarray) or sims.ndim != 3 or sims.shape[1] != len(forecast_df):
        raise ValueError("forecast_df.attrs['sims'] must be a runs × hours × classes array")
    if forecast_df["scenario"].nunique() != 1:
        raise ValueError("forecast_df must contain one scenario")

    departures = forecast_df.attrs.get("departure_sims")
    if not isinstance(departures, np.ndarray) or departures.shape != sims.shape:
        departures = _simulate_departures(forecast_df, cfg)
    parking = np.array([cfg["aircraft_classes"][name]["parking_up"] for name in _CLASSES])
    fuel_rate = np.array([cfg["aircraft_classes"][name]["fuel_gal_at_departure"] for name in _CLASSES])
    parked_classes = np.cumsum(sims - departures, axis=1)
    if np.any(parked_classes < 0):
        raise ValueError("departures exceed arrivals in a draw")
    demand_up = parked_classes @ parking
    movements = sims.sum(axis=2) + departures.sum(axis=2)
    fuel_gal = departures @ fuel_rate
    uncertainty = cfg["uncertainty"]
    levels = [uncertainty[f"percentile_{name}"] for name in ("low", "median", "high")]
    occupancy_levels = np.percentile(demand_up, levels, axis=0)
    capacity = cfg["resources"]["main_ramp_capacity_up"] + cfg["resources"]["ordinary_overflow_up"]
    unserved = np.maximum(demand_up - capacity, 0)
    output = pd.DataFrame({
        "timestamp": forecast_df["timestamp"].to_numpy(),
        "scenario": forecast_df["scenario"].to_numpy(),
        "occupancy_up_p10": occupancy_levels[0],
        "occupancy_up_p50": occupancy_levels[1],
        "occupancy_up_p90": occupancy_levels[2],
        "occupancy_unserved_up_p50": np.percentile(unserved, levels[1], axis=0),
        "occupancy_unserved_up_p90": np.percentile(unserved, levels[2], axis=0),
        "capacity_up": capacity,
        "movements_p90": np.percentile(movements, levels[2], axis=0),
        "fuel_gal_p50": np.percentile(fuel_gal, levels[1], axis=0),
        "fuel_gal_p90": np.percentile(fuel_gal, levels[2], axis=0),
    })
    output["staff_needed"] = np.minimum(
        np.ceil(output["movements_p90"] / cfg["resources"]["movements_per_ramp_agent_per_hour"]),
        cfg["resources"]["max_ramp_agents_per_shift"],
    ).astype(int)
    output = output.loc[:, list(_COLUMNS)]
    output.attrs["arrival_sims"] = sims
    output.attrs["departure_sims"] = departures
    output.attrs["demand_up_sims"] = demand_up
    return output
