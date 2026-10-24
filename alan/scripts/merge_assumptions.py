"""Step 7 (Alan): merge the three team assumption ledgers into one
root-level assumptions.csv deliverable.

Sources, each with a different schema:
  alan/assumptions.csv            id,label,value,unit,classification,source,note
                                   (written by build_baseline.py on every run)
  alan/assumptions_research.csv   already in the output schema below; Alan's hand-maintained
                                   research rows (landing fee, hangar, TFR), copied as-is
  alan/data/processed/assumptions_nazar.csv
                                   assumption_id,parameter,value,unit,classification,
                                   confidence,source_ids,status,notes
  elia/assumptions_p3.csv         parameter,value,unit,classification,source_or_rationale

Output: assumptions.csv (repo root), common schema:
  id,owner,label,value,unit,classification,confidence,source,status,note

classification is normalized to the dashboard's four-way vocabulary
(public, synthetic, assumption, benchmark) per nazar/INTEGRATION.md:
  "benchmark estimate" -> benchmark
  "estimate"           -> assumption  (team-derived, not independently benchmarked)
  everything else unchanged

IDs are prefixed by owner (ALAN-, NAZAR-, ELIA-) to avoid collisions.
Elia's source file has no id column; ids are generated from the parameter
name. Confidence/status columns are left blank where a source doesn't
provide them, not fabricated.

IMPORTANT -- hand-written rows are preserved, not wiped: this script
only knows how to regenerate the specific ids that come out of
load_alan()/load_nazar()/load_elia() -- exactly what's currently in
alan/assumptions.csv, alan/data/processed/assumptions_nazar.csv, and
elia/assumptions_p3.csv. Anything else in the existing root
assumptions.csv -- Marvin's hand-maintained rows (no per-owner source
file exists for them), or any row someone added directly to the root
ledger under an ALAN-/NAZAR-/ELIA- id without also adding it to that
owner's source file -- is preserved by id, not wiped on rewrite. This
matters because nazar/scripts/release_team.py runs this script as a
release step; a plain "regenerate from the three source files" rewrite
silently deletes every hand-written row on every release.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = ROOT / "assumptions.csv"

CLASS_MAP = {
    "benchmark estimate": "benchmark",
    "estimate": "assumption",
}


def norm_class(c):
    c = (c or "").strip()
    return CLASS_MAP.get(c, c)


def load_alan():
    rows = []
    with open(ROOT / "alan" / "assumptions.csv", newline="") as f:
        for r in csv.DictReader(f):
            rows.append({
                "id": "ALAN-" + r["id"],
                "owner": "Alan",
                "label": r["label"],
                "value": r["value"],
                "unit": r["unit"],
                "classification": norm_class(r["classification"]),
                "confidence": "",
                "source": r["source"],
                "status": "",
                "note": r["note"],
            })
    return rows


def load_nazar():
    rows = []
    with open(ROOT / "alan" / "data" / "processed" / "assumptions_nazar.csv", newline="") as f:
        for r in csv.DictReader(f):
            rows.append({
                "id": r["assumption_id"],  # already NAZAR-prefixed
                "owner": "Nazar",
                "label": r["parameter"],
                "value": r["value"],
                "unit": r["unit"],
                "classification": norm_class(r["classification"]),
                "confidence": r["confidence"],
                "source": r["source_ids"],
                "status": r["status"],
                "note": r["notes"],
            })
    return rows


def load_elia():
    rows = []
    with open(ROOT / "elia" / "assumptions_p3.csv", newline="") as f:
        for r in csv.DictReader(f):
            rows.append({
                "id": "ELIA-" + r["parameter"],
                "owner": "Elia",
                "label": r["parameter"],
                "value": r["value"],
                "unit": r["unit"],
                "classification": norm_class(r["classification"]),
                "confidence": "",
                "source": r["source_or_rationale"],
                "status": "",
                "note": "",
            })
    return rows


CARRIED_FIELDS = ("confidence", "status", "note")


def load_alan_research():
    """Alan's research rows, kept in their own hand-maintained file because build_baseline.py
    rewrites alan/assumptions.csv; they are regenerated like any other source, so they no
    longer trip the stale-row warning."""
    with open(ROOT / "alan" / "assumptions_research.csv", newline="") as f:
        return list(csv.DictReader(f))


def load_existing():
    """The ledger this script is about to overwrite, keyed by id. Used
    both to preserve rows this script can't regenerate, and to carry
    forward hand-written confidence/status/note values on rows it does
    regenerate but whose owner source file has no column for them.
    """
    if not OUT_PATH.exists():
        return {}
    with open(OUT_PATH, newline="") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def fill_from_existing(row, existing):
    """A row's owner source file (e.g. alan/assumptions.csv, 7 columns,
    no confidence/status) has no way to express some fields, so
    load_alan()/load_elia() always emit them blank. If this id already
    had a hand-written value for one of those fields, keep it instead of
    overwriting it with blank -- the owner source file not having the
    column is not evidence the value should be erased.
    """
    prior = existing.get(row["id"])
    if not prior:
        return row
    for field in CARRIED_FIELDS:
        if not row.get(field) and prior.get(field):
            row[field] = prior[field]
    return row


def main():
    existing = load_existing()
    regenerated = [fill_from_existing(r, existing)
                   for r in load_alan() + load_alan_research() + load_nazar() + load_elia()]
    regenerated_ids = {r["id"] for r in regenerated}
    preserved = [r for id_, r in existing.items() if id_ not in regenerated_ids]
    rows = preserved + regenerated
    fields = ["id", "owner", "label", "value", "unit", "classification", "confidence", "source", "status", "note"]
    with open(OUT_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUT_PATH} ({len(preserved)} preserved, not regenerated)")
    by_owner = {}
    for r in rows:
        by_owner[r["owner"]] = by_owner.get(r["owner"], 0) + 1
    for owner, n in by_owner.items():
        print(f"  {owner}: {n}")
    stale = sorted(r["id"] for r in preserved if r["id"].startswith(("ALAN-", "NAZAR-", "ELIA-")))
    if stale:
        print(f"WARNING: {len(stale)} preserved row(s) look owner-prefixed but weren't regenerated "
              f"-- confirm these weren't just removed from their owner's source file: {stale}")


if __name__ == "__main__":
    main()
