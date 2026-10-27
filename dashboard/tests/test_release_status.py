"""Release provenance, stale-file rejection and the data team's independent reference."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from readiness.contracts import ContractError
from readiness.release_status import MANIFEST, RELEASE_FILES, EVIDENCE_FILES, EVIDENCE_MANIFEST, release_review, attach_release_status, sources_reference

class ReleaseStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.bundle={'meta':{'data_classification':'mixed'},'version':'model-version'}
    def tearDown(self):self.temp.cleanup()
    def manifest(self,status='provisional_pending_data_review'):
        hashes={}
        for name in RELEASE_FILES:
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('test fixture: '+name)
            hashes[name]=hashlib.sha256(p.read_bytes()).hexdigest()
        m={'status':status,'files':hashes,'run_id':hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()}
        (self.root/MANIFEST).write_text(json.dumps(m));return m
    def test_absent_manifest_is_unreviewed(self):
        self.assertEqual(release_review(self.root,self.bundle)['status'],'unreviewed')
    def test_provisional_manifest_stays_pending_after_hash_validation(self):
        m=self.manifest();s=release_review(self.root,self.bundle)
        self.assertTrue(s['manifest_verified']);self.assertEqual(s['status'],'provisional_pending_data_review');self.assertEqual(s['run_id'],m['run_id'])
    def test_hash_mismatch_blocks_load(self):
        self.manifest();(self.root/'parking/resource_requirements.csv').write_text('changed')
        with self.assertRaisesRegex(ContractError,'manifest mismatch'):release_review(self.root,self.bundle)
    def test_manifest_cannot_read_outside_known_files(self):
        m=self.manifest();m['files']['../../secret']='0'*64;(self.root/MANIFEST).write_text(json.dumps(m))
        with self.assertRaisesRegex(ContractError,'documented 20'):release_review(self.root,self.bundle)
    def test_invalid_run_id_rejected(self):
        m=self.manifest();m['run_id']='wrong';(self.root/MANIFEST).write_text(json.dumps(m))
        with self.assertRaisesRegex(ContractError,'run ID'):release_review(self.root,self.bundle)
    def test_producer_cannot_self_assert_verified_human_approval(self):
        self.manifest('approved');self.assertEqual(release_review(self.root,self.bundle)['status'],'unreviewed')
    def test_review_status_is_part_of_version(self):
        before=attach_release_status(self.root,dict(self.bundle))['version'];self.manifest()
        after=attach_release_status(self.root,dict(self.bundle))['version'];self.assertNotEqual(before,after)
    def test_sources_reference_retains_actual_values_and_units_warning(self):
        root=ROOT.parent;result=sources_reference(root)
        self.assertTrue(result['available']);self.assertEqual(len(result['rows']),7)
        self.assertIn('not the parking team',result['message'])
        import csv
        with (root/'sources/baseline.csv').open() as f:original=list(csv.DictReader(f))
        self.assertEqual(result['rows'][0]['arrivals'],float(original[0]['arrivals']))
    def test_fresh_install_opens_current_team_release(self):
        from app import Application
        app=Application(self.root/'state',ROOT.parent)
        self.assertEqual(app.source,'team-native')
        self.assertIsNone(app.load_error)
        self.assertTrue(app.bundle['release_review']['manifest_verified'])
        self.assertEqual(app.bundle['variants'],['standard','departure_delay_24h'])
    def test_missing_team_release_on_first_start_never_becomes_sample(self):
        from app import Application
        app=Application(self.root/'state',self.root/'missing-repo')
        self.assertEqual(app.source,'team-native');self.assertIsNone(app.bundle)
        self.assertIn('Missing inputs',app.load_error)
    def test_comparison_file_hash_mismatch_blocks_load(self):
        self.manifest();(self.root/'parking/ordinary_week_parking.csv').write_text('changed')
        with self.assertRaisesRegex(ContractError,'manifest mismatch'):release_review(self.root,self.bundle)
    def test_missing_sources_reference_never_becomes_sample(self):
        self.assertFalse(sources_reference(self.root)['available'])
    def evidence(self):
        m=self.manifest();files={}
        for name in EVIDENCE_FILES:
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('evidence fixture '+name)
            files[name]=hashlib.sha256(path.read_bytes()).hexdigest()
        (self.root/EVIDENCE_MANIFEST).write_text(json.dumps({'release_run_id':m['run_id'],'files':files}))
    def test_event_evidence_is_verified_and_tampering_rejected(self):
        self.evidence()
        self.assertIn('event_evidence_manifest_sha256',release_review(self.root,self.bundle))
        (self.root/'forecast/main_forecast/provisional_inputs/event_evidence.json').write_text('changed holiday assumption')
        with self.assertRaisesRegex(ContractError,'event evidence mismatch'):release_review(self.root,self.bundle)
    def test_partial_event_release_rejected(self):
        self.evidence();(self.root/EVIDENCE_MANIFEST).unlink()
        with self.assertRaisesRegex(ContractError,'evidence manifest'):release_review(self.root,self.bundle)
    def test_event_evidence_cannot_point_at_other_release_or_arbitrary_file(self):
        for mutation in ('run','file'):
            with self.subTest(mutation=mutation):
                self.evidence();path=self.root/EVIDENCE_MANIFEST;m=json.loads(path.read_text())
                if mutation=='run':m['release_run_id']='old'
                else:m['files']['../../secret']='0'*64
                path.write_text(json.dumps(m))
                with self.assertRaisesRegex(ContractError,'documented 16'):release_review(self.root,self.bundle)
