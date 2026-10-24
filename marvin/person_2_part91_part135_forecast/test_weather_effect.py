"""Checks for the observed NOAA × FAA weather analysis."""
import csv
import unittest
from datetime import date
from pathlib import Path

import weather_effect as weather


class WeatherEffectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.weather = weather.load_weather(weather.WEATHER_PATH)
        cls.days = weather.join_days(cls.weather, weather.load_operations(weather.OPS_PATH))
        cls.effects = weather.effect_rows(cls.days)

    def test_join_uses_only_requested_years(self):
        self.assertEqual({d['date'].year for d in self.days},
                         {2016, 2017, 2018, 2019, 2023, 2024, 2025})
        self.assertEqual(len(self.days), 365 * 7 + 2)
        self.assertFalse(any(2020 <= d['date'].year <= 2022 for d in self.days))

    def test_month_weekday_baseline_and_adjacent_fallback(self):
        days = [
            {'date': date(2024, 1, 1), 'types': {'dry_clear'}, 'part91_general_aviation': 100, 'part135_air_taxi': 200},
            {'date': date(2024, 1, 8), 'types': {'dry_clear'}, 'part91_general_aviation': 200, 'part135_air_taxi': 300},
            {'date': date(2024, 1, 15), 'types': {'rain'}, 'part91_general_aviation': 75, 'part135_air_taxi': 125},
            {'date': date(2024, 2, 5), 'types': {'dry_clear'}, 'part91_general_aviation': 300, 'part135_air_taxi': 400},
            {'date': date(2024, 2, 12), 'types': {'rain'}, 'part91_general_aviation': 80, 'part135_air_taxi': 160},
        ]
        weather.add_expected(days)
        self.assertEqual(days[2]['expected_part91_general_aviation'], 150)
        self.assertEqual(days[4]['expected_part91_general_aviation'], 200)
        self.assertEqual(days[4]['expected_part135_air_taxi'], 300)

    def test_missing_operations_do_not_count_as_baseline_days(self):
        days = [
            {'date': date(2024, 1, 1), 'types': {'dry_clear'}, 'part91_general_aviation': 100, 'part135_air_taxi': 200},
            {'date': date(2024, 1, 8), 'types': {'dry_clear'}, 'part91_general_aviation': None, 'part135_air_taxi': 300},
            {'date': date(2024, 1, 15), 'types': {'rain'}, 'part91_general_aviation': 75, 'part135_air_taxi': 125},
            {'date': date(2024, 2, 5), 'types': {'dry_clear'}, 'part91_general_aviation': 300, 'part135_air_taxi': 400},
        ]
        weather.add_expected(days)
        self.assertEqual(days[2]['expected_part91_general_aviation'], 200)
        self.assertEqual(days[2]['expected_part135_air_taxi'], 250)

    def test_effect_intervals_and_dry_reference(self):
        self.assertEqual(len(self.effects), 24)
        for row in self.effects:
            self.assertLessEqual(float(row['ci_low']), float(row['effect']))
            self.assertLessEqual(float(row['effect']), float(row['ci_high']))
            self.assertGreater(int(row['n_days']), 0)
        long_dry = [r for r in self.effects if r['window'] == '2016-2019+2023-2025'
                    and r['weather_type'] == 'dry_clear']
        self.assertEqual(len(long_dry), 2)
        self.assertTrue(all(abs(float(r['effect'])) < 0.05 for r in long_dry))

    def test_climatology_shares_are_probabilities(self):
        rows = weather.climatology_rows(self.weather)
        shares = [r for r in rows if r['metric'] == 'february_day_share']
        self.assertEqual({r['weather_type'] for r in shares}, set(weather.WEATHER_TYPES))
        self.assertTrue(all(0 <= float(r['value']) <= 1 for r in shares))
        self.assertTrue(all(int(r['n_years']) == 12 for r in shares))
        self.assertTrue(all(int(r['n_days']) == 339 for r in shares))

    def test_main_is_byte_identical_on_rerun(self):
        paths = [Path(weather.RESULTS_DIR, name) for name in
                 ('weather_effect_measured.csv', 'weather_feb_climatology.csv')]
        weather.main()
        first = [p.read_bytes() for p in paths]
        weather.main()
        self.assertEqual(first, [p.read_bytes() for p in paths])
        with paths[0].open(newline='') as f:
            self.assertEqual(len(list(csv.DictReader(f))), 24)


if __name__ == '__main__':
    unittest.main()
