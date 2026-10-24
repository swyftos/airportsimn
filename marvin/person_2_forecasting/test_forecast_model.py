import copy
import tempfile
import unittest
from pathlib import Path
from datetime import date
import forecast_model as m

class ForecastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        h,p = m.make_demo(Path(cls.tmp.name))
        cls.history = m.load_history(h)
        cls.planning = m.read_csv(p)
        cls.pred,cls.intervals,cls.metrics = m.forecast(cls.history,cls.planning)
    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
    def test_output_shape_and_bounds(self):
        self.assertEqual(len(self.pred),63)
        self.assertEqual(len(self.intervals),126)
        self.assertEqual(len(self.metrics),6)
        for r in self.intervals:
            self.assertLessEqual(0,r['lower'])
            self.assertLessEqual(r['lower'],r['expected'])
            self.assertLessEqual(r['expected'],r['upper'])
            self.assertFalse(r['event_coverage_validated'])
    def test_scenarios_ordered(self):
        for d,c in {(r['date'],r['aircraft_category']) for r in self.pred}:
            rows = {r['scenario']:r for r in self.pred if r['date']==d and r['aircraft_category']==c}
            for t in m.TARGETS:
                values = [rows[s]['expected_'+t] for s in m.SCENARIOS]
                self.assertEqual(values, sorted(values))
    def test_reservations_not_double_counted(self):
        plan = copy.deepcopy(self.planning)
        plan[0]['reserved_arrivals'] = 1000
        result,_,_ = m.forecast(self.history,plan)
        for r in result[:3]:
            self.assertEqual(r['expected_arrivals'],900)
    def test_event_off_and_zero_reservations(self):
        plan = copy.deepcopy(self.planning)
        for r in plan:
            r.update(event_indicator=0,reserved_arrivals=0,reserved_departures=0)
        result,_,_ = m.forecast(self.history,plan)
        for r in result:
            for t in m.TARGETS:
                self.assertEqual(r['expected_'+t],r['baseline_'+t])
    def test_test_period_does_not_leak(self):
        changed = copy.deepcopy(self.history)
        test_start = date.fromisoformat(self.metrics[0]['test_start'])
        for r in changed:
            if r['date'] >= test_start:
                r['arrivals'] += 500
        predictions,intervals,metrics = m.forecast(changed,self.planning)
        self.assertEqual(predictions,self.pred)
        self.assertEqual(intervals,self.intervals)
        self.assertNotEqual(metrics,self.metrics)
    def test_invalid_planning_rejected(self):
        with self.assertRaises(ValueError):
            m.forecast(self.history,self.planning[:-1])
        with self.assertRaises(ValueError):
            m.forecast(self.history,self.planning+[self.planning[0]])
        plan = copy.deepcopy(self.planning)
        plan[0]['arrivals_multiplier_low'] = 100
        with self.assertRaises(ValueError):
            m.forecast(self.history,plan)
        plan = copy.deepcopy(self.planning)
        plan[0]['reserved_arrivals'] = 'nan'
        with self.assertRaises(ValueError):
            m.forecast(self.history,plan)
    def test_provenance_exclusions_and_quantile(self):
        self.assertFalse(any(r['date'].year in m.EXCLUDED for r in self.history))
        self.assertTrue(all(r['evaluation_type']=='non_observed_demonstration' for r in self.metrics))
        self.assertEqual(m.conformal_radius(list(range(1,20)),.9),18)
    def test_airport_scope_rejected(self):
        row = dict(self.history[0],date=str(self.history[0]['date']),scope='airport')
        p = Path(self.tmp.name)/'invalid.csv'
        m.write_csv(p,[row])
        with self.assertRaises(ValueError):
            m.load_history(p)


    def test_pre_covid_rows_cannot_change_forecast_or_metrics(self):
        old = [dict(r, date=r['date'].replace(year=2019), arrivals=1000000, departures=1000000)
               for r in self.history if r['date'].year == 2023]
        self.assertEqual(m.forecast(old + self.history, self.planning),
                         (self.pred, self.intervals, self.metrics))
        with self.assertRaises(ValueError):
            m.forecast(old, self.planning)

    def test_postcovid_conversion_and_splits(self):
        from convert_monthly_to_daily import convert
        rows, months = convert()
        self.assertEqual(len(rows), 3288)
        self.assertEqual(len(months), 36)
        self.assertTrue(all('2023-01-01' <= r['date'] <= '2025-12-31' for r in rows))
        self.assertEqual(sum(r['date'] == '2024-02-29' for r in rows), 3)
        self.assertTrue(all(r['data_class'] == 'estimated' for r in rows))
        for metric in self.metrics:
            self.assertEqual((metric['train_rows'], metric['calibration_rows'], metric['test_rows']), (657,219,220))
            self.assertTrue('2023-01-01' <= metric['train_end'] < metric['calibration_start'] < metric['test_start'] <= '2025-12-31')



    def test_faa_event_anchor_and_no_demo_reservation_override(self):
        from build_event_inputs import build
        from convert_monthly_to_daily import convert
        rows, _ = convert()
        path = Path(self.tmp.name)/'estimated_history.csv'
        m.write_csv(path, rows)
        planning, evidence = build(path)
        forecast, _, _ = m.forecast(m.load_history(path), planning)
        event = [r for r in forecast if r['date'] <= '2027-02-15' and r['scenario']=='Medium']
        for t in m.TARGETS:
            baseline = sum(r['baseline_'+t] for r in event)
            predicted = sum(r['expected_'+t] for r in event)
            self.assertAlmostEqual(predicted/baseline-1, .155, places=4)
        self.assertTrue(all(r['reserved_arrivals']==0 and r['reserved_departures']==0 for r in planning))
        self.assertTrue(all(r['arrivals_reservation_floor']==0 and r['departures_reservation_floor']==0 for r in forecast))
        self.assertFalse(evidence['observed_directional_split'])
        for r in forecast:
            self.assertEqual(r['arrivals_multiplier'],r['departures_multiplier'])
            if r['scenario']=='Low' or r['date'] > '2027-02-15':
                self.assertEqual(r['arrivals_multiplier'],1)

if __name__ == '__main__':
    unittest.main()

