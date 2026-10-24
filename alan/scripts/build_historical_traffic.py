"""Step 3 (Alan): turn Elia's validated airport-wide monthly LAX movement counts
into a daily, arrivals/departures-split interim file.

This is the FIRST of three chained conversions toward the final
historical_traffic.csv that Marvin's forecast model needs:

    Alan (this script)  -> daily totals, airport-wide, GA + air taxi only
    Nazar (next step)   -> scale to the fictional FBO's share (adds scope=fbo)
    Marvin (last step)  -> split into aircraft_category rows (final format)

Input:  alan/elia_output/data/processed/lax_monthly_movements.csv
        columns: year, month, air_carrier, air_taxi, general_aviation,
        military, total, value_source, excluded_covid, data_classification,
        source_url

Output: alan/data/processed/historical_traffic_interim.csv
        columns: date, arrivals, departures, excluded_covid, data_class, source

Conversions applied, each a documented assumption (not an observed fact):

  1. Category filter: keep only air_taxi + general_aviation (airline and
     military traffic is not FBO-relevant).
  2. Monthly -> daily: each month's total is spread EVENLY across its
     calendar days. No day-of-week weighting is applied in this version;
     that is a documented possible refinement, not required for v1.
  3. Total -> arrivals/departures: split 50/50 per day. Over a full month,
     arrivals and departures must roughly balance under ordinary (non-event)
     conditions -- aircraft that land also take off, and nothing
     accumulates indefinitely. A monthly-level 50/50 split is therefore a
     defensible default for ORDINARY years, not an arbitrary guess. This
     does NOT apply to event-week skew (arrivals front-loaded, departures
     back-loaded around game day) -- that belongs to Marvin's event overlay
     on top of this ordinary-week baseline, not to this file.

Every output row is tagged data_class=estimated, because every row passed
through at least one of the conversions above. None of these numbers were
directly observed at daily granularity by any source.
"""
import calendar
import csv
from pathlib import Path

HERE = Path(__file__).parent
IN_PATH = HERE.parent / "elia_output" / "data" / "processed" / "lax_monthly_movements.csv"
OUT_PATH = HERE.parent / "data" / "processed" / "historical_traffic_interim.csv"

# Change this constant if a documented reason emerges to skew the ordinary-week
# arrivals/departures split away from 50/50. Keep it a single named constant
# so the assumption is easy to find and change.
ARRIVAL_SHARE = 0.5

SOURCE_NOTE = (
    "derived from LAWA TCOM monthly movements (Elia, lax_monthly_movements.csv); "
    "air_taxi + general_aviation only; month total spread evenly across days "
    "(monthly->daily assumption); day total split {:.0%}/{:.0%} arrivals/departures "
    "(ordinary-week balance assumption, see script docstring)"
).format(ARRIVAL_SHARE, 1 - ARRIVAL_SHARE)


def main():
    rows_out = []
    with open(IN_PATH, newline="") as f:
        for row in csv.DictReader(f):
            year = int(row["year"])
            month = int(row["month"])
            ga_air_taxi_total = int(row["air_taxi"]) + int(row["general_aviation"])
            excluded_covid = row["excluded_covid"]

            days_in_month = calendar.monthrange(year, month)[1]
            daily_total = ga_air_taxi_total / days_in_month

            for day in range(1, days_in_month + 1):
                date = f"{year:04d}-{month:02d}-{day:02d}"
                arrivals = daily_total * ARRIVAL_SHARE
                departures = daily_total * (1 - ARRIVAL_SHARE)
                rows_out.append(
                    {
                        "date": date,
                        "arrivals": round(arrivals, 2),
                        "departures": round(departures, 2),
                        "excluded_covid": excluded_covid,
                        "data_class": "estimated",
                        "source": SOURCE_NOTE,
                    }
                )

    rows_out.sort(key=lambda r: r["date"])
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "arrivals", "departures", "excluded_covid", "data_class", "source"])
        w.writeheader()
        w.writerows(rows_out)

    print(f"Wrote {len(rows_out)} daily rows to {OUT_PATH}")
    print(f"Date range: {rows_out[0]['date']} to {rows_out[-1]['date']}")


if __name__ == "__main__":
    main()
