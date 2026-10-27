"""Checks for the non-release forecast review."""

import json
import unittest

import sensitivity_review


class SensitivityReviewTests(unittest.TestCase):
    def test_share_changes_counts_but_not_event_percent(self):
        totals = sensitivity_review.read_csv(sensitivity_review.HERE / 'daily_totals.csv')
        planning = sensitivity_review.read_csv(
            sensitivity_review.HERE / 'provisional_inputs' / 'planning_inputs.csv')
        low = sensitivity_review.forecast_sensitivity(totals, planning, .05)
        high = sensitivity_review.forecast_sensitivity(totals, planning, .15)
        for left, right in zip(low, high):
            self.assertEqual(left['scenario'], right['scenario'])
            self.assertAlmostEqual(float(right['week_expected_movements']) /
                                   float(left['week_expected_movements']), 3, delta=.002)
            self.assertEqual(left['event_excess_percent'], right['event_excess_percent'])

    def test_bookings_block_linear_share_scaling(self):
        totals = sensitivity_review.read_csv(sensitivity_review.HERE / 'daily_totals.csv')
        planning = sensitivity_review.read_csv(
            sensitivity_review.HERE / 'provisional_inputs' / 'planning_inputs.csv')
        planning[0]['reserved_arrivals'] = '1'
        with self.assertRaisesRegex(ValueError, 'zero reservation floors'):
            sensitivity_review.forecast_sensitivity(totals, planning, .05)

    def test_public_analogs_do_not_all_fit_scenario_band(self):
        evidence = json.loads((sensitivity_review.HERE / 'provisional_inputs' /
                               'event_evidence.json').read_text(encoding='utf-8'))
        analogs = sensitivity_review.read_csv(
            sensitivity_review.HERE / 'calibration_evidence' / 'super_bowl_analog_summary.csv')
        rows = sensitivity_review.analog_check(analogs, evidence)
        by_event = {row['event']: row for row in rows}
        self.assertEqual(by_event['LVII_2023_Phoenix']['position'], 'below_low')
        self.assertEqual(by_event['LVIII_2024_Las_Vegas']['position'], 'within_low_high')
        self.assertEqual(by_event['LIX_2025_New_Orleans']['position'], 'above_high')
        self.assertTrue(all(row['fbo_transfer_validated'] == 'no' for row in rows))

    def test_large_event_stress_exceeds_current_high(self):
        totals = sensitivity_review.read_csv(sensitivity_review.HERE / 'daily_totals.csv')
        evidence = json.loads((sensitivity_review.HERE / 'provisional_inputs' /
                               'event_evidence.json').read_text(encoding='utf-8'))
        hosts = sensitivity_review.read_csv(sensitivity_review.ROOT / 'sources' / 'airport_traffic' /
                                            'data' / 'processed' / 'superbowl_hosts_excess.csv')
        cases = {row['case']: row for row in sensitivity_review.event_stress_cases(
            totals, evidence, hosts)}
        self.assertGreater(float(cases['bay_area_LX_air_taxi']['five_day_expected_movements']),
                           float(cases['current_high']['five_day_expected_movements']))
        self.assertTrue(all(row['fbo_transfer_validated'] == 'no' for row in cases.values()))


if __name__ == '__main__':
    unittest.main()
