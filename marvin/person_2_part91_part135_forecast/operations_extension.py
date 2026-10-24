"""Part 91/135 operations layer: synthetic hourly and service-time placeholders, observed weather effects."""
import csv
import json
import math
import random
from collections import defaultdict
from datetime import date
from pathlib import Path

MIX = {'light_jet': 0.47, 'midsize_jet': 0.33, 'large_jet': 0.20}
STAGES = ('landing_runway_min', 'taxi_in_min', 'unload_min', 'fuel_min',
          'reload_min', 'taxi_out_min', 'takeoff_runway_min')
BASE_MINUTES = dict(zip(STAGES, (4, 9, 18, 35, 16, 11, 3)))
SIZE_FACTOR = {'light_jet': .85, 'midsize_jet': 1.0, 'large_jet': 1.25}
BASE_PARKING = {'light_jet': 250, 'midsize_jet': 400, 'large_jet': 700}
EARLY_ARRIVAL_DISCOUNT = 0.15  # Illustrative slot incentive, not a real tariff.
EARLY_ARRIVAL_DATES = ('2027-02-11', '2027-02-12')  # before the Sat-Mon parking peak
MEAN_SU = .47*1.0 + .33*1.5 + .20*2.5
WEATHER_TYPES = ('rain', 'heavy_rain', 'heavy_fog')  # measured in weather_effect.py
PARTS = {'part91': 'part91_general_aviation', 'part135': 'part135_air_taxi'}
SOURCES = [
    ('NOAA GHCN-Daily, LAX station USW00023174', 'https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries&stations=USW00023174',
     'Observed daily rain and fog 2015-2026; joined with FAA daily counts in weather_effect.py.'),
    ('FAA VIP/TFR operating restrictions', 'https://www.faa.gov/uas/getting_started/where_can_i_fly/airspace_restrictions/tfr',
     'Actual restriction time, area and permitted flights come from the applicable notice; no fixed closure duration.'),
    ('FAA LAX capacity profile index', 'https://www.faa.gov/airports/planning_capacity/profiles',
     'Airport-wide profile, not available FBO stands or 2027 slots.'),
    ('FAA ATADS/OPSNET LAX daily operations', 'https://www.aspm.faa.gov/opsnet/sys/Airport.asp',
     'Observed GA (Part 91) and air taxi (Part 135) counts; categories are broader than FBO customers.'),
    ('Team assumptions ledger', 'https://github.com/swyftos/airportsimn/blob/main/alan/assumptions.csv',
     'fbo_market_share 0.10 (50% eligible x 20% capture) and 47/33/20 aircraft mix; assumptions, not measurements.'),
    ('Elia parking assumptions', 'https://github.com/swyftos/airportsimn/blob/main/elia/assumptions_p3.csv',
     'P3 ramp estimate in space units, unverified as usable FBO/PPR capacity.'),
]

def read_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def write_csv(path, rows):
    if not rows:
        raise ValueError('No rows: ' + str(path))
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def gaussian(hour, center, width):
    return math.exp(-.5 * ((hour-center)/width)**2)

def seed_weights(target, day_type):
    shift = 1 if day_type == 'weekend' else 0
    if target == 'arrivals':
        return [.015 + .54*gaussian(h, 10+shift, 2.3) + .46*gaussian(h, 17+shift, 2.6)
                for h in range(24)]
    return [.015 + .63*gaussian(h, 8+shift, 2.2) + .37*gaussian(h, 18+shift, 2.8)
            for h in range(24)]

