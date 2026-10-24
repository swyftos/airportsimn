"""Step 2 (Elia): LAWA monthly Traffic Comparison (TCOM) reports -> monthly FAA aircraft movements at LAX.

Source page: https://www.lawa.org/lawa-investor-relations/statistics-for-lax/volume-of-air-traffic (tab 1 = TCOM).
Each TCOM PDF gives the report month and the same month one year earlier, so every month appears in
two reports; both readings are kept and compared as a consistency check.

Output: processed/lawa_monthly_movements.csv
    year, month, air_carrier, air_taxi, general_aviation, military, total,
    report_file, report_url, column (current|prior_year), retrieved_utc
Raw PDFs are cached in raw/ so the run is repeatable offline.
"""
import csv
import datetime as dt
import re
import sys
import time
import urllib.request
from pathlib import Path

import pdfplumber

HERE = Path(__file__).parent
RAW, OUT = HERE / "raw", HERE / "processed"
BASE = "https://www.lawa.org"
PAGE = BASE + "/lawa-investor-relations/statistics-for-lax/volume-of-air-traffic"
UA = {"User-Agent": "Mozilla/5.0 (SpartHill Hacks research; contact elia108@proton.me)"}
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
FIELDS = {"Air Carrier": "air_carrier", "Air Taxi": "air_taxi", "General Aviation": "general_aviation",
          "Military": "military", "Total": "total"}


def get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def tcom_links() -> list[str]:
    html = get(PAGE).decode("utf-8", "replace")
    tab1 = html[html.find('id="tab1"'):html.find('id="tab2"')]
    return [BASE + h if h.startswith("/") else h
            for h in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*[A-Z][a-z]{2}\s*</a>', tab1)]


def parse(pdf_path: Path):
    """Return [(year, month, column, {field: value})] from the FAA movement block."""
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    # Header holds the YTD start pair (Jan-YYYY Jan-YYYY) then the report month pair; the last pair is the month
    pairs = re.findall(r"([A-Z][a-z]{2})-(\d{4})\s+([A-Z][a-z]{2})-(\d{4})", text.split("Passenger")[0])
    block = text[text.find("FAA Aircraft Movement"):] if "FAA Aircraft Movement" in text else ""
    if not pairs or not block:
        return []
    cur_m, cur_y, prior_m, prior_y = pairs[-1]
    cur = (int(cur_y), MONTHS[cur_m])
    prior = (int(prior_y), MONTHS[prior_m])
    vals = {"current": {}, "prior_year": {}}
    for label, key in FIELDS.items():
        m = re.search(rf"^{label}\s+([\d,]+)\s+([\d,]+)", block, re.M)
        if m:
            vals["current"][key] = int(m.group(1).replace(",", ""))
            vals["prior_year"][key] = int(m.group(2).replace(",", ""))
    return [(*cur, "current", vals["current"]), (*prior, "prior_year", vals["prior_year"])]


def main(min_year=2015):
    RAW.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    retrieved = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    rows, failed = [], []
    for url in tcom_links():
        name = re.sub(r"[^A-Za-z0-9]+", "_", url.split("lawa.org/")[-1]).strip("_") + ".pdf"
        path = RAW / name
        if not path.exists():
            path.write_bytes(get(url))
            time.sleep(0.3)
        try:
            parsed = parse(path)
        except Exception as e:  # corrupted or non-PDF download
            parsed, err = [], e
        if not parsed:
            failed.append(url)
            continue
        for year, month, col, v in parsed:
            rows.append({"year": year, "month": month, **{k: v.get(k) for k in FIELDS.values()},
                         "report_file": name, "report_url": url, "column": col, "retrieved_utc": retrieved})
        if min(p[0] for p in parsed) < min_year:
            break  # archive is newest first
    rows.sort(key=lambda r: (r["year"], r["month"], r["column"]))
    with open(OUT / "lawa_monthly_movements.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rows, {len(failed)} reports not parsed")
    for u in failed:
        print("  not parsed:", u)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2015)
