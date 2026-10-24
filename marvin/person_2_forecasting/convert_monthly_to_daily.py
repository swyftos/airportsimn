"""Provisional FBO history from observed FAA daily GA counts. No observed FBO claims.

File name kept for the release contract; the input is now daily, not monthly.
Scope: itinerant general aviation (Part 91) plus air taxi (Part 135); airlines and military excluded.
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'alan/elia_output/data/processed/opsnet_lax_daily.csv'
MONTHLY = ROOT / 'alan/elia_output/data/processed/opsnet_lax_monthly.csv'
MIX = {'light_jet': .47, 'midsize_jet': .33, 'large_jet': .20}
FBO_SHARE = .10  # fbo_market_share in alan/assumptions.csv: 50% private-eligible x 20% capture; one setting for the whole team
PARTS = ('general_aviation', 'air_taxi')  # FAA categories for Part 91 and Part 135
ARRIVAL_SHARE = .5
YEARS = (2023, 2024, 2025)

def convert(source=SOURCE, monthly=MONTHLY):
    with Path(source).open(newline='', encoding='utf-8-sig') as f:
        days = [r for r in csv.DictReader(f) if int(r['date'][:4]) in YEARS]
    rows, seen, sums = [], set(), defaultdict(float)
    for day in days:
        if day['date'] in seen:
            raise ValueError(f"Duplicate day: {day['date']}")
        seen.add(day['date'])
        movements = sum(float(day[part]) for part in PARTS)
        if movements < 0:
            raise ValueError('Negative movements')
        sums[day['date'][:7]] += movements
        for category, share in MIX.items():
            fbo = movements * FBO_SHARE * share
            rows.append(dict(date=day['date'], aircraft_category=category, scope='fbo', data_class='estimated',
                source=f"{day['source']};metric=general_aviation+air_taxi;conversion=PROVISIONAL_ASSUMPTIONS.md",
                arrivals=fbo * ARRIVAL_SHARE, departures=fbo * (1-ARRIVAL_SHARE)))
    with Path(monthly).open(newline='', encoding='utf-8-sig') as f:
        reported = {f"{int(r['year']):04}-{int(r['month']):02}": sum(float(r[part]) for part in PARTS)
                    for r in csv.DictReader(f) if int(r['year']) in YEARS}
    if set(sums) != set(reported) or len(reported) != 12 * len(YEARS):
        raise ValueError('Missing or unexpected baseline months')
    checks = []
    for month, movements in sorted(sums.items()):
        if movements != reported[month]:
            raise ValueError(f'Daily sum differs from FAA monthly total in {month}')
        checks.append(dict(month=month, days=sum(d[:7] == month for d in seen),
            airport_private_ops=movements, assumed_fbo_movements=movements * FBO_SHARE,
            allocation='observed_daily_faa_counts', data_class='estimated'))
    return rows, checks

def holiday_history(source=SOURCE):
    """Airport GA + air-taxi daily counts 2016-2019 and 2023-2025, used only for scale-free holiday ratios."""
    with Path(source).open(newline='', encoding='utf-8-sig') as f:
        days = [r for r in csv.DictReader(f) if int(r['date'][:4]) in (2016, 2017, 2018, 2019, *YEARS)]
    return [dict(date=d['date'], arrivals=sum(float(d[p]) for p in PARTS) * ARRIVAL_SHARE,
                 departures=sum(float(d[p]) for p in PARTS) * (1 - ARRIVAL_SHARE), source=d['source']) for d in days]

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
    write(dest/'holiday_history.csv',holiday_history())
    from build_event_inputs import build
    planning, evidence = build(dest/'historical_traffic.csv', dest/'holiday_history.csv')
    (dest/'event_evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    write(dest/'planning_inputs.csv',planning)
    print(f'{len(rows)} estimated rows from daily FAA GA + air-taxi counts; {len(checks)} months reconciled.')

if __name__=='__main__':
    main()
