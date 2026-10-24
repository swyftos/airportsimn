"""Provisional, deterministic monthly-to-daily FBO conversion. No observed FBO claims."""
import calendar
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'alan/elia_output/data/processed/lax_monthly_movements.csv'
MIX = {'light_jet': .47, 'midsize_jet': .33, 'large_jet': .20}
FBO_SHARE = .25
ARRIVAL_SHARE = .5

def convert(source=SOURCE):
    with Path(source).open(newline='', encoding='utf-8-sig') as f:
        months = list(csv.DictReader(f))
    rows, checks, seen = [], [], set()
    for month in months:
        year, mon = int(month['year']), int(month['month'])
        if not 2023 <= year <= 2025:
            continue
        key = (year, mon)
        if key in seen:
            raise ValueError(f'Duplicate month: {key}')
        seen.add(key)
        days = calendar.monthrange(year, mon)[1]
        movements = float(month['air_taxi']) + float(month['general_aviation'])
        if movements < 0:
            raise ValueError('Negative movements')
        monthly_fbo = movements * FBO_SHARE
        for day in range(1, days + 1):
            for category, share in MIX.items():
                daily = monthly_fbo / days * share
                rows.append(dict(date=f'{year:04}-{mon:02}-{day:02}',
                    aircraft_category=category, scope='fbo', data_class='estimated',
                    source=f"{month['source_url']};value_source={month['value_source']};conversion=PROVISIONAL_ASSUMPTIONS.md",
                    arrivals=daily * ARRIVAL_SHARE, departures=daily * (1-ARRIVAL_SHARE)))
        checks.append(dict(month=f'{year:04}-{mon:02}', days=days,
            airport_ga_air_taxi=movements, assumed_fbo_movements=monthly_fbo,
            allocation='uniform_calendar_day', data_class='estimated'))
    expected = {(y,m) for y in (2023,2024,2025) for m in range(1,13)}
    if seen != expected:
        raise ValueError('Missing or unexpected baseline months')
    return rows, checks

def write(path, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def main():
    dest=HERE/'provisional_inputs'
    dest.mkdir(exist_ok=True)
    rows,checks=convert()
    write(dest/'historical_traffic.csv',rows)
    write(dest/'monthly_reconciliation.csv',checks)
    from build_event_inputs import build
    planning, evidence = build(dest/'historical_traffic.csv')
    (dest/'event_evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    write(dest/'planning_inputs.csv',planning)
    print(f'{len(rows)} estimated rows; {len(checks)} months; original monthly source unchanged.')

if __name__=='__main__':
    main()
