import copy
import tempfile
import unittest
from pathlib import Path
from datetime import date, timedelta
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
    def test_holdout_metrics_use_earlier_data_and_forecast_refits(self):
        changed = copy.deepcopy(self.history)
        test_start = date.fromisoformat(self.metrics[0]['test_start'])
        for r in changed:
            if r['date'] >= test_start:
                r['arrivals'] += 500
        predictions,intervals,metrics = m.forecast(changed,self.planning)
        # The evaluated model and its calibration radius never see the test period ...
        for old, new in zip(self.metrics, metrics):
            self.assertEqual((old['baseline_radius'], old['train_end']), (new['baseline_radius'], new['train_end']))
            if new['target'] == 'arrivals':
                self.assertGreater(new['model_mae'], old['model_mae'])
        # ... while the final forecast refits on every day, the most recent included.
        self.assertNotEqual(predictions,self.pred)
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
        for scenario, excess in (('Low', .031), ('Medium', .155), ('High', .31)):
            event = [r for r in forecast if r['date'] <= '2027-02-15' and r['scenario']==scenario]
            baseline = sum(r['baseline_'+t] for r in event for t in m.TARGETS)
            predicted = sum(r['expected_'+t] for r in event for t in m.TARGETS)
            self.assertAlmostEqual(predicted/baseline-1, excess, places=3)
        event = [r for r in forecast if r['date'] <= '2027-02-15' and r['scenario']=='Medium']
        extra = {t: sum(r['expected_'+t]-r['baseline_'+t] for r in event) for t in m.TARGETS}
        self.assertAlmostEqual(extra['arrivals'], extra['departures'], places=2)  # outputs rounded to 3 decimals
        self.assertTrue(all(r['reserved_arrivals']==0 and r['reserved_departures']==0 for r in planning))
        self.assertTrue(all(r['arrivals_reservation_floor']==0 and r['departures_reservation_floor']==0 for r in forecast))
        self.assertFalse(evidence['observed_directional_split'])
        for r in forecast:
            if r['date'] > '2027-02-15':
                self.assertEqual(r['arrivals_multiplier'],1)
                self.assertEqual(r['departures_multiplier'],1)
            if r['date'] == '2027-02-15':
                self.assertEqual(r['arrivals_multiplier'],1)
            if r['date'] < '2027-02-14':
                self.assertEqual(r['departures_multiplier'],1)
    def test_presidents_day_effect_is_learned_from_history(self):
        self.assertEqual(m.presidents_day(2027), date(2027,2,15))
        self.assertEqual(m.presidents_day(2025), date(2025,2,17))
        from convert_monthly_to_daily import convert
        rows, _ = convert()
        path = Path(self.tmp.name)/'ga_history.csv'
        m.write_csv(path, rows)
        fitted, _ = m.fit_and_evaluate(m.load_history(path), .9)
        model = fitted['light_jet','arrivals'][0]
        holiday = model.holiday['presidents_day']
        self.assertGreater(holiday, 1)
        self.assertAlmostEqual(model.predict(date(2027,2,15)), model.ordinary(date(2027,2,15))*holiday)
        self.assertEqual(model.predict(date(2027,2,22)), model.ordinary(date(2027,2,22)))

    def test_holiday_ratio_uses_neighbouring_weeks(self):
        rows = [dict(date=date(2024,2,19)+timedelta(weeks=k), arrivals=10.0) for k in (-3,-2,-1,1,2,3)]
        rows.append(dict(date=date(2024,2,19), arrivals=13.0))
        self.assertAlmostEqual(m.holiday_factors(rows,'arrivals')['presidents_day'], 1.3)
        model = m.SeasonalModel(rows,'arrivals',{'presidents_day':2.0})
        self.assertAlmostEqual(model.predict(date(2027,2,15)), 2*model.ordinary(date(2027,2,15)))
        long = m.load_holiday_history(Path(__file__).resolve().parent/'provisional_inputs/holiday_history.csv')
        self.assertEqual({r['date'].year for r in long}, {2016,2017,2018,2019,2023,2024,2025})
        self.assertGreater(m.holiday_factors(long,'arrivals')['presidents_day'], 1)

if __name__ == '__main__':
    unittest.main()

