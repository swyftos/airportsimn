"""Step 3a (v2 -- Part 91 GA-only): verified daily LAX GA-category FAA
operations -> estimated airport-wide daily arrivals/departures.

Supersedes the original monthly air_taxi+general_aviation uniform-spread
version. Per the team's private-only (Part 91) scope decision (see
alan/docs/traffic_categories_and_fleet_mix.md section 1), air_taxi
(Part 135) is dropped entirely, and the input is now Marvin's verified
daily GA extract (already daily-resolution, cross-checked against the
official monthly GA totals in 132 of 132 months -- see
marvin/person_2_forecasting/private_only_review/README.md) instead of a
monthly total spread uniformly across days. This means day-to-day
variation in the output is now real FAA data, not an artifact of uniform
spreading.

No FBO share, aircraft mix, event uplift or parking occupancy is inferred
here. 50/50 arrivals/departures remains an unevidenced assumption (FAA GA
counts are not direction-split); it is now applied to each real daily
total instead of to a flat monthly average.
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
INPUT = ROOT / 'marvin/person_2_forecasting/private_only_review/ga_only_daily_source.csv'
MONTHLY_CHECK = ROOT / 'marvin/person_2_forecasting/private_only_review/ga_only_monthly_check.csv'
OUTPUT = ROOT / 'alan/data/processed/historical_traffic_interim.csv'
FIELDS = ('date', 'arrivals', 'departures', 'excluded_covid', 'data_class', 'source')
YEARS = range(2015, 2026)
EXCLUDED_YEARS = {2020, 2021, 2022}
PRECISION = Decimal('0.000000000001')
LOCID = 'LAX'
# Direction counts are unavailable. Equal shares are an assumption, not
# evidence of balanced observed flows.
ARRIVAL_SHARE = Decimal('0.5')
REQUIRED = {'date', 'locid', 'general_aviation', 'excluded_covid', 'classification', 'source_url'}


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
        raise ValueError('Missing required or duplicate GA daily CSV headers.')
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
        for field in ('source_url', 'classification'):
            if not row[field].strip():
                raise ValueError(f'{d.isoformat()}: missing {field}.')
        if d in rows:
            raise ValueError(f'Duplicate date: {d.isoformat()}.')
        rows[d] = {
            'general_aviation': count(row['general_aviation'], f'{d.isoformat()} general_aviation'),
            'excluded_covid': flag == 'true',
            'source_url': row['source_url'],
            'classification': row['classification'],
        }
    missing = sorted(
        {date(y, m, day) for y in YEARS for m in range(1, 13) for day in range(1, calendar.monthrange(y, m)[1] + 1)}
        - rows.keys()
    )
    if missing:
        raise ValueError(f'Missing {len(missing)} day(s) (never treated as zero), first: {missing[0].isoformat()}.')
    return rows, ignored


def validate_against_monthly(rows, monthly_path):
    """Independent cross-check: re-sum the daily rows this script just parsed
    and confirm they reproduce Marvin's already-validated monthly GA totals
    (ga_only_monthly_check.csv, 132/132 months matched upstream). This does
    not re-verify FAA's own data, only that this script's own parsing and
    date handling are correct.
    """
    monthly = {}
    with monthly_path.open(newline='', encoding='utf-8-sig') as handle:
        for row in csv.DictReader(handle):
            if row['matches'].strip().lower() != 'true':
                raise ValueError(f"{row['month']}: upstream monthly check failed (matches=False); refusing to build on it.")
            monthly[row['month']] = Decimal(row['ga_daily_sum'])
    sums = {}
    for d, r in rows.items():
        key = f'{d.year}-{d.month:02}'
        sums[key] = sums.get(key, Decimal(0)) + r['general_aviation']
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
        total = r['general_aviation']
        arrivals = (total * ARRIVAL_SHARE).quantize(PRECISION)
        departures = (total * (1 - ARRIVAL_SHARE)).quantize(PRECISION)
        source = (
            f"Marvin private_only_review/ga_only_daily_source.csv; source_url={r['source_url']}; "
            f"date={d.isoformat()}; upstream_class={r['classification']}; "
            f"components=general_aviation_only; rule=daily_direct_v2_ga_only; "
            f"arrivals_share=0.5; departures_share=0.5; airport_wide=true; scope=part91_general_aviation_only"
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
        raise ValueError('Output must not overwrite the GA daily input.')
    content = input_path.read_bytes()
    rows, ignored = load_daily(content.decode('utf-8-sig'))
    months_checked = validate_against_monthly(rows, monthly_check_path)
    daily = convert(rows)
    report = {
        'rule': 'daily_direct_v2_ga_only',
        'input_file': input_path.name,
        'input_sha256': hashlib.sha256(content).hexdigest(),
        'window_start': daily[0]['date'], 'window_end': daily[-1]['date'],
        'daily_rows': len(daily), 'out_of_window_rows_ignored': ignored,
        'months_cross_checked_against_monthly_totals': months_checked,
        'excluded_covid_rows': sum(r['excluded_covid'] == 'True' for r in daily),
        'data_class': 'estimated', 'arrivals_share': '0.5', 'departures_share': '0.5',
        'scope': 'part91_general_aviation_only_no_air_taxi',
        'limitations': [
            'Part 91 (general_aviation) FAA category only; air_taxi (Part 135) dropped per the team\'s private-only scope decision.',
            'The FAA general_aviation category still includes flight training, positioning and other non-FBO-relevant flights -- see alan/docs/traffic_categories_and_fleet_mix.md section 1.3.',
            'Equal arrivals/departures are assumed (unevidenced); applied per real daily total (prior version applied it to a uniform monthly spread).',
            'Source is Marvin\'s private_only_review/ga_only_daily_source.csv, itself FAA ATADS/OPSNET LAX GA-category tower operations.',
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
        parser.exit(1, f'Historical conversion failed: {exc}\n')
    print(f"Wrote {report['daily_rows']} estimated daily rows (Part 91 GA-only); "
          f"{report['excluded_covid_rows']} flagged excluded; "
          f"{report['months_cross_checked_against_monthly_totals']} months cross-checked. "
          f"Output: {args.output}")


if __name__ == '__main__':
    main()
