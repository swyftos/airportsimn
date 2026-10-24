"""Conservation checks for the counterfactual flow cases."""

import unittest

import operational_stress as stress


class OperationalStressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = stress.po.load_demand()
        cls.components = stress.prediction_components()

    def test_direction_cases_preserve_daily_total_movements(self):
        for case in ('arrivals_40_percent', 'arrivals_60_percent'):
            changed = stress.transform(self.original, self.components, case)
            keys = ['date', 'scenario', 'aircraft_category']
            before = self.original.groupby(keys)['expected_movements'].sum()
            after = changed.groupby(keys)['expected_movements'].sum()
            self.assertTrue(((before - after).abs() < .003).all())
            self.assertNotEqual(changed.attrs['baseline_first_day_arrivals'],
                                self.original.attrs['baseline_first_day_arrivals'])

    def test_timing_case_preserves_weekly_direction_totals(self):
        changed = stress.transform(self.original, self.components,
                                   'early_arrivals_late_departures')
        keys = ['scenario', 'aircraft_category', 'direction']
        before = self.original.groupby(keys)['expected_movements'].sum()
        after = changed.groupby(keys)['expected_movements'].sum()
        self.assertTrue(((before - after).abs() < .005).all())
        self.assertNotEqual(
            changed[(changed['scenario'] == 'Medium') & (changed['date'] == '2027-02-15') &
                    (changed['direction'] == 'departures')]['expected_movements'].sum(),
            self.original[(self.original['scenario'] == 'Medium') &
                          (self.original['date'] == '2027-02-15') &
                          (self.original['direction'] == 'departures')]['expected_movements'].sum())


if __name__ == '__main__':
    unittest.main()
