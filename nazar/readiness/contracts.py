"""Strict file contracts at the boundary between the four team modules."""
from __future__ import annotations
import csv
import hashlib
import io
import json
import math
from datetime import date, timedelta

START = date(2027, 2, 11)
DATES = [(START + timedelta(days=i)).isoformat() for i in range(7)]
SCENARIOS = ('low', 'medium', 'high')
FILES = ('manifest.json', 'baseline.csv', 'demand_predictions.csv',
         'uncertainty_results.csv', 'resource_requirements.csv',
         'scenario_recommendations.json', 'assumptions.csv')
ACTION_TYPES = {
    'verify_bookings': 'Verify booking estimates',
    'confirm_overflow': 'Confirm additional parking',
    'staffing_review': 'Review ground staffing',
    'fuel_review': 'Review fuel-service readiness',
    'monitor_capacity': 'Monitor parking demand',
}
RESOURCE_FIELDS = ('parking_units', 'capacity_units', 'prepared_capacity_units',
                   'staff_required', 'staff_available', 'prepared_staff',
                   'fuel_gallons', 'fuel_available_gallons', 'preparation_cost')

class ContractError(ValueError):
    pass

def fail(message):
    raise ContractError(message)

def text(value, field, limit=1200):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        fail(f'{field}: provide nonempty text up to {limit} characters.')
    return value.strip()

def number(value, field):
    if isinstance(value, bool):
        fail(f'{field}: a nonnegative finite number is required.')
    try:
        n = float(value)
    except (TypeError, ValueError):
        fail(f'{field}: a nonnegative finite number is required.')
    if not math.isfinite(n) or n < 0 or n > 1e9:
        fail(f'{field}: number must be finite and between 0 and 1 billion.')
    return n

def csv_rows(files, name, required, optional=()):
    source = files[name]
    reader = csv.DictReader(io.StringIO(source.lstrip('\ufeff')))
    fields = reader.fieldnames or []
    if len(fields) != len(set(fields)):
        fail(f'{name}: duplicate column names.')
    missing = set(required) - set(fields)
    unknown = set(fields) - set(required) - set(optional)
    if missing:
        fail(f'{name}: missing columns {", ".join(sorted(missing))}.')
    if unknown:
        fail(f'{name}: unsupported columns {", ".join(sorted(unknown))}; remove identifying data and use the documented aggregate schema.')
    rows = list(reader)
    if not rows or len(rows) > 5000:
        fail(f'{name}: expected 1–5000 rows.')
    if any(None in r or any(v is None for v in r.values()) for r in rows):
        fail(f'{name}: malformed CSV row.')
    return rows

def unique(rows, fields, name):
    keys = [tuple(r[f] for f in fields) for r in rows]
    if len(keys) != len(set(keys)):
        fail(f'{name}: duplicate {"/".join(fields)}.')

