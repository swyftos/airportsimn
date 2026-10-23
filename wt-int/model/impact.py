"""Impact comparison and synthetic backtest contracts."""

from model import _require_assumptions


def compare_plans(scenario: str, cfg: dict) -> dict:
    """Return a placeholder comparison until both plans are implemented."""
    _require_assumptions(cfg)
    if scenario not in {"low", "medium", "high"}:
        raise ValueError(f"Unknown scenario: {scenario}")
    return {}


def backtest(cfg: dict) -> dict:
    """Return the frozen metric keys; values await the synthetic holdout."""
    _require_assumptions(cfg)
    return {
        "mape": float("nan"),
        "coverage_p10_p90": float("nan"),
        "peak_error_up": float("nan"),
    }
