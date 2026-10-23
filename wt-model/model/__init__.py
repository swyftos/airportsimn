"""RampReady planning model.

The public functions live in the five modules named in AGENTS.md. This
package also validates that the shared assumptions file is available.
"""

from pathlib import Path

import yaml


_ASSUMPTIONS_PATH = Path(__file__).resolve().parents[1] / "config" / "assumptions.yaml"


def _require_assumptions(cfg: dict) -> dict:
    """Read shared assumptions and apply caller overrides recursively."""
    if not isinstance(cfg, dict):
        raise TypeError("cfg must be a dictionary of assumption overrides")
    if not _ASSUMPTIONS_PATH.is_file() and not cfg:
        raise FileNotFoundError(
            f"RampReady assumptions are missing: {_ASSUMPTIONS_PATH}. "
            "Ask the data agent to create config/assumptions.yaml."
        )
    if _ASSUMPTIONS_PATH.is_file():
        with _ASSUMPTIONS_PATH.open(encoding="utf-8") as source:
            assumptions = yaml.safe_load(source)
    else:
        assumptions = {}
    if not isinstance(assumptions, dict):
        raise ValueError("config/assumptions.yaml must contain a YAML mapping")
    def merge(base: dict, changes: dict) -> dict:
        result = base.copy()
        for key, value in changes.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = merge(result[key], value)
            else:
                result[key] = value
        return result

    return merge(assumptions, cfg)