def build_hourly_profile(results, seed):
    # Reproducible hourly samples are derived from synthetic 2023-25 FBO history.
    history = read_csv(results/'historical_traffic.csv')
    by_day = defaultdict(lambda: {'arrivals': 0.0, 'departures': 0.0})
    for row in history:
        if 2023 <= int(row['date'][:4]) <= 2025:
            for target in ('arrivals', 'departures'):
                by_day[row['date']][target] += float(row[target])
    rng = random.Random(seed + 1001)
    samples = []
    aggregate = defaultdict(float)
    for day, totals in sorted(by_day.items()):
        day_type = 'weekend' if date.fromisoformat(day).weekday() >= 5 else 'weekday'
        curves = {}
        for target in ('arrivals', 'departures'):
            raw = [max(.0001, w*rng.uniform(.75, 1.25))
                   for w in seed_weights(target, day_type)]
            total_w = sum(raw)
            curves[target] = [totals[target]*w/total_w for w in raw]
        for hour in range(24):
            row = dict(date=day, local_hour=hour, day_type=day_type,
                       synthetic_arrivals=round(curves['arrivals'][hour], 5),
                       synthetic_departures=round(curves['departures'][hour], 5),
                       classification='synthetic_placeholder')
            samples.append(row)
            for target in ('arrivals', 'departures'):
                aggregate[day_type, target, hour] += curves[target][hour]
    write_csv(results/'demo_hourly_history.csv', samples)
    profile = []
    lookup = {}
    for day_type in ('weekday', 'weekend'):
        for target in ('arrivals', 'departures'):
            denominator = sum(aggregate[day_type, target, h] for h in range(24))
            for hour in range(24):
                share = aggregate[day_type, target, hour]/denominator
                lookup[day_type, target, hour] = share
                profile.append(dict(day_type=day_type, target=target, local_hour=hour,
                    fitted_hour_share=round(share, 8), training_years='2023-2025_synthetic',
                    classification='synthetic_placeholder'))
    write_csv(results/'hourly_profile_weights.csv', profile)
    return lookup

def build_duration_estimates(results, seed):
    rng = random.Random(seed + 2002)
    samples, grouped = [], defaultdict(list)
    for category in MIX:
        for sample_id in range(240):
            row = dict(sample_id=sample_id, aircraft_category=category)
            for stage in STAGES:
                value = max(1, rng.gauss(BASE_MINUTES[stage]*SIZE_FACTOR[category],
                                         BASE_MINUTES[stage]*SIZE_FACTOR[category]*.18))
                row[stage] = round(value, 2)
                grouped[category, stage].append(value)
            row['classification'] = 'synthetic_placeholder'
            samples.append(row)
    write_csv(results/'demo_turnaround_samples.csv', samples)
    estimates, means = [], {}
    for stage in STAGES:
        for category in MIX:
            values = sorted(grouped[category, stage])
            mean = sum(values)/len(values)
            estimates.append(dict(aircraft_category=category, stage=stage,
                mean_minutes=round(mean, 2), p10_minutes=round(values[24], 2),
                p90_minutes=round(values[215], 2), training_samples=len(values),
                classification='synthetic_placeholder'))
            means[category, stage] = mean
        weighted = sum(MIX[c]*means[c, stage] for c in MIX)
        estimates.append(dict(aircraft_category='mix_weighted_selected_fleets',
            stage=stage, mean_minutes=round(weighted, 2), p10_minutes='',
            p90_minutes='', training_samples=720, classification='synthetic_placeholder'))
    write_csv(results/'turnaround_time_estimates.csv', estimates)
    return {stage: sum(MIX[c]*means[c, stage] for c in MIX) for stage in STAGES}

