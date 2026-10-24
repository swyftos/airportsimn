"""Behavioral tests for the rolling-origin FBO backtest."""

import copy
import csv
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import backtest
import forecast_model


HERE = Path(__file__).resolve().parent
HISTORY = HERE / 'provisional_inputs' / 'historical_traffic.csv'


class BacktestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history = forecast_model.load_history(HISTORY)
        cls.daily = backtest.aggregate_daily(cls.history)

    def test_future_history_cannot_change_origin_predictions(self):
        origin = date(2025, 2, 17)
        expected = backtest.forecast_origin(self.daily, origin)
        changed = copy.deepcopy(self.history)
        for row in changed:
            if row['date'] >= origin:
                row['arrivals'] += 1000
                row['departures'] += 2000
        actual = backtest.forecast_origin(backtest.aggregate_daily(changed), origin)
        for before, after in zip(expected, actual):
            for model in backtest.MODELS:
                self.assertEqual(before[model], after[model])
        self.assertNotEqual(expected[0]['actual'], actual[0]['actual'])

    def test_error_metrics_and_rolling_quantile(self):
        metrics = backtest.error_metrics([(10, 12), (20, 17), (0, 1)])
        self.assertEqual(metrics['n'], 3)
        self.assertAlmostEqual(metrics['mae'], 2)
        self.assertAlmostEqual(metrics['wape'], .2)
        self.assertAlmostEqual(metrics['bias'], 0)
        self.assertEqual(backtest.rolling_radius([1, 2, 3, 4, 5, 6, 7, 8, 9]), 9)
        self.assertEqual(backtest.rolling_radius([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]), 10)
        origins = [date(2025, 1, 6) + timedelta(days=7 * week) for week in range(13)]
        rows = [{'origin': origins[i // 7], 'target': 'arrivals',
                 'actual': 0, 'model': i + 1} for i in range(84)]
        rows.extend({'origin': origins[-1], 'target': 'arrivals',
                     'actual': 0, 'model': error}
                    for error in (0, 77, 78, 100, 1, 76, 80))
        self.assertEqual(backtest.rolling_coverage(rows, 'arrivals'), (4 / 7, 7))

    def test_main_rerun_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            backtest.main(history_path=HISTORY, output_dir=Path(first), print_table=False)
            backtest.main(history_path=HISTORY, output_dir=Path(second), print_table=False)
            for filename in ('backtest_metrics.csv', 'backtest_forecasts.csv'):
                self.assertEqual((Path(first) / filename).read_bytes(),
                                 (Path(second) / filename).read_bytes())

    def test_forecast_csv_has_all_origin_days_and_targets(self):
        with tempfile.TemporaryDirectory() as output:
            backtest.main(history_path=HISTORY, output_dir=Path(output), print_table=False)
            with (Path(output) / 'backtest_forecasts.csv').open(newline='') as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 51 * 7 * 2)
        self.assertEqual(len({row['origin'] for row in rows}), 51)
        self.assertEqual(len({(row['origin'], row['date'], row['target']) for row in rows}), len(rows))
        for origin in backtest.ORIGINS:
            self.assertEqual(sum(row['origin'] == str(origin) for row in rows), 14)


if __name__ == '__main__':
    unittest.main()
