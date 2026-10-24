"""Conservation, coverage and provenance checks for the Step 3a handoff."""
import csv
from decimal import Decimal
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ALAN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ALAN / 'scripts'))
import build_historical_traffic as pipeline


class HistoricalTrafficTests(unittest.TestCase):
    def source(self):
        return pipeline.INPUT.read_text(encoding='utf-8-sig')

    def changed_source(self, change):
        reader = csv.DictReader(io.StringIO(self.source()))
        rows = list(reader)
        change(rows)
        out = io.StringIO()
        # keep columns a test adds (e.g. airline counts absent from the private-only source)
        fieldnames = list(dict.fromkeys([*reader.fieldnames, *(k for r in rows for k in r)]))
        writer = csv.DictWriter(out, fieldnames=fieldnames, restval='')
        writer.writeheader()
        writer.writerows(rows)
        return out.getvalue()

    def test_real_input_coverage_and_monthly_conservation(self):
        months, ignored = pipeline.load_months(self.source())
        daily, _ = pipeline.convert(months)
        self.assertEqual((len(months), len(daily)), (120, 3653))
        self.assertEqual(ignored, 20)
        self.assertEqual((daily[0]['date'], daily[-1]['date']), ('2016-01-01', '2025-12-31'))
        self.assertEqual(sum(r['excluded_covid'] == 'True' for r in daily), 1096)
        self.assertEqual(sum(r['date'].startswith('2022-02-') for r in daily), 28)
        self.assertIn('2020-02-29', {r['date'] for r in daily})
        self.assertIn('2024-02-29', {r['date'] for r in daily})
        self.assertLessEqual(pipeline.validate_daily(daily, months), pipeline.TOLERANCE)
        for key, original in months.items():
            rows = [r for r in daily if r['date'].startswith(f'{key[0]}-{key[1]:02}-')]
            expected = original['air_taxi'] + original['general_aviation']
            for field in ('arrivals', 'departures'):
                self.assertLessEqual(abs(sum(Decimal(r[field]) for r in rows) - expected / 2), pipeline.TOLERANCE)
            self.assertEqual(len({r['arrivals'] for r in rows}), 1)

    def test_provenance_and_intermediate_schema(self):
        daily, _ = pipeline.convert(pipeline.load_months(self.source())[0])
        for row in daily:
            self.assertEqual(set(row), set(pipeline.FIELDS))
            self.assertEqual(row['data_class'], 'estimated')
            self.assertIn('rule=uniform_calendar_days_v1', row['source'])
            self.assertIn('arrivals_share=0.5; departures_share=0.5', row['source'])
        residual = next(r for r in daily if r['date'] == '2025-09-01')
        self.assertIn('value_source=annual_residual', residual['source'])
        excluded = next(r for r in daily if r['date'] == '2022-02-13')
        self.assertEqual(excluded['excluded_covid'], 'True')

    def test_missing_and_duplicate_months_fail(self):
        source = self.changed_source(lambda rows: rows.remove(next(r for r in rows if r['year'] == '2022' and r['month'] == '2')))
        with self.assertRaisesRegex(ValueError, 'Missing months.*2022-02'):
            pipeline.load_months(source)
        source = self.changed_source(lambda rows: rows.append(next(r.copy() for r in rows if r['year'] == '2016')))
        with self.assertRaisesRegex(ValueError, 'Duplicate month'):
            pipeline.load_months(source)

    def test_invalid_counts_flags_and_missing_sources_fail(self):
        for field, value in (('air_taxi', ''), ('general_aviation', '-1'),
                             ('air_taxi', 'NaN'), ('air_taxi', 'Infinity'),
                             ('air_taxi', '1.5'), ('excluded_covid', 'False'), ('source_url', '')):
            with self.subTest(field=field, value=value):
                def change(rows):
                    next(r for r in rows if r['year'] == '2020')[field] = value
                with self.assertRaises(ValueError):
                    pipeline.load_months(self.changed_source(change))

    def test_zero_is_valid_and_unrelated_categories_are_not_used(self):
        def change(rows):
            row = next(r for r in rows if r['year'] == '2016')
            row.update(air_taxi='0', general_aviation='0', air_carrier='999999999', military='999999999')
        daily, _ = pipeline.convert(pipeline.load_months(self.changed_source(change))[0])
        self.assertEqual(Decimal(daily[0]['arrivals']), 0)
        self.assertEqual(Decimal(daily[0]['departures']), 0)

    def test_cli_roundtrip_is_reproducible_from_another_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'daily.csv'
            command = [sys.executable, str(ALAN / 'scripts/build_historical_traffic.py'), '--output', str(output)]
            subprocess.run(command, cwd=tmp, check=True, capture_output=True)
            first = output.read_bytes()
            report = json.loads(output.with_suffix('.validation.json').read_text())
            self.assertEqual(report['daily_rows'], 3653)
            with output.open() as f:
                pipeline.validate_daily(list(csv.DictReader(f)), pipeline.load_months(self.source())[0])
            subprocess.run(command, cwd=tmp, check=True, capture_output=True)
            self.assertEqual(first, output.read_bytes())

    def test_invalid_input_does_not_replace_previous_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / 'bad.csv', Path(tmp) / 'daily.csv'
            source.write_text('year,month\n2022,2\n')
            output.write_text('existing output')
            with self.assertRaises(ValueError):
                pipeline.build(source, output)
            self.assertEqual(output.read_text(), 'existing output')


if __name__ == '__main__':
    unittest.main()