def load_bundle(files):
    if set(files) != set(FILES):
        fail('Provide exactly these files: ' + ', '.join(FILES) + '. Missing: ' + ', '.join(sorted(set(FILES)-set(files))) + '.')
    if any(not isinstance(v, str) or len(v.encode()) > 2_000_000 for v in files.values()):
        fail('Each input file must be UTF-8 text under 2 MB.')
    try:
        meta = json.loads(files['manifest.json'])
        recs = json.loads(files['scenario_recommendations.json'])
    except (ValueError, TypeError) as exc:
        fail(f'Invalid JSON: {exc}')
    if not isinstance(meta, dict) or set(meta) != {'schema_version','dataset_name','fbo_name','airport','timezone','window_start','window_end','data_classification','interval_kind','interval_description','model_version','generated_at','notes'}:
        fail('manifest.json: use exactly the documented metadata fields.')
    if meta['schema_version'] != '1.0' or meta['airport'] != 'LAX' or meta['timezone'] != 'America/Los_Angeles':
        fail('Manifest must use schema 1.0, LAX and America/Los_Angeles.')
    if meta['window_start'] != DATES[0] or meta['window_end'] != DATES[-1]:
        fail('Planning window must be February 11–17, 2027.')
    if meta['data_classification'] not in ('synthetic','mixed','observed'):
        fail('Manifest data_classification must be synthetic, mixed or observed.')
    if meta['interval_kind'] not in ('assumed_range','model_quantiles','prediction_interval'):
        fail('Manifest interval_kind must describe how the interval was constructed.')
    for key in meta:
        text(meta[key], 'manifest.'+key)
    baseline = csv_rows(files, 'baseline.csv', ('date','arrivals','departures','parking_units'))
    unique(baseline, ('date',), 'baseline.csv')
    if {r['date'] for r in baseline} != set(DATES):
        fail('baseline.csv: include all seven planning dates exactly once.')
    for r in baseline:
        for f in ('arrivals','departures','parking_units'): r[f] = number(r[f], 'baseline.'+f)
    demand = csv_rows(files, 'demand_predictions.csv', ('scenario','date','arrivals','departures'))
    intervals = csv_rows(files, 'uncertainty_results.csv', ('scenario','date','arrivals_lower','arrivals_upper'))
    expected = {(s,d) for s in SCENARIOS for d in DATES}
    for name, rows in [('demand_predictions.csv', demand), ('uncertainty_results.csv', intervals)]:
        unique(rows, ('scenario','date'), name)
        if {(r['scenario'],r['date']) for r in rows} != expected:
            fail(f'{name}: include each of three scenarios for each of seven dates (21 rows).')
        for r in rows:
            for f in set(r)-{'scenario','date'}: r[f] = number(r[f], name+'.'+f)
    bands = {(r['scenario'],r['date']):r for r in intervals}
    for r in demand:
        band = bands[(r['scenario'],r['date'])]
        if not band['arrivals_lower'] <= r['arrivals'] <= band['arrivals_upper']:
            fail('uncertainty_results.csv: lower ≤ expected arrivals ≤ upper is required for every row.')
        r.update({k:band[k] for k in ('arrivals_lower','arrivals_upper')})
    resources = csv_rows(files, 'resource_requirements.csv', ('scenario','variant','date',*RESOURCE_FIELDS))
    unique(resources, ('scenario','variant','date'), 'resource_requirements.csv')
    variants = {r['variant'] for r in resources}
    if 'standard' not in variants or not variants <= {'standard','departure_delay_24h'}:
        fail('Resources require standard; departure_delay_24h is the only optional variant.')
    if {(r['scenario'],r['variant'],r['date']) for r in resources} != {(s,v,d) for s in SCENARIOS for v in variants for d in DATES}:
        fail('resource_requirements.csv: each supplied variant needs all 21 scenario/date rows.')
    for r in resources:
        for f in RESOURCE_FIELDS: r[f] = number(r[f], 'resources.'+f)
        if r['prepared_capacity_units'] < r['capacity_units']:
            fail('Prepared capacity cannot be below the ordinary capacity in this comparison contract.')
        if r['prepared_staff'] < r['staff_available']:
            fail('Prepared staffing cannot be below ordinary available staffing.')
    assumptions = csv_rows(files, 'assumptions.csv', ('id','label','value','unit','classification','source','note'))
    unique(assumptions, ('id',), 'assumptions.csv')
    for r in assumptions:
        for f in r: text(r[f], 'assumptions.'+f)
        if r['classification'] not in ('public','synthetic','assumption','benchmark'):
            fail('Assumption classification must be public, synthetic, assumption or benchmark.')
    if not isinstance(recs, list) or len(recs) > 100:
        fail('scenario_recommendations.json must be a list with no more than 100 actions.')
    required = {'id','scenario','variant','action_type','reason','owner','due_date','affected_dates','source','evidence'}
    lookup = {(r['scenario'],r['variant'],r['date']):r for r in resources}
    seen=set()
    for rec in recs:
        if not isinstance(rec,dict) or set(rec) != required:
            fail('Every recommendation must match the documented action schema exactly.')
        for f in ('id','reason','owner','source'): text(rec[f], 'recommendation.'+f)
        if rec['scenario'] not in SCENARIOS or rec['variant'] not in variants or rec['action_type'] not in ACTION_TYPES:
            fail('Recommendation scenario, variant or action_type is unsupported.')
        if rec['owner'] not in ('manager','reservations','operations'):
            fail('Recommendation owner must be manager, reservations or operations.')
        key=(rec['scenario'],rec['variant'],rec['id'])
        if key in seen: fail('Duplicate recommendation ID within a scenario and variant.')
        seen.add(key)
        if not isinstance(rec['affected_dates'],list) or not rec['affected_dates'] or not set(rec['affected_dates']) <= set(DATES):
            fail('Recommendation affected_dates must contain planning dates.')
        try: date.fromisoformat(rec['due_date'])
        except (ValueError,TypeError): fail('Recommendation due_date must be an ISO date.')
        if not isinstance(rec['evidence'],list) or not rec['evidence']:
            fail('Each recommendation requires at least one numerical evidence reference.')
        for e in rec['evidence']:
            if not isinstance(e,dict) or set(e) != {'date','field','value'} or e['date'] not in rec['affected_dates'] or e['field'] not in RESOURCE_FIELDS:
                fail('Recommendation evidence must reference an affected date and a resource field.')
            actual=lookup[(rec['scenario'],rec['variant'],e['date'])][e['field']]
            if abs(number(e['value'],'evidence.value')-actual)>1e-6:
                fail(f'Recommendation {rec["id"]}: evidence does not match the resource output.')
        rec['title']=ACTION_TYPES[rec['action_type']]
    canonical=json.dumps({'meta':meta,'baseline':baseline,'demand':demand,'resources':resources,'recommendations':recs,'assumptions':assumptions},sort_keys=True,separators=(',',':'))
    version=hashlib.sha256(canonical.encode()).hexdigest()
    return {'version':version,'meta':meta,'baseline':sorted(baseline,key=lambda r:r['date']),
            'demand':demand,'resources':resources,'recommendations':recs,
            'assumptions':assumptions,'variants':sorted(variants)}

def summarize(bundle, scenario, variant):
    if scenario not in SCENARIOS or variant not in bundle['variants']:
        fail('Unsupported scenario or stress-test variant.')
    rows=sorted([r for r in bundle['resources'] if r['scenario']==scenario and r['variant']==variant],key=lambda r:r['date'])
    before=[max(0,r['parking_units']-r['capacity_units']) for r in rows]
    after=[max(0,r['parking_units']-r['prepared_capacity_units']) for r in rows]
    peak=max(rows,key=lambda r:r['parking_units'])
    return {'peak_demand':peak['parking_units'],'peak_date':peak['date'],
            'peak_shortfall':max(before),'remaining_shortfall':max(after),
            'days_over_capacity':sum(x>0 for x in before),'remaining_days':sum(x>0 for x in after),
            'first_shortage':next((r['date'] for r,gap in zip(rows,before) if gap>0),None),
            'preparation_cost':sum(r['preparation_cost'] for r in rows),
            'capacity_at_peak':peak['capacity_units'],
            'peak_extra_capacity':max(r['prepared_capacity_units']-r['capacity_units'] for r in rows),
            'max_staff':max(r['staff_required'] for r in rows),
            'total_fuel':sum(r['fuel_gallons'] for r in rows)}
