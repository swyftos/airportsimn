"""Part 135 (air_taxi) supplement -- verified daily LAX air-taxi FAA
operations -> estimated airport-wide daily arrivals/departures.

Kept DELIBERATELY SEPARATE from the Part 91-only baseline pipeline
(build_historical_traffic.py / build_baseline.py). The team's
private-only scope decision excludes air_taxi from alan/baseline.csv --
this file does not feed that pipeline and is not meant to. It exists so
the team has real Part 135 numbers available for comparison/context
(e.g. Marvin's confirmed use of air-taxi's measured event-size uplift
for the Medium forecast scenario, which needed a real air-taxi baseline
to reference). See alan/docs/traffic_categories_and_fleet_mix.md
section 1.2 for what Part 135/air_taxi legally includes (on-demand
charter AND scheduled commuter service).

Source: Elia's alan/elia_output/data/processed/opsnet_lax_daily.csv
(FAA ATADS/OPSNET, verified_public), cross-checked against
opsnet_lax_daily_check.csv (132/132 months already validated to match
the official monthly air_taxi totals).
"""
import argparse
import calendar
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / 'alan/elia_output/data/processed/opsnet_lax_daily.csv'
MONTHLY_CHECK = ROOT / 'alan/elia_output/data/processed/opsnet_lax_daily_check.csv'
OUTPUT = ROOT / 'alan/data/processed/historical_traffic_air_taxi_interim.csv'
FIELDS = ('date', 'arrivals', 'departures', 'excluded_covid', 'data_class', 'source')
YEARS = range(2015, 2026)
EXCLUDED_YEARS = {2020, 2021, 2022}
PRECISION = Decimal('0.000000000001')
LOCID = 'LAX'
ARRIVAL_SHARE = Decimal('0.5')
REQUIRED = {'date', 'locid', 'air_taxi', 'excluded_covid', 'data_classification', 'source'}


def count(value, label):
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f'{label}: expected a nonnegative integer count.') from exc
    if not result.is_finite() or result < 0 or result != result.to_integral_value():
        raise ValueError(f'{label}: expected a nonnegative integer count.')
    return result


def load_daily(content):
    reader = csv.DictReader(io.StringIO(content.lstrip('﻿')))
    headers = reader.fieldnames or []
    if len(headers) != len(set(headers)) or not REQUIRED <= set(headers):
        raise ValueError('Missing required or duplicate air_taxi daily CSV headers.')
    rows = {}
    ignored = 0
    for line, row in enumerate(reader, 2):
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f'Line {line}: malformed CSV row.')
        if row['locid'] != LOCID:
            ignored += 1
            continue
        try:
            d = date.fromisoformat(row['date'])
        except ValueError as exc:
            raise ValueError(f'Line {line}: invalid date.') from exc
        if d.year not in YEARS:
            ignored += 1
            continue
        flag = row['excluded_covid'].strip().lower()
        if flag not in ('true', 'false') or (flag == 'true') != (d.year in EXCLUDED_YEARS):
            raise ValueError(f'{d.isoformat()}: excluded_covid conflicts with the 2020-2022 policy.')
        for field in ('source', 'data_classification'):
            if not row[field].strip():
                raise ValueError(f'{d.isoformat()}: missing {field}.')
        if d in rows:
            raise ValueError(f'Duplicate date: {d.isoformat()}.')
        rows[d] = {
            'air_taxi': count(row['air_taxi'], f'{d.isoformat()} air_taxi'),
            'excluded_covid': flag == 'true',
            'source_url': row['source'],
            'classification': row['data_classification'],
        }
    missing = sorted(
        {date(y, m, day) for y in YEARS for m in range(1, 13) for day in range(1, calendar.monthrange(y, m)[1] + 1)}
        - rows.keys()
    )
    if missing:
        raise ValueError(f'Missing {len(missing)} day(s) (never treated as zero), first: {missing[0].isoformat()}.')
    return rows, ignored


