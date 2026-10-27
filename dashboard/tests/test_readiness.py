"""Boundary, audit and HTTP tests. No external services or dependencies."""
import copy
import csv
import io
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
        self.server.application.activate('sample')
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
    def review(self,version=None,decision='approved',checks=None,variant='standard'):
        b=self.server.application.bundle
        r=next((r for r in b['recommendations'] if r['scenario']=='medium' and r['variant']==variant),None)
        r=r or next((r for r in b['recommendations'] if r['variant']==variant),None)
        r=r or {'scenario':'medium','id':'no-action-supplied'}
        return {'version':version or b['version'],'scenario':r['scenario'],'variant':variant,'recommendation_id':r['id'],'decision':decision,'note':'Confirmed illustrative assumptions for demo.', 'checks':checks if checks is not None else {'assumptions':True,'availability':True,'cost':True}}
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
        (self.root/'repo'/'sources'/'baseline.csv').unlink()
        restored=Application(self.root/'state',self.root/'repo');self.assertIsNone(restored.bundle);self.assertEqual(restored.source,'team')
    def test_native_http_review_and_export(self):
        from readiness.team_adapter import NATIVE_PATHS
        self.assertTrue(all((ROOT.parent/p).is_file() for p in NATIVE_PATHS.values()), 'Required current team outputs are missing')
        self.server.application.repo_root=ROOT.parent
        status,data=self.request('/api/source',{'source':'team-native'});self.assertEqual(status,200)
        self.assertTrue(data['bundle']['native'])
        review=self.review();has_action=review['recommendation_id']!='no-action-supplied';sc=review['scenario']
        self.assertEqual(self.request('/api/review',review)[0],201 if has_action else 400)
        status,export=self.request(f'/api/export?scenario={sc}&variant=standard')
        self.assertEqual(status,200);self.assertEqual(export['source'],'team-native');self.assertEqual(len(export['reviews']),int(has_action))
        self.assertEqual(export['simulation_impact'],data['bundle']['impacts'][sc])
        self.assertEqual(len(export['forecast_drivers']),42)
        status,delayed=self.request(f'/api/export?scenario={sc}&variant=departure_delay_24h')
        self.assertEqual(status,200)
        self.assertEqual(delayed['simulation_impact'],data['bundle']['impacts_by_variant']['departure_delay_24h'][sc])
        self.assertEqual(len(delayed['resources']),7)
        self.assertEqual(len(delayed['carryover']),2)
        self.assertEqual(delayed['reviews'],[])
        delayed_review=self.review(variant='departure_delay_24h')
        self.assertEqual(self.request('/api/review',delayed_review)[0],201 if delayed_review['recommendation_id']!='no-action-supplied' else 400)
        self.assertEqual(len(self.request(f'/api/export?scenario={sc}&variant=standard')[1]['reviews']),int(has_action))
        self.assertEqual(self.request('/api/export?scenario=medium&variant=missing')[0],400)
    def test_release_tampering_blocks_review_export_and_refresh(self):
        from readiness.release_status import RELEASE_FILES, MANIFEST, EVIDENCE_FILES, EVIDENCE_MANIFEST
        repo=self.root/'hashed-release'
        release_files=RELEASE_FILES|{MANIFEST}
        if (ROOT.parent/EVIDENCE_MANIFEST).exists():release_files=release_files|EVIDENCE_FILES|{EVIDENCE_MANIFEST}
        for relative in release_files:
            dest=repo/relative;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes((ROOT.parent/relative).read_bytes())
        self.server.application.repo_root=repo
        self.assertEqual(self.request('/api/source',{'source':'team-native'})[0],200)
        review=self.review()
        self.assertEqual(self.request('/api/review',review)[0],201 if review['recommendation_id']!='no-action-supplied' else 400)
        exported=self.request('/api/export?scenario=medium&variant=standard')[1]
        self.assertEqual(exported['release_review']['status'],'provisional_pending_data_review')
        original=self.server.application.bundle['version']
        path=repo/'parking/ordinary_week_parking.csv';saved=path.read_bytes();path.write_bytes(saved+b'\n')
        self.assertTrue(self.request('/api/dashboard')[1]['input_status']['stale'])
        self.assertEqual(self.request('/api/review',self.review())[0],409)
        self.assertEqual(self.request('/api/export?scenario=medium&variant=standard')[0],409)
        self.assertEqual(self.request('/api/source',{'source':'team-native'})[0],400)
        self.assertEqual(self.server.application.bundle['version'],original)
        path.write_bytes(saved)
        self.assertEqual(self.request('/api/source',{'source':'team-native'})[0],200)
        self.assertFalse(self.request('/api/dashboard')[1]['input_status']['stale'])
    def test_changed_native_files_block_review_and_export_until_refresh(self):
        from readiness.team_adapter import NATIVE_PATHS
        repo=self.root/'changed-inputs'
        for name,relative in NATIVE_PATHS.items():
            dest=repo/relative;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes((ROOT.parent/relative).read_bytes())
        self.server.application.repo_root=repo
        self.assertEqual(self.request('/api/source',{'source':'team-native'})[0],200)
        original=self.server.application.bundle['version']
        report=repo/NATIVE_PATHS['p2_report'];data=json.loads(report.read_text());data['seed']=12345;report.write_text(json.dumps(data))
        status,snapshot=self.request('/api/dashboard');self.assertTrue(snapshot['input_status']['stale'])
        self.assertEqual(snapshot['bundle']['version'],original)
        self.assertEqual(self.request('/api/review',self.review())[0],409)
        self.assertEqual(self.request('/api/export?scenario=medium&variant=standard')[0],409)
        self.assertEqual(self.request('/api/source',{'source':'team-native'})[0],200)
        self.assertFalse(self.request('/api/dashboard')[1]['input_status']['stale'])
        self.assertNotEqual(self.server.application.bundle['version'],original)
        export=self.request('/api/export?scenario=medium&variant=standard')[1]
        self.assertEqual(export['release_review']['status'],'unreviewed')
    def test_login_malformed_role(self):
        self.assertEqual(self.request('/api/login',{'role':[]})[0],400)
    def test_path_traversal_and_static(self):
        self.assertEqual(self.request('/../app.py')[0],404)
        self.assertEqual(self.request('/')[0],200)
        self.assertEqual(self.request('/app.js')[0],200)
        self.assertEqual(self.request('/styles.css')[0],200)

class NativeAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from readiness.team_adapter import NATIVE_PATHS
        cls.paths=NATIVE_PATHS
        cls.repo=ROOT.parent
        if not all((cls.repo/p).is_file() for p in NATIVE_PATHS.values()):
            raise AssertionError('Required native P2/P3 outputs are missing; integration must not silently skip.')
    def native_files(self):
        return {k:(self.repo/p).read_text(encoding='utf-8-sig') for k,p in self.paths.items()}
    def test_native_summary_matches_producer(self):
        from readiness.team_adapter import load_native
        f=self.native_files();b=load_native(f);plans=json.loads(f['p3_recommendations'])
        for sc in ('low','medium','high'):
            summary=summarize(b,sc,'standard')
            self.assertAlmostEqual(summary['peak_demand'],plans['scenarios'][sc.title()]['summary']['peak_parking_demand_su_p50'])
            self.assertEqual(summary['preparation_cost'],plans['scenarios'][sc.title()]['preparation_cost_usd'])
    def test_no_invented_baseline_ranges_or_delay(self):
        from readiness.team_adapter import load_native
        b=load_native(self.native_files())
        self.assertTrue(all(r['parking_units'] is None for r in b['baseline']))
        self.assertTrue(all(r['arrivals_lower'] is None and r['arrivals_upper'] is None for r in b['demand']))
        self.assertEqual(b['variants'],['standard']);self.assertEqual(len(b['category_ranges']),126)
    def test_mismatched_forecast_rejected(self):
        from readiness.team_adapter import load_native
        f=self.native_files();lines=f['p2_uncertainty'].splitlines();parts=lines[1].split(',');parts[4]='999';lines[1]=','.join(parts);f['p2_uncertainty']='\n'.join(lines)
        with self.assertRaisesRegex(ContractError,'disagree'):load_native(f)
    def test_unknown_actions_rejected(self):
        from readiness.team_adapter import load_native
        f=self.native_files();j=json.loads(f['p3_recommendations']);j['scenarios']['Medium']['actions'].append({'id':'auto_accept_reservations','cost_usd':0});f['p3_recommendations']=json.dumps(j)
        with self.assertRaisesRegex(ContractError,'unknown'):load_native(f)
    def test_action_costs_reconcile(self):
        from readiness.team_adapter import load_native
        f=self.native_files();j=json.loads(f['p3_recommendations']);j['scenarios']['Medium']['preparation_cost_usd']+=1;f['p3_recommendations']=json.dumps(j)
        with self.assertRaisesRegex(ContractError,'costs'):load_native(f)
    def test_native_source_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Application(Path(tmp),self.repo);a.activate('team-native');first=a.bundle['version']
            self.assertEqual(a.snapshot()['source'],'team-native')
            a=Application(Path(tmp),self.repo);self.assertEqual(first,a.bundle['version'])
    def alter_csv(self,raw,name,field,value):
        reader=csv.DictReader(io.StringIO(raw[name]));data=list(reader);data[0][field]=value
        out=io.StringIO();writer=csv.DictWriter(out,fieldnames=reader.fieldnames);writer.writeheader();writer.writerows(data);raw[name]=out.getvalue()
    def test_current_schema_and_provenance(self):
        from readiness.team_adapter import load_native
        raw=self.native_files();b=load_native(raw)
        self.assertEqual(len(b['forecast_metrics']),6)
        self.assertEqual(len(b['forecast_drivers']),126)
        self.assertIn('month/weekday',b['meta']['model_version'])
        classes=json.loads(raw['p2_report'])['historical_data_classes']
        self.assertTrue(all(any(c in m['evaluation_data'] for c in classes) for m in b['forecast_metrics']))
    def test_estimated_history_remains_non_observed(self):
        from readiness.team_adapter import load_native
        raw=self.native_files()
        for key in ('p2_demand','p2_uncertainty','p2_metrics','p2_report'):
            raw[key]=raw[key].replace('synthetic','estimated')
        b=load_native(raw)
        self.assertEqual(b['meta']['data_classification'],'mixed')
        self.assertTrue(all('estimated / non_observed_demonstration' in m['evaluation_data'] for m in b['forecast_metrics']))
    def test_missing_current_file_fails(self):
        from readiness.team_adapter import load_native
        raw=self.native_files();del raw['p2_metrics']
        with self.assertRaisesRegex(ContractError,'seven'):load_native(raw)
    def test_duplicate_demand_and_metrics_rejected(self):
        from readiness.team_adapter import load_native
        for name in ('p2_demand','p2_metrics'):
            with self.subTest(name=name):
                raw=self.native_files();raw[name]+='\n'+raw[name].splitlines()[1]+'\n'
                with self.assertRaisesRegex(ContractError,'duplicate'):load_native(raw)
    def test_interval_and_provenance_mismatch_rejected(self):
        from readiness.team_adapter import load_native
        for field,value in (('arrivals_upper','999'),('historical_data_class','observed')):
            with self.subTest(field=field):
                raw=self.native_files();self.alter_csv(raw,'p2_demand',field,value)
                with self.assertRaisesRegex(ContractError,'disagree|provenance'):load_native(raw)
    def test_evaluation_cannot_claim_observed_accuracy(self):
        from readiness.team_adapter import load_native
        raw=self.native_files();self.alter_csv(raw,'p2_metrics','evaluation_type','invented_evaluation')
        with self.assertRaisesRegex(ContractError,'evaluation type'):load_native(raw)
    def test_impact_matches_producer_including_losses(self):
        from readiness.team_adapter import load_native, parse_impact
        raw=self.native_files();b=load_native(raw);plans=json.loads(raw['p3_recommendations'])
        for sc,impact in b['impacts'].items():
            self.assertEqual(impact,plans['scenarios'][sc.title()]['impact'])
        # Negative benefits are legitimate: costs can exceed avoided losses.
        impact=copy.deepcopy(b['impacts']['low'])
        impact['no_preparation']['total_cost_usd']['mean']=0
        impact['ai_preparation']['total_cost_usd']['mean']=10
        impact['net_benefit_usd']={'mean':-10,'p10':-20,'p50':-10,'p90':-5}
        self.assertEqual(parse_impact(impact)['net_benefit_usd']['mean'],-10)
    def test_invalid_impact_rejected(self):
        from readiness.team_adapter import load_native
        for field,value in (('prob_preparation_pays_off',1.1),('runs',0)):
            raw=self.native_files();j=json.loads(raw['p3_recommendations']);j['scenarios']['Medium']['impact'][field]=value;raw['p3_recommendations']=json.dumps(j)
            with self.assertRaises(ContractError):load_native(raw)
        raw=self.native_files();j=json.loads(raw['p3_recommendations']);j['scenarios']['Medium']['impact']['net_benefit_usd']['mean']+=100;raw['p3_recommendations']=json.dumps(j)
        with self.assertRaisesRegex(ContractError,'reconcile'):load_native(raw)
    def test_changed_input_changes_review_version(self):
        from readiness.team_adapter import load_native
        f=self.native_files();old=load_native(f)['version'];j=json.loads(f['p2_report']);j['seed']=(j.get('seed') or 0)+1;f['p2_report']=json.dumps(j)
        self.assertNotEqual(old,load_native(f)['version'])

