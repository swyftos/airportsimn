"""Presentation adapters for the supplied RampReady design.

Producer forecast and parking code is unchanged. The optional hourly illustration
rounds daily category forecasts into fictitious visits and states its timing rule;
it is not a reconstruction of bookings or the P3 Monte Carlo paths.
"""
import csv
import io
import math
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from .contracts import DATES, ContractError, SCENARIOS, summarize

TZ = ZoneInfo('America/Los_Angeles')
CATS = ('light_jet','midsize_jet','large_jet')


def rounded(value):
    return int(math.floor(float(value) + .5))


def assumptions(bundle):
    return {a['id']:a for a in bundle['assumptions']}


def allocate(values):
    """Largest remainder preserves the rounded daily total across categories."""
    whole = [math.floor(x) for x in values]
    left = rounded(sum(values)) - sum(whole)
    for i in sorted(range(len(values)),key=lambda i:values[i]-whole[i],reverse=True)[:left]:whole[i]+=1
    return whole


def illustration(bundle, scenario, variant):
    ledger=assumptions(bundle)
    def val(key,default):return float(ledger.get(key,{}).get('value',default))
    weights={c:val('su_'+c.replace('_jet',''),1) for c in CATS}
    if not bundle.get('category_ranges'):
        return {'visits':[],'hours':[],'available':False,'note':'This source does not include category forecasts for an hourly illustration.'}
    lookup={(r['date'],r['category'],r['direction']):r['expected'] for r in bundle['category_ranges'] if r['scenario']==scenario}
    start=datetime.fromisoformat(DATES[0]).replace(tzinfo=TZ)
    end=start+timedelta(days=7)
    visits=[];live={c:[] for c in CATS}
    opening=allocate([val('initial_transient_aircraft',0)*val('mix_'+c.replace('_jet',''),0) for c in CATS])
    for c,n in zip(CATS,opening):
        for _ in range(n):
            v={'id':f'E-{len(visits)+1:04d}','category':c,'arrival':start-timedelta(days=1),'departure':None,'opening':True}
            visits.append(v);live[c].append(v)
    unmatched=0
    for day,date in enumerate(DATES):
        arrivals=allocate([lookup[(date,c,'arrivals')] for c in CATS])
        departures=allocate([lookup[(date,c,'departures')] for c in CATS])
        for c,n,dep in zip(CATS,arrivals,departures):
            early=rounded(dep*val('dep_share_before_peak',.5))
            for i in range(early):
                if live[c]:live[c].pop(0)['departure']=start+timedelta(days=day,hours=6+i%4)
                else:unmatched+=1
            for i in range(n):
                v={'id':f'E-{len(visits)+1:04d}','category':c,'arrival':start+timedelta(days=day,hours=10+i%8),'departure':None,'opening':False}
                visits.append(v);live[c].append(v)
            for i in range(dep-early):
                if live[c]:live[c].pop(0)['departure']=start+timedelta(days=day,hours=18+i%4)
                else:unmatched+=1
    delay_start=start+timedelta(days=int(val('delay_24h_first_day',3)))
    eligible=[v for v in visits if v['departure'] is not None and v['departure']>=delay_start]
    delayed_ids=set()
    for day in DATES:
        daily=[v for v in eligible if v['departure'].date().isoformat()==day]
        delayed_ids.update(v['id'] for v in daily[:rounded(len(daily)*val('delay_24h_share',1))])
    for v in visits:
        if v['departure'] is None:v['departure']=end+timedelta(days=1)
        elif variant=='departure_delay_24h' and v['id'] in delayed_ids:v['departure']+=timedelta(hours=24)
        v['units']=weights[v['category']]
        v['status']='Estimated'
    hours=[]
    for h in range(168):
        time=start+timedelta(hours=h)
        active=[v for v in visits if v['arrival']<=time<v['departure']]
        hours.append({'time':time.isoformat(),'units':sum(v['units'] for v in active),'aircraft':len(active)})
    return {'available':True,'hours':hours,'visits':[{**v,'arrival':v['arrival'].isoformat(),'departure':v['departure'].isoformat()} for v in visits],
            'unmatched_departures':unmatched,'note':f'{unmatched} rounded departures could not be matched to an assumed stay. '+'Illustration from rounded P2 category forecasts. Assumed arrivals 10:00–17:00; early departures 06:00–09:00, late departures 18:00–21:00; FIFO stays. Unscheduled carryover is shown through the following day. These are generated E-codes, not bookings. Its hourly peak may differ from the P3 daily median.'}


