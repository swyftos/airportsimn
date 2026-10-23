"""Plain-language briefing for the manager.

The LLM only rewrites numbers it is given (passed as JSON). Without an API key,
or on any API error, a deterministic template is used instead.
"""
from __future__ import annotations

import json
import os

import pandas as pd

BRIEFING_MODEL = os.environ.get("RAMPREADY_BRIEFING_MODEL", "claude-sonnet-5-5")

SYSTEM_PROMPT = (
    "You write a short operational briefing for an FBO operations manager. "
    "Use ONLY the numbers in the JSON you are given; never invent or extrapolate a figure. "
    "Always state uncertainty as a P10-P90 range. Never recommend accepting, refusing, "
    "moving or prioritizing a specific aircraft, and never mention people. "
    "The tool plans; the manager decides. Plain English, at most 180 words, no bullet lists."
)


def summarize(occ: pd.DataFrame, recs: list[dict], scenario: str) -> dict:
    """Compact, numbers-only facts handed to the LLM or the template."""
    peak = occ.loc[occ["occupancy_up_p50"].idxmax()]
    cap = float(occ["capacity_up"].iloc[0])
    over = occ[occ["occupancy_up_p90"] > occ["capacity_up"]]
    return {
        "scenario": scenario,
        "capacity_pu": cap,
        "peak_time": peak["timestamp"].strftime("%a %b %d %H:00"),
        "peak_occupancy_pu": {
            "p10": round(float(peak["occupancy_up_p10"]), 1),
            "p50": round(float(peak["occupancy_up_p50"]), 1),
            "p90": round(float(peak["occupancy_up_p90"]), 1),
        },
        "hours_p90_over_capacity": int(len(over)),
        "first_hour_p90_over_capacity": over["timestamp"].min().strftime("%a %b %d %H:00") if len(over) else None,
        "max_staff_needed": int(occ["staff_needed"].max()),
        "recommendations": [
            {k: r.get(k) for k in ("id", "category", "action", "status", "confidence")} for r in recs
        ],
    }


def template_briefing(facts: dict) -> str:
    p = facts["peak_occupancy_pu"]
    text = (
        f"Scenario {facts['scenario']}. Ramp occupancy peaks around {facts['peak_time']} at "
        f"{p['p50']} PU (likely range {p['p10']} to {p['p90']} PU) against {facts['capacity_pu']:.0f} PU of capacity. "
    )
    if facts["hours_p90_over_capacity"]:
        text += (
            f"In the pessimistic case (P90), demand exceeds capacity for {facts['hours_p90_over_capacity']} hours, "
            f"starting {facts['first_hour_p90_over_capacity']}. "
        )
    else:
        text += "Even in the pessimistic case (P90), demand stays within capacity. "
    text += f"Peak ramp staffing need is {facts['max_staff_needed']} agents per shift. "
    pending = [r for r in facts["recommendations"] if r["status"] == "PROPOSED"]
    decided = len(facts["recommendations"]) - len(pending)
    text += (
        f"{len(facts['recommendations'])} recommendations: {decided} decided, {len(pending)} awaiting your review. "
        "These are planning estimates only; every operational decision stays with you."
    )
    return text


def generate(facts: dict) -> tuple[str, str]:
    """Return (text, source) where source is 'llm' or 'template'."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return template_briefing(facts), "template"
    try:
        import anthropic

        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=BRIEFING_MODEL,
            max_tokens=600,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(facts)}],
        )
        return msg.content[0].text, "llm"
    except Exception:  # any API problem falls back, the app must never depend on the LLM
        return template_briefing(facts), "template"
