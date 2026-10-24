"""Step 3a: monthly LAX GA + air taxi -> estimated airport-wide daily flows.

No FBO share, aircraft mix, event uplift or parking occupancy is inferred here.
Uniform allocation preserves monthly seasonality, not actual daily variation.
Day-of-week weighting requires independent evidence and is a possible v2 refinement.
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
INPUT = ROOT / 'alan/elia_output/data/processed/lax_monthly_movements.csv'
OUTPUT = ROOT / 'alan/data/processed/historical_traffic_interim.csv'
FIELDS = ('date', 'arrivals', 'departures', 'excluded_covid', 'data_class', 'source')
YEARS = range(2016, 2026)
EXCLUDED_YEARS = {2020, 2021, 2022}
REQUIRED = {'year', 'month', 'air_taxi', 'general_aviation', 'excluded_covid',
            'data_classification', 'value_source', 'source_url'}
PRECISION = Decimal('0.000000000001')
TOLERANCE = Decimal('0.000000001')
# Direction counts are unavailable. Equal shares are an assumption, not evidence
# of balanced observed flows or a valid aircraft-inventory model.
ARRIVAL_SHARE = Decimal('0.5')


def count(value, label):
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f'{label}: expected a nonnegative integer count.') from exc
    if not result.is_finite() or result < 0 or result != result.to_integral_value():
        raise ValueError(f'{label}: expected a nonnegative integer count.')
    return result


def load_months(content):
    reader = csv.DictReader(io.StringIO(content.lstrip('\ufeff')))
    headers = reader.fieldnames or []
    if len(headers) != len(set(headers)) or not REQUIRED <= set(headers):
        raise ValueError('Missing required or duplicate monthly CSV headers.')
    selected = {}
    ignored = 0
    for line, row in enumerate(reader, 2):
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f'Line {line}: malformed CSV row.')
        try:
            year, month = int(row['year']), int(row['month'])
            date(year, month, 1)
        except ValueError as exc:
            raise ValueError(f'Line {line}: invalid year/month.') from exc
        if year not in YEARS:
            ignored += 1
            continue
        key = (year, month)
        if key in selected:
            raise ValueError(f'Duplicate month: {year}-{month:02}.')
        flag = row['excluded_covid'].strip().lower()
        if flag not in ('true', 'false') or (flag == 'true') != (year in EXCLUDED_YEARS):
            raise ValueError(f'{year}-{month:02}: excluded_covid conflicts with the 2020–2022 policy.')
        for field in ('source_url', 'value_source', 'data_classification'):
            if not row[field].strip():
                raise ValueError(f'{year}-{month:02}: missing {field}.')
        selected[key] = {
            **row,
            'air_taxi': count(row['air_taxi'], f'{key} air_taxi'),
            'general_aviation': count(row['general_aviation'], f'{key} general_aviation'),
            'excluded_covid': flag == 'true',
        }
    missing = sorted({(y, m) for y in YEARS for m in range(1, 13)} - selected.keys())
    if missing:
        raise ValueError('Missing months (never treated as zero): ' +
                         ', '.join(f'{y}-{m:02}' for y, m in missing))
    return selected, ignored


def convert(months):
    daily = []
    checks = []
    for (year, month), row in sorted(months.items()):
        days = calendar.monthrange(year, month)[1]
        total = row['air_taxi'] + row['general_aviation']
        # Decimal fractions remain estimates. Integer rounding would create
        # artificial day-to-day variation, so retain 12 decimal places.
        arrivals = (total * ARRIVAL_SHARE / days).quantize(PRECISION)
        departures = (total * (1 - ARRIVAL_SHARE) / days).quantize(PRECISION)
        source = (
            f"LAWA LAX; source_url={row['source_url']}; month={year}-{month:02}; "
            f"value_source={row['value_source']}; upstream_class={row['data_classification']}; "
            f"components=air_taxi+general_aviation; rule=uniform_calendar_days_v1; "
            f"days={days}; arrivals_share=0.5; departures_share=0.5; airport_wide=true"
        )
        for day in range(1, days + 1):
            daily.append({'date': date(year, month, day).isoformat(),
                          'arrivals': str(arrivals), 'departures': str(departures),
                          'excluded_covid': str(row['excluded_covid']),
                          'data_class': 'estimated', 'source': source})
        checks.append({'month': f'{year}-{month:02}', 'days': days,
                       'source_movements': str(total)})
    return daily, checks


def validate_daily(daily, months):
    """Independent reconciliation of the rows that will be written to disk."""
    dates = [r['date'] for r in daily]
    expected_dates = [date(y, m, d).isoformat() for y, m in sorted(months)
                      for d in range(1, calendar.monthrange(y, m)[1] + 1)]
    if dates != expected_dates:
        raise ValueError('Daily coverage/order is incomplete or duplicated.')
    sums = {key: Decimal(0) for key in months}
    for row in daily:
        key = (int(row['date'][:4]), int(row['date'][5:7]))
        if row['data_class'] != 'estimated' or row['excluded_covid'] != str(months[key]['excluded_covid']):
            raise ValueError('Daily provenance or exclusion flag changed.')
        sums[key] += Decimal(row['arrivals']) + Decimal(row['departures'])
    errors = {key: sums[key] - (r['air_taxi'] + r['general_aviation'])
              for key, r in months.items()}
    if any(abs(error) > TOLERANCE for error in errors.values()):
        raise ValueError('Daily totals do not reconcile to source monthly counts.')
    return max(abs(error) for error in errors.values())


def build(input_path=INPUT, output_path=OUTPUT):
    input_path, output_path = Path(input_path), Path(output_path)
    report_path = output_path.with_suffix('.validation.json')
    if input_path.resolve() in (output_path.resolve(), report_path.resolve()):
        raise ValueError('Output must not overwrite the monthly input.')
    content = input_path.read_bytes()
    months, ignored = load_months(content.decode('utf-8-sig'))
    daily, checks = convert(months)
    max_error = validate_daily(daily, months)
    report = {
        'rule': 'uniform_calendar_days_v1',
        'input_file': input_path.name,
        'input_sha256': hashlib.sha256(content).hexdigest(),
        'window_start': daily[0]['date'], 'window_end': daily[-1]['date'],
        'selected_months': len(months), 'out_of_window_rows_ignored': ignored,
        'daily_rows': len(daily),
        'excluded_covid_rows': sum(r['excluded_covid'] == 'True' for r in daily),
        'february_2022_rows_retained': sum(r['date'].startswith('2022-02-') for r in daily),
        'data_class': 'estimated', 'arrivals_share': '0.5', 'departures_share': '0.5',
        'decimal_places': 12, 'monthly_reconciliation_tolerance': str(TOLERANCE),
        'max_absolute_monthly_reconciliation_error': str(max_error),
        'monthly_controls': checks,
        'limitations': [
            'Airport-wide GA/air-taxi flows; FBO share and aircraft categories have not been applied.',
            'Uniform daily allocation cannot establish weekday patterns or a Super Bowl week surge.',
            'Equal arrivals/departures are assumed; these rows cannot establish parking occupancy.',
            'Upstream 2018 monthly/annual mismatch, 2016 outlier and annual-residual provenance remain unchanged. See the handoff documentation.',
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
    args = parser.parse_args()
    try:
        report = build(args.input, args.output)
    except (ValueError, OSError, UnicodeError) as exc:
        parser.exit(1, f'Historical conversion failed: {exc}\n')
    print(f"Wrote {report['daily_rows']} estimated daily rows; "
          f"{report['excluded_covid_rows']} flagged excluded; "
          f"{report['selected_months']} months reconciled. Output: {args.output}")


if __name__ == '__main__':
    main()
