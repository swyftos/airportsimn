"""Step 7 (Alan): merge the three team assumption ledgers into one
root-level assumptions.csv deliverable.

Sources, each with a different schema:
  alan/assumptions.csv            id,label,value,unit,classification,source,note
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


def main():
    rows = load_alan() + load_nazar() + load_elia()
    fields = ["id", "owner", "label", "value", "unit", "classification", "confidence", "source", "status", "note"]
    with open(OUT_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUT_PATH}")
    by_owner = {}
    for r in rows:
        by_owner[r["owner"]] = by_owner.get(r["owner"], 0) + 1
    for owner, n in by_owner.items():
        print(f"  {owner}: {n}")


if __name__ == "__main__":
    main()
