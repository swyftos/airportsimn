"""Build Alan -> Marvin -> Elia -> verification in an isolated tracked-file snapshot.

Nothing is fetched from the internet or silently reclassified as approved.
Only the declared outputs are installed, after all checks pass.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[2]
P2 = 'marvin/person_2_forecasting/'
MANIFEST = P2 + 'release_manifest.json'
REPORT = 'nazar/team_release_report.json'
EVIDENCE_MANIFEST = P2 + 'event_evidence_manifest.json'
EVIDENCE_OUTPUTS = (P2+'provisional_inputs/event_evidence.json', EVIDENCE_MANIFEST)
OUTPUTS = (
    'alan/data/processed/historical_traffic_interim.csv',
    'alan/data/processed/historical_traffic_interim.validation.json',
    'alan/baseline.csv', 'alan/assumptions.csv', 'assumptions.csv',
    *(P2 + n for n in ('provisional_inputs/historical_traffic.csv',
      'provisional_inputs/monthly_reconciliation.csv','provisional_inputs/planning_inputs.csv',
      'demand_predictions.csv','uncertainty_results.csv','evaluation_metrics.csv',
      'daily_totals.csv','run_metadata.json')),
    *('elia/' + n for n in ('resource_requirements.csv','scenario_recommendations.json',
      'ordinary_week_parking.csv','parking_carryover.csv',
      'resource_requirements_departure_delay_24h.csv','scenario_recommendations_departure_delay_24h.json')),
)

class ReleaseError(Exception):
    pass

def output_names(root):
    return OUTPUTS + (EVIDENCE_OUTPUTS if (root/(P2+'build_event_inputs.py')).is_file() else ())

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run_step(root, label, *args):
    print(f'\n[{label}]', flush=True)
    subprocess.run([sys.executable, '-B', *args], cwd=root, check=True,
                   env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1'})

def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def assumption_mismatches(root):
    """Compare actual converted P2 inputs with Alan's declared baseline policy."""
    ledger = {r['id']:r['value'] for r in rows(root/'alan/assumptions.csv')}
    years = sorted({int(r['date'][:4]) for r in rows(root/(P2+'provisional_inputs/historical_traffic.csv'))})
    alan_years = sorted(json.loads(ledger['baseline_training_window']))
    alan_share = float(ledger['fbo_market_share'])
    actual_shares = {round(float(r['assumed_fbo_movements'])/float(r['airport_ga_ops']), 8)
                     for r in rows(root/(P2+'provisional_inputs/monthly_reconciliation.csv'))
                     if float(r['airport_ga_ops']) > 0}
    issues = []
    if years != alan_years:
        issues.append(f'History years differ: Alan {alan_years}; Marvin converted history {years}. This compares input windows, not the fitted train/calibration/test split.')
    if not actual_shares or any(abs(s-alan_share)>1e-8 for s in actual_shares):
        issues.append(f'FBO share differs: Alan {alan_share:g}; Marvin {sorted(actual_shares)}.')
    return issues

def opening_check(root):
    # Call the owner's explicit check; never silently change the assumption ledger.
    run_step(root, 'Elia opening-inventory check', '-c',
        "import sys;sys.path.insert(0,'elia');import test_parking_optimizer as t;t.test_opening_inventory_follows_p2_baseline()")

def stamp_manifest(root):
    sys.path.insert(0, str(REPO/'nazar'))
    from readiness.release_status import RELEASE_FILES, EVIDENCE_FILES
    files = {p:digest(root/p) for p in sorted(RELEASE_FILES)}
    manifest = {'generated_at':datetime.now(timezone.utc).isoformat(),
                'status':'provisional_pending_Alan_review', 'historical_data_class':'estimated',
                'reservation_class':'synthetic', 'event_multipliers':'FAA_ATADS_OPSNET_anchored_FBO_transfer_assumption' if (root/(P2+'build_event_inputs.py')).is_file() else 'assumed_not_empirically_validated',
                'files':files,
                'run_id':hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()}
    (root/MANIFEST).write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    if (root/(P2+'build_event_inputs.py')).is_file():
        evidence={'release_run_id':manifest['run_id'],'files':{p:digest(root/p) for p in sorted(EVIDENCE_FILES)}}
        (root/EVIDENCE_MANIFEST).write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    return manifest

