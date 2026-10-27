"""Expose review provenance separately from numerical/model validation."""
import csv
import hashlib
import json
from pathlib import Path
from .contracts import ContractError, DATES, number

P2='forecast/main_forecast/'
MANIFEST=P2+'release_manifest.json'
EVIDENCE_MANIFEST=P2+'event_evidence_manifest.json'
EVIDENCE_FILES={P2+p for p in ('FAA_EVENT_UPDATE.md','build_event_inputs.py',
    'provisional_inputs/event_evidence.json','test_forecast_model.py',
    'forecast_output_contract.json','provisional_inputs/monthly_reconciliation.csv')} | {
    'parking/test_parking_optimizer.py',
    'sources/airport_traffic/data/processed/superbowl_lvi_surge.csv',
    'sources/airport_traffic/data/processed/superbowl_lvi_daily_profile.csv',
    'sources/airport_traffic/data/processed/opsnet_daily_superbowl.csv',
    'sources/airport_traffic/scripts/analyze_superbowl_lvi.py',
    'sources/airport_traffic/data_sources_lawa_bts.md',
    'sources/airport_traffic/data/processed/opsnet_lax_monthly.csv',
    'sources/data/processed/security_restriction_model_input.csv',
    'parking/resource_requirements_security_restriction.csv',
    'parking/scenario_recommendations_security_restriction.json'}
RELEASE_FILES={P2+p for p in (
    'demand_predictions.csv','uncertainty_results.csv','evaluation_metrics.csv',
    'daily_totals.csv','run_metadata.json','forecast_model.py',
    'convert_monthly_to_daily.py','PROVISIONAL_ASSUMPTIONS.md','run_provisional.py',
    'provisional_inputs/historical_traffic.csv','provisional_inputs/holiday_history.csv',
    'provisional_inputs/planning_inputs.csv',
)}|{'parking/'+p for p in ('resource_requirements.csv','scenario_recommendations.json','assumptions_p3.csv','parking_optimizer.py','ordinary_week_parking.csv','parking_carryover.csv','resource_requirements_departure_delay_24h.csv','scenario_recommendations_departure_delay_24h.json')}|{'sources/airport_traffic/data/processed/opsnet_lax_daily.csv'}

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def evidence_review(root, run_id):
    """Validate the optional FAA-event release as one complete, versioned set."""
    root=Path(root).resolve();path=root/EVIDENCE_MANIFEST
    enabled=path.exists() or (root/(P2+'build_event_inputs.py')).exists() or (root/(P2+'provisional_inputs/event_evidence.json')).exists()
    if not enabled:return None
    if not path.is_file() or path.stat().st_size>100_000:
        raise ContractError('FAA event evidence manifest is missing or too large.')
    try:audit=json.loads(path.read_text(encoding='utf-8-sig'))
    except ValueError as exc:raise ContractError('FAA event evidence manifest contains invalid JSON.') from exc
    if not isinstance(audit,dict) or audit.get('release_run_id')!=run_id or not isinstance(audit.get('files'),dict) or set(audit['files'])!=EVIDENCE_FILES:
        raise ContractError('FAA event evidence manifest must match this release and the documented 16 evidence files.')
    for name,expected in audit['files'].items():
        target=(root/name).resolve()
        if not target.is_relative_to(root) or not target.is_file() or target.stat().st_size>5_000_000 or digest(target)!=expected:
            raise ContractError('FAA event evidence mismatch: '+name+'. Regenerate the complete release.')
    return digest(path)

def release_review(repo,bundle):
    root=Path(repo).resolve();path=root/MANIFEST
    if not path.is_file():
        return {'status':'unreviewed','label':'Synthetic team demonstration — not an approved forecast' if bundle['meta']['data_classification']=='synthetic' else 'Provisional team estimates — review not recorded',
                'message':'No matched release manifest or the data team review record was supplied. Numerical checks do not establish approval or forecasting accuracy.',
                'manifest_verified':False,'run_id':None}
    if path.stat().st_size>100_000:raise ContractError('Release manifest is too large.')
    try:m=json.loads(path.read_text(encoding='utf-8-sig'))
    except ValueError as exc:raise ContractError('Release manifest contains invalid JSON.') from exc
    if not isinstance(m,dict) or not isinstance(m.get('files'),dict) or set(m['files'])!=RELEASE_FILES:
        raise ContractError('Release manifest must list the documented 20 producer/source files.')
    expected_run=hashlib.sha256(json.dumps(m['files'],sort_keys=True).encode()).hexdigest()
    if m.get('run_id')!=expected_run:raise ContractError('Release manifest run ID does not match its file hashes.')
    for name,expected in m['files'].items():
        target=(root/name).resolve()
        if not target.is_relative_to(root) or not target.is_file() or target.stat().st_size>5_000_000:
            raise ContractError('Release manifest file unavailable or invalid: '+name)
        if digest(target)!=expected:
            raise ContractError('Release manifest mismatch: '+name+'. Regenerate the complete P2/P3 release before loading it.')
    evidence_sha=evidence_review(root,m['run_id'])
    status=m.get('status')
    return {'status':'provisional_pending_data_review' if status=='provisional_pending_data_review' else 'unreviewed',
            'label':'Provisional — pending the data team’s review' if status=='provisional_pending_data_review' else 'Producer release — approval not verified',
            'message':'Matched release files do not establish team approval. The data team’s baseline update does not automatically update this forecast’s training window or FBO-share assumptions. Review those choices before presenting these estimates as the agreed team forecast.',
            'manifest_verified':True,'run_id':m['run_id'],'manifest_sha256':digest(path),
            **({'event_evidence_manifest_sha256':evidence_sha} if evidence_sha else {})}

def attach_release_status(repo,bundle):
    status=release_review(repo,bundle)
    bundle['release_review']=status
    bundle['version']=hashlib.sha256(json.dumps({'model_version':bundle['version'],'release_review':status},sort_keys=True).encode()).hexdigest()
    return bundle

def sources_reference(repo):
    """Display the data team's supplied reference without mixing aircraft and space units."""
    root=Path(repo);bp=root/'sources/baseline.csv';ap=root/'sources/assumptions.csv'
    if not bp.is_file() or not ap.is_file():return {'available':False,'message':'the data team’s baseline and assumption files have not both been supplied.'}
    try:
        if max(bp.stat().st_size,ap.stat().st_size)>2_000_000:raise ValueError('Reference files exceed the size limit.')
        with bp.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
        with ap.open(encoding='utf-8-sig',newline='') as f:assumptions=list(csv.DictReader(f))
        if len(rows)!=7 or {r['date'] for r in rows}!=set(DATES):raise ValueError('Expected all seven baseline dates.')
        values=[{'date':r['date'],**{k:number(r[k],'the data team '+k) for k in ('arrivals','departures','parking_units')}} for r in rows]
        selected=[{'label':r['label'],'value':r['value'],'note':r['note']} for r in assumptions if r['id'] in ('baseline_training_window','fbo_market_share','parking_units_method')]
        return {'available':True,'rows':sorted(values,key=lambda r:r['date']),'assumptions':selected,
                'files':{'sources/baseline.csv':digest(bp),'sources/assumptions.csv':digest(ap)},
                'message':'Estimated ordinary-week reference from the data team’s committed files, not observed FBO traffic. Its parking_units field currently estimates parked aircraft using arrivals × dwell time; it is not the parking team’s size-weighted space units. It does not replace the forecast or parking simulation.'}
    except (ValueError,KeyError,OSError) as exc:return {'available':False,'message':'the data team reference could not be validated: '+str(exc)}
