import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from readiness.contracts import ContractError, DATES
from readiness.what_if import plan, CATEGORIES
import test_readiness as existing_tests


def inventory_fixture():
    values = {'initial_transient_aircraft':10, 'dep_share_before_peak':.5,
              'mix_light':1, 'mix_midsize':0, 'mix_large':0,
              'su_light':1, 'su_midsize':1.5, 'su_large':2.5}
    return {'native':True, 'version':'fixture-v1', 'meta':{'airport':'LAX','fbo_name':'Test FBO','data_classification':'synthetic'},
            'assumptions':[{'id':k,'label':k,'value':str(v),'unit':'fixture','classification':'synthetic','source':'test','note':'fixture'} for k,v in values.items()],
            'resources':[{'date':d,'scenario':s,'variant':'standard','capacity_units':20} for d in DATES for s in ('low','medium','high')],
            'category_ranges':[{'date':d,'scenario':s,'category':c,'direction':direction,
                                'expected':(arr if direction=='arrivals' else 1) if c=='light_jet' else 0}
                               for d in DATES for s,arr in [('low',1),('medium',2),('high',4)]
                               for c in CATEGORIES for direction in ('arrivals','departures')]}


class InventoryTests(unittest.TestCase):
    def test_conservation_and_day_carryover(self):
        result=plan(inventory_fixture(),{})
        self.assertEqual(result['summary']['remaining_aircraft'],17)
        for i,r in enumerate(result['rows']):
            self.assertAlmostEqual(r['closing_aircraft'],r['opening_aircraft']+r['arrivals']-r['departures'])
            if i:self.assertEqual(r['opening_aircraft'],result['rows'][i-1]['closing_aircraft'])
        s=result['summary']
        self.assertAlmostEqual(s['remaining_aircraft'],s['opening_aircraft']+s['total_arrivals']-s['total_departures'])
    def test_day_change_changes_later_inventory_not_later_arrival_forecast(self):
        result=plan(inventory_fixture(),{'days':{DATES[0]:{'scenario':'high'}}})
        self.assertEqual(result['rows'][0]['arrivals'],4)
        self.assertEqual(result['rows'][1]['arrivals'],2)
        self.assertEqual(result['rows'][1]['delta_closing_aircraft'],2)
        self.assertEqual(result['rows'][-1]['delta_closing_aircraft'],2)
    def test_manual_counts_override_selected_day_only(self):
        result=plan(inventory_fixture(),{'days':{DATES[0]:{'arrivals':0,'departures':0}}})
        self.assertEqual(result['rows'][0]['closing_aircraft'],10)
        self.assertEqual(result['rows'][1]['arrivals'],2)
    def test_departures_cannot_create_negative_inventory(self):
        result=plan(inventory_fixture(),{'days':{DATES[0]:{'arrivals':0,'departures':100}}})
        self.assertEqual(result['rows'][0]['closing_aircraft'],0)
        self.assertEqual(result['rows'][0]['departures'],10)
        self.assertEqual(result['rows'][0]['unmatched_departures'],90)
        self.assertEqual(result['rows'][0]['parking_units'],10) # opening is larger than arrival peak
    def test_delay_retains_end_of_window_aircraft(self):
        result=plan(inventory_fixture(),{'delay_departures':True})
        self.assertEqual(result['rows'][0]['departures'],0)
        self.assertEqual(result['summary']['remaining_aircraft'],18)
        self.assertEqual(result['summary']['departure_requests_shifted_beyond_window'],1)
    def test_holiday_adjusts_only_monday_arrivals(self):
        result=plan(inventory_fixture(),{'holiday_arrival_pct':10})
        for row in result['rows']:
            self.assertAlmostEqual(row['arrivals'],2.2 if row['date']=='2027-02-15' else 2)
        self.assertAlmostEqual(result['summary']['remaining_aircraft'],17.2)
    def test_capacity_changes_gap_not_demand(self):
        original=plan(inventory_fixture(),{'scenario':'high'})
        changed=plan(inventory_fixture(),{'scenario':'high','extra_capacity_units':50})
        self.assertEqual(original['summary']['peak_units'],changed['summary']['peak_units'])
        self.assertGreater(original['summary']['max_gap_units'],0)
        self.assertEqual(changed['summary']['max_gap_units'],0)
    def test_category_footprints_and_conservation(self):
        b=inventory_fixture()
        for row in b['category_ranges']:
            if row['direction']=='arrivals' and row['category']=='large_jet':row['expected']=1
        result=plan(b,{})
        first=result['rows'][0]
        self.assertAlmostEqual(first['parking_units'],11.5+2.5)
        self.assertEqual(first['closing_by_category']['large_jet'],1)
        self.assertEqual(result['rows'][-1]['closing_by_category']['large_jet'],7)
    def test_zero_category_forecast_custom_arrivals_uses_documented_mix(self):
        b=inventory_fixture()
        for r in b['category_ranges']:
            if r['date']==DATES[0] and r['direction']=='arrivals':r['expected']=0
        result=plan(b,{'days':{DATES[0]:{'arrivals':5}}})
        self.assertEqual(result['rows'][0]['arrivals_by_category']['light_jet'],5)
    def test_invalid_inputs_and_unknown_fields_rejected(self):
        invalid=[{'days':{'2027-02-18':{}}},{'scenario':[]},{'delay_departures':1},
                 {'holiday_arrival_pct':float('nan')},{'extra_capacity_units':-1},
                 {'days':{DATES[0]:{'arrivals':float('inf')}}},
                 {'days':{DATES[0]:{'arrivals':True}}},{'days':{DATES[0]:{'tail_number':'private'}}},
                 {'airport':'VNY'}]
        for value in invalid:
            with self.subTest(value=value),self.assertRaises(ContractError):plan(inventory_fixture(),value)
    def test_reject_samples_missing_mix_and_inconsistent_capacity(self):
        for mutate in (lambda b:b.update(native=False),lambda b:b['assumptions'].pop(),lambda b:b['resources'][0].update(capacity_units=19)):
            b=inventory_fixture();mutate(b)
            with self.assertRaises(ContractError):plan(b,{})
    def test_no_source_mutation_and_plan_fingerprint(self):
        b=inventory_fixture();before=copy.deepcopy(b)
        base=plan(b,{})
        self.assertEqual(b,before)
        self.assertEqual(base['plan_id'],plan(b,{'scenario':'medium'})['plan_id'])
        self.assertNotEqual(base['plan_id'],plan(b,{'holiday_arrival_pct':1})['plan_id'])
        self.assertIsNone(base['drop_and_go_ratio'])
        self.assertNotIn('probability',base)
        json.dumps(base,allow_nan=False)


