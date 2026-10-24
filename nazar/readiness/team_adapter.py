"""Read P2/P3's committed native outputs without modifying their modules.

No forecasting or parking simulation here. Unavailable quantities stay unavailable:
no summed category intervals, invented ordinary parking, or invented delay scenario.
"""
import csv
import hashlib
import io
import json
import math
from .contracts import DATES, SCENARIOS, ContractError, number, text

P2='marvin/person_2_forecasting/'
NATIVE_PATHS={
    'p2_demand':P2+'demand_predictions.csv',
    'p2_uncertainty':P2+'uncertainty_results.csv',
    'p2_report':P2+'run_metadata.json',
    'p2_metrics':P2+'evaluation_metrics.csv',
    'p3_resources':'elia/resource_requirements.csv',
    'p3_recommendations':'elia/scenario_recommendations.json',
    'p3_assumptions':'elia/assumptions_p3.csv',
}
CATEGORIES=('large_jet','light_jet','midsize_jet')
DIRECTIONS=('arrivals','departures')
ACTION_MAP={
    'tow_packing':('Review the proposed ramp layout','operations'),
    'overflow_apron':('Review overflow availability and lease','manager'),
    'ppr_and_referrals':('Review reservation and referral contingency','manager'),
    'extra_line_staff':('Review additional technician shifts','manager'),
    'extra_refuelers':('Review extra fuel-service resources','manager'),
}

def check(condition,message):
    if not condition:raise ContractError('Team outputs: '+message)

def rows(raw,name,required):
    reader=csv.DictReader(io.StringIO(raw[name].lstrip('\ufeff')))
    check(reader.fieldnames is not None and len(reader.fieldnames)==len(set(reader.fieldnames)),name+': missing or duplicate headers.')
    check(set(required)<=set(reader.fieldnames),name+': missing required columns.')
    out=list(reader)
    check(0<len(out)<=5000,name+': expected 1–5000 rows.')
    check(all(None not in r and all(v is not None for v in r.values()) for r in out),name+': malformed CSV.')
    # Only the explicit aggregate fields are retained in the normalized bundle.
    return [{k:r[k] for k in required} for r in out]

def keyed(data,keys,expected,label):
    result={tuple(r[k] for k in keys):r for r in data}
    check(len(result)==len(data) and set(result)==expected,label+': duplicate or missing date/scenario/category/direction combinations.')
    return result

def probability(value,label):
    result=number(value,label)
    check(result<=1,label+': probability must be between zero and one.')
    return result

def distribution(value,label,signed=False):
    check(isinstance(value,dict),label+': missing distribution.')
    result={}
    for key in ('mean','p10','p50','p90'):
        v=value.get(key)
        if signed:
            check(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and abs(v)<=1e9,label+': invalid signed value.')
            result[key]=float(v)
        else: result[key]=number(v,label+'.'+key)
    check(result['p10']<=result['p50']<=result['p90'],label+': unordered quantiles.')
    return result

def parse_impact(value):
    check(isinstance(value,dict),'missing P3 impact results.')
    result={'runs':number(value.get('runs'),'simulation runs')}
    check(result['runs']>0 and result['runs'].is_integer(),'simulation runs must be a positive integer.')
    for plan in ('no_preparation','ai_preparation'):
        p=value.get(plan)
        check(isinstance(p,dict),'missing impact plan '+plan)
        result[plan]={k:distribution(p.get(k),plan+'.'+k) for k in ('unaccommodated_aircraft','delayed_turns','total_cost_usd')}
        result[plan]['prob_any_unaccommodated']=probability(p.get('prob_any_unaccommodated'),'prob_any_unaccommodated')
    result['net_benefit_usd']=distribution(value.get('net_benefit_usd'),'net benefit',signed=True)
    result['prob_preparation_pays_off']=probability(value.get('prob_preparation_pays_off'),'prob_preparation_pays_off')
    difference=result['no_preparation']['total_cost_usd']['mean']-result['ai_preparation']['total_cost_usd']['mean']
    check(abs(difference-result['net_benefit_usd']['mean'])<=.16,'P3 mean net benefit does not reconcile with mean costs.')
    return result

