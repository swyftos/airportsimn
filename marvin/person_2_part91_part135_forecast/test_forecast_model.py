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
        self.assertEqual(len(self.metrics),12)
        self.assertEqual({r['operation_part'] for r in self.metrics}, {'part91','part135'})
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


    def test_placeholder_generation_reproducible_and_labeled(self):
        a = Path(self.tmp.name)/'a'; b = Path(self.tmp.name)/'b'
        a.mkdir(); b.mkdir()
        ah,ap=m.make_demo(a,42); bh,bp=m.make_demo(b,42)
        self.assertEqual(ah.read_bytes(),bh.read_bytes())
        self.assertEqual(ap.read_bytes(),bp.read_bytes())
        _,other=m.make_demo(b,43)
        self.assertNotEqual(ap.read_bytes(),other.read_bytes())
        raw=m.read_csv(ah)
        self.assertEqual(len(raw),21918)
        self.assertEqual({r['operation_part'] for r in raw}, {'part91','part135'})
        self.assertTrue(all(r['data_class']=='synthetic' and 'PLACEHOLDER' in r['source'] for r in raw))
        self.assertTrue(all('PLACEHOLDER' in r['assumption_source'] for r in m.read_csv(ap)))
        self.assertTrue(all(r['date'].year>=2023 for r in m.load_history(ah)))

        # FBO capture uses only eligible selected-fleet airport operations,
        # and the agreed 47/33/20 mix persists through the forecast.
        pool = m.read_csv(a/'demo_eligible_private_airport_pool.csv')
        for day in pool[:30]:
            self.assertEqual(float(day['fbo_capture_share']), .20)
            self.assertAlmostEqual(float(day['fbo_total_arrivals']),
                float(day['eligible_total_arrivals'])*.20)
            self.assertEqual(day['excluded_part121'], 'yes_not_in_pool')
            self.assertEqual(day['excluded_outside_fleets'], 'yes_not_in_pool')
            for target in m.TARGETS:
                self.assertEqual(float(day['eligible_total_'+target]),
                    float(day['eligible_part91_'+target])+float(day['eligible_part135_'+target]))
        first = [r for r in raw if r['date'] == pool[0]['date']]
        for r in first:
            self.assertAlmostEqual(float(r['arrivals']),
                float(pool[0]['eligible_'+r['operation_part']+'_arrivals'])*.20*m.AIRCRAFT_MIX[r['aircraft_category']], places=4)
        for d, scenario in {(r['date'],r['scenario']) for r in self.pred}:
            group = [r for r in self.pred if r['date']==d and r['scenario']==scenario]
            total = sum(r['expected_arrivals'] for r in group)
            for r in group:
                self.assertAlmostEqual(r['expected_arrivals']/total,
                    m.AIRCRAFT_MIX[r['aircraft_category']], delta=.0001)

    def test_part135_event_proxy_is_explicit_and_aggregates(self):
        for r in self.planning:
            if r['operation_part']=='part135':
                expected = 1.155 if '2027-02-12' <= r['date'] <= '2027-02-16' else 1.0
                self.assertEqual(float(r['arrivals_multiplier_medium']), expected)
                self.assertEqual(float(r['departures_multiplier_medium']), expected)
                self.assertIn('proxy_transferred_by_assumption',r['assumption_source'])
        aggregate,_,_,by_part = m.forecast_parts(self.history,self.planning)
        for r in aggregate:
            group=[x for x in by_part if (x['date'],x['scenario'],x['aircraft_category']) ==
                   (r['date'],r['scenario'],r['aircraft_category'])]
            self.assertEqual({x['operation_part'] for x in group},{'part91','part135'})
            for target in m.TARGETS:
                self.assertAlmostEqual(r['expected_'+target],sum(x['expected_'+target] for x in group),places=3)

if __name__ == '__main__':
    unittest.main()
