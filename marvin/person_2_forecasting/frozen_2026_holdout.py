"""Evaluate the frozen 2023–2025 model on public 2026 LAX airport counts.

The holdout measures an airport-level daily pattern. Its 10% FBO conversion is
an assumed constant and does not turn airport observations into FBO validation.
"""

import csv
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import forecast_model as fm
from sensitivity_review import HERE, ROOT, input_share


EVIDENCE = HERE / 'calibration_evidence'
HOLDOUT = EVIDENCE / 'opsnet_lax_2026_holdout.csv'
HISTORY = HERE / 'provisional_inputs' / 'historical_traffic.csv'
HOLIDAY_HISTORY = HERE / 'provisional_inputs' / 'holiday_history.csv'
FAA_HISTORY = ROOT / 'alan/elia_output/data/processed/opsnet_lax_daily.csv'
BACKTEST = HERE / 'backtest_forecasts.csv'
TARGETS = ('arrivals', 'departures')


def read(path):
    with path.open(newline='', encoding='utf-8-sig') as handle:
        return list(csv.DictReader(handle))


def write(path, rows):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def airport_count(row):
    return int(row['general_aviation']) + int(row['air_taxi'])


def frozen_predictions(holdout_rows, history_path=HISTORY, holiday_path=HOLIDAY_HISTORY,
                       airport_history_path=FAA_HISTORY):
    """Predict 2026 dates from pre-2026 history only; actuals are used for scoring."""
    share = input_share()
    if not 0 < share <= 1:
        raise ValueError('Invalid FBO share')
    history = fm.load_history(history_path)
    if max(row['date'] for row in history) > date(2025, 12, 31):
        raise ValueError('Training leaks into the 2026 holdout')
    holiday = fm.load_holiday_history(holiday_path)
    if max(row['date'] for row in holiday) > date(2025, 12, 31):
        raise ValueError('Holiday fitting leaks into the holdout')
    fitted, _ = fm.fit_and_evaluate(history, .9, holiday)
    prior = {row['date']: airport_count(row) for row in read(airport_history_path)
             if row['date'].startswith('2025-') and row['locid'] == 'LAX'}
    if len(prior) != 365:
        raise ValueError('Expected complete 2025 LAX comparison year')

    dates = [row['date'] for row in holdout_rows]
    expected = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(273)]
    if dates != expected:
        raise ValueError('2026 holdout must contain all ordered January–September dates once')

    categories = sorted({category for category, _ in fitted})
    result = []
    for row in holdout_rows:
        day = date.fromisoformat(row['date'])
        old_day = (day - timedelta(days=364)).isoformat()
        if old_day not in prior:
            raise ValueError(f'Missing year-ago LAX day {old_day}')
        predicted_fbo = sum(fitted[category, target][0].predict(day)
                            for category in categories for target in TARGETS)
        result.append(dict(date=row['date'], airport_actual_operations=airport_count(row),
                           airport_model_operations=round(predicted_fbo / share, 3),
                           airport_same_weekday_2025_operations=prior[old_day],
                           assumed_fbo_share=f'{share:.2f}',
                           actual_classification='observed_airport',
                           model_classification='assumption_scaled_airport_pattern'))
    return result


def descriptive_radius(backtest_rows):
    """Last 12 rolling 2025 origins provide a descriptive error band, not a guarantee."""
    origins = sorted({row['origin'] for row in backtest_rows})[-12:]
    days = defaultdict(lambda: defaultdict(float))
    for row in backtest_rows:
        if row['origin'] in origins:
            days[row['date']]['actual'] += float(row['actual'])
            days[row['date']]['model'] += float(row['model'])
    if len(origins) != 12 or len(days) != 84:
        raise ValueError('Expected 12 complete seven-day 2025 backtest origins')
    residuals = [abs(row['actual'] - row['model']) for row in days.values()]
    return fm.conformal_radius(residuals, .9) / input_share(), len(residuals)


