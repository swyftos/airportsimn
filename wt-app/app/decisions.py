"""Human approval gate: every decision on a recommendation is appended to a CSV log."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

LOG_PATH = Path(__file__).resolve().parent / "state" / "decision_log.csv"
STATUSES = ["APPROVED", "MODIFIED", "REJECTED"]
COLUMNS = ["logged_at", "rec_id", "scenario", "category", "action", "status", "human_note"]


def load_log() -> pd.DataFrame:
    if LOG_PATH.exists():
        return pd.read_csv(LOG_PATH, dtype=str).fillna("")
    return pd.DataFrame(columns=COLUMNS)


def record(rec: dict, status: str, note: str) -> None:
    if status not in STATUSES:
        raise ValueError(status)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "logged_at": datetime.now().isoformat(timespec="seconds"),
        "rec_id": rec["id"],
        "scenario": rec.get("scenario", ""),
        "category": rec.get("category", ""),
        "action": rec.get("action", ""),
        "status": status,
        "human_note": note,
    }
    log = pd.concat([load_log(), pd.DataFrame([row])], ignore_index=True)
    log.to_csv(LOG_PATH, index=False)


def apply_statuses(recs: list[dict], scenario: str) -> list[dict]:
    """Overlay the latest logged decision on each recommendation (default PROPOSED)."""
    log = load_log()
    log = log[log["scenario"] == scenario]
    latest = log.groupby("rec_id").tail(1).set_index("rec_id") if len(log) else None
    out = []
    for rec in recs:
        rec = {**rec, "status": rec.get("status") or "PROPOSED", "human_note": rec.get("human_note", "")}
        if latest is not None and rec["id"] in latest.index:
            rec["status"] = latest.loc[rec["id"], "status"]
            rec["human_note"] = latest.loc[rec["id"], "human_note"]
        out.append(rec)
    return out