def catalog(bundle,scenario,variant):
    summary=summarize(bundle,scenario,variant)
    recs=[dict(r) for r in bundle['recommendations'] if r['scenario']==scenario and r['variant']==variant]
    basic=[('ready-timing','Check arrival and departure estimates','reservations','The forecast is estimated. Verify timings and overnight stays before using it for customer arrangements.'),
           ('ready-capacity','Confirm usable ramp space and aircraft access','operations',f"The parking model uses {rounded(summary['capacity_at_peak'])} space units at its peak. Confirm geometry, access and protected operating areas with the operations lead."),
           ('ready-monitor','Review the busy week and delayed departures','manager','Compare the model cases and keep the contingency plan ready. No partner space or price has been confirmed in this app.')]
    for aid,title,owner,reason in basic:
        recs.append({'id':aid,'title':title,'owner':owner,'due_date':DATES[0],'reason':reason,'scenario':scenario,'variant':variant,'source':'Preparation checklist; does not alter the producer plan'})
    return recs


def parse_bookings(raw):
    if not isinstance(raw,str) or len(raw.encode())>2_000_000:raise ContractError('Upload a UTF-8 CSV under 2 MB.')
    reader=csv.DictReader(io.StringIO(raw.lstrip('\ufeff')))
    required={'visit_id','category','arrival','departure','status'}
    if set(reader.fieldnames or [])!=required or len(reader.fieldnames or [])!=len(required):raise ContractError('Use exactly visit_id, category, arrival, departure, status. Do not include names or tail numbers.')
    result=[];seen=set()
    for line,r in enumerate(reader,2):
        try:
            if None in r or any(v is None for v in r.values()):raise ValueError('row must have exactly five fields')
            if not re.fullmatch(r'V-[0-9]{3,8}',r['visit_id']) or r['visit_id'] in seen:raise ValueError('use unique V-#### visit codes')
            if r['category'] not in CATS:raise ValueError('category must be light_jet, midsize_jet or large_jet')
            if r['status'] not in ('Booked','Estimated'):raise ValueError('status must be Booked or Estimated')
            a,d=[datetime.fromisoformat(r[k]) for k in ('arrival','departure')]
            a=a.replace(tzinfo=TZ) if a.tzinfo is None else a.astimezone(TZ)
            d=d.replace(tzinfo=TZ) if d.tzinfo is None else d.astimezone(TZ)
            if a>=d:raise ValueError('departure must be after arrival')
            result.append({'id':r['visit_id'],'category':r['category'],'arrival':a.isoformat(),'departure':d.isoformat(),'status':r['status'],'opening':a.date().isoformat()<DATES[0]})
            seen.add(r['visit_id'])
            if len(result)>5000:raise ValueError('maximum 5000 visits')
        except (ValueError,TypeError,KeyError) as exc:raise ContractError(f'Row {line}: {exc}.') from exc
    if not result:raise ContractError('The CSV has no visit rows.')
    return result


def view(bundle,scenario,variant,bookings):
    if scenario not in SCENARIOS or variant not in bundle['variants']:raise ContractError('Unsupported demand case or departure test.')
    return {'illustration':illustration(bundle,scenario,variant),'actions':catalog(bundle,scenario,variant),'bookings':bookings}