def metrics(rows, radius):
    result = []
    for month in ['all_Jan_Sep_2026'] + [f'2026-{m:02}' for m in range(1, 10)]:
        selected = rows if month.startswith('all_') else [row for row in rows if row['date'].startswith(month)]
        actual = sum(row['airport_actual_operations'] for row in selected)
        for model, key in (('frozen_model', 'airport_model_operations'),
                           ('same_weekday_2025', 'airport_same_weekday_2025_operations')):
            errors = [float(row[key]) - row['airport_actual_operations'] for row in selected]
            result.append(dict(period=month, method=model, days=len(selected),
                               airport_wape=f'{sum(map(abs, errors)) / actual:.4f}',
                               airport_mae=f'{sum(map(abs, errors)) / len(selected):.3f}',
                               airport_bias=f'{sum(errors) / len(selected):.3f}',
                               descriptive_90_band_coverage=(
                                   f'{sum(abs(error) <= radius for error in errors) / len(selected):.4f}'
                                   if model == 'frozen_model' else ''),
                               actual_classification='observed_airport',
                               fbo_accuracy_validated='no'))
    return result


def render_report(result, scores, radius, calibrated_days):
    overall = {row['method']: row for row in scores if row['period'] == 'all_Jan_Sep_2026'}
    frozen = overall['frozen_model']
    baseline = overall['same_weekday_2025']
    lines = [
        '# Frozen 2026 airport holdout', '',
        'The current demand model was fitted to 2023–2025 and was not updated with 2026 counts.',
        'The 273 January–September 2026 LAX daily observations are from FAA OPSNET; their GA and',
        'air-taxi daily sums match all nine FAA monthly totals. February also matches the separately',
        'collected February 2026 extract. No FBO records are included.', '',
        '| Method | Airport WAPE | Airport MAE/day | Airport bias/day |',
        '| --- | ---: | ---: | ---: |',
        f"| Frozen model | {100 * float(frozen['airport_wape']):.1f}% | {frozen['airport_mae']} | {frozen['airport_bias']} |",
        f"| Same weekday in 2025 | {100 * float(baseline['airport_wape']):.1f}% | "
        f"{baseline['airport_mae']} | {baseline['airport_bias']} |", '',
        f"A descriptive ±{radius:.1f} airport-operation band comes from {calibrated_days} "
        'prequential days in the last 12 rolling 2025 backtest origins. It covered '
        f"{100 * float(frozen['descriptive_90_band_coverage']):.1f}% of 2026 holdout days. "
        'This is a drift diagnostic, not calibrated 2026 coverage or a validated FBO interval.', '',
        'Monthly scores are in `frozen_2026_metrics.csv`; daily predictions and FAA observations are',
        'in `frozen_2026_daily.csv`. The FAA extracts and monthly reconciliation are in',
        '`calibration_evidence/`. Values are airport operations (takeoffs plus landings). The model',
        'first predicts estimated FBO movements using the assumed 10% share, then divides by that',
        'same share for this airport comparison. This cancellation tests the daily airport pattern',
        'only. It does not measure FBO capture, direction split, aircraft mix, reservations, event',
        'demand, or parking capacity.', '',
        'No 2026 observations were used to fit or select this model. Do not describe these scores',
        'as FBO forecast accuracy.', '',
    ]
    return '\n'.join(lines)


def main(output_dir=HERE):
    holdout = read(HOLDOUT)
    rows = frozen_predictions(holdout)
    radius, n = descriptive_radius(read(BACKTEST))
    scores = metrics(rows, radius)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write(output_dir / 'frozen_2026_daily.csv', rows)
    write(output_dir / 'frozen_2026_metrics.csv', scores)
    (output_dir / 'FROZEN_2026_HOLDOUT.md').write_text(
        render_report(rows, scores, radius, n), encoding='utf-8', newline='\n')
    print(f'Evaluated {len(rows)} frozen 2026 LAX airport days')


if __name__ == '__main__':
    main()
