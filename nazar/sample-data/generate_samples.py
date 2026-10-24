"""Reproduce the synthetic integration fixtures. This is NOT a forecasting model."""
import csv
import json
from pathlib import Path
from datetime import date,timedelta
P=Path(__file__).resolve().parent
D=[(date(2027,2,11)+timedelta(days=i)).isoformat() for i in range(7)]
def write(name,rows):
    with (P/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader();w.writerows(rows)
meta={'schema_version':'1.0','dataset_name':'Super Bowl planning demonstration','fbo_name':'Pacific Executive FBO','airport':'LAX','timezone':'America/Los_Angeles','window_start':D[0],'window_end':D[-1],'data_classification':'synthetic','interval_kind':'assumed_range','interval_description':'Illustrative arrival ranges, not calibrated statistical intervals. Parking values are daily peak fixtures.','model_version':'sample-fixtures-1.0','generated_at':'2026-10-23T12:00:00-07:00','notes':'Fictional FBO and handcrafted demonstration outputs. No live bookings, actual partner capacity or trained forecast is represented.'}
(P/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
write('baseline.csv',[dict(date=d,arrivals=a,departures=a-1 if i<3 else a+1,parking_units=u) for i,(d,a,u) in enumerate(zip(D,[8,9,8,7,9,8,7],[19,21,21,18,20,19,17]))])
demand=[]; intervals=[]; resources=[]; recs=[]
settings={
 'low':([11,14,18,12,7,7,6],[24,34,55,62,58,29,20],[24,34,55,62,69,54,28],0,6),
 'medium':([14,21,28,18,8,7,6],[27,42,75,92,84,36,21],[27,42,75,92,98,78,35],28,34),
 'high':([19,29,38,25,10,8,7],[34,56,92,118,112,49,27],[34,56,92,118,131,102,42],40,40)}
for sc,(arrivals,normal,delay,extra,delayextra) in settings.items():
    for i,d in enumerate(D):
        demand.append(dict(scenario=sc,date=d,arrivals=arrivals[i],departures=[8,10,9,12,35,25,12][i]))
        intervals.append(dict(scenario=sc,date=d,arrivals_lower=max(0,arrivals[i]-4),arrivals_upper=arrivals[i]+6))
    for variant,peaks,units in [('standard',normal,extra),('departure_delay_24h',delay,delayextra)]:
        days=[i for i,p in enumerate(peaks) if p>64]
        for i,d in enumerate(D):
            staff=max(4,(arrivals[i]+[8,10,9,12,35,25,12][i]+7)//8)
            resources.append(dict(scenario=sc,variant=variant,date=d,parking_units=peaks[i],capacity_units=64,prepared_capacity_units=64+(units if i in days else 0),staff_required=staff,staff_available=5,prepared_staff=max(5,staff),fuel_gallons=arrivals[i]*270,fuel_available_gallons=8000,preparation_cost=(units*45 if i in days else 0)))
        peak=max(range(7),key=lambda i:peaks[i]); affected=[D[i] for i in days] or [D[peak]]
        for action,owner,reason in [
            ('verify_bookings','reservations','Check arrival and departure estimates, especially aircraft staying through the game. These are sample estimates, not confirmed bookings.'),
            ('confirm_overflow' if days else 'monitor_capacity','manager',(f'Investigate {units} additional parking units on the affected dates. Verify aircraft suitability, availability and the actual quote. '+('Some demand remains uncovered; escalate the gap.' if max(peaks)>64+units else 'The modeled comparison assumes this capacity can be secured.')) if days else 'Monitor booking and departure updates. This supplied scenario fits existing capacity; recheck if demand or usable space changes.'),
            ('staffing_review','operations','Review the supporting shift estimate against qualifications and actual duties. The dashboard does not assign staff.')]:
            recs.append(dict(id=action,scenario=sc,variant=variant,action_type=action,reason=reason,owner=owner,due_date=D[max(0,min(days)-1)] if days else D[0],affected_dates=affected,source='Synthetic preparation fixture; not AI-generated',evidence=[dict(date=D[peak],field='parking_units',value=peaks[peak])]))
write('demand_predictions.csv',demand);write('uncertainty_results.csv',intervals);write('resource_requirements.csv',resources)
(P/'scenario_recommendations.json').write_text(json.dumps(recs,indent=2)+'\n')
write('assumptions.csv',[
 dict(id='capacity',label='Usable FBO capacity',value='64',unit='parking units',classification='synthetic',source='Team demonstration fixture',note='Not measured LAX capacity. The operator must verify usable space.'),
 dict(id='units',label='Aircraft footprint convention',value='1 / 1.5 / 2.5',unit='light / midsize / large units',classification='assumption',source='Integration contract example',note='Scalar units do not establish safe physical positions or clearances.'),
 dict(id='price',label='Illustrative overflow price',value='45',unit='USD per unit per day',classification='assumption',source='Team demonstration fixture',note='No supplier quote or availability has been obtained.'),
 dict(id='arrivals',label='Arrival range',value='central minus 4 / plus 6',unit='aircraft per day',classification='synthetic',source='Handcrafted demonstration',note='Not a prediction interval and not a confidence score.'),
 dict(id='fuel',label='Fuel service example',value='270',unit='gallons per arriving aircraft',classification='assumption',source='Supporting sample only',note='Not a fuel purchase forecast. Replace with Person 3 outputs.'),
 dict(id='stays',label='Parking and delayed departures',value='daily peak snapshots',unit='parking units',classification='synthetic',source='Handcrafted standard and delayed fixtures',note='These snapshots demonstrate the interface; they are not calculated from real visits.')])
print('Wrote seven synthetic fixture files.')