def load_native(raw):
    check(set(raw)==set(NATIVE_PATHS),'provide all seven native input files.')
    check(all(isinstance(v,str) and len(v.encode())<=2_000_000 for v in raw.values()),'files must be UTF-8 text below 2 MB.')
    try:report=json.loads(raw['p2_report']);plans=json.loads(raw['p3_recommendations'])
    except ValueError as exc:raise ContractError('Team outputs: invalid JSON.') from exc
    check(isinstance(report,dict) and isinstance(plans,dict),'reports must be JSON objects.')
    check(report.get('model')=='month_weekday_shrinkage_mean','unsupported P2 model; update the integration contract.')
    check(report.get('excluded_years')==[2020,2021,2022],'P2 trend exclusion policy differs from the team plan.')
    # P3 currently interprets the endpoints as 5th/95th percentiles.
    check(report.get('nominal_baseline_coverage')==.9,'P3 currently requires P2 nominal coverage of 0.9.')
    check(set(plans.get('scenarios',{}))=={'Low','Medium','High'},'P3 requires Low, Medium and High scenarios.')
    expected={(d,s.title(),c,k) for d in DATES for s in SCENARIOS for c in CATEGORIES for k in DIRECTIONS}
    wide=rows(raw,'p2_demand',('date','scenario','aircraft_category','forecast_scope','historical_data_class','reservation_class','assumption_source','baseline_arrivals','baseline_departures','expected_arrivals','expected_departures','arrivals_lower','arrivals_upper','departures_lower','departures_upper','arrivals_multiplier','departures_multiplier','arrivals_reservation_floor','departures_reservation_floor'))
    keyed(wide,('date','scenario','aircraft_category'),{k[:3] for k in expected},'P2 demand')
    dp=[]
    drivers=[]
    for r in wide:
        check(r['reservation_class'] in ('observed','estimated','synthetic'),'invalid reservation provenance.')
        check(set(r['historical_data_class'].split('|'))<={'observed','estimated','synthetic'},'invalid historical provenance.')
        text(r['assumption_source'],'forecast assumption source')
        for direction in DIRECTIONS:
            dp.append({'date':r['date'],'scenario':r['scenario'],'aircraft_category':r['aircraft_category'],'direction':direction,'expected_movements':r['expected_'+direction],'normal_fbo_baseline':r['baseline_'+direction],'input_provenance':r['historical_data_class'],'traffic_scope':r['forecast_scope']})
            drivers.append({'date':r['date'],'scenario':r['scenario'].lower(),'category':r['aircraft_category'],'direction':direction,'multiplier':number(r[direction+'_multiplier'],'event multiplier'),'reservation_floor':number(r[direction+'_reservation_floor'],'reservation floor'),'reservation_class':r['reservation_class'],'source':r['assumption_source']})
    current=rows(raw,'p2_uncertainty',('date','scenario','aircraft_category','target','expected','lower','upper','event_coverage_validated','historical_data_class','nominal_baseline_coverage'))
    up=[]
    for r in current:
        check(r['event_coverage_validated'].lower()=='false','current model does not establish event coverage.')
        check(number(r['nominal_baseline_coverage'],'nominal coverage')==.9,'inconsistent nominal coverage.')
        up.append({'date':r['date'],'scenario':r['scenario'],'aircraft_category':r['aircraft_category'],'direction':r['target'],'expected_movements':r['expected'],'lower90_prediction':r['lower'],'upper90_prediction':r['upper'],'event_coverage_validated':r['event_coverage_validated'],'input_provenance':r['historical_data_class']})
    dk=keyed(dp,('date','scenario','aircraft_category','direction'),expected,'P2 demand')
    uk=keyed(up,('date','scenario','aircraft_category','direction'),expected,'P2 uncertainty')
    category_rows=[]
    for key,r in dk.items():
        check(r['traffic_scope']=='fictional_fbo','expected fictional_fbo demand scope.')
        for f in ('expected_movements','normal_fbo_baseline'):r[f]=number(r[f],f)
        u=uk[key];lo=number(u['lower90_prediction'],'lower90_prediction');hi=number(u['upper90_prediction'],'upper90_prediction')
        check(abs(r['expected_movements']-number(u['expected_movements'],'uncertainty expected'))<.0001,'P2 point forecasts and uncertainty rows disagree.')
        check(r['input_provenance']==u['input_provenance'],'P2 provenance differs between demand and intervals.')
        w=next(x for x in wide if (x['date'],x['scenario'],x['aircraft_category'])==key[:3])
        check(abs(lo-number(w[key[3]+'_lower'],'demand lower'))<.0001 and abs(hi-number(w[key[3]+'_upper'],'demand upper'))<.0001,'P2 interval columns disagree.')
        check(lo<=r['expected_movements']<=hi,'P2 range must contain its point forecast.')
        check(u['event_coverage_validated'].lower() in ('false','true'),'invalid event coverage flag.')
        category_rows.append({'date':r['date'],'scenario':r['scenario'].lower(),'category':r['aircraft_category'],'direction':r['direction'],'expected':r['expected_movements'],'lower':lo,'upper':hi})
    demand=[];baseline=[]
    for d in DATES:
        normal={k:sum(dk[(d,'Medium',c,k)]['normal_fbo_baseline'] for c in CATEGORIES) for k in DIRECTIONS}
        for s in SCENARIOS:
            for k in DIRECTIONS:
                check(all(abs(dk[(d,s.title(),c,k)]['normal_fbo_baseline']-dk[(d,'Medium',c,k)]['normal_fbo_baseline'])<.0001 for c in CATEGORIES),'ordinary baseline differs between scenarios.')
            demand.append({'date':d,'scenario':s,**{k:sum(dk[(d,s.title(),c,k)]['expected_movements'] for c in CATEGORIES) for k in DIRECTIONS},'arrivals_lower':None,'arrivals_upper':None})
        baseline.append({'date':d,**normal,'parking_units':None})
    resource_cols=('scenario','date','parking_demand_su_p10','parking_demand_su_p50','parking_demand_su_p90','capacity_normal_su','capacity_prepared_su','prob_over_normal_capacity','prob_over_prepared_capacity','techs_morning','techs_day','techs_night','techs_normal_per_shift','fuel_gallons_p50','fuel_trucks','fuel_trucks_normal')
    rp=rows(raw,'p3_resources',resource_cols)
    rk=keyed(rp,('date','scenario'),{(d,s.title()) for d in DATES for s in SCENARIOS},'P3 resources')
    resources=[]
    for r in rp:
        for f in resource_cols[2:]:r[f]=number(r[f],f)
        check(r['parking_demand_su_p10']<=r['parking_demand_su_p50']<=r['parking_demand_su_p90'],'parking quantiles are not ordered.')
        check(r['capacity_prepared_su']>=r['capacity_normal_su'],'prepared capacity is below ordinary capacity.')
        check(0<=r['prob_over_prepared_capacity']<=r['prob_over_normal_capacity']<=1,'invalid capacity exceedance probabilities.')
        staff=max(r['techs_morning'],r['techs_day'],r['techs_night'])
        check(staff>=r['techs_normal_per_shift'],'prepared staffing is below ordinary staffing.')
        resources.append({'date':r['date'],'scenario':r['scenario'].lower(),'variant':'standard','parking_units':r['parking_demand_su_p50'],'parking_p10':r['parking_demand_su_p10'],'parking_p90':r['parking_demand_su_p90'],'capacity_units':r['capacity_normal_su'],'prepared_capacity_units':r['capacity_prepared_su'],'staff_required':staff,'staff_available':r['techs_normal_per_shift'],'prepared_staff':staff,'fuel_gallons':r['fuel_gallons_p50'],'fuel_available_gallons':None,'preparation_cost':None,'prob_over_normal':r['prob_over_normal_capacity'],'prob_over_prepared':r['prob_over_prepared_capacity'],'staff_shifts':{k:r['techs_'+k] for k in ('morning','day','night')}})
    recs=[];costs={};impacts={}
    for s in SCENARIOS:
        plan=plans['scenarios'][s.title()];sr=[r for r in resources if r['scenario']==s];peak=max(sr,key=lambda r:r['parking_units'])
        check(isinstance(plan,dict) and isinstance(plan.get('actions'),list),'invalid P3 action list.')
        check(abs(number(plan['summary']['peak_parking_demand_su_p50'],'P3 summary peak')-peak['parking_units'])<.11,'P3 summary and resource table disagree.')
        costs[s]=number(plan['preparation_cost_usd'],'preparation_cost_usd')
        impacts[s]=parse_impact(plan.get('impact'))
        check(abs(sum(number(a['cost_usd'],'action cost') for a in plan['actions'])-costs[s])<.01,'P3 action costs do not equal the preparation total.')
        seen=set()
        for a in plan['actions']:
            aid=text(a.get('id'),'P3 action ID')
            check(aid in ACTION_MAP and aid not in seen,'unknown or repeated P3 action ID: '+aid);seen.add(aid)
            check(a.get('requires_human_approval') is True,'every P3 action must require human approval.')
            dates=a.get('dates');check(isinstance(dates,list) and dates and all(isinstance(d,str) and d in DATES for d in dates),'invalid action dates.')
            title,owner=ACTION_MAP[aid]
            reason='Review proposal: '+text(a.get('action'),'P3 proposal')+'. '+text(a.get('rationale'),'P3 rationale')+'.'
            if aid=='tow_packing':reason+=' A qualified operations lead must validate geometry, clearances and procedures; this app cannot authorize towing or a layout change.'
            affected=sorted(set(dates+[peak['date']]))
            recs.append({'id':aid,'scenario':s,'variant':'standard','action_type':aid,'title':title,'owner':owner,'due_date':min(dates),'affected_dates':affected,'source':'P3 Monte Carlo resource model; producer advice pending human review','reason':reason,'evidence':[{'date':peak['date'],'field':'parking_units','value':peak['parking_units']},{'date':peak['date'],'field':'parking_p90','value':peak['parking_p90']}]})
    ap=rows(raw,'p3_assumptions',('parameter','value','unit','classification','source_or_rationale'))
    check(len({a['parameter'] for a in ap})==len(ap),'duplicate P3 assumptions.')
    assumptions=[]
    for a in ap:
        for k in a:text(a[k],'P3 assumption '+k)
        assumptions.append({'id':a['parameter'],'label':a['parameter'].replace('_',' '),'value':a['value'],'unit':a['unit'],'classification':a['classification'],'source':'Elia / assumptions_p3.csv','note':a['source_or_rationale']})
    for k in ('prior_days','excluded_years','nominal_baseline_coverage'):
        assumptions.append({'id':'p2_'+k,'label':k.replace('_',' '),'value':json.dumps(report.get(k)),'unit':'model setting','classification':'assumption','source':'Marvin / run_metadata.json','note':'Producer-specified setting; baseline coverage does not establish event coverage.'})
    provenance=sorted({v for r in dp for v in r['input_provenance'].split('|')})
    check(report.get('historical_data_classes')==provenance,'P2 metadata and demand provenance disagree.')
    metric_rows=rows(raw,'p2_metrics',('aircraft_category','target','data_class','evaluation_type','model_mae','historical_mean_mae','nominal_coverage','test_coverage','test_rows'))
    keyed(metric_rows,('aircraft_category','target'),{(c,k) for c in CATEGORIES for k in DIRECTIONS},'P2 evaluation')
    metrics=[]
    for m in metric_rows:
        classes=set(m['data_class'].split('|'))
        expected_classes={v for r in dp if r['aircraft_category']==m['aircraft_category'] for v in r['input_provenance'].split('|')}
        check(classes==expected_classes,'evaluation and forecast provenance disagree.')
        evaluation='historical_observed' if classes=={'observed'} else 'non_observed_demonstration'
        check(m['evaluation_type']==evaluation,'evaluation type must match input provenance.')
        check(number(m['nominal_coverage'],'metric nominal coverage')==.9,'evaluation nominal coverage differs from forecast.')
        count=number(m['test_rows'],'test rows')
        check(count>0 and count.is_integer(),'test rows must be a positive integer.')
        metrics.append({'aircraft_category':m['aircraft_category'],'direction':m['target'],'scope':'fictional_fbo','evaluation_data':m['data_class']+' / '+evaluation,'model_mae':number(m['model_mae'],'model MAE'),'baseline_mae':number(m['historical_mean_mae'],'baseline MAE'),'interval_coverage90':probability(m['test_coverage'],'historical coverage'),'n_test':count})
    classification='synthetic' if provenance==['synthetic'] and all(r['reservation_class']=='synthetic' for r in wide) else 'mixed'
    method=text(plans.get('meta',{}).get('method'),'P3 method')
    limitations=text(plans.get('meta',{}).get('limitations'),'P3 limitations')
    meta={'schema_version':'native-p2-p3-v2','dataset_name':'Team forecast + Monte Carlo parking output','fbo_name':'Pacific Executive FBO','airport':'LAX','timezone':'America/Los_Angeles','window_start':DATES[0],'window_end':DATES[-1],'data_classification':classification,'interval_kind':'model_quantiles','interval_description':'P3 parking P10–P90 ranges describe simulated daily peaks. P2 ranges use nominal 90% baseline intervals scaled by event assumptions; event coverage is unvalidated. Category endpoints are not summed.','model_version':'P2 month/weekday shrinkage mean + P3 Monte Carlo (native adapter v2)','generated_at':'Output generation time not supplied by producers','notes':limitations+' Ordinary parking baseline and a separate 24-hour-delay output have not been supplied. Re-run P3 after changing P2 outputs; upstream files currently have no shared run identifier.'}
    result={'meta':meta,'baseline':baseline,'demand':demand,'resources':resources,'recommendations':recs,'assumptions':assumptions,'variants':['standard'],'category_ranges':category_rows,'forecast_drivers':drivers,'forecast_metrics':metrics,'weekly_costs':costs,'impacts':impacts,'method':method,'native':True,'limitations':['Ordinary parking baseline is unavailable; compare ordinary and event arrivals instead.','Only standard departures are supplied; no 24-hour delay variant is available.','P2/P3 outputs lack a shared run fingerprint. Run the pipeline verification command after refreshing both producers.','Simulation benefits and historical demonstration scores are not measured real-world performance.']}
    result['version']=hashlib.sha256(json.dumps({'adapter':'native-v2','inputs':raw},sort_keys=True).encode()).hexdigest()
    return result
