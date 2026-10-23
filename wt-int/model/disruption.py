"""Scenario disruption contract."""

import pandas as pd

from model import _require_assumptions


def apply_disruption(forecast_df: pd.DataFrame, kind: str, cfg: dict) -> pd.DataFrame:
    """Return a copy of hourly rows until disruption shifts are implemented."""
    _require_assumptions(cfg)
    if kind not in {"fog", "extended_stay", "airspace"}:
        raise ValueError(f"Unknown disruption: {kind}")
    if not isinstance(forecast_df, pd.DataFrame):
        raise TypeError("forecast_df must be a pandas DataFrame")
    return forecast_df.copy(deep=True)
