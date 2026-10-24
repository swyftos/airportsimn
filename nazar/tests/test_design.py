"""Evidence boundaries and persistent reviews for the approved design adapter."""
import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import Application
from readiness.design_view import illustration, allocate, parse_bookings
from readiness.contracts import ContractError, DATES
import test_readiness as shared

CSV='visit_id,category,arrival,departure,status\nV-0001,light_jet,2027-02-14T10:00:00-08:00,2027-02-15T10:00:00-08:00,Booked\n'

class IllustrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.app=Application(Path(self.temp.name));self.b=self.app.bundle
    def tearDown(self):self.temp.cleanup()
    def test_all_cases_preserve_sources_and_reconcile_hourly_inventory(self):
        before=copy.deepcopy(self.b)
        for scenario in ('low','medium','high'):
            for variant in self.b['variants']:
                data=illustration(self.b,scenario,variant)
                self.assertEqual(len(data['hours']),168)
                self.assertTrue(all(v['status']=='Estimated' and v['id'].startswith('E-') for v in data['visits']))
                for h in data['hours']:
                    active=[v for v in data['visits'] if datetime.fromisoformat(v['arrival'])<=datetime.fromisoformat(h['time'])<datetime.fromisoformat(v['departure'])]
                    self.assertEqual(h['aircraft'],len(active));self.assertAlmostEqual(h['units'],sum(v['units'] for v in active))
                self.assertTrue(all(v['arrival']<v['departure'] for v in data['visits']))
        self.assertEqual(before,self.b)
    def test_daily_arrivals_equal_rounded_category_forecast(self):
        v=illustration(self.b,'medium','standard')['visits']
        for d in DATES:
            expected=[r['expected'] for r in self.b['category_ranges'] if r['date']==d and r['scenario']=='medium' and r['direction']=='arrivals']
            self.assertEqual(sum(x['arrival'].startswith(d) and not x['opening'] for x in v),sum(allocate(expected)))
    def test_departure_delay_never_removes_parked_aircraft(self):
        normal=illustration(self.b,'high','standard');late=illustration(self.b,'high','departure_delay_24h')
        self.assertTrue(all(b['units']>=a['units'] for a,b in zip(normal['hours'],late['hours'])))
        self.assertTrue(any(b['units']>a['units'] for a,b in zip(normal['hours'],late['hours'])))
    def test_no_category_records_has_no_invented_hourly_data(self):
        self.b['category_ranges']=[];result=illustration(self.b,'medium','standard')
        self.assertFalse(result['available']);self.assertEqual(result['hours'],[])
    def test_strict_booking_contract(self):
        v=parse_bookings(CSV);self.assertEqual(v[0]['status'],'Booked')
        for bad in [CSV.replace('visit_id','passenger_name'),CSV+CSV.splitlines()[1]+'\n',CSV.replace(',Booked',',Booked,SECRET'),CSV.replace('V-0001','N123AA'),CSV.replace('2027-02-15','2027-02-13'),CSV.replace('status\n','status,status\n')]:
            with self.subTest(bad=bad):
                with self.assertRaises(ContractError):parse_bookings(bad)
    def test_largest_remainder_preserves_total(self):
        self.assertEqual(sum(allocate([.6,.6,.6])),2)

class DesignHTTPTests(unittest.TestCase):
    request=shared.ServerTests.request
    login=shared.ServerTests.login
    tearDown=shared.ServerTests.tearDown
    def setUp(self):
        shared.ServerTests.setUp(self)
        self.server.application.repo_root=ROOT.parent
        self.server.application.activate('team-native')
    def payload(self,**kwargs):
        status,d=self.request('/api/design');self.assertEqual(status,200)
        return {'version':d['version'],'scenario':'medium','variant':'standard',**kwargs}
    def test_unauthenticated_and_invalid_case(self):
        self.assertEqual(self.request('/api/design?scenario=unknown')[0],400)
        self.cookie='';self.assertEqual(self.request('/api/design')[0],401)
    def test_roles_csrf_and_checks_persist(self):
        body=self.payload(kind='ramp_checks',key='capacity',checked=True)
        self.assertEqual(self.request('/api/design/check',body,csrf=False)[0],403)
        self.login('reservations');self.assertEqual(self.request('/api/design/check',body)[0],403)
        self.login('operations');s,d=self.request('/api/design/check',body);self.assertEqual(s,200)
        self.assertTrue(d['ramp_checks'][d['version']+':capacity']['checked'])
        self.assertIn('Sam',d['ramp_checks'][d['version']+':capacity']['reviewer'])
        self.assertEqual(self.request('/api/design/bookings',self.payload(csv=CSV))[0],403)
    def test_review_needs_approvals_and_is_versioned(self):
        body=self.payload(recommendation_id='ready-timing',decision='approved',note='QA verification only.',checks={})
        self.assertEqual(self.request('/api/design/review',body)[0],400)
        body['checks']={k:True for k in ('assumptions','availability','cost')}
        s,d=self.request('/api/design/review',body);self.assertEqual(s,200);self.assertFalse(d['history'][0]['stale'])
        self.assertTrue(self.request('/api/design?scenario=high')[1]['history'][0]['stale'])
        self.login('operations');self.assertEqual(self.request('/api/design/review',body)[0],403)
    def test_booking_upload_invalidates_reviews_not_forecast(self):
        bundle_before=copy.deepcopy(self.server.application.bundle);payload=self.payload(csv=CSV)
        s,d=self.request('/api/design/bookings',payload);self.assertEqual(s,200)
        self.assertNotEqual(d['version'],payload['version']);self.assertEqual(d['bookings']['visits'][0]['id'],'V-0001')
        self.assertEqual(bundle_before,self.server.application.bundle)
        self.assertEqual(self.request('/api/design/bookings',payload)[0],409)
    def test_reject_unknown_action_and_check(self):
        self.assertEqual(self.request('/api/design/check',self.payload(kind='ramp_checks',key='authorize-movement',checked=True))[0],400)
        self.assertEqual(self.request('/api/design/review',self.payload(recommendation_id='clear-for-takeoff',decision='approved',note='Not allowed.',checks={}))[0],400)
    def test_static_design_and_original_tools_available(self):
        for path in ['/', '/design.js','/design-tools.js','/design.css','/templates/Main.html','/legacy']:
            self.assertEqual(self.request(path)[0],200,path)
        self.assertEqual(self.request('/templates/../../app.py')[0],404)

if __name__=='__main__':unittest.main()