def build(results, seed, capacity_su):
    spots = math.floor(capacity_su / MEAN_SU)  # aircraft-equivalent positions of the P3 ramp
    profile = build_hourly_profile(results, seed)
    stages = build_duration_estimates(results, seed)
    totals = read_csv(results/'daily_totals.csv')
    capacity = {(r['date'], r['scenario']): r for r in read_csv(results/'capacity_plan.csv')}
    hourly = []
    for row in totals:
        day, scenario = row['date'], row['scenario']
        day_type = 'weekend' if date.fromisoformat(day).weekday() >= 5 else 'weekday'
        activity = [profile[day_type, 'arrivals', h] + profile[day_type, 'departures', h]
                    for h in range(24)]
        order = sorted(activity)
        low_cut, high_cut = order[5], order[18]
        for hour in range(24):
            arr = float(row['expected_arrivals'])*profile[day_type, 'arrivals', hour]
            dep = float(row['expected_departures'])*profile[day_type, 'departures', hour]
            band = 'Low' if activity[hour] <= low_cut else 'High' if activity[hour] >= high_cut else 'Medium'
            hourly.append(dict(date=day, scenario=scenario, local_hour=hour,
                hour_window=f'{hour:02d}:00-{hour:02d}:59', activity_band=band,
                expected_arrivals=round(arr, 4), expected_departures=round(dep, 4),
                expected_movements=round(arr+dep, 4), fitted_day_type=day_type,
                classification='synthetic_placeholder'))
    write_csv(results/'hourly_activity_curve.csv', hourly)
    rates = []
    for scenario in ('Low', 'Medium', 'High'):
        for category, base in BASE_PARKING.items():
            for slot, discount in [('early_arrival', EARLY_ARRIVAL_DISCOUNT), ('other_arrival', 0.0)]:
                rates.append(dict(traffic_scenario=scenario, aircraft_category=category,
                    arrival_slot=slot, arrival_dates='|'.join(EARLY_ARRIVAL_DATES) if slot == 'early_arrival' else 'other dates',
                    base_usd_per_24h=base,
                    illustrative_discount_fraction=discount,
                    suggested_usd_per_24h=round(base*(1-discount), 2),
                    real_fbo_rate_known='no', classification='synthetic_placeholder'))
    write_csv(results/'parking_price_scenarios.csv', rates)
    operations, weather = [], []
    effects = {(r['category'], r['weather_type']): r for r in read_csv(results/'weather_effect_measured.csv')
               if r['window'] == '2016-2019+2023-2025'}
    february = {r['weather_type']: float(r['value']) for r in read_csv(results/'weather_feb_climatology.csv')
                if r['metric'] == 'february_day_share'}
    parts = defaultdict(dict)
    for r in read_csv(results/'part_daily_totals.csv'):
        parts[r['date'], r['scenario']][r['operation_part']] = float(r['expected_arrivals']) + float(r['expected_departures'])
    for row in totals:
        day, scenario = row['date'], row['scenario']
        cap = capacity[day, scenario]
        occupied = float(cap['end_day_ground_if_demand_occurs'])
        utilization = occupied/spots
        congestion = round(max(0, utilization-.5)*12, 2)
        landing_to_park = stages['landing_runway_min'] + stages['taxi_in_min'] + congestion
        park_to_takeoff = stages['taxi_out_min'] + stages['takeoff_runway_min'] + congestion
        turnaround = sum(stages.values()) + 2*congestion
        weighted_rate = sum(MIX[c]*BASE_PARKING[c] for c in MIX)
        operations.append(dict(date=day, scenario=scenario,
            expected_private_arrivals=row['expected_arrivals'],
            expected_private_departures=row['expected_departures'],
            parking_overflow_to_resolve=cap['parking_overflow_to_resolve'],
            departure_inventory_gap_to_reconcile=cap['departure_inventory_gap_to_reconcile'],
            end_day_ground=occupied, capacity_aircraft_equivalent=spots,
            ramp_capacity_su=capacity_su, estimated_open_positions=round(max(0, spots-occupied), 2),
            landing_to_park_minutes=round(landing_to_park, 1),
            park_to_takeoff_minutes=round(park_to_takeoff, 1),
            minimum_service_turnaround_minutes=round(turnaround, 1),
            mix_weighted_parking_usd_per_24h=round(weighted_rate, 2),
            classification='synthetic_service_times_FAA_based_demand',
            note='Part 91/135 forecast. No acceptance or refusal decision. Durations are synthetic and exclude flight time, ATC delay and overnight dwell. Rates are invented.'))
        for condition in WEATHER_TYPES:
            row = dict(date=day, scenario=scenario, condition=condition,
                       february_day_probability=february[condition])
            change = 0.0
            for part, category in PARTS.items():
                e = effects[category, condition]
                row[f'{part}_effect'] = float(e['effect'])
                row[f'{part}_effect_ci'] = f"{float(e['ci_low']):+.3f} to {float(e['ci_high']):+.3f}"
                change += parts[day, scenario][part] * float(e['effect'])
            weather.append(dict(row, expected_movements=round(sum(parts[day, scenario].values()), 3),
                movements_change_if_condition=round(change, 3), actual_weather_forecast='not_available_for_2027',
                classification='observed_NOAA_x_FAA_effect_applied_to_forecast',
                note='Effect on completed airport operations on such days vs dry days of the same weekday and month (2016-2019, 2023-2025).'))
    write_csv(results/'daily_operational_plan.csv', operations)
    write_csv(results/'weather_sensitivity.csv', weather)
    # No visit is forecast. Full movement holds are purely hypothetical stress tests.
    visit = []
    for scenario in ('Low', 'Medium', 'High'):
        for hours in (0, 2, 4):
            day = '2027-02-14'
            affected = sum(float(r['expected_movements']) for r in hourly
                if r['date']==day and r['scenario']==scenario and 12 <= int(r['local_hour']) < 12+hours)
            visit.append(dict(date=day, scenario=scenario, hypothetical_pause_start_local='12:00',
                hypothetical_full_pause_hours=hours,
                expected_private_movements_in_window=round(affected, 2),
                approximate_movements_to_reschedule=round(affected, 2),
                president_visit_known='no', actual_TFR_duration_known='no',
                airport_closure_required='not_established',
                classification='synthetic_stress_test_only',
                note='A VIP TFR is not automatically an airport-wide closure; use actual FAA notice and airport coordination.'))
    write_csv(results/'presidential_security_sensitivity.csv', visit)
    write_csv(results/'operational_source_links.csv',
        [dict(name=name, url=url, use_and_limit=limit) for name, url, limit in SOURCES])
    metadata = dict(status='MIXED_OBSERVED_AND_PLACEHOLDER', seed=seed, scope='Part 91 (FAA GA) and Part 135 (FAA air taxi); Part 121 excluded',
        hourly_curve='Synthetic hour shares (no observed hourly data) applied to the FAA-based daily forecast',
        hourly_formula='expected hourly movements = expected daily arrivals x fitted arrival hour share + expected daily departures x fitted departure hour share',
        timing='720 seeded synthetic category turnaround samples; stages are sequential minimum service times, not full dwell or ATC slot times',
        weather='Observed NOAA x FAA effects of rain, heavy rain and heavy fog on completed operations (weather_effect_measured.csv), with February probabilities; no 2027 weather forecast exists',
        parking='P3 ramp estimate read from elia/assumptions_p3.csv; price slot incentive invented (early = Feb 11-12); overflow requires manager review',
        presidential_visit='No visit assumed; 0/2/4-hour full-pause stress tests on Feb 14 are not FAA closure requirements; actual notice controls',
        primary_event_uplift='Measured FAA Super Bowl LVI excess; per-day factors in planning_inputs.csv',
        evaluation='Holdout on observed FAA daily counts; not observed FBO accuracy',
        source_links='operational_source_links.csv')
    (results/'operations_run_metadata.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')
    heavy = {part: float(effects[c, 'heavy_rain']['effect']) for part, c in PARTS.items()}
    weather_note = (f"Weather is measured, not invented: on LAX heavy-rain days (at least 0.5 in), Part 91 operations were "
                    f"{heavy['part91']:+.1%} and Part 135 {heavy['part135']:+.1%} vs comparable dry days. In February "
                    f"{february['rain']:.0%} of days have rain and {february['heavy_fog']:.0%} heavy fog. No 2027 weather forecast exists.")
    return {'operations': operations, 'hourly': hourly, 'rates': rates, 'stages': stages,
            'weather': weather, 'visit': visit, 'spots': spots, 'weather_note': weather_note}
