"""Boundary, audit and HTTP tests. No external services or dependencies."""
import copy
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import create_server, Application
from readiness.contracts import FILES, ContractError, load_bundle, summarize
from readiness.data import TEAM_PATHS
from readiness.storage import ReviewStore

def fixture():
    return {n:(ROOT/'sample-data'/n).read_text() for n in FILES}

class ContractTests(unittest.TestCase):
    def test_sample_summary(self):
        b=load_bundle(fixture());s=summarize(b,'medium','standard')
        self.assertEqual((s['peak_demand'],s['peak_shortfall'],s['remaining_shortfall']),(92,28,0))
        self.assertEqual((s['days_over_capacity'],s['remaining_days']),(3,0))
        self.assertEqual(s['first_shortage'],'2027-02-13')
        self.assertEqual(s['preparation_cost'],3780)
        self.assertEqual(summarize(b,'high','standard')['remaining_shortfall'],14)
        self.assertEqual(summarize(b,'high','departure_delay_24h')['remaining_shortfall'],27)
    def test_missing_file(self):
        f=fixture();del f['baseline.csv']
        with self.assertRaisesRegex(ContractError,'Missing'):load_bundle(f)
    def test_reject_private_column(self):
        f=fixture();f['baseline.csv']=f['baseline.csv'].replace('date,','passenger_name,date,',1)
        with self.assertRaisesRegex(ContractError,'unsupported columns'):load_bundle(f)
    def test_recommendation_numbers_must_match(self):
        f=fixture();r=json.loads(f['scenario_recommendations.json']);r[0]['evidence'][0]['value']=999
        f['scenario_recommendations.json']=json.dumps(r)
        with self.assertRaisesRegex(ContractError,'evidence does not match'):load_bundle(f)
    def test_no_unknown_actions(self):
        f=fixture();r=json.loads(f['scenario_recommendations.json']);r[0]['action_type']='authorize_takeoff'
        f['scenario_recommendations.json']=json.dumps(r)
        with self.assertRaisesRegex(ContractError,'unsupported'):load_bundle(f)
    def test_ranges_must_cover_central(self):
        f=fixture();lines=f['uncertainty_results.csv'].splitlines();parts=lines[1].split(',');parts[-1]='0';lines[1]=','.join(parts);f['uncertainty_results.csv']='\n'.join(lines)
        with self.assertRaisesRegex(ContractError,'lower'):load_bundle(f)
    def test_nan_rejected(self):
        f=fixture();f['baseline.csv']=f['baseline.csv'].replace('2027-02-11,8,','2027-02-11,NaN,')
        with self.assertRaisesRegex(ContractError,'finite'):load_bundle(f)
    def test_duplicate_day_rejected(self):
        f=fixture();f['baseline.csv']+=f['baseline.csv'].splitlines()[1]+'\n'
        with self.assertRaisesRegex(ContractError,'duplicate'):load_bundle(f)
    def test_partial_variant_rejected(self):
        f=fixture();lines=f['resource_requirements.csv'].splitlines();f['resource_requirements.csv']='\n'.join(lines[:-1])
        with self.assertRaisesRegex(ContractError,'21'):load_bundle(f)
    def test_equivalent_json_has_same_version(self):
        f=fixture();original=load_bundle(f)['version'];f['manifest.json']=json.dumps(json.loads(f['manifest.json']),sort_keys=True)
        self.assertEqual(original,load_bundle(f)['version'])

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.server=create_server(0,self.root/'state',self.root/'repo')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.cookie='';self.csrf='';self.login('manager')
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
    def request(self,path,body=None,csrf=True,origin=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        headers={'Cookie':self.cookie}
        if body is not None:headers.update({'Content-Type':'application/json','X-CSRF-Token':self.csrf if csrf else ''})
        if origin:headers['Origin']=origin
        conn.request('GET' if body is None else 'POST',path,None if body is None else json.dumps(body),headers)
        response=conn.getresponse();raw=response.read();cookie=response.getheader('Set-Cookie')
        if cookie:self.cookie=cookie.split(';')[0]
        try:data=json.loads(raw)
        except ValueError:data=raw
        status=response.status;conn.close();return status,data
    def login(self,role):
        status,data=self.request('/api/login',{'role':role});self.assertEqual(status,200);self.csrf=data['csrf']
    def review(self,version=None,decision='approved',checks=None):
        b=self.server.application.bundle;r=next(r for r in b['recommendations'] if r['scenario']=='medium' and r['variant']=='standard')
        return {'version':version or b['version'],'scenario':'medium','variant':'standard','recommendation_id':r['id'],'decision':decision,'note':'Confirmed illustrative assumptions for demo.', 'checks':checks if checks is not None else {'assumptions':True,'availability':True,'cost':True}}
    def test_snapshot_and_export(self):
        status,data=self.request('/api/dashboard');self.assertEqual(status,200);self.assertEqual(data['source'],'sample')
        self.assertEqual(data['summaries']['medium']['standard']['peak_shortfall'],28)
        status,data=self.request('/api/export?scenario=high&variant=standard');self.assertEqual(status,200);self.assertEqual(data['summary']['remaining_shortfall'],14)
        self.assertEqual(self.request('/api/export?scenario=unknown')[0],400)
    def test_unauthenticated_no_data(self):
        self.cookie='';self.assertEqual(self.request('/api/dashboard')[0],401)
    def test_csrf_and_origin(self):
        self.assertEqual(self.request('/api/review',self.review(),csrf=False)[0],403)
        self.assertEqual(self.request('/api/review',self.review(),origin='https://evil.example')[0],403)
    def test_role_guard(self):
        self.login('operations');self.assertEqual(self.request('/api/review',self.review())[0],403)
        self.assertEqual(self.request('/api/source',{'source':'sample'})[0],403)
        self.assertEqual(self.request('/api/dashboard')[0],200)
    def test_review_requires_checks_and_note(self):
        self.assertEqual(self.request('/api/review',self.review(checks={}))[0],400)
        p=self.review();p['note']='';self.assertEqual(self.request('/api/review',p)[0],400)
        self.assertEqual(self.request('/api/review',self.review(decision='changes_requested',checks={}))[0],201)
    def test_version_review_and_restart(self):
        old=self.server.application.bundle['version']
        self.assertEqual(self.request('/api/review',self.review())[0],201)
        f=fixture();m=json.loads(f['manifest.json']);m['model_version']='new-model';f['manifest.json']=json.dumps(m)
        self.assertEqual(self.request('/api/import',{'files':f})[0],200)
        self.assertEqual(self.request('/api/review',self.review(version=old))[0],409)
        status,d=self.request('/api/dashboard');self.assertTrue(d['history'][0]['stale'])
        restored=Application(self.root/'state',self.root/'repo');self.assertEqual(restored.bundle['version'],d['bundle']['version']);self.assertTrue(restored.store.history(restored.bundle['version'])[0]['stale'])
        self.assertEqual(self.request('/api/source',{'source':'import'})[0],200)
    def test_bad_import_keeps_current(self):
        old=self.server.application.bundle['version'];f=fixture();f['manifest.json']='broken'
        self.assertEqual(self.request('/api/import',{'files':f})[0],400)
        self.assertEqual(self.server.application.bundle['version'],old)
        self.assertEqual(self.request('/api/source',{'source':'team'})[0],400)
        self.assertEqual(self.server.application.source,'sample')
    def test_team_files_and_missing_after_restart(self):
        f=fixture()
        for name,parts in TEAM_PATHS.items():
            p=self.root/'repo'/Path(*parts);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(f[name])
        self.assertEqual(self.request('/api/source',{'source':'team'})[0],200)
        (self.root/'repo'/'alan'/'baseline.csv').unlink()
        restored=Application(self.root/'state',self.root/'repo');self.assertIsNone(restored.bundle);self.assertEqual(restored.source,'team')
    def test_login_malformed_role(self):
        self.assertEqual(self.request('/api/login',{'role':[]})[0],400)
    def test_path_traversal_and_static(self):
        self.assertEqual(self.request('/../app.py')[0],404)
        self.assertEqual(self.request('/')[0],200)
        self.assertEqual(self.request('/app.js')[0],200)
        self.assertEqual(self.request('/styles.css')[0],200)

if __name__=='__main__':unittest.main()
