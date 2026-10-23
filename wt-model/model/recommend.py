"""Human-reviewed preparation recommendation contract."""

import pandas as pd

from model import _require_assumptions


def recommend(occupancy_df: pd.DataFrame, cfg: dict) -> list[dict]:
    """Return proposed actions; T3 emits none before rules are implemented."""
    _require_assumptions(cfg)
    if not isinstance(occupancy_df, pd.DataFrame):
        raise TypeError("occupancy_df must be a pandas DataFrame")
    return []