class ParkingVariantTests(unittest.TestCase):
    def files(self):
        from readiness.data import native_paths, read_paths
        return read_paths(native_paths(ROOT.parent))
    def test_release_loads_both_variants_and_ordinary_units(self):
        from readiness.team_adapter import load_native
        b=load_native(self.files())
        self.assertEqual(b['variants'],['standard','departure_delay_24h'])
        self.assertEqual(len(b['resources']),42)
        self.assertEqual(len(b['carryover']),7)
        original=list(csv.DictReader(io.StringIO(self.files()['p3_ordinary'])))
        for row,expected in zip(b['baseline'],original):
            self.assertEqual(row['parking_units'],float(expected['parking_demand_su_p50']))
        for variant,key in [('standard','p3_recommendations'),('departure_delay_24h','p3_delay_recommendations')]:
            plans=json.loads(self.files()[key])['scenarios']
            for sc in ('low','medium','high'):
                self.assertEqual(summarize(b,sc,variant)['preparation_cost'],plans[sc.title()]['preparation_cost_usd'])
                self.assertEqual(b['impacts_by_variant'][variant][sc],plans[sc.title()]['impact'])
    def test_partial_release_rejected(self):
        from readiness.team_adapter import load_native
        from readiness.parking_variants import EXTENSION_PATHS
        for key in EXTENSION_PATHS:
            with self.subTest(key=key):
                raw=self.files();del raw[key]
                with self.assertRaisesRegex(ContractError,'four files'):load_native(raw)
    def test_bad_ordinary_join_quantiles_and_carryover_rejected(self):
        from readiness.team_adapter import load_native
        mutations=[('p3_ordinary','arrivals_baseline','999'),('p3_ordinary','parking_demand_su_p10','999'),('p3_ordinary','capacity_normal_su','99'),('p3_carryover','opening_aircraft','99'),('p3_carryover','aircraft_remaining_p90','0'),('p3_carryover','departures_pushed_past_window_p50','1')]
        for name,field,value in mutations:
            with self.subTest(name=name,field=field):
                raw=self.files();NativeAdapterTests.alter_csv(self,raw,name,field,value)
                with self.assertRaises(ContractError):load_native(raw)
    def test_duplicate_and_missing_carryover_rejected(self):
        from readiness.team_adapter import load_native
        for duplicate in (True,False):
            raw=self.files();lines=raw['p3_carryover'].splitlines()
            raw['p3_carryover']='\n'.join(lines+[lines[1]] if duplicate else lines[:-1])
            with self.assertRaisesRegex(ContractError,'duplicate or missing'):load_native(raw)
    def test_delay_metadata_and_provenance_rejected(self):
        from readiness.team_adapter import load_native
        provenance=json.loads(self.files()['p2_report'])['historical_data_classes']
        different=['synthetic'] if provenance != ['synthetic'] else ['estimated']
        for field,value in [('variant','standard'),('demand_provenance',different)]:
            raw=self.files();doc=json.loads(raw['p3_delay_recommendations']);doc['meta'][field]=value
            raw['p3_delay_recommendations']=json.dumps(doc)
            with self.assertRaises(ContractError):load_native(raw)
    def test_extension_change_invalidates_reviews(self):
        from readiness.team_adapter import load_native
        raw=self.files();old=load_native(raw)['version']
        row=next(csv.DictReader(io.StringIO(raw['p3_carryover'])))
        lo,mid,hi=(float(row['aircraft_remaining_'+q]) for q in ('p10','p50','p90'))
        changed=(mid+hi)/2 if hi>mid else (lo+mid)/2
        self.assertNotEqual(changed,mid,'Fixture needs a nonzero carryover range for this mutation')
        NativeAdapterTests.alter_csv(self,raw,'p3_carryover','aircraft_remaining_p50',str(changed))
        self.assertNotEqual(load_native(raw)['version'],old)
    def test_partial_disk_release_does_not_fall_back(self):
        from readiness.data import native_bundle
        from readiness.team_adapter import NATIVE_PATHS
        from readiness.parking_variants import EXTENSION_PATHS
        with tempfile.TemporaryDirectory() as tmp:
            raw=self.files()
            for key,rel in NATIVE_PATHS.items():
                p=Path(tmp)/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(raw[key])
            key='p3_ordinary';p=Path(tmp)/EXTENSION_PATHS[key];p.write_text(raw[key])
            with self.assertRaisesRegex(ContractError,'Missing inputs'):native_bundle(tmp)

if __name__=='__main__':unittest.main()
