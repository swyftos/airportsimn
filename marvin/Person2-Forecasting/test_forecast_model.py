"""Run: python test_forecast_model.py. Tests do not assert invented real-world accuracy."""
import io
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
import forecast_model as m

ROOT=Path(__file__).resolve().parent

class ForecastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=pd.read_csv(ROOT/'demand_predictions.csv')
        cls.u=pd.read_csv(ROOT/'uncertainty_results.csv')
        cls.h=pd.read_csv(ROOT/'historical_traffic_demo.csv',parse_dates=['date'])

    def test_seven_day_window(self):
        self.assertEqual(sorted(self.p.date.unique()),[str(d.date()) for d in pd.date_range('2027-02-11',periods=7)])
    def test_full_cross_product(self):
        self.assertEqual(len(self.p),126)
        self.assertFalse(self.p.duplicated(['date','scenario','aircraft_category','direction']).any())
    def test_nonnegative(self):
        self.assertTrue(np.isfinite(self.p.expected_movements).all())
        self.assertTrue((self.p.expected_movements>=0).all())
    def test_scenarios_ordered(self):
        t=self.p.pivot(index=['date','aircraft_category','direction'],columns='scenario',values='expected_movements')
        self.assertTrue(((t.Low<=t.Medium)&(t.Medium<=t.High)).all())
    def test_booking_floor_no_double_count(self):
        expected=np.maximum(self.p.learned_normal_forecast*self.p.event_multiplier,self.p.reserved_movements*self.p.booking_show_rate)
        np.testing.assert_allclose(self.p.expected_movements,expected,atol=.001)
    def test_prediction_bounds(self):
        self.assertTrue((self.u.lower90_prediction>=0).all())
        self.assertTrue((self.u.lower90_prediction<=self.u.expected_movements).all())
        self.assertTrue((self.u.expected_movements<=self.u.upper90_prediction).all())
        self.assertTrue((self.u.lower90_mean<=self.u.upper90_mean).all())
    def test_matching_uncertainty_keys(self):
        key=['date','scenario','aircraft_category','direction']
        self.assertEqual(len(self.p.merge(self.u,on=key,validate='one_to_one')),126)
        self.assertFalse(self.u.event_coverage_validated.any())
    def test_explanations_reconcile(self):
        e=pd.read_csv(ROOT/'prediction_explanations.csv')
        np.testing.assert_allclose(e.normal_forecast+e.event_addition+e.booking_floor_addition,e.expected_movements,atol=.001)
    def test_demo_provenance(self):
        self.assertEqual(set(self.h.data_classification),{'synthetic'})
        e=pd.read_csv(ROOT/'evaluation_metrics.csv')
        self.assertEqual(set(e.evaluation_data),{'synthetic'})
    def test_total_reconciliation(self):
        expected=self.p.groupby(['date','scenario','direction']).expected_movements.sum()
        actual=pd.read_csv(ROOT/'daily_summary.csv').set_index(['date','scenario','direction']).expected_movements
        np.testing.assert_allclose(expected.sort_index(),actual.sort_index(),atol=.001)
    def test_future_booking_snapshot_rejected(self):
        r=pd.read_csv(ROOT/'simulated_reservations.csv');r.loc[0,'as_of_date']='2027-02-01'
        with self.assertRaises(ValueError):m.validate_reservations(r,self.h.aircraft_category.unique(),pd.Timestamp('2026-10-23'))
    def test_negative_counts_rejected(self):
        h=self.h.copy();h.loc[0,'arrivals']=-1
        p=io.StringIO();h.to_csv(p,index=False);p.seek(0)
        with self.assertRaises(ValueError):m.load_history(p)
    def test_excluded_years_removed(self):
        h=self.h.copy();extra=h.iloc[[0]].copy();extra['date']=pd.Timestamp('2022-02-13')
        p=io.StringIO();pd.concat([h,extra]).to_csv(p,index=False);p.seek(0)
        self.assertNotIn(2022,set(m.load_history(p).date.dt.year))
    def test_no_within_block_target_leakage(self):
        g=self.h[self.h.aircraft_category=='large'].tail(365).copy()
        first=m.train(g,'arrivals');dates=first['test'].date.iloc[:7].tolist()
        changed=g.copy();changed.loc[changed.date.isin(dates),'arrivals']+=50
        second=m.train(changed,'arrivals')
        np.testing.assert_allclose(first['test'].predicted.iloc[:7],second['test'].predicted.iloc[:7])
    def test_vectorized_forecast_matches_single(self):
        g=self.h[self.h.aircraft_category=='large'].tail(365).copy();model=m.train(g,'arrivals')
        a=np.array([p for p,x in m.predict_baseline(model)])
        b=m.predict_many(model,np.array([model['beta']]))[0]
        np.testing.assert_allclose(a,b,rtol=1e-10)

if __name__=='__main__':unittest.main(verbosity=2)

