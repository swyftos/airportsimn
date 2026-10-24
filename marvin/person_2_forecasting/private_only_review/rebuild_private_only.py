from pathlib import Path
from datetime import date, timedelta
import csv, json, math, statistics
P=Path(__file__).resolve().parent
def read(name):
 with (P/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(name,rows):
 with (P/name).open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
FAA='https://www.aspm.faa.gov/opsnet/sys/Airport.asp'
FAA_DEF='https://aspmhelp.faa.gov/index/OPSNET_Reports__Definitions_of_Variables.html'
CAP='https://www.faa.gov/sites/faa.gov/files/airports/planning_capacity/profiles/LAX-Airport-Capacity-Profile-2014.pdf'
REPO='https://github.com/swyftos/airportsimn'
ASSUM=REPO+'/blob/main/assumptions.csv'
P3=REPO+'/blob/main/elia/assumptions_p3.csv'
LVI=REPO+'/blob/main/alan/elia_output/data/processed/superbowl_lvi_surge.csv'
OPM='https://www.opm.gov/policy-data-oversight/pay-leave/federal-holidays/'
data=read('ga_only_daily_source.csv')
counts={date.fromisoformat(r['date']):int(r['general_aviation']) for r in data}
recent={d:n for d,n in counts.items() if d.year in (2023,2024,2025)}
ga2025=sum(n for d,n in counts.items() if d.year==2025)
assert ga2025==12234
eligible=.50;fbo=.20;direction=.50
baseline=ga2025*eligible*fbo*direction/365
mix={'light':.47,'midsize':.33,'large':.20}
su=round(.47*1+.33*1.5+.20*2.5,3);capacity=75;slots=math.floor(capacity/su)
arr_med=[1.25,1.6,2.2,1.8,1.1,1.0,1.0]
dep_med=[1.0,1.0,1.1,1.3,2.5,1.8,1.2]
scales={'Low':.5,'Medium':1.0,'High':1.6}
plan=[];opening=round(baseline*1.1)
for scenario,scale in scales.items():
 occ=opening
 for i in range(7):
  d=date(2027,2,11)+timedelta(days=i)
  am=1+scale*(arr_med[i]-1);dm=1+scale*(dep_med[i]-1)
  req_a=math.ceil(baseline*am);req_d=math.ceil(baseline*dm)
  early=min(math.floor(req_d*.5),occ)
  can_a=min(req_a,max(0,slots-(occ-early)))
  can_d=early+min(req_d-early,occ-early+can_a)
  occ+=can_a-can_d
  same=min(round(can_a*.4,2),can_d)
  plan.append(dict(date=str(d),scenario=scenario,modeled_scope='PRIVATE_ONLY_SCENARIO_GA_CATEGORY_PROXY_NOT_OBSERVED_PRIVATE_FLEET',
   ga_2025_airport_ops=ga2025,private_eligible_ga_fraction_placeholder=eligible,
   fbo_capture_of_eligible=fbo,ordinary_baseline_arrivals=round(baseline,4),
   arrival_event_multiplier=round(am,3),departure_event_multiplier=round(dm,3),
   requested_land=req_a,can_land=can_a,unserved_land=req_a-can_a,
   requested_leave=req_d,can_leave=can_d,unserved_leave=req_d-can_d,
   new_arrivals_same_day_leave_est=same,new_arrivals_remaining_overnight_est=round(can_a-same,2),
   aircraft_remaining_end_day=occ,modeled_private_share=1.0,observed_private_fleet_share='unknown',
   fbo_capacity_su=capacity,size_mix_light=.47,size_mix_midsize=.33,size_mix_large=.20,
   mean_aircraft_footprint_su=su,runway_profile_instrument_gross_ops_per_hour_lower_end=133,
   runway_screen='gross_airport_rate_only_no_residual_slot_proof',
   presidents_day_effect_in_primary='none_unmeasured',
   classification='synthetic_private_only_scenario_from_public_GA_proxy',
   note='FAA GA is not selected-fleet data. Eligibility, share, direction, events, dwell and parking are assumptions.'))
plan.sort(key=lambda r:(r['date'],list(scales).index(r['scenario'])))
write('daily_private_only_plan.csv',plan)
sens=[]
for v in (0,.25,.5,.75,1):
 sens.append(dict(eligible_fraction_of_FAA_GA_category=v,
  ordinary_fbo_arrivals_per_day=round(ga2025*v*fbo*direction/365,4),
  classification='synthetic_sensitivity_not_observed',
  note='20% FBO share applied only after private-eligibility filter; 100% is an upper case, not an assertion.'))
write('private_eligibility_sensitivity.csv',sens)
print('baseline',round(baseline,4),'plan rows',len(plan),'opening',opening,'slots',slots)

normal=statistics.mean(recent.values())
analog=[]
def add_analog(name,dates,urls):
 values=[recent[d] for d in dates]
 avg=statistics.mean(values)
 analog.append(dict(period=name,n_days=len(values),ga_category_ops_per_day=round(avg,2),
  index_vs_all_day_ga_mean=round(avg/normal,3),
  classification='public_GA_category_descriptive_not_private_fleet',
  source='; '.join(urls),note='Not verified private fleet or FBO traffic; no causal event uplift.'))
add_analog('normal_all_days_2023_2025',list(recent),[FAA])
add_analog('normal_weekday',[d for d in recent if d.weekday()<5],[FAA])
add_analog('normal_weekend',[d for d in recent if d.weekday()>=5],[FAA])
add_analog('Thanksgiving',[date(2023,11,23),date(2024,11,28),date(2025,11,27)],[FAA,OPM])
add_analog('Christmas_and_New_Year',[date(y,12,25) for y in (2023,2024,2025)]+[date(y,1,1) for y in (2023,2024,2025)],[FAA,OPM])
add_analog('July_4',[date(y,7,4) for y in (2023,2024,2025)],[FAA,OPM])
oscars=['https://www.oscars.org/oscars/ceremonies/2023/U--Z','https://www.oscars.org/oscars/ceremonies/2024','https://www.oscars.org/oscars/ceremonies/2025']
add_analog('Oscars',[date(2023,3,12),date(2024,3,10),date(2025,3,2)],[FAA]+oscars)
coachella=['https://blog.youtube/news-and-events/coachella-livestream-youtube-goldenvoice-2023/','https://blog.youtube/news-and-events/coachella-2024-livestream-how-to-watch/','https://blog.youtube/news-and-events/the-countdown-to-coachella-weekend-1-begins/']
weekends=[(date(2023,4,14),date(2023,4,16)),(date(2023,4,21),date(2023,4,23)),(date(2024,4,12),date(2024,4,14)),(date(2024,4,19),date(2024,4,21)),(date(2025,4,11),date(2025,4,13)),(date(2025,4,18),date(2025,4,20))]
coachella_days=[a+timedelta(days=i) for a,b in weekends for i in range((b-a).days+1)]
add_analog('Coachella_festival_Fri_Sun_2023_2025',coachella_days,[FAA]+coachella)
add_analog('normal_Fri_Sun_2023_2025',[d for d in recent if d.weekday() in (4,5,6)],[FAA])
write('ga_category_historical_comparisons.csv',analog)
lvi=read('lvi_ga_only_comparison.csv')[0]
gaps=[dict(game='LVI',host_region='Los Angeles',year=2022,FAA_GA_category_excess=round(float(lvi['excess_2022']),3),
 private_fleet_ratio='unknown',classification='GA_category_proxy_not_private_fleet',source=LVI,
 note='Control-adjusted LAX GA category change; not applied to private-only scenario.')]
for game,city,year in [('LVII','Phoenix',2023),('LVIII','Las Vegas',2024),('LIX','New Orleans',2025),('LX','Santa Clara',2026)]:
 gaps.append(dict(game=game,host_region=city,year=year,FAA_GA_category_excess='not_in_review',
 private_fleet_ratio='unknown',classification='not_available',source='',
 note='Selected private-fleet arrivals, departures, dwell and ratios unavailable.'))
write('super_bowl_private_scope_gaps.csv',gaps)
holiday=[]
for r in plan:
 if r['date']=='2027-02-15':
  for label,factor in [('lower_hypothetical',.9),('unchanged_primary',1),('upper_hypothetical',1.1)]:
   holiday.append(dict(date=r['date'],scenario=r['scenario'],case=label,additional_holiday_factor=factor,
    requested_land_sensitivity=round(baseline*r['arrival_event_multiplier']*factor,3),
    requested_leave_sensitivity=round(baseline*r['departure_event_multiplier']*factor,3),
    primary_plan_changed='no',classification='synthetic_unmeasured_sensitivity',source=OPM,
    note='OPM confirms holiday date, not private aviation effect. +/-10% hypothetical only.'))
write('presidents_day_sensitivity.csv',holiday)
sources=[
 ('FAA ATADS/OPSNET','public',FAA,'LAX GA daily and monthly operations','Select LAX and GA; raw category not selected-fleet data.'),
 ('FAA category definitions','public',FAA_DEF,'GA inclusion/exclusion boundary','GA excludes air carrier and air taxi but does not identify private fleet.'),
 ('FAA LAX 2014 capacity profile','benchmark',CAP,'Gross airport hourly runway rates','No residual 2027 slot guarantee.'),
 ('FAA capacity profile index','public','https://www.faa.gov/airports/planning_capacity/profiles','Current listed LAX edition and benchmark replacement','LAX listed 2014.'),
 ('Repo daily FAA export PR','repo_snapshot',REPO+'/pull/22/files','Original daily OPSNET export used for GA-only extract','Team repository access may be required.'),
 ('Repo monthly FAA export','repo_snapshot',REPO+'/blob/main/alan/elia_output/data/processed/opsnet_lax_monthly.csv','132-month GA total cross-check','Team repository access may be required.'),
 ('Team assumption ledger','team_assumption',ASSUM,'20% FBO share, 40/45/15 dwell, 47/33/20 mix, 75-su ramp','Share adapted to filtered GA-only scope; not observed.'),
 ('Elia parking assumptions','team_assumption',P3,'75-su parking proxy and size footprints','Not confirmed free PPR capacity.'),
 ('LVI GA comparison','derived_public',LVI,'LAX GA-category +3.1% control-adjusted comparison','Only GA row used; not private-fleet result.'),
 ('OPM holiday calendar','public',OPM,'Holiday comparison dates and Feb 15 2027','Calendar only, no aviation effect.')]
for year,url in zip((2023,2024,2025),oscars):
 sources.append(('Academy Oscars '+str(year),'official_event_date',url,'Oscars comparison date','No private-fleet attribution.'))
for year,url in zip((2023,2024,2025),coachella):
 sources.append(('Coachella date '+str(year),'organizer_or_partner_event_date',url,'Festival comparison dates','No private-fleet attribution.'))
write('source_links.csv',[dict(name=n,source_type=t,url=u,used_for=use,qualification=q) for n,t,u,use,q in sources])
print('GA analogs',len(analog),'source links',len(sources))

cols=['id','owner','label','value','unit','classification','confidence','source','status','note']
ledger=[]
def add(id,label,value,unit,classification,confidence,source,status,note):
 ledger.append(dict(zip(cols,[id,'Marvin',label,value,unit,classification,confidence,source,status,note])))
add('MARVIN-GA-2025','LAX 2025 FAA GA-category operations',ga2025,'airport_operations','public','high',FAA,'category_observed','Not a private-fleet or FBO count.')
add('MARVIN-private-eligibility','Private FBO-eligible fraction of GA category',eligible,'fraction','synthetic','low','none; placeholder','review_required','Unknown fraction; excludes other GA users. Sensitivity 0-100% supplied.')
add('MARVIN-FBO-share','FBO capture of filtered eligible GA operations',fbo,'fraction','assumption','low',ASSUM,'adapted_review_only','20% team assumption adapted from broader original scope; Alan review needed.')
add('MARVIN-direction','Arrivals share of filtered eligible operations',direction,'fraction','assumption','low','none; placeholder','review_required','FAA category totals do not establish direction.')
add('MARVIN-private-baseline','Conditional private-only FBO arrivals/day',round(baseline,6),'aircraft/day','synthetic','low',FAA+'; '+ASSUM,'not_observed','GA 2025 x 0.50 eligibility x 0.20 FBO capture x 0.50 arrivals / 365.')
for c,v in mix.items():
 add('MARVIN-mix-'+c,'Aircraft size mix '+c,v,'fraction','assumption','low',ASSUM,'inherited_unverified','Team 47/33/20 size mix, not FAA aircraft observations.')
add('MARVIN-ramp','FBO parking proxy ceiling',capacity,'space_units','assumption','low',P3,'replace_with_Alan_capacity','75-su unverified proxy, not free PPR inventory.')
add('MARVIN-footprint','Mix-weighted mean space units',su,'space_units/aircraft','assumption','low',P3,'conditional','47/33/20 mix x 1/1.5/2.5 space units.')
add('MARVIN-same-day','New arrivals leaving same day',.4,'fraction','assumption','low',ASSUM,'inherited_unverified','Preserves illustrative 40/45/15 dwell mix.')
add('MARVIN-runway','Gross LAX instrument weather lower-end hourly throughput',133,'airport_operations/hour','benchmark','medium',CAP,'secondary_sanity_only','2014 gross airport rate, not residual slot availability.')
add('MARVIN-LVI-GA','LAX LVI GA-category control-adjusted excess',float(lvi['excess_2022']),'fraction','public','medium',LVI,'descriptive_not_applied','2022 excluded from normal baseline; not private-fleet multiplier.')
add('MARVIN-Presidents-Day','Additional Feb 15 2027 holiday effect','unmeasured','effect','assumption','unknown',OPM,'sensitivity_only','No effect in primary plan; +/-10% hypothetical sidecar.')
for r in plan:
 for key in ('can_land','can_leave','aircraft_remaining_end_day'):
  add('MARVIN-'+r['date']+'-'+r['scenario'].lower()+'-'+key,key+' '+r['date']+' '+r['scenario'],
   r[key],'aircraft','synthetic','low','daily_private_only_plan.csv','local_review_only',
   'Private-only by scenario definition; FAA GA proxy plus unverified eligibility.')
write('assumptions.csv',ledger)
metadata=dict(status='LOCAL_REVIEW_ONLY',scope='Modeled Part91 private-only; zero charter or air-taxi input',
 observed_scope='FAA GA airport category only, not verified private-fleet or FBO',
 private_eligible_GA_fraction=eligible,eligibility_provenance='synthetic placeholder',
 fbo_capture_share=fbo,aircraft_size_mix=mix,capacity_su=capacity,mean_su=su,
 ga_2025_operations=ga2025,conditional_baseline_arrivals=baseline,
 event_multipliers='synthetic and explicit in daily_private_only_plan.csv',
 presidents_day='unmeasured; no primary effect; +/-10% hypothetical sidecar only',
 covid_years='2020-2022 omitted from normal 2023-2025 analog; 2022 LVI descriptive only',
 runway='2014 FAA gross airport rate; residual slots unknown',source_links='source_links.csv')
(P/'run_metadata.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
print('assumption rows',len(ledger))

