import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path
from datetime import date

# Both Marvin packages have a forecast_model.py. Load this package's model by path
# so a repository-wide pytest run cannot reuse the other one from sys.modules.
_model_path = Path(__file__).with_name('forecast_model.py')
_spec = importlib.util.spec_from_file_location('part_forecast_model', _model_path)
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

class ForecastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        h,p = m.build_faa_inputs(Path(cls.tmp.name))
        cls.history = m.load_history(h)
        cls.planning = m.read_csv(p)
        cls.pred,cls.intervals,cls.metrics = m.forecast(cls.history,cls.planning)
    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
    def test_output_shape_and_bounds(self):
        self.assertEqual(len(self.pred),63)
        self.assertEqual(len(self.intervals),126)
        self.assertEqual(len(self.metrics),12)
        self.assertEqual({r['operation_part'] for r in self.metrics}, {'part91','part135'})
        for r in self.intervals:
            self.assertLessEqual(0,r['lower'])
            self.assertLessEqual(r['lower'],r['expected'])
            self.assertLessEqual(r['expected'],r['upper'])
            self.assertFalse(r['event_coverage_validated'])

    def test_planning_forecasts_never_negative(self):
        for row in self.pred:
            for target in m.TARGETS:
                with self.subTest(date=row['date'], scenario=row['scenario'],
                                  category=row['aircraft_category'], target=target):
                    for prefix in ('baseline_', 'expected_'):
                        self.assertGreaterEqual(row[prefix + target], 0)
                    self.assertGreaterEqual(row[target + '_lower'], 0)
                    self.assertGreaterEqual(row[target + '_upper'], 0)
    def test_scenarios_ordered(self):
        for d,c in {(r['date'],r['aircraft_category']) for r in self.pred}:
            rows = {r['scenario']:r for r in self.pred if r['date']==d and r['aircraft_category']==c}
            for t in m.TARGETS:
                values = [rows[s]['expected_'+t] for s in m.SCENARIOS]
                self.assertEqual(values, sorted(values))
    def test_reservations_not_double_counted(self):
        plan = copy.deepcopy(self.planning)
        key = (plan[0]['date'], plan[0]['aircraft_category'])
        for r in plan:
            if (r['date'],r['aircraft_category']) == key:
                r['reserved_arrivals'] = 1000
                r['reservation_show_rate'] = .9
        result,_,_ = m.forecast(self.history,plan)
        for r in result:
            if (r['date'],r['aircraft_category']) == key:
                self.assertEqual(r['expected_arrivals'],1800)
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

    def test_part121_rejected(self):
        row = dict(self.history[0],date=str(self.history[0]['date']),operation_part='part121')
        p = Path(self.tmp.name)/'part121.csv'
        m.write_csv(p,[row])
        with self.assertRaises(ValueError):
            m.load_history(p)
        planning = copy.deepcopy(self.planning)
        planning[0]['operation_part'] = 'part121'
        with self.assertRaises(ValueError):
            m.forecast(self.history,planning)


    def test_faa_inputs_reproducible_and_traceable(self):
        a = Path(self.tmp.name)/'a'; b = Path(self.tmp.name)/'b'
        a.mkdir(); b.mkdir()
        ah,ap=m.build_faa_inputs(a); bh,bp=m.build_faa_inputs(b)
        self.assertEqual(ah.read_bytes(),bh.read_bytes())
        self.assertEqual(ap.read_bytes(),bp.read_bytes())
        raw=m.read_csv(ah)
        self.assertEqual(len(raw),1096*2*3)
        self.assertEqual({r['operation_part'] for r in raw}, {'part91','part135'})
        self.assertTrue(all(r['data_class']=='estimated' and 'aspm.faa.gov' in r['source'] for r in raw))
        faa = {r['date']: r for r in m.read_csv(m.FAA_DAILY)}
        for r in raw[:60]:
            column = m.PART_COLUMNS[r['operation_part']]
            expected = float(faa[r['date']][column])*m.PRIVATE_ELIGIBLE[r['operation_part']]*m.FBO_CAPTURE_SHARE*.5*m.AIRCRAFT_MIX[r['aircraft_category']]
            self.assertAlmostEqual(float(r['arrivals']), expected, places=5)
        self.assertAlmostEqual(m.PRIVATE_ELIGIBLE['part91']*m.FBO_CAPTURE_SHARE, .10)
        for d, scenario in {(r['date'],r['scenario']) for r in self.pred}:
            group = [r for r in self.pred if r['date']==d and r['scenario']==scenario]
            total = sum(r['expected_arrivals'] for r in group)
            for r in group:
                self.assertAlmostEqual(r['expected_arrivals']/total,
                    m.AIRCRAFT_MIX[r['aircraft_category']], delta=.001)

    def test_measured_scenarios_and_part_aggregation(self):
        for scenario, excess in (('Low', .031), ('Medium', .155), ('High', .31)):
            event = [r for r in self.pred if r['date'] <= '2027-02-15' and r['scenario']==scenario]
            baseline = sum(r['baseline_'+t] for r in event for t in m.TARGETS)
            predicted = sum(r['expected_'+t] for r in event for t in m.TARGETS)
            self.assertAlmostEqual(predicted/baseline-1, excess, places=3)
        for r in self.pred:
            if r['date'] > '2027-02-15':
                self.assertEqual(r['expected_arrivals'], r['baseline_arrivals'])
        aggregate,_,_,by_part = m.forecast_parts(self.history,self.planning)
        for r in aggregate:
            group=[x for x in by_part if (x['date'],x['scenario'],x['aircraft_category']) ==
                   (r['date'],r['scenario'],r['aircraft_category'])]
            self.assertEqual({x['operation_part'] for x in group},{'part91','part135'})
            for target in m.TARGETS:
                self.assertAlmostEqual(r['expected_'+target],sum(x['expected_'+target] for x in group),places=3)

    def test_presidents_day_effect_is_learned(self):
        self.assertEqual(m.presidents_day(2027), date(2027,2,15))
        fitted,_ = m.fit_and_evaluate(self.history,.9)
        model = fitted['light_jet','part91','arrivals'][0]
        self.assertNotEqual(model.holiday['presidents_day'], 1.0)
        self.assertAlmostEqual(model.predict(date(2027,2,15)), model.ordinary(date(2027,2,15))*model.holiday['presidents_day'])
        self.assertEqual(model.predict(date(2027,2,22)), model.ordinary(date(2027,2,22)))

if __name__ == '__main__':
    unittest.main()
