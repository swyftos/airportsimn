"""Generate a selected-fleet Part 91/135 PLACEHOLDER Person 2 forecast."""
from __future__ import annotations
import argparse
import csv
import hashlib
import html
import json
import math
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from forecast_model import AIRCRAFT_MIX, FBO_CAPTURE_SHARE, PART_SHARES, AIR_TAXI_EVENT_EXCESS
from operations_extension import build as build_operations

HERE = Path(__file__).resolve().parent
RESULTS = HERE / 'results'
SCENARIOS = ('Low', 'Medium', 'High')
CAPACITY_SU = 75.0  # Inherited unverified P3 estimate.
CAPACITY_SPOTS = 24  # Invented physical-stand ceiling; replace with real available PPR stands.
AIRCRAFT_SU = round(sum(AIRCRAFT_MIX[c]*su for c,su in [('light_jet',1.0),('midsize_jet',1.5),('large_jet',2.5)]), 3)
DEPART_BEFORE_PEAK = 0.5  # PLACEHOLDER schedule split.
SAME_DAY_SHARE = 0.4      # Existing illustrative dwell mix; not observed.

def read_csv(path: Path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def write_csv(path: Path, rows):
    if not rows:
        raise ValueError('No rows for ' + str(path))
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def as_table(rows, cols):
    cell = lambda x: html.escape(str(x))
    head = ''.join('<th>' + cell(c.replace('_', ' ')) + '</th>' for c in cols)
    body = ''.join('<tr>' + ''.join('<td>' + cell(r[c]) + '</td>' for c in cols) + '</tr>' for r in rows)
    return '<table><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table>'

def make_capacity_plan(totals, predictions):
    by_key = defaultdict(list)
    for r in predictions:
        by_key[r['date'], r['scenario']].append(r)
    baseline_day = [float(r['baseline_arrivals']) for r in totals if r['scenario'] == 'Medium']
    opening = round(sum(baseline_day) / len(baseline_day) * 1.1)
    capacity_aircraft = min(CAPACITY_SPOTS, math.floor(CAPACITY_SU / AIRCRAFT_SU))
    rows = []
    for scenario in SCENARIOS:
        occupied = opening
        for r in (x for x in totals if x['scenario'] == scenario):
            arrivals = math.ceil(float(r['expected_arrivals']))
            departures = math.ceil(float(r['expected_departures']))
            early = min(math.floor(departures * DEPART_BEFORE_PEAK), occupied)
            peak = occupied - early + arrivals
            overflow = max(0, peak - capacity_aircraft)
            inventory_gap = max(0, departures - occupied - arrivals)
            end_ground = max(0, occupied + arrivals - departures)
            details = by_key[r['date'], scenario]
            assert set(x['aircraft_category'] for x in details) == set(AIRCRAFT_MIX)
            same_day_est = min(departures, round(arrivals * SAME_DAY_SHARE, 2))
            overnight_new_est = round(arrivals - same_day_est, 2)
            rows.append(dict(date=r['date'], scenario=scenario,
                scope='PLACEHOLDER_selected_fleets_part91_part135_excludes_part121',
                forecast_arrivals_rounded=arrivals, forecast_departures_rounded=departures,
                projected_peak_ground=peak, parking_overflow_to_resolve=overflow,
                departure_inventory_gap_to_reconcile=inventory_gap,
                opening_ground=opening if r['date']=='2027-02-11' else '',
                end_day_ground_if_demand_occurs=end_ground,
                new_arrivals_same_day_leave_est=same_day_est,
                new_arrivals_remaining_overnight_est=overnight_new_est,
                fbo_ppr_capacity_su=CAPACITY_SU, assumed_su_per_aircraft=AIRCRAFT_SU,
                capacity_aircraft_equivalent=capacity_aircraft,
                classification='synthetic_placeholder',
                note='Aggregate sensitivity only. Overflow needs manager review; no flight is accepted, refused or canceled. Departure inventory gap is unknown itinerary/opening-inventory reconciliation, not a stuck aircraft. 24 spots are invented; 75 su is unverified.'))
            occupied = end_ground
    return sorted(rows, key=lambda r:(r['date'], SCENARIOS.index(r['scenario']))), opening

def write_assumptions(seed, opening):
    placeholder_source = 'PLACEHOLDER synthetic eligible selected-fleet airport pool; seed ' + str(seed)
    rows = []
    def add(id,label,value,unit,note,classification='synthetic',source=None,status='PLACEHOLDER_REVIEW_REQUIRED'):
        rows.append(dict(id=id,owner='Marvin',label=label,value=value,unit=unit,
            classification=classification,confidence='low',source=source or placeholder_source,status=status,note=note))
    add('MARVIN-PH-scope','Forecast eligible fleet scope','selected-fleet Part 91 and Part 135; no Part 121','scope',
        'Part 135 is included only for selected fleets. FAA Air Taxi is a broader proxy, not identified FBO bookings.')
    for part, share in PART_SHARES.items():
        add('MARVIN-PH-share-'+part,'Synthetic selected-fleet share '+part,share,'fraction',
            'Unmeasured split of the eligible pool; replace when fleet records are available.')
    add('MARVIN-PH-fbo-capture','FBO capture of eligible selected private-fleet airport operations',FBO_CAPTURE_SHARE,'fraction',
        'Uses team 20% share. Applied only after eligibility filtering, exactly once; no all-airport denominator.',
        classification='assumption',source='ALAN-fbo_market_share in repository assumptions.csv',status='AGREED_ASSUMPTION_NOT_OBSERVED')
    for category,mix in AIRCRAFT_MIX.items():
        add('MARVIN-PH-mix-'+category,'FBO aircraft size mix '+category,mix,'fraction',
            'Agreed 47/33/20 aircraft size allocation; used in history, reservations, forecasts and mean parking footprint.',
            classification='assumption',source='ELIA-mix_light / mix_midsize / mix_large in repository assumptions.csv',
            status='AGREED_ASSUMPTION_NOT_OBSERVED')
    add('MARVIN-PH-eligible-pool','Synthetic eligible selected-fleet airport total before FBO capture',33,
        'eligible arrivals or departures/day before seasonality','Random PLACEHOLDER pool; not all airport operations.')
    add('MARVIN-PH-seasonal-amplitude','Synthetic February-peaking seasonality',0.15,'fraction','Not measured.')
    add('MARVIN-PH-weekday','Synthetic weekday multipliers','Mon/Fri/Sun 1.20; other days 0.85','ratio','Not measured.')
    add('MARVIN-PH-event-profile','Part 91 synthetic Super Bowl uplift','Low=0.5x, Medium=1x, High=1.6x of invented central incremental uplift','scenario formula',
        'Part 91 per-day multipliers in demo_planning_inputs.csv. No Presidents Day effect in primary forecast.')
    add('MARVIN-PH-air-taxi-proxy','LAX 2022 airport Air Taxi event excess',AIR_TAXI_EVENT_EXCESS,'fraction',
        'Observed five-day airport Air Taxi excess; transferred to selected-fleet Part 135 on 2027 Fri-Tue for illustration. Not an observed fleet or directional effect.',
        classification='benchmark',source='alan/elia_output/data/processed/superbowl_lvi_surge.csv; air_taxi,LAX')
    add('MARVIN-PH-reservations','Synthetic FBO-specific bookings','Random FBO bookings; show rate 0.75-0.95',
        'aircraft and fraction','Already FBO-specific; do not apply the 20% capture a second time.')
    add('MARVIN-PH-ramp-capacity','Unverified FBO parking/PPR ceiling',CAPACITY_SU,'space units',
        'Inherited P3 ramp estimate, not Alan-confirmed available PPR capacity.',
        classification='assumption',source='ELIA-ramp_capacity_su; elia/assumptions_p3.csv',status='REPLACE_WITH_ALAN_CAPACITY')
    add('MARVIN-PH-physical-spots','Invented physical parking stands',CAPACITY_SPOTS,'stands',
        'Additional hard ceiling for the demo; real usable stands and class limits unknown.')
    add('MARVIN-PH-footprint','Mix-weighted mean parking footprint',round(AIRCRAFT_SU,3),'space units/aircraft',
        '0.47x1.0 + 0.33x1.5 + 0.20x2.5, based on inherited P3 size footprints.',
        classification='assumption',source='ELIA-mix_* and elia/assumptions_p3.csv',status='AGREED_MIX_UNVERIFIED_FOOTPRINT')
    add('MARVIN-PH-departure-timing','Departures before arrival peak',DEPART_BEFORE_PEAK,'fraction','Planning assumption; no hourly slots.')
    add('MARVIN-PH-opening-ground','Synthetic opening aircraft on ground',opening,'aircraft',
        'Computed from synthetic ordinary arrivals times illustrative 1.1-day dwell.')
    add('MARVIN-PH-same-day','Same-day departing share of new arrivals',SAME_DAY_SHARE,'fraction',
        'Carries team illustrative 40/45/15 dwell mix unchanged.')
    add('MARVIN-PH-presidents-day','Presidents Day additional demand effect','unmeasured','effect',
        'No effect included in main forecast. Separate -10/0/+10 percent purely hypothetical sensitivity for 2027-02-15.',
        status='UNMEASURED_SENSITIVITY_ONLY')
    add('MARVIN-PH-hourly-shape','Synthetic hourly demand curve','weekday/weekend fitted hour shares','distribution',
        'Fitted to generated 2023-2025 hourly samples; see hourly_profile_weights.csv. No observed hourly FBO demand.')
    add('MARVIN-PH-turnaround','Synthetic service duration samples','720 generated aircraft samples','minutes',
        'Landing, taxi-in, unload, fuel, reload, taxi-out and takeoff stages; see demo_turnaround_samples.csv.')
    add('MARVIN-PH-parking-prices','Invented parking rates','light 250; midsize 400; large 700','USD/aircraft/24h',
        'Illustrative early-arrival discount 15%; no scenario-based premium or actual LAX FBO quote.')
    add('MARVIN-PH-weather','Weather sensitivity','clear 1.0; rain 0.85; low visibility 0.65','throughput factor',
        'Invented scenario factors and added timing delays; actual weather unknown.')
    add('MARVIN-PH-vip','Hypothetical VIP movement hold','0, 2, or 4','hours',
        'Stress test on Feb 14 only. No presidential visit or airport closure is assumed; actual FAA notice controls.')
    write_csv(RESULTS/'placeholder_assumptions.csv',rows)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seed',type=int,default=42)
    args=p.parse_args()
    RESULTS.mkdir(exist_ok=True)
    subprocess.run([sys.executable,str(HERE/'forecast_model.py'),'--demo','--seed',str(args.seed),'--output-dir',str(RESULTS)],check=True)
    history=read_csv(RESULTS/'demo_historical_traffic.csv')
    planning=read_csv(RESULTS/'demo_planning_inputs.csv')
    predictions=read_csv(RESULTS/'demand_predictions.csv')
    part_predictions=read_csv(RESULTS/'part_demand_predictions.csv')
    totals=read_csv(RESULTS/'daily_totals.csv')
    metrics=read_csv(RESULTS/'evaluation_metrics.csv')
    # Keep existing P2 file names, headers and metadata keys stable.
    contract=json.loads((HERE/'forecast_output_contract.json').read_text(encoding='utf-8'))
    for name,cols in contract['csv_columns'].items():
        assert list(read_csv(RESULTS/name)[0])==cols, name+' header changed'
    assert list(json.loads((RESULTS/'run_metadata.json').read_text(encoding='utf-8')))==contract['metadata_keys']
    capacity, opening=make_capacity_plan(totals,predictions)
    write_csv(RESULTS/'capacity_plan.csv',capacity)
    part_totals=[]
    for day in sorted({r['date'] for r in part_predictions}):
        for scenario in SCENARIOS:
            for part in PART_SHARES:
                group=[r for r in part_predictions if r['date']==day and r['scenario']==scenario and r['operation_part']==part]
                part_totals.append(dict(date=day,scenario=scenario,operation_part=part,
                    baseline_arrivals=round(sum(float(r['baseline_arrivals']) for r in group),3),
                    expected_arrivals=round(sum(float(r['expected_arrivals']) for r in group),3),
                    baseline_departures=round(sum(float(r['baseline_departures']) for r in group),3),
                    expected_departures=round(sum(float(r['expected_departures']) for r in group),3),
                    classification='synthetic_selected_fleet_estimate'))
    write_csv(RESULTS/'part_daily_totals.csv',part_totals)
    write_assumptions(args.seed,opening)
    source=HERE.parents[1]/'alan/elia_output/data/processed/superbowl_lvi_surge.csv'
    air_taxi=[r for r in read_csv(source) if r['metric']=='air_taxi' and r['locid']=='LAX']
    if len(air_taxi)!=1 or abs(float(air_taxi[0]['excess_2022'])-AIR_TAXI_EVENT_EXCESS)>1e-9:
        raise ValueError('LAX Air Taxi event benchmark changed; review the transfer assumption')
    write_csv(RESULTS/'air_taxi_event_reference.csv',[dict(metric='air_taxi',airport='LAX',event='Super_Bowl_LVI_2022',
        observed_five_day_excess=air_taxi[0]['excess_2022'],
        source_repo_path='alan/elia_output/data/processed/superbowl_lvi_surge.csv',
        forecast_use='Assumed Part 135 medium multiplier 1.155 for 2027-02-12 through 2027-02-16; not measured selected-fleet effect',
        scope_limit='FAA Air Taxi is broader than selected-fleet Part 135; no directional split')])
    reference=[r for r in history if r['date'].startswith('2022-02')]
    write_csv(RESULTS/'placeholder_feb2022_reference.csv',reference)
    gap_rows=[]
    for game,year,city in [('LVI',2022,'Los Angeles'),('LVII',2023,'Phoenix'),('LVIII',2024,'Las Vegas'),('LIX',2025,'New Orleans'),('LX',2026,'Santa Clara')]:
        gap_rows.append(dict(super_bowl=game,year=year,host_region=city,
            selected_private_fleet_observed_ratio='',classification='not_available',
            note='No flight-level selected-fleet records. LAX 2022 FAA Air Taxi excess is a broader airport-category proxy, not this ratio.'))
    write_csv(RESULTS/'previous_super_bowls_data_gaps.csv',gap_rows)
    holiday=[]
    for row in (x for x in totals if x['date']=='2027-02-15'):
        for label,factor in [('lower_hypothetical',0.9),('unchanged_primary',1.0),('upper_hypothetical',1.1)]:
            holiday.append(dict(date=row['date'],scenario=row['scenario'],sensitivity=label,
                additional_presidents_day_factor=factor,
                arrival_demand_sensitivity=round(float(row['expected_arrivals'])*factor,3),
                departure_demand_sensitivity=round(float(row['expected_departures'])*factor,3),
                primary_forecast_changed='no',classification='PLACEHOLDER_UNMEASURED_SENSITIVITY',
                note='Hypothetical +/-10 percent only; no measured Presidents Day effect or capacity rerun.'))
    write_csv(RESULTS/'presidents_day_sensitivity.csv',holiday)
    private_meta=dict(status='PLACEHOLDER',seed=args.seed,
        scope='Selected-fleet Part 91 and Part 135; Part 121 and outside fleets excluded',
        history='Seeded synthetic 2016-2025; 2020-2022 excluded; model trained/calibrated/tested on 2023-2025 only',
        event_uplift='Part 91 synthetic profile; Part 135 uses assumed transfer of observed LAX 2022 five-day Air Taxi +15.5% proxy to 2027 Fri-Tue, with Low 0% and High 31% sensitivities',
        reservations='Synthetic FBO-specific bookings; 20% capture is not applied twice',
        fbo_capture_share=FBO_CAPTURE_SHARE,eligible_pool='Selected fleets Part 91/135 only; synthetic 70/30 split; no Part 121 or all-airport total multiplied by FBO share',
        aircraft_size_mix=AIRCRAFT_MIX,
        presidents_day='Unmeasured; excluded from primary forecast; sidecar +/-10 percent hypothetical sensitivity only',
        fbo_ppr_capacity_su=CAPACITY_SU,physical_spots_placeholder=CAPACITY_SPOTS,assumed_su_per_aircraft=AIRCRAFT_SU,
        opening_ground=opening,departure_before_arrival_peak=DEPART_BEFORE_PEAK,
        same_day_share=SAME_DAY_SHARE,
        evaluation='Synthetic holdout only; not observed FBO or selected-fleet accuracy',
        uncertainty='90% nominal baseline prediction intervals; event-adjusted planning ranges are not calibrated',
        runway='No verified residual LAX slot allocation; capacity plan flags illustrative parking overflow for manager review and makes no accept/refuse decisions')
    (RESULTS/'private_fleet_run_metadata.json').write_text(json.dumps(private_meta,indent=2)+'\n',encoding='utf-8')
    ops=build_operations(RESULTS,args.seed,CAPACITY_SPOTS)
    css='body{font:16px system-ui,sans-serif;margin:0;background:#f4f6f8;color:#17263c}main{max-width:1180px;margin:32px auto;padding:20px}.banner{background:#fff0c2;border-left:7px solid #ae7000;padding:18px;border-radius:8px}.card{background:white;margin:22px 0;padding:22px;border:1px solid #dce3eb;border-radius:12px;overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:8px;text-align:left;border-bottom:1px solid #dce3eb}th{background:#e9eef5}tr:nth-child(even){background:#f8fafc}a{color:#125b9f}'
    page='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>PLACEHOLDER â€” Private Fleet Person 2</title><style>'+css+'</style><main>'
    page+='<div class="banner"><strong>PLACEHOLDER â€” SYNTHETIC DEMONSTRATION</strong><p>History and reservations are synthetic. The Part 135 event factor transfers observed airport Air Taxi evidence by assumption; it is not measured selected-fleet uplift. The 75-unit capacity is unverified. Synthetic backtest scores are not real-world accuracy.</p></div>'
    page+='<h1>Person 2: selected-fleet Part 91 and Part 135 forecast</h1><p>Part 121 and outside fleets are excluded. The synthetic eligible pool uses an unmeasured 70/30 Part 91/135 split. The 20% FBO capture is applied once; the 47/33/20 aircraft size mix is used throughout.</p>'
    page+='<section class="card"><h2>Feb 11â€“17, 2027 demand</h2><p>Expected movements include assumed event uplifts and simulated reservations. These are demand forecasts for parking review.</p>'+as_table(totals,list(totals[0]))+'</section>'
    page+='<section class="card"><h2>Part 91 and Part 135 demand</h2><p>Part 135 uses the observed LAX 2022 Air Taxi five-day +15.5% excess as a transferred Medium scenario assumption for Friday through Tuesday. FAA Air Taxi is broader than the selected fleets, and no direction-specific effect was measured. Low and High are sensitivities, not confidence bounds.</p>'+as_table(part_totals,['date','scenario','operation_part','expected_arrivals','expected_departures'])+'<p><a href="air_taxi_event_reference.csv">Air Taxi evidence and transfer limit</a> · <a href="part_demand_predictions.csv">Category and Part detail</a></p></section>'
    show=['date','scenario','forecast_arrivals_rounded','forecast_departures_rounded','projected_peak_ground','parking_overflow_to_resolve','departure_inventory_gap_to_reconcile','end_day_ground_if_demand_occurs']
    page+='<section class="card"><h2>PLACEHOLDER parking review</h2><p>Overflow is a planning flag for a manager. This model does not accept, refuse or cancel any aircraft. A departure inventory gap means the aggregate forecast cannot reconcile aircraft histories; it is not a stuck aircraft. The 24 stands are invented and 75 space units are unverified.</p>'+as_table(capacity,show)+'</section>'
    page+='<section class="card"><h2>Daily operational sensitivity: time, spots and price</h2><p>All times, 24 stands and dollar rates are placeholders. Ground time to park is distinct from overnight dwell; minimum turnaround is sequential service time.</p>'+as_table(ops['operations'],['date','scenario','expected_private_arrivals','expected_private_departures','parking_overflow_to_resolve','departure_inventory_gap_to_reconcile','landing_to_park_minutes','park_to_takeoff_minutes','minimum_service_turnaround_minutes'])+'</section>'
    peak=sorted([r for r in ops['hourly'] if r['scenario']=='Medium'],key=lambda r:float(r['expected_movements']),reverse=True)[:12]
    page+='<section class="card"><h2>Hourly activity curve</h2><p>Expected hourly movements = daily arrivals times fitted arrival-hour share + daily departures times fitted departure-hour share. The shares were fitted on seeded synthetic 2023–2025 hourly history. High/Medium/Low activity bands rank hours within a day and are distinct from demand scenarios.</p>'+as_table(peak,['date','hour_window','activity_band','expected_arrivals','expected_departures','expected_movements'])+'<p><a href="hourly_activity_curve.csv">All 504 hourly rows</a> · <a href="hourly_profile_weights.csv">Fitted hourly shares</a></p></section>'
    page+='<section class="card"><h2>Illustrative early-arrival price incentive</h2><p>Invented USD per aircraft per 24 hours. Early arrival is 15% lower than other slots in every scenario. No real LAX FBO tariff or automated price decision is claimed.</p>'+as_table(ops['rates'],['traffic_scenario','aircraft_category','arrival_slot','suggested_usd_per_24h'])+'</section>'
    page+='<section class="card"><h2>Weather and VIP sensitivities</h2><p>No weather forecast or presidential visit is assumed. Rain and low visibility add invented delay minutes. A 0/2/4-hour full movement pause is only a stress test; an FAA notice determines any actual VIP restriction, which need not close the airport.</p>'+as_table(ops['visit'],['scenario','hypothetical_full_pause_hours','expected_private_movements_in_window','approximate_movements_to_reschedule'])+'<p><a href="weather_sensitivity.csv">Weather sensitivity</a> · <a href="turnaround_time_estimates.csv">Service-stage times</a> · <a href="operational_source_links.csv">Source links</a></p></section>'
    page+='<section class="card"><h2>Synthetic model check</h2><p>Chronological 2023â€“2025 split. All outcomes are randomly generated; no observed FBO accuracy is measured.</p>'+as_table(metrics,['aircraft_category','operation_part','target','model_mae','historical_mean_mae','test_coverage'])+'</section>'
    page+='<section class="card"><h2>Presidents Day: unmeasured sensitivity only</h2><p>February 15 has no holiday adjustment in the main forecast. The +/-10% values below are hypothetical illustrations, not measured effects.</p>'+as_table(holiday,['scenario','sensitivity','arrival_demand_sensitivity','departure_demand_sensitivity'])+'</section>'
    page+='<section class="card"><h2>Uncertainty and provenance</h2><p>Nominal baseline prediction coverage is 90%; scaled event ranges have no validated event coverage. See the exact per-day multipliers, assumptions and provenance files.</p><p><a href="uncertainty_results.csv">Uncertainty</a> Â· <a href="demo_planning_inputs.csv">Event multipliers and reservations</a> Â· <a href="placeholder_assumptions.csv">Assumptions</a> Â· <a href="private_fleet_run_metadata.json">Run metadata</a></p></section></main></html>'
    page=page.replace('History and reservations are synthetic. The Part 135 event factor transfers observed airport Air Taxi evidence by assumption; it is not measured selected-fleet uplift. The 75-unit capacity is unverified.',
        'History and reservations are synthetic. The Part 135 event factor transfers observed airport Air Taxi evidence by assumption; it is not measured selected-fleet uplift. The 75-unit capacity is unverified.')
    page=page.replace('These are demand forecasts for parking review.',
        'These are demand forecasts for parking review.')
    page=page.replace('\ufffd', ' / ').replace('Â·', ' / ')
    (RESULTS/'report.html').write_text(page,encoding='utf-8')
    files=sorted(x for x in RESULTS.iterdir() if x.is_file() and x.name!='placeholder_manifest.json')
    manifest={'status':'PLACEHOLDER','seed':args.seed,'files':{x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in files}}
    (RESULTS/'placeholder_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('PLACEHOLDER private-fleet run complete:',len(predictions),'forecasts,',len(capacity),'capacity rows; open results/report.html')
if __name__=='__main__':
    main()
