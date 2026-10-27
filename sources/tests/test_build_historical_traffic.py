"""Conservation, coverage and provenance checks for the Step 3a handoff.

Rewritten for the v2 (Part 91 GA-only, daily-direct) pipeline -- the v1
tests exercised a monthly air_taxi+general_aviation input and a
load_months/validate_daily API that no longer exist after the team's
private-only scope decision (see
sources/docs/traffic_categories_and_fleet_mix.md section 1.4).
"""
import csv
from decimal import Decimal
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

DATA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DATA / 'scripts'))
import build_historical_traffic as pipeline


class HistoricalTrafficTests(unittest.TestCase):
    def source(self):
        return pipeline.INPUT.read_text(encoding='utf-8-sig')

    def changed_source(self, change):
        reader = csv.DictReader(io.StringIO(self.source()))
        rows = list(reader)
        change(rows)
        out = io.StringIO()
        fieldnames = list(dict.fromkeys([*reader.fieldnames, *(k for r in rows for k in r)]))
        writer = csv.DictWriter(out, fieldnames=fieldnames, restval='')
        writer.writeheader()
        writer.writerows(rows)
        return out.getvalue()

    def test_real_input_coverage_and_date_range(self):
        rows, ignored = pipeline.load_daily(self.source())
        daily = pipeline.convert(rows)
        self.assertEqual((len(rows), len(daily)), (4018, 4018))
        self.assertEqual(ignored, 0)
        self.assertEqual((daily[0]['date'], daily[-1]['date']), ('2015-01-01', '2025-12-31'))
        self.assertEqual(sum(r['excluded_covid'] == 'True' for r in daily), 1096)
        self.assertEqual(sum(r['date'].startswith('2022-02-') for r in daily), 28)
        self.assertIn('2020-02-29', {r['date'] for r in daily})
        self.assertIn('2024-02-29', {r['date'] for r in daily})
        months_checked = pipeline.validate_against_monthly(rows, pipeline.MONTHLY_CHECK)
        self.assertEqual(months_checked, 132)
        for d, r in rows.items():
            daily_row = next(x for x in daily if x['date'] == d.isoformat())
            total = r['general_aviation']
            for field in ('arrivals', 'departures'):
                self.assertEqual(Decimal(daily_row[field]), total / 2)

    def test_provenance_and_schema(self):
        rows, _ = pipeline.load_daily(self.source())
        daily = pipeline.convert(rows)
        for row in daily:
            self.assertEqual(set(row), set(pipeline.FIELDS))
            self.assertEqual(row['data_class'], 'estimated')
            self.assertIn('rule=daily_direct_v2_ga_only', row['source'])
            self.assertIn('arrivals_share=0.5; departures_share=0.5', row['source'])
            self.assertIn('scope=part91_general_aviation_only', row['source'])
        excluded = next(r for r in daily if r['date'] == '2022-02-13')
        self.assertEqual(excluded['excluded_covid'], 'True')
        ordinary = next(r for r in daily if r['date'] == '2025-09-01')
        self.assertEqual(ordinary['excluded_covid'], 'False')

    def test_missing_and_duplicate_dates_fail(self):
        source = self.changed_source(lambda rows: rows.remove(next(r for r in rows if r['date'] == '2022-02-14')))
        with self.assertRaisesRegex(ValueError, 'Missing 1 day'):
            pipeline.load_daily(source)
        source = self.changed_source(lambda rows: rows.append(next(r.copy() for r in rows if r['date'] == '2016-06-01')))
        with self.assertRaisesRegex(ValueError, 'Duplicate date'):
            pipeline.load_daily(source)

    def test_invalid_values_and_missing_fields_fail(self):
        for field, value in (('general_aviation', ''), ('general_aviation', '-1'),
                             ('general_aviation', 'NaN'), ('general_aviation', 'Infinity'),
                             ('general_aviation', '1.5'), ('excluded_covid', 'False'),
                             ('source_url', '')):
            with self.subTest(field=field, value=value):
                def change(rows):
                    next(r for r in rows if r['date'] == '2020-06-15')[field] = value
                with self.assertRaises(ValueError):
                    pipeline.load_daily(self.changed_source(change))

    def test_zero_is_valid_and_other_locids_are_ignored(self):
        def change(rows):
            row = next(r for r in rows if r['date'] == '2019-06-01')
            row['general_aviation'] = '0'
            rows.append({**row, 'date': '2019-06-01', 'locid': 'SJC', 'general_aviation': '999999'})
        rows, ignored = pipeline.load_daily(self.changed_source(change))
        self.assertEqual(ignored, 1)
        daily = pipeline.convert(rows)
        target = next(r for r in daily if r['date'] == '2019-06-01')
        self.assertEqual(Decimal(target['arrivals']), 0)
        self.assertEqual(Decimal(target['departures']), 0)

    def test_cli_roundtrip_is_reproducible_from_another_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'daily.csv'
            command = [sys.executable, str(DATA / 'scripts/build_historical_traffic.py'), '--output', str(output)]
            subprocess.run(command, cwd=tmp, check=True, capture_output=True)
            first = output.read_bytes()
            report = json.loads(output.with_suffix('.validation.json').read_text())
            self.assertEqual(report['daily_rows'], 4018)
            self.assertEqual(report['scope'], 'part91_general_aviation_only_no_air_taxi')
            subprocess.run(command, cwd=tmp, check=True, capture_output=True)
            self.assertEqual(first, output.read_bytes())

    def test_invalid_input_does_not_replace_previous_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / 'bad.csv', Path(tmp) / 'daily.csv'
            source.write_text('date,locid\n2022-02-01,LAX\n')
            output.write_text('existing output')
            with self.assertRaises(ValueError):
                pipeline.build(source, output, pipeline.MONTHLY_CHECK)
            self.assertEqual(output.read_text(), 'existing output')


if __name__ == '__main__':
    unittest.main()