def validate_against_monthly(rows, monthly_path):
    """Independent cross-check against Elia's already-validated monthly
    air_taxi totals (opsnet_lax_daily_check.csv, 132/132 months matched)."""
    monthly = {}
    with monthly_path.open(newline='', encoding='utf-8-sig') as handle:
        for row in csv.DictReader(handle):
            if row['matches'].strip().lower() != 'true':
                raise ValueError(f"{row['year']}-{row['month']}: upstream monthly check failed (matches=False); refusing to build on it.")
            monthly[f"{row['year']}-{int(row['month']):02}"] = Decimal(row['air_taxi_monthly'])
    sums = {}
    for d, r in rows.items():
        key = f'{d.year}-{d.month:02}'
        sums[key] = sums.get(key, Decimal(0)) + r['air_taxi']
    missing_months = sorted(set(monthly) - set(sums))
    if missing_months:
        raise ValueError(f'Monthly check file has months not covered by the daily rows: {missing_months[:3]}')
    mismatches = sorted(k for k, v in sums.items() if k in monthly and v != monthly[k])
    if mismatches:
        raise ValueError(f'Daily sums do not match validated monthly totals for: {mismatches[:3]}')
    return len(monthly)


def convert(rows):
    daily = []
    for d in sorted(rows):
        r = rows[d]
        total = r['air_taxi']
        arrivals = (total * ARRIVAL_SHARE).quantize(PRECISION)
        departures = (total * (1 - ARRIVAL_SHARE)).quantize(PRECISION)
        source = (
            f"Elia opsnet_lax_daily.csv; source_url={r['source_url']}; "
            f"date={d.isoformat()}; upstream_class={r['classification']}; "
            f"components=air_taxi_only; rule=daily_direct_v1_air_taxi; "
            f"arrivals_share=0.5; departures_share=0.5; airport_wide=true; scope=part135_air_taxi_only"
        )
        daily.append({
            'date': d.isoformat(), 'arrivals': str(arrivals), 'departures': str(departures),
            'excluded_covid': str(r['excluded_covid']), 'data_class': 'estimated', 'source': source,
        })
    return daily


def build(input_path=INPUT, output_path=OUTPUT, monthly_check_path=MONTHLY_CHECK):
    input_path, output_path, monthly_check_path = Path(input_path), Path(output_path), Path(monthly_check_path)
    report_path = output_path.with_suffix('.validation.json')
    if input_path.resolve() in (output_path.resolve(), report_path.resolve()):
        raise ValueError('Output must not overwrite the air_taxi daily input.')
    content = input_path.read_bytes()
    rows, ignored = load_daily(content.decode('utf-8-sig'))
    months_checked = validate_against_monthly(rows, monthly_check_path)
    daily = convert(rows)
    report = {
        'rule': 'daily_direct_v1_air_taxi',
        'input_file': input_path.name,
        'input_sha256': hashlib.sha256(content).hexdigest(),
        'window_start': daily[0]['date'], 'window_end': daily[-1]['date'],
        'daily_rows': len(daily), 'out_of_window_rows_ignored': ignored,
        'months_cross_checked_against_monthly_totals': months_checked,
        'excluded_covid_rows': sum(r['excluded_covid'] == 'True' for r in daily),
        'data_class': 'estimated', 'arrivals_share': '0.5', 'departures_share': '0.5',
        'scope': 'part135_air_taxi_only',
        'limitations': [
            'Part 135 (air_taxi) FAA category only. NOT fed into alan/baseline.csv -- the team baseline is Part 91 GA-only by design.',
            'Part 135/air_taxi legally includes both on-demand charter AND scheduled commuter service -- see alan/docs/traffic_categories_and_fleet_mix.md section 1.2.',
            'Equal arrivals/departures are assumed (unevidenced), same as the GA-only pipeline.',
            'Provided for comparison/context only, e.g. the Medium forecast scenario\'s event-size uplift, which is borrowed from the measured air-taxi response.',
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator='\n')
        writer.writeheader()
        writer.writerows(daily)
    report['output_sha256'] = hashlib.sha256(output_path.read_bytes()).hexdigest()
    report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=INPUT)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--monthly-check', type=Path, default=MONTHLY_CHECK)
    args = parser.parse_args()
    try:
        report = build(args.input, args.output, args.monthly_check)
    except (ValueError, OSError, UnicodeError) as exc:
        parser.exit(1, f'Air-taxi historical conversion failed: {exc}\n')
    print(f"Wrote {report['daily_rows']} estimated daily rows (Part 135 air_taxi only); "
          f"{report['excluded_covid_rows']} flagged excluded; "
          f"{report['months_cross_checked_against_monthly_totals']} months cross-checked. "
          f"Output: {args.output}")


if __name__ == '__main__':
    main()
