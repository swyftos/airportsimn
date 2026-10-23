"""RampReady planning model.

The public functions live in the five modules named in AGENTS.md. This
package also validates that the shared assumptions file is available.
"""

from pathlib import Path

import yaml


_ASSUMPTIONS_PATH = Path(__file__).resolve().parents[1] / "config" / "assumptions.yaml"


def _require_assumptions(cfg: dict) -> dict:
    """Read the shared YAML and apply caller overrides, or fail clearly."""
    if not _ASSUMPTIONS_PATH.is_file():
        raise FileNotFoundError(
            f"RampReady assumptions are missing: {_ASSUMPTIONS_PATH}. "
            "Ask the data agent to create config/assumptions.yaml."
        )
    with _ASSUMPTIONS_PATH.open(encoding="utf-8") as source:
        assumptions = yaml.safe_load(source)
    if not isinstance(assumptions, dict):
        raise ValueError("config/assumptions.yaml must contain a YAML mapping")
    if not isinstance(cfg, dict):
        raise TypeError("cfg must be a dictionary of assumption overrides")
    return {**assumptions, **cfg}