def build(root, allow_mismatch=False):
    run_step(root, 'Alan: validate and allocate monthly history', 'alan/scripts/build_historical_traffic.py')
    run_step(root, 'Alan: ordinary baseline and assumptions', 'alan/scripts/build_baseline.py')
    run_step(root, 'Marvin: explicit estimated FBO allocation', P2+'convert_monthly_to_daily.py')
    issues = assumption_mismatches(root)
    if issues:
        print('\nUNRESOLVED ASSUMPTIONS:\n'+'\n'.join(issues),flush=True)
        if not allow_mismatch:
            raise ReleaseError('Alan and Marvin must agree on the history window/share. No working files were changed. For an explicitly provisional demo only, use --allow-provisional-mismatch.')
    run_step(root, 'Marvin: forecast and uncertainty', P2+'forecast_model.py',
             '--history', P2+'provisional_inputs/historical_traffic.csv',
             '--planning', P2+'provisional_inputs/planning_inputs.csv', '--output-dir', P2.rstrip('/'))
    opening_check(root)
    run_step(root, 'Elia: all parking variants and carryover', 'elia/parking_optimizer.py', P2.rstrip('/'))
    run_step(root, 'Alan: consolidated assumption ledger', 'alan/scripts/merge_assumptions.py')
    run_step(root, 'Verify every parking output against the forecast', 'nazar/scripts/verify_team_pipeline.py')
    manifest = stamp_manifest(root)
    run_step(root, 'Forecast tests', '-m','unittest','discover','-s',P2.rstrip('/'),'-p','test_*.py')
    run_step(root, 'Parking tests', '-c',
        "import sys;sys.path.insert(0,'elia');import test_parking_optimizer as t;names=[n for n in dir(t) if n.startswith('test_')];[getattr(t,n)() for n in names];print(f'{len(names)} parking tests passed')")
    run_step(root, 'Dashboard, release and integration tests', '-m','unittest','discover','-s','nazar/tests')
    report = {'status':'provisional_pending_Alan_review','generated_at':manifest['generated_at'],
              'release_run_id':manifest['run_id'],'assumption_mismatches':issues,
              'provisional_mismatch_override':allow_mismatch,
              'output_sha256':{p:digest(root/p) for p in (*output_names(root),MANIFEST)},
              'meaning':'Outputs reproduce together; assumptions, forecast accuracy and safe capacity are not approved.'}
    (root/REPORT).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')

def snapshot(repo, stage):
    listed = subprocess.check_output(['git','ls-files','-z'],cwd=repo).decode().split('\0')
    fingerprints = {}
    for rel in filter(None, listed):
        path = repo/rel
        if path.is_symlink() or not path.is_file():
            raise ReleaseError(f'Tracked file missing or symlink unsupported: {rel}')
        content = path.read_bytes()
        fingerprints[rel] = hashlib.sha256(content).hexdigest()
        dest = stage/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(content)
    # Optional new reports are still protected against concurrent edits.
    for rel in (*OUTPUTS, *EVIDENCE_OUTPUTS, MANIFEST, REPORT):
        fingerprints.setdefault(rel, digest(repo/rel) if (repo/rel).is_file() else None)
    return fingerprints

def unchanged(repo, fingerprints):
    for rel, before in fingerprints.items():
        path = repo/rel
        if path.is_symlink() or (digest(path) if path.is_file() else None) != before:
            raise ReleaseError(f'Working file changed during the build: {rel}. Retry after edits stop; no release was installed.')

def replace_bytes(path, content):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent,prefix='.team-release-')
    try:
        with os.fdopen(fd,'wb') as f:f.write(content)
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)

def install(repo, stage, fingerprints):
    unchanged(repo, fingerprints)
    # Validate the whole list before any write. Manifest last: interrupted updates
    # are rejected by the dashboard rather than accepted as a mixed release.
    names = (*output_names(stage), REPORT, MANIFEST)
    incoming = {n:(stage/n).read_bytes() for n in names}
    previous = {n:(repo/n).read_bytes() if (repo/n).exists() else None for n in names}
    written = []
    try:
        for name in names:
            if incoming[name] == previous[name]:continue
            replace_bytes(repo/name,incoming[name]);written.append(name)
    except BaseException:
        for name in reversed(written):
            if previous[name] is None:(repo/name).unlink(missing_ok=True)
            else:replace_bytes(repo/name,previous[name])
        raise

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only',action='store_true',help='Build and verify in a temporary directory; do not install outputs.')
    parser.add_argument('--allow-provisional-mismatch',action='store_true',help='Explicitly permit documented Alan/P2 window/share mismatches for demo reproduction; never marks them approved.')
    args=parser.parse_args(argv)
    lock=REPO/'nazar/.state/team-release.lock'
    acquired=False
    try:
        if any(importlib.util.find_spec(n) is None for n in ('numpy','pandas')):
            raise ReleaseError('Use a Python environment with numpy and pandas installed. Example: python3 -m pip install numpy pandas')
        lock.parent.mkdir(parents=True,exist_ok=True)
        try:
            with lock.open('x') as f:f.write(str(os.getpid()))
        except FileExistsError:
            raise ReleaseError(f'Another release may be running. Lock: {lock}. Only remove a stale lock after confirming no release process remains.')
        acquired=True
        with tempfile.TemporaryDirectory(prefix='intelligent-fbo-release-') as temp:
            stage=Path(temp)
            fingerprints=snapshot(REPO,stage)
            build(stage,args.allow_provisional_mismatch)
            unchanged(REPO,fingerprints)
            if args.check_only:print('\nPASS: staged provisional release verified; working outputs unchanged.')
            else:
                install(REPO,stage,fingerprints)
                print('\nPASS: complete provisional release installed. Commit all changed outputs together, then refresh the dashboard. See '+REPORT)
        return 0
    except (ReleaseError,subprocess.CalledProcessError,OSError,ValueError,KeyError) as exc:
        print(f'\nRelease stopped: {exc}',file=sys.stderr)
        return 1
    finally:
        if acquired:lock.unlink(missing_ok=True)

if __name__=='__main__':sys.exit(main())
