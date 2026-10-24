"""Cross-file checks for the selected-fleet Part 91/135 placeholder forecast."""
import csv
import hashlib
import json
import subprocess
import sys
import unittest
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'results'

def rows(name):
    with (OUT/name).open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

class OperationsReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(ROOT/'run_demo.py')], check=True, capture_output=True)

    def test_part_scope_and_reproducible_manifest(self):
        for name in ('demo_eligible_private_airport_pool.csv', 'capacity_plan.csv',
                     'daily_operational_plan.csv'):
            fields = list(rows(name)[0])
            self.assertFalse(any('part121' in x.lower() and x != 'excluded_part121' for x in fields))
        self.assertEqual({r['operation_part'] for r in rows('part_daily_totals.csv')}, {'part91','part135'})
        manifest = json.loads((OUT/'placeholder_manifest.json').read_text(encoding='utf-8'))
        for name, digest in manifest['files'].items():
            self.assertEqual(digest, hashlib.sha256((OUT/name).read_bytes()).hexdigest())
        self.assertEqual(json.loads((OUT/'operations_run_metadata.json').read_text())['status'], 'PLACEHOLDER')

    def test_hourly_curve_reconciles_to_daily_forecast(self):
        totals = {(r['date'], r['scenario']): r for r in rows('daily_totals.csv')}
        hourly = defaultdict(lambda: [0.0, 0.0])
        for r in rows('hourly_activity_curve.csv'):
            key = r['date'], r['scenario']
            hourly[key][0] += float(r['expected_arrivals'])
            hourly[key][1] += float(r['expected_departures'])
        self.assertEqual(len(hourly), 21)
        for key, (arr, dep) in hourly.items():
            self.assertAlmostEqual(arr, float(totals[key]['expected_arrivals']), delta=.002)
            self.assertAlmostEqual(dep, float(totals[key]['expected_departures']), delta=.002)
        profiles = defaultdict(float)
        for r in rows('hourly_profile_weights.csv'):
            profiles[r['day_type'], r['target']] += float(r['fitted_hour_share'])
        for value in profiles.values():
            self.assertAlmostEqual(value, 1, delta=1e-6)

    def test_capacity_price_weather_and_security_sensitivities(self):
        capacity = rows('capacity_plan.csv')
        self.assertEqual(len(capacity), 21)
        for scenario in ('Low', 'Medium', 'High'):
            previous = None
            for r in [x for x in capacity if x['scenario']==scenario]:
                occupied = int(r['end_day_ground_if_demand_occurs'])
                self.assertGreaterEqual(occupied, 0)
                if previous is not None:
                    self.assertEqual(occupied,
                        max(0, previous + int(r['forecast_arrivals_rounded']) - int(r['forecast_departures_rounded'])))
                previous = occupied
                self.assertEqual(int(r['parking_overflow_to_resolve']),
                    max(0,int(r['projected_peak_ground'])-int(r['capacity_aircraft_equivalent'])))
                self.assertFalse(any(k in r for k in ('can_land','can_leave','unserved_land','unserved_leave')))
        rates = defaultdict(dict)
        for r in rows('parking_price_scenarios.csv'):
            rates[r['traffic_scenario'],r['aircraft_category']][r['arrival_slot']] = float(r['suggested_usd_per_24h'])
        for values in rates.values():
            self.assertLess(values['early_arrival'],values['other_arrival'])
        weather = defaultdict(dict)
        for r in rows('weather_sensitivity.csv'):
            weather[r['date'],r['scenario']][r['condition']] = r
            self.assertEqual(r['demand_changed'], 'no')
        for group in weather.values():
            self.assertLess(float(group['clear_placeholder']['landing_to_park_minutes']),
                            float(group['rain_placeholder']['landing_to_park_minutes']))
            self.assertLess(float(group['rain_placeholder']['landing_to_park_minutes']),
                            float(group['low_visibility_placeholder']['landing_to_park_minutes']))
        self.assertEqual(len(rows('presidential_security_sensitivity.csv')), 9)
        for r in rows('presidential_security_sensitivity.csv'):
            self.assertEqual(r['president_visit_known'], 'no')
            self.assertEqual(r['airport_closure_required'], 'not_established')

if __name__ == '__main__':
    unittest.main()
