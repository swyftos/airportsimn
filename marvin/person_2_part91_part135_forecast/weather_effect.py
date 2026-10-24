"""Observed LAX weather effects on completed FAA airport operations."""
import csv
import math
import random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path


HERE = Path(__file__).resolve().parent
WEATHER_PATH = HERE / 'data/noaa_lax_daily.csv'
OPS_PATH = HERE.parents[1] / 'alan/elia_output/data/processed/opsnet_lax_daily.csv'
RESULTS_DIR = HERE / 'results'
ALLOWED_YEARS = {2016, 2017, 2018, 2019, 2023, 2024, 2025}
WEATHER_TYPES = ('rain', 'heavy_rain', 'fog', 'heavy_fog', 'dry_clear', 'day_after_rain')
CATEGORIES = ('part91_general_aviation', 'part135_air_taxi')
WINDOWS = (('2016-2019+2023-2025', ALLOWED_YEARS),
           ('2023-2025', {2023, 2024, 2025}))
NOAA_SOURCE = ('https://www.ncei.noaa.gov/access/services/data/v1'
               '?dataset=daily-summaries&stations=USW00023174')
FAA_SOURCE = 'https://www.aspm.faa.gov/opsnet/sys/Airport.asp'
EFFECT_NOTE = ('completed airport operations; does not separate cancelled demand '
               'from shifted flights; FAA General Aviation/Air Taxi are airport categories')


def read_csv(path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fieldnames):
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def optional_number(value):
    if not value or not value.strip():
        return None
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f'Expected a finite, nonnegative number: {value!r}')
    return number


def load_weather(path):
    """Read weather for all dates, including those used only for climatology."""
    weather = {}
    for row in read_csv(path):
        day = date.fromisoformat(row['DATE'])
        if day in weather:
            raise ValueError(f'Duplicate NOAA date: {day}')
        rain = optional_number(row['PRCP'])
        # WT01 (fog) is reported on over a third of LAX days, mostly marine layer; WT02 (heavy fog) marks low visibility.
        fog = any(row.get(key, '').strip() == '1' for key in ('WT01', 'WT02'))
        heavy_fog = row.get('WT02', '').strip() == '1'
        types = set()
        if rain is not None:
            if rain >= 0.10:
                types.add('rain')
            if rain >= 0.50:
                types.add('heavy_rain')
            if rain < 0.01 and not fog:
                types.add('dry_clear')
        if fog:
            types.add('fog')
        if heavy_fog:
            types.add('heavy_fog')
        weather[day] = {'date': day, 'types': types}
    for day, row in weather.items():
        previous = weather.get(day - timedelta(days=1))
        if previous and 'rain' in previous['types'] and 'rain' not in row['types']:
            row['types'].add('day_after_rain')
    return weather


def load_operations(path):
    operations = {}
    for row in read_csv(path):
        if row['locid'].strip() != 'LAX':
            continue
        day = date.fromisoformat(row['date'])
        if day in operations:
            raise ValueError(f'Duplicate FAA date: {day}')
        operations[day] = {
            'part91_general_aviation': optional_number(row['general_aviation']),
            'part135_air_taxi': optional_number(row['air_taxi']),
        }
    return operations


def join_days(weather, operations):
    """Join only effect years; keep days with either category missing for the other."""
    days = []
    for day in sorted(weather.keys() & operations.keys()):
        if day.year in ALLOWED_YEARS:
            days.append({'date': day, 'types': weather[day]['types'], **operations[day]})
    return days


def add_expected(days):
    """Attach dry-clear weekday reference means, with a one-month fallback."""
    dry = defaultdict(list)
    for row in days:
        if 'dry_clear' in row['types']:
            day = row['date']
            dry[day.year, day.month, day.weekday()].append(row)
    for row in days:
        day = row['date']
        key = day.year, day.month, day.weekday()
        for category in CATEGORIES:
            values = [candidate[category] for candidate in dry[key]
                      if candidate[category] is not None]
            if len(values) < 2:
                values = [candidate[category]
                          for month in (day.month - 1, day.month, day.month + 1)
                          if 1 <= month <= 12
                          for candidate in dry[day.year, month, day.weekday()]
                          if candidate[category] is not None]
            row[f'expected_{category}'] = sum(values) / len(values) if values else None
    return days


def percentile(sorted_values, percentage):
    position = (len(sorted_values) - 1) * percentage
    lower = math.floor(position)
    upper = math.ceil(position)
    return (sorted_values[lower] * (upper - position)
            + sorted_values[upper] * (position - lower)) if lower != upper else sorted_values[lower]


