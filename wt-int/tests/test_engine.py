import copy
import sys
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import *


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.cfg=config()
        self.start,self.end=bounds(self.cfg)

    def test_three_aircraft_cross_midnight_and_exact_unit_hours(self):
        # Hand calculation: 23:00–00:00 light+midsize = 2.5 units;
        # 00:00–01:00 all three = 5; 01:00–02:00 light+large = 3.5.
        cfg=copy.deepcopy(self.cfg);cfg['main_ramp_units']=3;cfg['protected_reserve_units']=1
        visits=[Visit('V-001','light',self.start+timedelta(hours=23),self.start+timedelta(hours=26),'Estimated, not yet booked'),
                Visit('V-002','midsize',self.start+timedelta(hours=23),self.start+timedelta(hours=25),'Estimated, not yet booked'),
                Visit('V-003','large',self.start+timedelta(hours=24),self.start+timedelta(hours=26),'Estimated, not yet booked')]
        r=simulate(visits,cfg)
        self.assertEqual(r['peak_units'],5)
        self.assertEqual(r['shortage_unit_hours'],.5+3+1.5)
        self.assertEqual(r['shortage_hours'],3)
        self.assertEqual(r['first_shortage'],self.start+timedelta(hours=23))
        self.assertEqual([r['hourly'][i]['units'] for i in (23,24,25,26)],[2.5,5,3.5,0])

    def test_departure_boundary_does_not_double_count(self):
        visits=[Visit('V-001','large',self.start-timedelta(hours=2),self.start,'Estimated, not yet booked'),
                Visit('V-002','light',self.start,self.start+timedelta(hours=1),'Estimated, not yet booked'),
                Visit('V-003','midsize',self.start+timedelta(hours=1),self.end,'Estimated, not yet booked')]
        r=simulate(visits,self.cfg)
        self.assertEqual(r['peak_units'],1.5)
        self.assertEqual(r['closing_aircraft'],0)

    def test_subhour_shortage_integrates_duration(self):
        cfg=copy.deepcopy(self.cfg);cfg['main_ramp_units']=2;cfg['protected_reserve_units']=0
        visit=Visit('V-001','large',self.start+timedelta(minutes=15),self.start+timedelta(minutes=45),'Recorded reservation')
        r=simulate([visit],cfg)
        self.assertEqual(r['shortage_unit_hours'],.25)
        self.assertEqual(r['shortage_hours'],.5)

    def test_plan_preserves_demand_and_reserve(self):
        visits=generate_visits(self.cfg,self.cfg['demo']['daily_arrivals'])
        a=simulate(visits,self.cfg);b=simulate(visits,self.cfg,overflow=25)
        self.assertEqual(a['visits'],b['visits'])
        self.assertEqual(a['usable_main'],36)
        self.assertEqual(b['capacity'],61)
        self.assertLessEqual(b['peak_gap'],a['peak_gap'])
        self.assertEqual([r['units'] for r in a['hourly']],[r['units'] for r in b['hourly']])

    def test_delay_and_weather_restrictions_cannot_reduce_shortage(self):
        visits=generate_visits(self.cfg,self.cfg['demo']['daily_arrivals'])
        a=simulate(visits,self.cfg);b=simulate(visits,self.cfg,delay=6,unavailable=8)
        self.assertGreaterEqual(b['shortage_unit_hours'],a['shortage_unit_hours'])
        self.assertEqual(b['capacity'],28)
        self.assertEqual(len(a['visits']),len(b['visits']))

    def test_marvin_source_all_days_cases_and_counts(self):
        rows,meta,sha=source_snapshot(self.cfg)
        for case in SCENARIOS:
            counts,ordinary=arrival_counts(self.cfg,'marvin',case,rows)
            self.assertEqual(counts,[int(float(r['requested_land'])) for r in rows if r['scenario']==case])
            visits=generate_visits(self.cfg,counts,'marvin')
            r=simulate(visits,self.cfg)
            self.assertEqual([d['arrivals'] for d in r['daily']],counts)
        self.assertEqual(meta['fbo_capture_share'],.2)
        self.assertEqual(len(sha),64)

    def test_daily_change_carries_inventory_into_next_day(self):
        counts,ordinary=arrival_counts(self.cfg,'demo','Medium')
        changed=counts.copy();changed[3]+=10
        a=simulate(generate_visits(self.cfg,counts),self.cfg)
        b=simulate(generate_visits(self.cfg,changed),self.cfg)
        self.assertGreater(b['daily'][4]['peak_units'],a['daily'][4]['peak_units'])

    def test_holiday_changes_only_holiday_arrivals(self):
        normal,_=arrival_counts(self.cfg,'demo','Medium')
        extra,_=arrival_counts(self.cfg,'demo','Medium',holiday_pct=50)
        self.assertEqual([i for i in range(7) if normal[i]!=extra[i]],[4])

    def test_uploaded_visits_validate_identity_and_intervals(self):
        v=Visit('V-001','light',self.start,self.end,'Recorded reservation')
        self.assertEqual(parse_visits(visits_csv([v]).encode(),self.cfg),[v])
        for invalid in [replace(v,departure=self.start),replace(v,visit_id='N123AB'),replace(v,category='unknown')]:
            with self.assertRaises(ValueError):parse_visits(visits_csv([invalid]).encode(),self.cfg)
        with self.assertRaises(ValueError):parse_visits(visits_csv([v,v]).encode(),self.cfg)

    def test_input_hash_covers_weather_delay_and_capacity(self):
        a=digest(dict(cfg=self.cfg,delay=0,weather=False))
        self.assertNotEqual(a,digest(dict(cfg=self.cfg,delay=1,weather=False)))
        self.assertNotEqual(a,digest(dict(cfg=self.cfg,delay=0,weather=True)))


if __name__=='__main__':unittest.main()
