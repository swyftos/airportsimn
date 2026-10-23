"""Parking occupancy output contract for the future simulation model."""

import numpy as np
import pandas as pd

from model import _require_assumptions


_COLUMNS = (
    "timestamp", "scenario", "occupancy_up_p10", "occupancy_up_p50",
    "occupancy_up_p90", "occupancy_unserved_up_p50",
    "occupancy_unserved_up_p90", "capacity_up", "movements_p90",
    "staff_needed", "fuel_gal_p50", "fuel_gal_p90",
)


def compute_occupancy(forecast_df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Return the occupancy schema for every forecast hour.

    T3 leaves occupancy and resource estimates unset until the data team's
    assumption keys and the departure simulation are integrated. The class
    draw array is validated so later percentiles can be taken per draw (D2).
    Unserved demand columns are included now (D4).
    """
    _require_assumptions(cfg)
    required = {"timestamp", "scenario"}
    missing = required - set(forecast_df.columns)
    if missing:
        raise ValueError(f"forecast_df is missing columns: {sorted(missing)}")
    sims = forecast_df.attrs.get("sims")
    if sims is None or not isinstance(sims, np.ndarray) or sims.ndim != 3:
        raise ValueError("forecast_df.attrs['sims'] must be a runs × hours × classes array")
    if sims.shape[1] != len(forecast_df):
        raise ValueError("forecast draws and forecast rows have different hour counts")

    output = forecast_df[["timestamp", "scenario"]].copy().reset_index(drop=True)
    for column in _COLUMNS[2:]:
        output[column] = pd.Series(np.full(len(output), np.nan), dtype=float)
    output["staff_needed"] = pd.Series(pd.array([pd.NA] * len(output), dtype="Int64"))
    return output.loc[:, list(_COLUMNS)]
