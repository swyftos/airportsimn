"""Single entry point between the app and the model layer.

Every model call goes through here so the app keeps rendering (with a clear
message) while other modules are still skeletons.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONFIG_PATH = ROOT / "config" / "assumptions.yaml"
EVENT_CSV = ROOT / "data" / "event_hourly.csv"
SCENARIOS = ["low", "medium", "high"]


class ModelUnavailable(RuntimeError):
    """Raised when a model function is missing or not implemented yet."""


def ensure_data() -> None:
    """Build the synthetic datasets on first run (clean machine)."""
    if not EVENT_CSV.exists() and (ROOT / "data" / "generate.py").exists():
        subprocess.run([sys.executable, str(ROOT / "data" / "generate.py")], cwd=ROOT, check=True)


def load_cfg() -> dict:
    if not CONFIG_PATH.exists():
        raise ModelUnavailable("config/assumptions.yaml is missing (data role).")
    with CONFIG_PATH.open() as fh:
        return yaml.safe_load(fh)


def _call(module: str, fn: str, *args, **kwargs):
    try:
        mod = __import__(f"model.{module}", fromlist=[fn])
        return getattr(mod, fn)(*args, **kwargs)
    except (ImportError, AttributeError, NotImplementedError, FileNotFoundError) as exc:
        raise ModelUnavailable(f"model.{module}.{fn}: {exc}") from exc


def forecast(scenario: str, cfg: dict, n_sims: int = 1000) -> pd.DataFrame:
    return _call("forecast", "forecast", scenario, cfg, n_sims=n_sims)


def occupancy(forecast_df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    df = _call("occupancy", "compute_occupancy", forecast_df, cfg)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def recommendations(occupancy_df: pd.DataFrame, cfg: dict) -> list[dict]:
    return _call("recommend", "recommend", occupancy_df, cfg)


def compare_plans(scenario: str, cfg: dict) -> dict:
    return _call("impact", "compare_plans", scenario, cfg)


def backtest(cfg: dict) -> dict:
    return _call("impact", "backtest", cfg)


def disrupt(forecast_df: pd.DataFrame, kind: str, cfg: dict) -> pd.DataFrame:
    return _call("disruption", "apply_disruption", forecast_df, kind, cfg)