def bootstrap_interval(ratios):
    rng = random.Random(2027)
    n = len(ratios)
    samples = sorted(sum(rng.choices(ratios, k=n)) / n - 1 for _ in range(2000))
    return percentile(samples, 0.025), percentile(samples, 0.975)


def effect_rows(days):
    add_expected(days)
    rows = []
    for category in CATEGORIES:
        for window, years in WINDOWS:
            for weather_type in WEATHER_TYPES:
                usable = [(row[category], row[f'expected_{category}']) for row in days
                          if row['date'].year in years and weather_type in row['types']
                          and row[category] is not None
                          and row[f'expected_{category}'] is not None
                          and row[f'expected_{category}'] > 0]
                if not usable:
                    continue
                ratios = [ops / expected for ops, expected in usable]
                effect = sum(ratios) / len(ratios) - 1
                ci_low, ci_high = bootstrap_interval(ratios)
                rows.append({
                    'category': category, 'window': window, 'weather_type': weather_type,
                    'n_days': len(usable), 'effect': round(effect, 4), 'ci_low': round(ci_low, 4),
                    'ci_high': round(ci_high, 4),
                    'mean_ops_on_type_days': round(sum(ops for ops, _ in usable) / len(usable), 2),
                    'mean_expected_ops': round(sum(expected for _, expected in usable) / len(usable), 2),
                    'classification': 'observed_NOAA_x_FAA_derived',
                    'source': f'{NOAA_SOURCE} | {FAA_SOURCE}', 'note': EFFECT_NOTE,
                })
    return rows


def climatology_rows(weather):
    february = [row for day, row in sorted(weather.items())
                if day.month == 2 and 2015 <= day.year <= 2026]
    years = sorted({row['date'].year for row in february})
    rows = []

    def append(metric, weather_type, period, year, value, n_years, n_days):
        rows.append({'metric': metric, 'weather_type': weather_type, 'period': period,
                     'year': year, 'value': value, 'n_years': n_years, 'n_days': n_days,
                     'classification': 'observed_NOAA', 'source': NOAA_SOURCE})

    for weather_type in WEATHER_TYPES:
        count = sum(weather_type in row['types'] for row in february)
        append('february_day_share', weather_type, 'all_february', '',
               round(count / len(february), 4), len(years), len(february))
    for weather_type in ('rain', 'heavy_fog'):
        annual = []
        total_days = 0
        for year in years:
            week = [weather[date(year, 2, day)] for day in range(11, 18)
                    if date(year, 2, day) in weather]
            if not week:
                continue
            count = sum(weather_type in row['types'] for row in week)
            annual.append(count)
            total_days += len(week)
            append('feb_11_17_days', weather_type, 'feb_11_17', year,
                   count, 1, len(week))
        append('feb_11_17_days_mean', weather_type, 'feb_11_17', '',
               round(sum(annual) / len(annual), 3), len(annual), total_days)
        append('feb_11_17_days_max', weather_type, 'feb_11_17', '',
               max(annual), len(annual), total_days)
    return rows


def main():
    weather = load_weather(WEATHER_PATH)
    days = join_days(weather, load_operations(OPS_PATH))
    effects = effect_rows(days)
    climatology = climatology_rows(weather)
    RESULTS_DIR.mkdir(exist_ok=True)
    write_csv(RESULTS_DIR / 'weather_effect_measured.csv', effects,
              ('category', 'window', 'weather_type', 'n_days', 'effect', 'ci_low',
               'ci_high', 'mean_ops_on_type_days', 'mean_expected_ops',
               'classification', 'source', 'note'))
    write_csv(RESULTS_DIR / 'weather_feb_climatology.csv', climatology,
              ('metric', 'weather_type', 'period', 'year', 'value', 'n_years',
               'n_days', 'classification', 'source'))
    print('Category                  Weather   Effect    95% CI       Days')
    for row in effects:
        if row['window'] == WINDOWS[0][0] and row['weather_type'] in ('rain', 'heavy_rain', 'heavy_fog'):
            print(f"{row['category']:<25} {row['weather_type']:<8} "
                  f"{row['effect']:+7.1%}  "
                  f"[{row['ci_low']:+.1%}, {row['ci_high']:+.1%}]  "
                  f"{row['n_days']:4}")


if __name__ == '__main__':
    main()
