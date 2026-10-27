"""agent_data.json (the FBO agent app's only data file): it matches the team's committed outputs, it is
internally consistent, and the numbers we say in the presentation are true."""
import contextlib
import csv
import io
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[2]
APP_DATA=REPO/'agent_gemini'/'agent_data.json'
KIT_DATA=REPO/'site_kit'/'agent_data.json'
P2=REPO/'forecast'/'main_forecast'
PKG=REPO/'forecast'/'category_forecast'/'results'
SCENARIOS=('Low','Medium','High')

def rows(path):
    with open(path,newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def clock(t):h,m=t.split(':');return int(h)+int(m)/60
def peak_window(shares,n=3):
    return max(range(25-n),key=lambda h:(sum(shares[h:h+n]),-h))
def without_timestamp(d):
    d=json.loads(json.dumps(d));d['meta'].pop('generated_utc',None);return d

class AgentDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads(APP_DATA.read_text(encoding='utf-8'))
        cls.days={d['date']:d for d in cls.data['days']}

    # --- the file is the team's data, not a stale or hand-edited copy ---
    def test_app_and_site_kit_copies_are_identical(self):
        self.assertEqual(APP_DATA.read_bytes(),KIT_DATA.read_bytes(),'run the export and copy site_kit/agent_data.json to agent_gemini/')
    def test_export_script_reproduces_the_committed_file(self):
        spec=importlib.util.spec_from_file_location('export_agent_data',REPO/'site_kit'/'export_agent_data.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as tmp:
            mod.OUT=Path(tmp)/'agent_data.json'
            with contextlib.redirect_stdout(io.StringIO()):mod.main()
            fresh=json.loads(mod.OUT.read_text(encoding='utf-8'))
        self.assertEqual(without_timestamp(fresh),without_timestamp(self.data),'agent_data.json is out of date: run python site_kit/export_agent_data.py')
    def test_daily_numbers_match_the_forecast(self):
        for r in rows(P2/'daily_totals.csv'):
            s=self.days[r['date']]['scenarios'][r['scenario']]
            for k in ('arrivals','departures'):
                self.assertAlmostEqual(s['expected_'+k],float(r['expected_'+k]),places=3)
                self.assertAlmostEqual(s['ordinary_'+k],float(r['baseline_'+k]),places=3)
    def test_parking_matches_elias_model(self):
        for r in rows(REPO/'parking'/'resource_requirements.csv'):
            s=self.days[r['date']]['scenarios'][r['scenario']]
            self.assertEqual(s['parking_su_p90'],float(r['parking_demand_su_p90']))
            self.assertEqual(s['ramp_capacity_su'],float(r['capacity_normal_su']))
            self.assertEqual(s['prob_ramp_full'],float(r['prob_over_normal_capacity']))
    def test_restriction_matches_the_data_file(self):
        sec=rows(REPO/'sources'/'data'/'processed'/'security_restriction_model_input.csv')[0]
        g=self.data['game_day_restriction']
        self.assertEqual((g['date'],g['start'],g['end']),(sec['date'],sec['start_time_local'],sec['end_time_local']))
        self.assertTrue(self.days[g['date']]['security_restriction'])
        self.assertEqual(sum(d['security_restriction'] for d in self.data['days']),1)
    def test_weather_effects_match_measured_file(self):
        for r in rows(PKG/'weather_effect_measured.csv'):
            if r['window']!='2016-2019+2023-2025' or r['weather_type'] not in self.data['weather']['effects']:continue
            part='part91' if r['category'].startswith('part91') else 'part135'
            self.assertAlmostEqual(self.data['weather']['effects'][r['weather_type']][part]['effect'],float(r['effect']),delta=0.0006)  # exported to 3 decimals
    def test_accuracy_matches_backtest(self):
        wape=self.data['accuracy']['rolling_backtest_2025_wape']
        for r in rows(P2/'backtest_metrics.csv'):
            if r['target']=='arrivals' and r['window']=='all_2025_origins':
                self.assertAlmostEqual(wape[r['model']],float(r['wape']),places=3)

    # --- the file makes sense on its own ---
    def test_planning_week_is_seven_consecutive_days(self):
        dates=[d['date'] for d in self.data['days']]
        self.assertEqual(dates,[f'2027-02-{d}' for d in range(11,18)])
        self.assertEqual(self.data['meta']['planning_window'],[dates[0],dates[-1]])
        self.assertTrue(self.days['2027-02-14']['game_day'])
        self.assertEqual(self.days['2027-02-14']['weekday'],'Sunday')
    def test_every_day_has_sane_numbers(self):
        for d in self.data['days']:
            for name in SCENARIOS:
                s=d['scenarios'][name]
                with self.subTest(date=d['date'],scenario=name):
                    for k in ('arrivals','departures'):
                        lo,hi=s[k+'_range90']
                        self.assertGreaterEqual(lo,0);self.assertLessEqual(lo,s['expected_'+k]);self.assertLessEqual(s['expected_'+k],hi)
                    self.assertAlmostEqual(s['share_part91']+s['share_part135'],1,places=3)
                    self.assertTrue(0<=s['prob_ramp_full']<=1)
                    self.assertLessEqual(s['parking_su_p50'],s['parking_su_p90'])
    def test_scenarios_are_ordered_and_share_the_ordinary_week(self):
        for d in self.data['days']:
            s=d['scenarios']
            for k in ('arrivals','departures'):
                with self.subTest(date=d['date'],target=k):
                    self.assertLessEqual(s['Low']['expected_'+k],s['Medium']['expected_'+k]+1e-9)
                    self.assertLessEqual(s['Medium']['expected_'+k],s['High']['expected_'+k]+1e-9)
                    self.assertEqual({s[n]['ordinary_'+k] for n in SCENARIOS},{s['Low']['ordinary_'+k]})
    def test_hour_shares_are_a_full_day(self):
        curves=dict(self.data['hourly_profile']['shares'])
        curves.update({'game_day_'+k:v for k,v in self.data['game_day_restriction']['hour_shares'].items()})
        self.assertEqual(set(self.data['hourly_profile']['shares']),{f'{d}_{t}' for d in ('weekday','weekend') for t in ('arrivals','departures')})
        for name,c in curves.items():
            with self.subTest(curve=name):
                self.assertEqual(len(c),24);self.assertTrue(all(x>=0 for x in c));self.assertAlmostEqual(sum(c),1,places=3)
    def test_no_movements_during_the_game_day_pause(self):
        g=self.data['game_day_restriction'];start,end=clock(g['start']),clock(g['end'])
        for t,c in g['hour_shares'].items():
            for h in range(24):
                if h>=start and h+1<=end:self.assertEqual(c[h],0,f'{t} at {h}:00 is inside the pause')
    def test_only_the_super_bowl_days_change_between_scenarios(self):
        for d in self.data['days']:
            changes=any(d['scenarios']['Low'][k]!=d['scenarios']['High'][k] for k in ('expected_arrivals','expected_departures'))
            self.assertEqual(changes,'2027-02-11'<=d['date']<='2027-02-15',d['date'])

    # --- what we say in the presentation ---
    def test_model_beats_all_four_simple_methods(self):
        wape=self.data['accuracy']['rolling_backtest_2025_wape'];model=wape.pop('model')
        self.assertEqual(len(wape),4);self.assertAlmostEqual(model,0.149,places=3)
        for name,v in wape.items():self.assertLess(model,v,name)
        self.assertAlmostEqual(self.data['accuracy']['coverage_90'],0.879,places=3)
    def test_super_bowl_effect_sizes(self):
        self.assertIn('+3.1%',self.data['scenarios']['Low']);self.assertIn('+15.5%',self.data['scenarios']['Medium']);self.assertIn('+31%',self.data['scenarios']['High'])
        excess=[float(r['excess']) for r in self.data['super_bowl_test'] if r['metric']=='private']
        self.assertAlmostEqual(min(excess),-0.323,places=3);self.assertAlmostEqual(max(excess),0.813,places=3)
    def test_friday_has_the_most_landings_and_monday_the_most_departures(self):
        med={d['weekday']:d['scenarios']['Medium'] for d in self.data['days']}
        self.assertEqual(max(med,key=lambda w:med[w]['expected_arrivals']),'Friday')
        self.assertEqual(max(med,key=lambda w:med[w]['expected_departures']),'Monday')
        self.assertAlmostEqual(med['Friday']['expected_arrivals'],7.3,delta=0.05)
        self.assertAlmostEqual(med['Monday']['expected_departures'],10.0,delta=0.05)
        self.assertEqual(round(100*(med['Friday']['expected_arrivals']/med['Friday']['ordinary_arrivals']-1)),44)
        self.assertEqual(round(100*(med['Monday']['expected_departures']/med['Monday']['ordinary_departures']-1)),55)
    def test_peak_hours(self):
        shares=self.data['hourly_profile']['shares']
        self.assertEqual(peak_window(shares['weekday_arrivals']),9,'Friday landings peak 09:00-12:00')
        self.assertEqual(peak_window(shares['weekday_departures']),7,'Monday departures peak 07:00-10:00')
    def test_sunday_departures_after_the_pause(self):
        g=self.data['game_day_restriction'];end=clock(g['end'])
        after=sum(v for h,v in enumerate(g['hour_shares']['departures']) if h+1>end)
        self.assertEqual(round(after*100),40)
    def test_no_personal_data(self):
        text=APP_DATA.read_text(encoding='utf-8').lower()
        for word in ('passenger_name','owner','email','phone','crew'):self.assertNotIn(word,text)

if __name__=='__main__':unittest.main()
