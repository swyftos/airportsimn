"""Hourly arrival forecast contract for the future simulation model."""

from pathlib import Path

import numpy as np
import pandas as pd

from model import _require_assumptions


_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_CLASSES = ("light", "mid", "large")
_COLUMNS = (
    "timestamp", "scenario", "arrivals_p10", "arrivals_p50", "arrivals_p90",
    "departures_p50", "arrivals_light", "arrivals_mid", "arrivals_large",
)


def forecast(scenario: str, cfg: dict, n_sims: int = 1000, seed: int = 42) -> pd.DataFrame:
    """Return contract-shaped hourly rows and attach class draws in ``attrs``.

    This T3 skeleton reads the data agent's stub CSV when available. Its draws
    repeat the CSV's P50 class values; stochastic forecasting comes later.
    """
    _require_assumptions(cfg)
    if scenario not in {"baseline", "low", "medium", "high"}:
        raise ValueError(f"Unknown scenario: {scenario}")
    if n_sims <= 0:
        raise ValueError("n_sims must be positive")

    csv_name = "baseline_week.csv" if scenario == "baseline" else "event_hourly.csv"
    source = _DATA_DIR / csv_name
    if source.is_file():
        frame = pd.read_csv(source)
        missing = set(_COLUMNS) - set(frame.columns)
        if missing:
            raise ValueError(f"{source} is missing forecast columns: {sorted(missing)}")
        frame = frame.loc[frame["scenario"] == scenario, list(_COLUMNS)].reset_index(drop=True)
    else:
        frame = pd.DataFrame({
            column: pd.Series(dtype="str" if column in {"timestamp", "scenario"} else "float64")
            for column in _COLUMNS
        })

    class_columns = [f"arrivals_{name}" for name in _CLASSES]
    class_values = frame[class_columns].to_numpy(dtype=float)
    frame.attrs["sims"] = np.broadcast_to(
        class_values, (n_sims, len(frame), len(_CLASSES))
    ).copy()
    return frame
