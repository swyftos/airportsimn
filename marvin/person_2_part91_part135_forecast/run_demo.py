"""Generate the Person 2 Part 91/135 forecast from observed FAA daily counts, plus operations sensitivities."""
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
import forecast_model as fm
from forecast_model import AIRCRAFT_MIX, FBO_CAPTURE_SHARE, PART_COLUMNS, PRIVATE_ELIGIBLE, EVENT_EXCESS
from operations_extension import build as build_operations

HERE = Path(__file__).resolve().parent
RESULTS = HERE / 'results'
SCENARIOS = ('Low', 'Medium', 'High')
P3_ASSUMPTIONS = HERE.parents[1]/'elia/assumptions_p3.csv'
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

def ramp_capacity_su():
    """Elia's P3 ramp estimate; parking capacity is owned by P3, not invented here."""
    return next(float(r['value']) for r in read_csv(P3_ASSUMPTIONS) if r['parameter'] == 'ramp_capacity_su')

def make_capacity_plan(totals, predictions, capacity_su):
    by_key = defaultdict(list)
    for r in predictions:
        by_key[r['date'], r['scenario']].append(r)
    baseline_day = [float(r['baseline_arrivals']) for r in totals if r['scenario'] == 'Medium']
    opening = round(sum(baseline_day) / len(baseline_day) * 1.1, 2)
    capacity_aircraft = math.floor(capacity_su / AIRCRAFT_SU)
    rows = []
    for scenario in SCENARIOS:
        occupied = opening
        for r in (x for x in totals if x['scenario'] == scenario):
            # Expected values stay fractional; rounding each day up would inflate demand.
            arrivals = round(float(r['expected_arrivals']), 2)
            departures = round(float(r['expected_departures']), 2)
            early = min(departures * DEPART_BEFORE_PEAK, occupied)
            peak = round(occupied - early + arrivals, 2)
            overflow = round(max(0, peak - capacity_aircraft), 2)
            inventory_gap = round(max(0, departures - occupied - arrivals), 2)
            end_ground = round(max(0, occupied + arrivals - departures), 2)
            details = by_key[r['date'], scenario]
            assert set(x['aircraft_category'] for x in details) == set(AIRCRAFT_MIX)
            same_day_est = min(departures, round(arrivals * SAME_DAY_SHARE, 2))
            overnight_new_est = round(arrivals - same_day_est, 2)
            rows.append(dict(date=r['date'], scenario=scenario,
                scope='part91_part135_excludes_part121',
                forecast_arrivals=arrivals, forecast_departures=departures,
                projected_peak_ground=peak, parking_overflow_to_resolve=overflow,
                departure_inventory_gap_to_reconcile=inventory_gap,
                opening_ground=opening if r['date']=='2027-02-11' else '',
                end_day_ground_if_demand_occurs=end_ground,
                new_arrivals_same_day_leave_est=same_day_est,
                new_arrivals_remaining_overnight_est=overnight_new_est,
                fbo_ppr_capacity_su=capacity_su, assumed_su_per_aircraft=AIRCRAFT_SU,
                capacity_aircraft_equivalent=capacity_aircraft,
                classification='estimated_from_FAA_counts',
                note='Aggregate check only; the P3 optimizer (elia/) does the parking plan. Overflow needs manager review; no flight is accepted, refused or canceled. Departure inventory gap is unknown itinerary/opening-inventory reconciliation, not a stuck aircraft. Capacity is the P3 ramp estimate (unverified).'))
            occupied = end_ground
    return sorted(rows, key=lambda r:(r['date'], SCENARIOS.index(r['scenario']))), opening

