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
        subprocess.run(command,cwd=ROOT,check=True)
    for name,columns in contract['csv_columns'].items():
        assert read(HERE/name)[0]==columns, f'Schema changed: {name}'
    meta=json.loads((HERE/'run_metadata.json').read_text())
    assert list(meta)==contract['metadata_keys']
    assert meta['historical_data_classes']==['estimated']
    _,history=read(HERE/'provisional_inputs/historical_traffic.csv')
    assert len(history)==7671 and all(r['data_class']=='estimated' for r in history)
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
    paths=[HERE/name for name in contract['csv_columns']]
    paths += [HERE/'run_metadata.json',HERE/'forecast_model.py',HERE/'convert_monthly_to_daily.py',
              HERE/'PROVISIONAL_ASSUMPTIONS.md',HERE/'run_provisional.py',
              HERE/'provisional_inputs/historical_traffic.csv',HERE/'provisional_inputs/planning_inputs.csv',
              P3/'resource_requirements.csv',P3/'scenario_recommendations.json',P3/'assumptions_p3.csv',
              P3/'parking_optimizer.py',source]
    manifest={'generated_at':datetime.now(timezone.utc).isoformat(),
              'status':'provisional_pending_Alan_review','historical_data_class':'estimated',
              'reservation_class':'synthetic','event_multipliers':'assumed_not_empirically_validated',
              'files':{str(p.relative_to(ROOT)).replace(chr(92),'/'):digest(p) for p in paths}}
    manifest['run_id']=hashlib.sha256(json.dumps(manifest['files'],sort_keys=True).encode()).hexdigest()
    (HERE/'release_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Verified schema stability, provenance, monthly conservation, forecast/range consistency and source preservation.')
if __name__=='__main__': run()