class WhatIfHTTPTests(unittest.TestCase):
    setUp=existing_tests.ServerTests.setUp
    tearDown=existing_tests.ServerTests.tearDown
    request=existing_tests.ServerTests.request
    login=existing_tests.ServerTests.login
    def native(self):
        self.server.application.repo_root=ROOT.parent
        self.server.application.activate('team-native')
        return {'version':self.server.application.bundle['version'],'settings':{}}
    def test_native_calculation_does_not_change_source_or_reviews(self):
        body=self.native();before=self.server.application.snapshot()
        status,result=self.request('/api/what-if',body)
        self.assertEqual(status,200)
        self.assertEqual(len(result['rows']),7)
        self.assertEqual(self.server.application.snapshot(),before)
    def test_other_employee_can_experiment_but_not_change_source(self):
        body=self.native();self.login('operations')
        self.assertEqual(self.request('/api/what-if',body)[0],200)
        self.assertEqual(self.request('/api/source',{'source':'sample'})[0],403)
    def test_stale_version_csrf_and_authentication(self):
        body=self.native()
        self.assertEqual(self.request('/api/what-if',body,csrf=False)[0],403)
        self.assertEqual(self.request('/api/what-if',{**body,'version':'stale'})[0],409)
        self.cookie=''
        self.assertEqual(self.request('/api/what-if',body)[0],401)
    def test_sample_and_invalid_request_fail_explicitly(self):
        body={'version':self.server.application.bundle['version'],'settings':{}}
        self.assertEqual(self.request('/api/what-if',body)[0],400)
        body=self.native();body['settings']={'holiday_arrival_pct':999}
        self.assertEqual(self.request('/api/what-if',body)[0],400)
    def test_stale_files_block_calculation(self):
        body=self.native()
        self.server.application.input_status=lambda:{'stale':True,'message':'Inputs changed'}
        self.assertEqual(self.request('/api/what-if',body)[0],409)


if __name__=='__main__':unittest.main()
