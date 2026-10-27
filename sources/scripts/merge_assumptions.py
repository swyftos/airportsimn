"""Step 7 (the data team): merge the three team assumption ledgers into one
root-level assumptions.csv deliverable.

Sources, each with a different schema:
  sources/assumptions.csv            id,label,value,unit,classification,source,note
                                   (written by build_baseline.py on every run)
  sources/assumptions_research.csv   already in the output schema below; the data team's hand-maintained
                                   research rows (landing fee, hangar, TFR), copied as-is
  sources/data/processed/assumptions_apron.csv
                                   assumption_id,parameter,value,unit,classification,
                                   confidence,source_ids,status,notes
  parking/assumptions_p3.csv         parameter,value,unit,classification,source_or_rationale

Output: assumptions.csv (repo root), common schema:
  id,owner,label,value,unit,classification,confidence,source,status,note

classification is normalized to the dashboard's four-way vocabulary
(public, synthetic, assumption, benchmark) per dashboard/INTEGRATION.md:
  "benchmark estimate" -> benchmark
  "estimate"           -> assumption  (team-derived, not independently benchmarked)
  everything else unchanged

IDs are prefixed by owner (DATA-, DASH-, PARK-) to avoid collisions.
The parking team's source file has no id column; ids are generated from the parameter
name. Confidence/status columns are left blank where a source doesn't
provide them, not fabricated.

IMPORTANT -- hand-written rows are preserved, not wiped: this script
only knows how to regenerate the specific ids that come out of
load_sources()/load_dashboard()/load_parking() -- exactly what's currently in
sources/assumptions.csv, sources/data/processed/assumptions_apron.csv, and
parking/assumptions_p3.csv. Anything else in the existing root
assumptions.csv -- the forecast team's hand-maintained rows (no per-owner source
file exists for them), or any row someone added directly to the root
ledger under an DATA-/DASH-/PARK- id without also adding it to that
owner's source file -- is preserved by id, not wiped on rewrite. This
matters because dashboard/scripts/release_team.py runs this script as a
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


def load_sources():
    rows = []
    with open(ROOT / "sources" / "assumptions.csv", newline="") as f:
        for r in csv.DictReader(f):
            rows.append({
                "id": "DATA-" + r["id"],
                "owner": "data",
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


def load_dashboard():
    rows = []
    with open(ROOT / "sources" / "data" / "processed" / "assumptions_apron.csv", newline="") as f:
        for r in csv.DictReader(f):
            rows.append({
                "id": r["assumption_id"],  # already DASH-prefixed
                "owner": "dashboard",
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


def load_parking():
    rows = []
    with open(ROOT / "parking" / "assumptions_p3.csv", newline="") as f:
        for r in csv.DictReader(f):
            rows.append({
                "id": "PARK-" + r["parameter"],
                "owner": "parking",
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


def load_sources_research():
    """data's research rows, kept in their own hand-maintained file because build_baseline.py
    rewrites sources/assumptions.csv; they are regenerated like any other source, so they no
    longer trip the stale-row warning."""
    with open(ROOT / "sources" / "assumptions_research.csv", newline="") as f:
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
    """A row's owner source file (e.g. sources/assumptions.csv, 7 columns,
    no confidence/status) has no way to express some fields, so
    load_sources()/load_parking() always emit them blank. If this id already
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
                   for r in load_sources() + load_sources_research() + load_dashboard() + load_parking()]
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
    stale = sorted(r["id"] for r in preserved if r["id"].startswith(("DATA-", "DASH-", "PARK-")))
    if stale:
        print(f"WARNING: {len(stale)} preserved row(s) look owner-prefixed but weren't regenerated "
              f"-- confirm these weren't just removed from their owner's source file: {stale}")


if __name__ == "__main__":
    main()
