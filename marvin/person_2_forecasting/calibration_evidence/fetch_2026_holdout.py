"""Fetch finalized 2026 LAX airport counts for a frozen forecast check.

Uses FAA OPSNET airport operations, not FBO bookings. As of 2026-10-24 the
public finalized window is January through September 2026. The script checks
every daily date against the FAA monthly totals before writing either file.
"""

import csv
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fetch_public_counts import FORM, Opsnet, private, query_days


HERE = Path(__file__).resolve().parent
FIRST = date(2026, 1, 1)
LAST = date(2026, 9, 30)
CATEGORIES = ('air_taxi', 'general_aviation', 'local_ga')


def write(path, rows):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def fetch(api):
    daily = list(query_days(api, FIRST, LAST, ('LAX',)))
    expected = {(FIRST + timedelta(days=i)).isoformat() for i in range((LAST - FIRST).days + 1)}
    if len(daily) != len(expected) or {row['date'] for row in daily} != expected:
        raise ValueError(f'Incomplete 2026 LAX daily series: got {len(daily)} of {len(expected)}')
    if any(row['airport'] != 'LAX' or any(int(row[c]) < 0 for c in CATEGORIES) for row in daily):
        raise ValueError('Unexpected airport or negative FAA count')

    monthly = {}
    for month, airport, *values in api.query(
            'yyyymm,LOCID', "yyyymm>=202601 and yyyymm<=202609 and locid in ('LAX')",
            'm', 'yyyymm', '202601', '202609', ['LAX']):
        mm, yyyy = month.split('/')
        key = f'{yyyy}-{mm}'
        if key in monthly or airport.strip() != 'LAX':
            raise ValueError('Duplicate month or unexpected FAA airport')
        monthly[key] = dict(zip(CATEGORIES, private(values)))
    if set(monthly) != {f'2026-{m:02}' for m in range(1, 10)}:
        raise ValueError('Missing FAA monthly reconciliation rows')

    checks = []
    for month, reported in sorted(monthly.items()):
        rows = [row for row in daily if row['date'].startswith(month)]
        result = dict(month=month, days=len(rows))
        for category in CATEGORIES:
            observed = sum(int(row[category]) for row in rows)
            if observed != reported[category]:
                raise ValueError(f'{month} {category}: daily {observed}, monthly {reported[category]}')
            result[category] = observed
        checks.append(result)
    return daily, checks


def main():
    daily, checks = fetch(Opsnet())
    retrieved = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
    write(HERE / 'opsnet_lax_2026_holdout.csv',
          [dict(**row, data_classification='observed_airport', source=FORM,
                retrieved_utc=retrieved) for row in daily])
    write(HERE / 'opsnet_lax_2026_monthly_check.csv', checks)
    print(f'Wrote {len(daily)} daily FAA rows; {len(checks)} months reconciled')


if __name__ == '__main__':
    main()
