"""Checks that the 2026 holdout remains independent of model fitting."""

import copy
import unittest
from collections import defaultdict

import frozen_2026_holdout as holdout


class FrozenHoldoutTests(unittest.TestCase):
    def test_faa_daily_monthly_and_existing_february_agree(self):
        daily = holdout.read(holdout.HOLDOUT)
        monthly = {row['month']: row for row in holdout.read(
            holdout.EVIDENCE / 'opsnet_lax_2026_monthly_check.csv')}
        february = {row['date']: row for row in holdout.read(
            holdout.EVIDENCE / 'opsnet_lax_feb2026.csv')}
        self.assertEqual(len(daily), 273)
        self.assertEqual(len(monthly), 9)
        sums = defaultdict(lambda: defaultdict(int))
        for row in daily:
            for category in ('air_taxi', 'general_aviation', 'local_ga'):
                sums[row['date'][:7]][category] += int(row[category])
                if row['date'] in february:
                    self.assertEqual(int(row[category]), int(february[row['date']][category]))
        self.assertEqual(len(february), 28)
        for month, categories in sums.items():
            for category, value in categories.items():
                self.assertEqual(value, int(monthly[month][category]))

    def test_2026_actuals_cannot_change_frozen_predictions(self):
        observed = holdout.read(holdout.HOLDOUT)
        original = holdout.frozen_predictions(observed)
        changed = copy.deepcopy(observed)
        changed[0]['general_aviation'] = str(int(changed[0]['general_aviation']) + 1000)
        retested = holdout.frozen_predictions(changed)
        self.assertEqual([row['airport_model_operations'] for row in original],
                         [row['airport_model_operations'] for row in retested])
        self.assertNotEqual(original[0]['airport_actual_operations'],
                            retested[0]['airport_actual_operations'])

    def test_2025_band_has_no_2026_scores(self):
        radius, n = holdout.descriptive_radius(holdout.read(holdout.BACKTEST))
        self.assertEqual(n, 84)
        self.assertGreater(radius, 0)


if __name__ == '__main__':
    unittest.main()
