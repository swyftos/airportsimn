"""Rolling-origin backtest for daily FBO arrivals and departures."""

import csv
import math
from datetime import date, timedelta
from pathlib import Path

import forecast_model


HERE = Path(__file__).resolve().parent
HISTORY_PATH = HERE / 'provisional_inputs' / 'historical_traffic.csv'
MODELS = ('model', 'naive_last_week', 'seasonal_naive_last_year',
          'weekday_mean_8w', 'overall_mean')
TARGETS = ('arrivals', 'departures')
FIRST_ORIGIN = date(2025, 1, 6)
LAST_ORIGIN = date(2025, 12, 22)
ORIGINS = tuple(FIRST_ORIGIN + timedelta(days=7 * i)
                for i in range((LAST_ORIGIN - FIRST_ORIGIN).days // 7 + 1))
PRESIDENTS_DAY = date(2025, 2, 17)


def aggregate_daily(history):
    """Sum the three category rows into one FBO row per date."""
    by_date = {}
    for row in history:
        day = by_date.setdefault(row['date'],
                                 {'date': row['date'], 'arrivals': 0.0, 'departures': 0.0})
        for target in TARGETS:
            day[target] += row[target]
    return [by_date[day] for day in sorted(by_date)]


def forecast_origin(daily_rows, origin):
    """Fit and predict using only daily observations before ``origin``."""
    train = [row for row in daily_rows if row['date'] < origin]
    observed = {row['date']: row for row in daily_rows}
    past = {row['date']: row for row in train}
    if not train:
        raise ValueError('Origin needs earlier training days')
    fitted = {target: forecast_model.SeasonalModel(train, target) for target in TARGETS}
    mean = {target: sum(row[target] for row in train) / len(train) for target in TARGETS}
    forecasts = []
    for offset in range(7):
        day = origin + timedelta(days=offset)
        for target in TARGETS:
            last_week = day - timedelta(days=7)
            if last_week not in past:
                last_week = max((past_day for past_day in past
                                 if past_day < origin and past_day.weekday() == day.weekday()),
                                default=None)
            if last_week is None:
                raise ValueError(f'No prior {day:%A} observation for {origin}')
            last_year = day - timedelta(days=364)
            if last_year not in past:
                raise ValueError(f'No year-ago observation for {day}')
            weekdays = [past[day - timedelta(days=7 * week)][target]
                        for week in range(1, 9)]
            forecasts.append({
                'origin': origin,
                'date': day,
                'target': target,
                'actual': observed[day][target],
                'model': fitted[target].predict(day),
                'naive_last_week': past[last_week][target],
                'seasonal_naive_last_year': past[last_year][target],
                'weekday_mean_8w': sum(weekdays) / 8,
                'overall_mean': mean[target],
            })
    return forecasts


def error_metrics(actual_prediction_pairs):
    """Calculate error metrics without rounding intermediate values."""
    pairs = list(actual_prediction_pairs)
    if not pairs:
        raise ValueError('At least one forecast is required')
    errors = [prediction - actual for actual, prediction in pairs]
    absolute_error = sum(abs(error) for error in errors)
    actual_total = sum(actual for actual, _ in pairs)
    return {'n': len(pairs), 'mae': absolute_error / len(pairs),
            'wape': absolute_error / actual_total if actual_total else '',
            'bias': sum(errors) / len(pairs)}


def rolling_radius(residuals):
    """Return the finite-sample 90% absolute-error radius."""
    rank = math.ceil((len(residuals) + 1) * .9)
    if not residuals or rank > len(residuals):
        raise ValueError('Insufficient residuals for 90% coverage')
    return sorted(residuals)[rank - 1]


def rolling_coverage(forecasts, target):
    """Evaluate intervals from the prior 12 origins only."""
    origins = sorted({row['origin'] for row in forecasts if row['target'] == target})
    by_origin = {origin: [row for row in forecasts
                          if row['origin'] == origin and row['target'] == target]
                 for origin in origins}
    covered = evaluated = 0
    for index, origin in enumerate(origins):
        if index < 12:
            continue
        residuals = [abs(row['model'] - row['actual'])
                     for prior in origins[index - 12:index]
                     for row in by_origin[prior]]
        radius = rolling_radius(residuals)
        for row in by_origin[origin]:
            covered += abs(row['model'] - row['actual']) <= radius
            evaluated += 1
    return (covered / evaluated if evaluated else '', evaluated)


def summarize(forecasts):
    """Create all-origin and Presidents Day metrics for each model/target."""
    metrics = []
    for target in TARGETS:
        coverage, n_coverage = rolling_coverage(forecasts, target)
        for model in MODELS:
            for window, selected in (
                ('all_2025_origins', [row for row in forecasts if row['target'] == target]),
                ('presidents_day_2025', [row for row in forecasts
                                         if row['target'] == target and row['date'] == PRESIDENTS_DAY]),
            ):
                result = error_metrics((row['actual'], row[model]) for row in selected)
                result.update(model=model, target=target, window=window,
                              coverage_90=coverage if model == 'model' and window == 'all_2025_origins' else '',
                              n_coverage=n_coverage if model == 'model' and window == 'all_2025_origins' else '')
                metrics.append(result)
    return metrics


def write_csv(path, fieldnames, rows):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def decimal(value):
    return f'{value:.4f}' if isinstance(value, float) else value


def main(history_path=HISTORY_PATH, output_dir=HERE, print_table=True):
    daily = aggregate_daily(forecast_model.load_history(history_path))
    forecasts = [row for origin in ORIGINS for row in forecast_origin(daily, origin)]
    metrics = summarize(forecasts)
    output_dir = Path(output_dir)
    metric_fields = ('model', 'target', 'window', 'n', 'mae', 'wape', 'bias',
                     'coverage_90', 'n_coverage')
    forecast_fields = ('origin', 'date', 'target', 'actual') + MODELS
    write_csv(output_dir / 'backtest_metrics.csv', metric_fields,
              ({field: decimal(row[field]) for field in metric_fields} for row in metrics))
    write_csv(output_dir / 'backtest_forecasts.csv', forecast_fields,
              ({field: decimal(row[field]) for field in forecast_fields} for row in forecasts))
    if print_table:
        print('target      model                     n      wape      mae      bias')
        for row in sorted((row for row in metrics if row['window'] == 'all_2025_origins'),
                          key=lambda row: row['wape']):
            print(f"{row['target']:<11} {row['model']:<24} {row['n']:>3}  "
                  f"{row['wape']:>8.4f} {row['mae']:>8.4f} {row['bias']:>9.4f}")
    return metrics


if __name__ == '__main__':
    main()