def write_assumptions(opening, capacity_su, excess):
    faa = 'https://www.aspm.faa.gov/opsnet/sys/Airport.asp'
    rows = []
    def add(id,label,value,unit,note,classification='assumption',source=None,status='REVIEW_REQUIRED'):
        rows.append(dict(id=id,owner='Marvin',label=label,value=value,unit=unit,
            classification=classification,confidence='low',source=source or 'team assumption',status=status,note=note))
    add('MARVIN-P27-scope','Forecast scope','Part 91 (FAA general aviation) and Part 135 (FAA air taxi); no Part 121 or military','scope',
        'Each part is forecast separately (part_daily_totals.csv) so either scope can be used.',classification='public',source=faa,status='OBSERVED_CATEGORIES')
    for part, column in PART_COLUMNS.items():
        add(f'MARVIN-P27-history-{part}',f'History for {part}',f'FAA daily LAX {column} operations 2023-2025','airport operations',
            'Observed tower counts. Air taxi also includes cargo feeders and small commuter flights; GA also includes training and positioning.',
            classification='public',source=faa,status='OBSERVED')
        add(f'MARVIN-P27-eligible-{part}',f'Private-eligible share of {column}',PRIVATE_ELIGIBLE[part],'fraction',
            'Placeholder filter for non-FBO traffic in the FAA category; not measured.',status='PLACEHOLDER')
    add('MARVIN-P27-fbo-capture','FBO capture of eligible operations',FBO_CAPTURE_SHARE,'fraction',
        '0.50 x 0.20 = 0.10, the fbo_market_share in alan/assumptions.csv.',source='alan/assumptions.csv fbo_market_share',status='AGREED_ASSUMPTION_NOT_OBSERVED')
    for category,mix in AIRCRAFT_MIX.items():
        add('MARVIN-P27-mix-'+category,'FBO aircraft size mix '+category,mix,'fraction',
            'Team 47/33/20 mix; no official source found.',source='ELIA-mix_* in assumptions.csv',status='AGREED_ASSUMPTION_NOT_OBSERVED')
    for scenario,(metric,factor) in EVENT_EXCESS.items():
        add(f'MARVIN-P27-event-{scenario}',f'{scenario.title()} five-day Super Bowl excess',round(excess[scenario],4),'fraction',
            f'{factor}x LAX {metric} control-adjusted excess around Super Bowl LVI; same scenarios as the main forecast.',
            classification='benchmark',source='alan/elia_output/data/processed/superbowl_lvi_surge.csv',status='MEASURED_PROXY')
    add('MARVIN-P27-presidents-day','Presidents Day effect','learned from 2023-2024 training holidays','factor',
        'See presidents_day_effect.csv; applied to the baseline of 2027-02-15.',classification='estimated',source=faa,status='LEARNED')
    add('MARVIN-P27-reservations','FBO bookings','none supplied','aircraft','Reservation floors disabled.',status='NO_DATA')
    add('MARVIN-P27-ramp-capacity','FBO parking ceiling',capacity_su,'space units',
        'Read from elia/assumptions_p3.csv; the P3 optimizer owns parking capacity.',source='elia/assumptions_p3.csv ramp_capacity_su',status='P3_ESTIMATE')
    add('MARVIN-P27-footprint','Mix-weighted mean parking footprint',round(AIRCRAFT_SU,3),'space units/aircraft',
        '0.47x1.0 + 0.33x1.5 + 0.20x2.5.',source='elia/assumptions_p3.csv',status='AGREED_MIX_UNVERIFIED_FOOTPRINT')
    add('MARVIN-P27-departure-timing','Departures before arrival peak',DEPART_BEFORE_PEAK,'fraction','Planning assumption; no hourly slots.')
    add('MARVIN-P27-opening-ground','Opening aircraft on ground',opening,'aircraft','Ordinary arrivals x 1.1-day dwell.',classification='estimated')
    add('MARVIN-P27-same-day','Same-day departing share of new arrivals',SAME_DAY_SHARE,'fraction','Team illustrative 40/45/15 dwell mix.')
    add('MARVIN-P27-hourly-shape','Hourly demand curve','weekday/weekend hour shares','distribution',
        'Synthetic: no observed hourly FBO or GA data. Replace when hourly records exist.',classification='synthetic',status='PLACEHOLDER')
    add('MARVIN-P27-turnaround','Service duration samples','720 generated aircraft samples','minutes',
        'Synthetic landing, taxi, unload, fuel, reload, taxi and takeoff stages.',classification='synthetic',status='PLACEHOLDER')
    add('MARVIN-P27-parking-prices','Illustrative parking rates','light 250; midsize 400; large 700','USD/aircraft/24h',
        'Invented; early arrival = landing on Thu 2027-02-11 or Fri 2027-02-12, before the Sat-Mon peak, 15% lower.',classification='synthetic',status='PLACEHOLDER')
    add('MARVIN-P27-vip','Hypothetical VIP movement hold','0, 2, or 4','hours',
        'Stress test on Feb 14 only; actual FAA notice controls.',classification='synthetic',status='STRESS_TEST')
    write_csv(RESULTS/'forecast_assumptions.csv',rows)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seed',type=int,default=42,help='Seed for the synthetic hourly and service-time layers only')
    args=p.parse_args()
    RESULTS.mkdir(exist_ok=True)
    subprocess.run([sys.executable,str(HERE/'forecast_model.py'),'--faa','--output-dir',str(RESULTS)],check=True)
    history=fm.load_history(RESULTS/'historical_traffic.csv')
    predictions=read_csv(RESULTS/'demand_predictions.csv')
    part_predictions=read_csv(RESULTS/'part_demand_predictions.csv')
    totals=read_csv(RESULTS/'daily_totals.csv')
    metrics=read_csv(RESULTS/'evaluation_metrics.csv')
    # Keep existing P2 file names, headers and metadata keys stable.
    contract=json.loads((HERE/'forecast_output_contract.json').read_text(encoding='utf-8'))
    for name,cols in contract['csv_columns'].items():
        assert list(read_csv(RESULTS/name)[0])==cols, name+' header changed'
    assert list(json.loads((RESULTS/'run_metadata.json').read_text(encoding='utf-8')))==contract['metadata_keys']
    capacity_su=ramp_capacity_su()
    capacity, opening=make_capacity_plan(totals,predictions,capacity_su)
    write_csv(RESULTS/'capacity_plan.csv',capacity)
    part_totals=[]
    for day in sorted({r['date'] for r in part_predictions}):
        for scenario in SCENARIOS:
            for part in PART_COLUMNS:
                group=[r for r in part_predictions if r['date']==day and r['scenario']==scenario and r['operation_part']==part]
                part_totals.append(dict(date=day,scenario=scenario,operation_part=part,
                    baseline_arrivals=round(sum(float(r['baseline_arrivals']) for r in group),3),
                    expected_arrivals=round(sum(float(r['expected_arrivals']) for r in group),3),
                    baseline_departures=round(sum(float(r['baseline_departures']) for r in group),3),
                    expected_departures=round(sum(float(r['expected_departures']) for r in group),3),
                    classification='estimated_from_FAA_counts'))
    write_csv(RESULTS/'part_daily_totals.csv',part_totals)
    surge={r['metric']:float(r['excess_2022']) for r in read_csv(fm.SURGE) if r['locid']=='LAX'}
    excess={s:surge[metric]*k for s,(metric,k) in EVENT_EXCESS.items()}
    write_assumptions(opening,capacity_su,excess)
    write_csv(RESULTS/'event_reference.csv',[dict(scenario=s,metric=metric,factor=k,five_day_excess=round(excess[s],4),
        source_repo_path='alan/elia_output/data/processed/superbowl_lvi_surge.csv',
        method='FAA counts Thu-Mon around Super Bowl LVI vs same weekdays, divided by control years 2019, 2023, 2024')
        for s,(metric,k) in EVENT_EXCESS.items()])
    feb2022=[dict(date=r['date'],part91_general_aviation=r['general_aviation'],part135_air_taxi=r['air_taxi'],
                  super_bowl_lvi=r['date']=='2022-02-13',classification='observed_FAA_airport_operations',source=r['source'])
             for r in read_csv(fm.FAA_DAILY) if r['date'].startswith('2022-02')]
    write_csv(RESULTS/'feb2022_faa_reference.csv',feb2022)
    gap_rows=[]
    for game,year,city in [('LVI',2022,'Los Angeles'),('LVII',2023,'Phoenix'),('LVIII',2024,'Las Vegas'),('LIX',2025,'New Orleans'),('LX',2026,'Santa Clara')]:
        gap_rows.append(dict(super_bowl=game,year=year,host_region=city,
            faa_lax_excess_measured='yes' if year==2022 else 'not_host_city_for_LAX',
            note='Only LVI was hosted in Los Angeles; other host airports could be pulled from FAA OPSNET for comparison.'))
    write_csv(RESULTS/'previous_super_bowls_data_gaps.csv',gap_rows)
    fitted,_=fm.fit_and_evaluate(history,.9)
    holiday=[dict(operation_part=part,target=t,learned_factor=round(fitted['light_jet',part,t][0].holiday['presidents_day'],4),
                  training_holidays='2023-02-20, 2024-02-19',applied_to='2027-02-15 baseline',classification='estimated_from_FAA_counts')
             for part in PART_COLUMNS for t in fm.TARGETS]
    write_csv(RESULTS/'presidents_day_effect.csv',holiday)
    private_meta=dict(status='ESTIMATED_FROM_FAA_COUNTS',
        scope='Part 91 (FAA GA) and Part 135 (FAA air taxi); Part 121 and military excluded',
        history='Observed FAA daily LAX counts 2023-2025; 2020-2022 excluded',
        event_uplift={s:round(e,4) for s,e in excess.items()},
        reservations='None supplied; floors disabled',
        fbo_capture_share=FBO_CAPTURE_SHARE,private_eligible_share=PRIVATE_ELIGIBLE,
        aircraft_size_mix=AIRCRAFT_MIX,presidents_day='Learned factor applied to baseline; see presidents_day_effect.csv',
        fbo_ppr_capacity_su=capacity_su,assumed_su_per_aircraft=AIRCRAFT_SU,
        opening_ground=opening,departure_before_arrival_peak=DEPART_BEFORE_PEAK,same_day_share=SAME_DAY_SHARE,
        evaluation='Chronological holdout on observed daily airport counts; not observed FBO accuracy',
        uncertainty='90% nominal baseline prediction intervals; event-adjusted planning ranges are not calibrated',
        synthetic_layers='Hourly curve, service times, parking prices and VIP pause remain synthetic placeholders',
        runway='No verified residual LAX slot allocation; capacity plan flags overflow for manager review and makes no accept/refuse decisions')
    (RESULTS/'private_fleet_run_metadata.json').write_text(json.dumps(private_meta,indent=2)+'\n',encoding='utf-8')
    ops=build_operations(RESULTS,args.seed,capacity_su)
    css='body{font:16px system-ui,sans-serif;margin:0;background:#f4f6f8;color:#17263c}main{max-width:1180px;margin:32px auto;padding:20px}.banner{background:#fff0c2;border-left:7px solid #ae7000;padding:18px;border-radius:8px}.card{background:white;margin:22px 0;padding:22px;border:1px solid #dce3eb;border-radius:12px;overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:8px;text-align:left;border-bottom:1px solid #dce3eb}th{background:#e9eef5}tr:nth-child(even){background:#f8fafc}a{color:#125b9f}'
    page='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Person 2 Part 91 and 135 forecast</title><style>'+css+'</style><main>'
    page+='<div class="banner"><strong>Estimated from observed FAA counts</strong><p>Daily history is observed FAA tower data at LAX (general aviation for Part 91, air taxi for Part 135). The 50% private-eligible share and 20% FBO capture are assumptions, so these are not observed FBO counts. Hourly curve, service times, prices and the VIP pause are synthetic placeholders.</p></div>'
    page+='<h1>Person 2: Part 91 and Part 135 forecast</h1><p>Part 121 and military are excluded. Each part is forecast separately and summed; the 47/33/20 aircraft size mix is used throughout.</p>'
    page+='<section class="card"><h2>Feb 11–17, 2027 demand</h2><p>Expected movements include the measured Super Bowl scenarios (Low +3.1%, Medium +15.5%, High +31%) and a learned Presidents Day effect. No bookings were supplied.</p>'+as_table(totals,list(totals[0]))+'</section>'
    page+='<section class="card"><h2>Part 91 and Part 135 demand</h2><p>Both parts use the same scenario multipliers. Medium is the measured LAX air-taxi response, so it is a direct measurement for Part 135 and an analog for Part 91.</p>'+as_table(part_totals,['date','scenario','operation_part','expected_arrivals','expected_departures'])+'<p><a href="event_reference.csv">Scenario evidence</a> / <a href="part_demand_predictions.csv">Category and part detail</a></p></section>'
    show=['date','scenario','forecast_arrivals','forecast_departures','projected_peak_ground','parking_overflow_to_resolve','departure_inventory_gap_to_reconcile','end_day_ground_if_demand_occurs']
    page+='<section class="card"><h2>Parking check</h2><p>Aggregate check against the P3 ramp estimate ('+f'{capacity_su:g}'+' su). The P3 optimizer does the parking plan. Overflow would be a planning flag for a manager; this model does not accept, refuse or cancel any aircraft.</p>'+as_table(capacity,show)+'</section>'
    page+='<section class="card"><h2>Daily operational sensitivity: time and price</h2><p>Service times and dollar rates are placeholders. Ground time to park is distinct from overnight dwell; minimum turnaround is sequential service time.</p>'+as_table(ops['operations'],['date','scenario','expected_private_arrivals','expected_private_departures','parking_overflow_to_resolve','landing_to_park_minutes','park_to_takeoff_minutes','minimum_service_turnaround_minutes'])+'</section>'
    peak=sorted([r for r in ops['hourly'] if r['scenario']=='Medium'],key=lambda r:float(r['expected_movements']),reverse=True)[:12]
    page+='<section class="card"><h2>Hourly activity curve</h2><p>Expected hourly movements = daily arrivals x arrival-hour share + daily departures x departure-hour share. The hour shares are synthetic (no observed hourly data); the daily totals are the FAA-based forecast.</p>'+as_table(peak,['date','hour_window','activity_band','expected_arrivals','expected_departures','expected_movements'])+'<p><a href="hourly_activity_curve.csv">All 504 hourly rows</a> / <a href="hourly_profile_weights.csv">Hour shares</a></p></section>'
    page+='<section class="card"><h2>Illustrative early-arrival price incentive</h2><p>Invented USD per aircraft per 24 hours. Early arrival means landing on Thursday 11 or Friday 12 February, before the Saturday to Monday peak, at 15% less. No real LAX FBO tariff or automated price decision is claimed.</p>'+as_table(ops['rates'],['traffic_scenario','aircraft_category','arrival_slot','suggested_usd_per_24h'])+'</section>'
    page+='<section class="card"><h2>Weather and VIP sensitivities</h2><p>'+ops['weather_note']+' A 0/2/4-hour full movement pause is only a stress test; an FAA notice determines any actual VIP restriction.</p>'+as_table(ops['visit'],['scenario','hypothetical_full_pause_hours','expected_private_movements_in_window','approximate_movements_to_reschedule'])+'<p><a href="weather_sensitivity.csv">Weather sensitivity</a> / <a href="turnaround_time_estimates.csv">Service-stage times</a> / <a href="operational_source_links.csv">Source links</a></p></section>'
    page+='<section class="card"><h2>Model check on observed days</h2><p>Chronological 2023–2025 split on observed FAA daily counts (test days from 2025-05-26). Errors measure the daily airport pattern scaled by the assumed shares, not observed FBO accuracy.</p>'+as_table(metrics,['aircraft_category','operation_part','target','model_mae','historical_mean_mae','improvement_percent','test_coverage'])+'</section>'
    page+='<section class="card"><h2>Presidents Day</h2><p>Factor learned from the 2023 and 2024 holidays in the training days, applied to the 2027-02-15 baseline.</p>'+as_table(holiday,['operation_part','target','learned_factor'])+'</section>'
    page+='<section class="card"><h2>Uncertainty and provenance</h2><p>Nominal baseline prediction coverage is 90%; scaled event ranges have no validated event coverage.</p><p><a href="uncertainty_results.csv">Uncertainty</a> / <a href="planning_inputs.csv">Event multipliers</a> / <a href="forecast_assumptions.csv">Assumptions</a> / <a href="private_fleet_run_metadata.json">Run metadata</a></p></section></main></html>'
    (RESULTS/'report.html').write_text(page,encoding='utf-8')
    files=sorted(x for x in RESULTS.iterdir() if x.is_file() and x.name!='forecast_manifest.json')
    manifest={'status':'ESTIMATED_FROM_FAA_COUNTS','seed':args.seed,'files':{x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in files}}
    (RESULTS/'forecast_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('Part 91/135 run complete:',len(predictions),'forecasts,',len(capacity),'capacity rows; open results/report.html')
if __name__=='__main__':
    main()
