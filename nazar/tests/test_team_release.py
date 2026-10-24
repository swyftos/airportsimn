"""Failure isolation and publishing rules for the coordinated release command."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/release_team.py'
spec=importlib.util.spec_from_file_location('team_release',SCRIPT)
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class TeamReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.repo=self.root/'repo';self.stage=self.root/'stage'
        self.repo.mkdir();self.stage.mkdir()
    def tearDown(self):self.tmp.cleanup()
    def write(self,root,name,content):
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
    def releases(self):
        names=(*r.OUTPUTS,r.MANIFEST,r.REPORT)
        for name in names:
            self.write(self.repo,name,'previous '+name);self.write(self.stage,name,'new '+name)
        return {n:r.digest(self.repo/n) for n in names}
    def test_policy_mismatch_stops_before_forecast(self):
        labels=[]
        with patch.object(r,'run_step',side_effect=lambda root,label,*args:labels.append(label)),patch.object(r,'assumption_mismatches',return_value=['share mismatch']):
            with self.assertRaisesRegex(r.ReleaseError,'No working files'):r.build(self.stage)
        self.assertEqual(len(labels),3)
        self.assertNotIn('Marvin: forecast and uncertainty',labels)
    def test_stage_failure_stops_later_stages(self):
        labels=[]
        def failing(root,label,*args):
            labels.append(label)
            if len(labels)==2:raise r.subprocess.CalledProcessError(1,args)
        with patch.object(r,'run_step',side_effect=failing):
            with self.assertRaises(r.subprocess.CalledProcessError):r.build(self.stage)
        self.assertEqual(len(labels),2)
    def test_newer_working_file_is_not_overwritten(self):
        hashes=self.releases();name=r.OUTPUTS[0];self.write(self.repo,name,'teammate edit')
        with self.assertRaisesRegex(r.ReleaseError,'changed during'):r.install(self.repo,self.stage,hashes)
        self.assertEqual((self.repo/name).read_text(),'teammate edit')
        self.assertTrue((self.repo/r.MANIFEST).read_text().startswith('previous'))
    def test_publish_writes_manifest_last(self):
        hashes=self.releases();order=[];original=r.replace_bytes
        def record(path,content):order.append(str(path.relative_to(self.repo)));original(path,content)
        with patch.object(r,'replace_bytes',side_effect=record):r.install(self.repo,self.stage,hashes)
        self.assertEqual(order[-1],r.MANIFEST)
        for name in hashes:self.assertEqual((self.repo/name).read_bytes(),(self.stage/name).read_bytes())
    def test_failed_publish_restores_previous_release(self):
        hashes=self.releases();original=r.replace_bytes;calls=0
        def failing(path,content):
            nonlocal calls
            calls+=1
            if calls==3:raise OSError('simulated write failure')
            original(path,content)
        with patch.object(r,'replace_bytes',side_effect=failing):
            with self.assertRaisesRegex(OSError,'simulated'):r.install(self.repo,self.stage,hashes)
        for name,sha in hashes.items():self.assertEqual(r.digest(self.repo/name),sha)
    def test_missing_staged_output_does_not_partially_publish(self):
        hashes=self.releases();(self.stage/r.OUTPUTS[-1]).unlink()
        with self.assertRaises(FileNotFoundError):r.install(self.repo,self.stage,hashes)
        for name,sha in hashes.items():self.assertEqual(r.digest(self.repo/name),sha)
    def test_actual_policy_comparison_reports_both_conflicts(self):
        self.write(self.stage,'alan/assumptions.csv','id,value\nbaseline_training_window,"[2023, 2024, 2025]"\nfbo_market_share,0.2\n')
        self.write(self.stage,r.P2+'provisional_inputs/historical_traffic.csv','date\n2016-01-01\n2023-01-01\n')
        self.write(self.stage,r.P2+'provisional_inputs/monthly_reconciliation.csv','assumed_fbo_movements,airport_private_ops\n25,100\n')
        self.assertEqual(len(r.assumption_mismatches(self.stage)),2)
        self.write(self.stage,r.P2+'provisional_inputs/historical_traffic.csv','date\n2023-01-01\n2024-01-01\n2025-01-01\n')
        self.write(self.stage,r.P2+'provisional_inputs/monthly_reconciliation.csv','assumed_fbo_movements,airport_private_ops\n20,100\n')
        self.assertEqual(r.assumption_mismatches(self.stage),[])
