"""Fetch aggregate FAA OPSNET checks without changing the shared forecast inputs.

Run from the repository root: python marvin/person_2_forecasting/calibration_evidence/fetch_public_counts.py
FAA source: https://www.aspm.faa.gov/opsnet/sys/Airport.asp
"""

import csv
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "alan/elia_output/scripts"))
from fetch_opsnet import Opsnet, FORM, private  # noqa: E402

OUT = Path(__file__).resolve().parent
# 2019 is a calendar-matched reference weekend, not the 2019 game weekend.
SUNDAYS = {2019: date(2019, 2, 10), 2023: date(2023, 2, 12),
           2024: date(2024, 2, 11), 2025: date(2025, 2, 9)}
EVENTS = {
    "LVII_2023_Phoenix": (2023, ("PHX", "DVT", "GYR", "IWA", "SDL", "GEU", "CHD", "FFZ")),
    "LVIII_2024_Las_Vegas": (2024, ("LAS", "HND", "VGT", "BVU")),
    "LIX_2025_New_Orleans": (2025, ("MSY", "NEW", "ASD", "HDC", "APS")),
}


def query_days(api, start, end, airports):
    first, last = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
    locids = ",".join(f"'{airport}'" for airport in airports)
    where = f"yyyymmdd>={first} and yyyymmdd<={last} and locid in ({locids})"
    for day, locid, *values in api.query("yyyymmdd,LOCID", where, "r", "yyyymmdd", first, last, airports):
        month, day_of_month, year = day.split("/")
        air_taxi, ga, local_ga = private(values)
        yield dict(date=f"{year}-{month}-{day_of_month}", airport=locid.strip(),
                   air_taxi=air_taxi, general_aviation=ga, local_ga=local_ga)


def write(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    api = Opsnet()
    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    event_rows = []
    for event, (event_year, airports) in EVENTS.items():
        for year, sunday in SUNDAYS.items():
            start, end = sunday - timedelta(days=14), sunday + timedelta(days=14)
            rows = list(query_days(api, start, end, airports))
            print(f"{event} comparison {year}: {len(rows)} airport-days", flush=True)
            for row in rows:
                event_rows.append(dict(event=event, event_year=event_year,
                                       comparison_year=year, game_sunday=sunday.isoformat(),
                                       **row, data_classification="observed_airport",
                                       source=FORM, retrieved_utc=retrieved))
    if not event_rows:
        raise RuntimeError("FAA returned no event-airport data")
    write(OUT / "opsnet_super_bowl_analog_daily.csv", event_rows)
    holiday = list(query_days(api, date(2026, 2, 1), date(2026, 2, 28), ("LAX",)))
    if len(holiday) != 28:
        raise RuntimeError(f"Expected all 28 February 2026 LAX dates; received {len(holiday)}")
    write(OUT / "opsnet_lax_feb2026.csv", [dict(**row, data_classification="observed_airport",
        source=FORM, retrieved_utc=retrieved) for row in holiday])
    print(f"Saved {len(event_rows)} event comparison rows and {len(holiday)} LAX holiday rows")


if __name__ == "__main__":
    main()
