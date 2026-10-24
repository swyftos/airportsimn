"""Regenerate matching P2/P3 artifacts on an isolated branch; preserve native schemas."""
import csv, hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
P2=HERE.relative_to(ROOT)
P3=ROOT/'elia'
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    with p.open(newline='',encoding='utf-8-sig') as f:
        r=csv.DictReader(f)
        return r.fieldnames,list(r)
def run():
    contract=json.loads((HERE/'forecast_output_contract.json').read_text(encoding='utf-8-sig'))
    source=ROOT/'alan/elia_output/data/processed/lax_monthly_movements.csv'
    source_hash=digest(source)
    p3_headers,_=read(P3/'resource_requirements.csv')
    before=json.loads((P3/'scenario_recommendations.json').read_text())
    commands=[
        [sys.executable,str(P2/'convert_monthly_to_daily.py')],
        [sys.executable,str(P2/'forecast_model.py'),'--history',str(P2/'provisional_inputs/historical_traffic.csv'),
         '--planning',str(P2/'provisional_inputs/planning_inputs.csv'),'--output-dir',str(P2)],
        [sys.executable,'elia/parking_optimizer.py',str(P2)]]
    for command in commands:
        if command[1]=='elia/parking_optimizer.py':
            # Preserve Elia's opening-dwell assumption; refresh its derived inventory.
            columns, assumptions = read(P3/'assumptions_p3.csv')
            dwell = float(next(r['value'] for r in assumptions if r['parameter']=='opening_dwell_days'))
            _, forecasts = read(HERE/'demand_predictions.csv')
            first = min(r['date'] for r in forecasts)
            baseline = sum(float(r['baseline_arrivals']) for r in forecasts if r['date']==first and r['scenario']=='Medium')
            for r in assumptions:
                if r['parameter']=='initial_transient_aircraft':
                    r['value'] = str(round(baseline*dwell, 1))
                    r['source_or_rationale'] = f'P2 ordinary arrivals {baseline:.3f} x opening_dwell_days {dwell}; derived estimate refreshed with this release, not observed inventory.'
            with (P3/'assumptions_p3.csv').open('w',newline='',encoding='utf-8') as f:
                w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows(assumptions)
        subprocess.run(command,cwd=ROOT,check=True)
    for name,columns in contract['csv_columns'].items():
        assert read(HERE/name)[0]==columns, f'Schema changed: {name}'
    meta=json.loads((HERE/'run_metadata.json').read_text())
    assert list(meta)==contract['metadata_keys']
    assert meta['historical_data_classes']==['estimated']
    _,history=read(HERE/'provisional_inputs/historical_traffic.csv')
    assert len(history)==3288 and all(r['data_class']=='estimated' for r in history)
    assert all('2023-01-01' <= r['date'] <= '2025-12-31' for r in history)
    monthly=defaultdict(float)
    for r in history:
        monthly[r['date'][:7]]+=float(r['arrivals'])+float(r['departures'])
    _,checks=read(HERE/'provisional_inputs/monthly_reconciliation.csv')
    for r in checks:
        assert abs(monthly[r['month']]-float(r['assumed_fbo_movements']))<1e-7
    _,demand=read(HERE/'demand_predictions.csv')
    _,uncertainty=read(HERE/'uncertainty_results.csv')
    _,metrics=read(HERE/'evaluation_metrics.csv')
    assert (len(demand),len(uncertainty),len(metrics))==(63,126,6)
    keyed={(r['date'],r['scenario'],r['aircraft_category']):r for r in demand}
    assert len(keyed)==63
    for r in uncertainty:
        t=r['target']; d=keyed[r['date'],r['scenario'],r['aircraft_category']]
        assert float(r['expected'])==float(d['expected_'+t])
        assert float(r['lower'])<=float(r['expected'])<=float(r['upper'])
        assert r['historical_data_class']=='estimated' and r['event_coverage_validated']=='False'
    assert all(r['data_class']=='estimated' and r['evaluation_type']=='non_observed_demonstration' for r in metrics)
    assert read(P3/'resource_requirements.csv')[0]==p3_headers
    after=json.loads((P3/'scenario_recommendations.json').read_text())
    assert list(after)==list(before) and list(after['meta'])==list(before['meta'])
    assert after['meta']['demand_provenance']==['estimated']
    assert digest(source)==source_hash
    # Verify every standard/ordinary/delay artifact before stamping this release.
    subprocess.run([sys.executable, '-B', 'nazar/scripts/verify_team_pipeline.py'], cwd=ROOT, check=True)
    paths=[HERE/name for name in contract['csv_columns']]
    paths += [HERE/'run_metadata.json',HERE/'forecast_model.py',HERE/'convert_monthly_to_daily.py',
              HERE/'PROVISIONAL_ASSUMPTIONS.md',HERE/'run_provisional.py',
              HERE/'provisional_inputs/historical_traffic.csv',HERE/'provisional_inputs/planning_inputs.csv',
              P3/'resource_requirements.csv',P3/'scenario_recommendations.json',P3/'assumptions_p3.csv',
              P3/'parking_optimizer.py',source,
              P3/'ordinary_week_parking.csv',P3/'parking_carryover.csv',
              P3/'resource_requirements_departure_delay_24h.csv',
              P3/'scenario_recommendations_departure_delay_24h.json']
    evidence_paths = [HERE/'FAA_EVENT_UPDATE.md',P3/'test_parking_optimizer.py',
              HERE/'build_event_inputs.py',HERE/'provisional_inputs/event_evidence.json',
              HERE/'test_forecast_model.py',HERE/'forecast_output_contract.json',
              HERE/'provisional_inputs/monthly_reconciliation.csv',
              ROOT/'alan/elia_output/data/processed/superbowl_lvi_surge.csv',
              ROOT/'alan/elia_output/data/processed/superbowl_lvi_daily_profile.csv',
              ROOT/'alan/elia_output/data/processed/opsnet_daily_superbowl.csv',
              ROOT/'alan/elia_output/scripts/analyze_superbowl_lvi.py',
              ROOT/'alan/elia_output/data_sources_lawa_bts.md']
    manifest={'generated_at':datetime.now(timezone.utc).isoformat(),
              'status':'provisional_pending_Alan_review','historical_data_class':'estimated',
              'reservation_class':'synthetic','event_multipliers':'FAA_ATADS_OPSNET_anchored_FBO_transfer_assumption',
              'files':{str(p.relative_to(ROOT)).replace(chr(92),'/'):digest(p) for p in paths}}
    manifest['run_id']=hashlib.sha256(json.dumps(manifest['files'],sort_keys=True).encode()).hexdigest()
    (HERE/'release_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    # Keep Nazar's exact 20-file manifest contract. Additional evidence has a separate audit sidecar.
    audit={'release_run_id':manifest['run_id'],
           'files':{str(p.relative_to(ROOT)).replace(chr(92),'/'):digest(p) for p in evidence_paths}}
    (HERE/'event_evidence_manifest.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print('Verified schema stability, provenance, monthly conservation, forecast/range consistency and source preservation.')
if __name__=='__main__': run()
