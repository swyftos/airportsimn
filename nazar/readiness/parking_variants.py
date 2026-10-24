"""Optional, complete P3 parking comparison release; no simulations on HTTP load."""
import json
from .contracts import DATES, SCENARIOS, number
from .team_adapter import NATIVE_PATHS, check, keyed, load_standard, probability, rows

DELAY = 'departure_delay_24h'
EXTENSION_PATHS = {
    'p3_ordinary': 'elia/ordinary_week_parking.csv',
    'p3_delay_resources': 'elia/resource_requirements_departure_delay_24h.csv',
    'p3_delay_recommendations': 'elia/scenario_recommendations_departure_delay_24h.json',
    'p3_carryover': 'elia/parking_carryover.csv',
}


def extend_bundle(bundle, raw):
    check(all(isinstance(raw[k], str) and len(raw[k].encode()) <= 2_000_000 for k in EXTENSION_PATHS), 'extensions must be UTF-8 text below 2 MB.')
    delayed = load_standard({**{k: raw[k] for k in NATIVE_PATHS},
                             'p3_resources': raw['p3_delay_resources'],
                             'p3_recommendations': raw['p3_delay_recommendations']})
    meta = json.loads(raw['p3_delay_recommendations'])['meta']
    check(meta.get('variant') == DELAY and meta.get('data_status') == 'provisional', 'unsupported delay metadata.')
    standard_meta = json.loads(raw['p3_recommendations'])['meta']
    expected_provenance = json.loads(raw['p2_report'])['historical_data_classes']
    for m in (meta, standard_meta):
        check(sorted({v for p in m.get('demand_provenance', []) for v in p.split('|')}) == expected_provenance, 'P3 and P2 provenance disagree; regenerate parking outputs.')
    assumptions = {r['id']: r['value'] for r in bundle['assumptions']}
    first = number(assumptions.get('delay_24h_first_day'), 'delay first day')
    share = probability(assumptions.get('delay_24h_share'), 'delayed departure share')
    check(first.is_integer() and first < len(DATES), 'delay first day must be an index in the planning week.')
    bundle['delay_definition'] = {'start_date': DATES[int(first)], 'share': share, 'hours': 24}

    ordinary = rows(raw, 'p3_ordinary', ('date', 'variant', 'arrivals_baseline', 'departures_baseline',
                    'parking_demand_su_p10', 'parking_demand_su_p50', 'parking_demand_su_p90',
                    'capacity_normal_su', 'prob_over_normal_capacity', 'data_status'))
    keyed(ordinary, ('date',), {(d,) for d in DATES}, 'ordinary parking')
    base_by_date = {r['date']: r for r in bundle['baseline']}
    for row in ordinary:
        check(row['variant'] == 'ordinary' and row['data_status'] == 'provisional', 'ordinary parking must be provisional/ordinary.')
        for key in set(row)-{'date', 'variant', 'data_status'}:
            row[key] = number(row[key], key)
        lo, mid, hi = (row['parking_demand_su_'+p] for p in ('p10', 'p50', 'p90'))
        check(lo <= mid <= hi, 'ordinary parking quantiles are unordered.')
        probability(row['prob_over_normal_capacity'], 'ordinary exceedance probability')
        base = base_by_date[row['date']]
        for direction in ('arrivals', 'departures'):
            check(abs(base[direction] - row[direction+'_baseline']) <= .051, 'ordinary arrivals/departures disagree with P2 baseline.')
        base.update(parking_units=mid, parking_p10=lo, parking_p90=hi,
                    capacity_units=row['capacity_normal_su'], data_status='provisional')
    for resource in bundle['resources'] + delayed['resources']:
        check(resource['capacity_units'] == base_by_date[resource['date']]['capacity_units'], 'ordinary/event capacity assumptions disagree.')
    for sc in SCENARIOS:
        check(bundle['impacts'][sc]['runs'] == delayed['impacts'][sc]['runs'], 'simulation run counts differ between variants.')
    for row in delayed['resources'] + delayed['recommendations']:
        row['variant'] = DELAY
    bundle['resources'].extend(delayed['resources'])
    bundle['recommendations'].extend(delayed['recommendations'])
    bundle['variants'].append(DELAY)
    bundle['weekly_costs_by_variant'] = {'standard': bundle['weekly_costs'], DELAY: delayed['weekly_costs']}
    bundle['impacts_by_variant'] = {'standard': bundle['impacts'], DELAY: delayed['impacts']}
    bundle['methods_by_variant'] = {'standard': bundle['method'], DELAY: delayed['method']}

    carry = rows(raw, 'p3_carryover', ('variant', 'scenario', 'opening_aircraft', 'aircraft_remaining_p10',
                 'aircraft_remaining_p50', 'aircraft_remaining_p90', 'parking_su_remaining_p50',
                 'departures_pushed_past_window_p50', 'data_status'))
    expected = {('ordinary', 'ordinary')} | {(v, s.title()) for v in bundle['variants'] for s in SCENARIOS}
    keyed(carry, ('variant', 'scenario'), expected, 'parking carryover')
    opening = number(assumptions.get('initial_transient_aircraft'), 'opening inventory')
    for row in carry:
        check(row['data_status'] == 'provisional', 'carryover must retain provisional status.')
        for key in set(row)-{'variant', 'scenario', 'data_status'}:
            row[key] = number(row[key], key)
        check(row['opening_aircraft'] == opening, 'carryover opening inventory differs from assumptions.')
        check(row['aircraft_remaining_p10'] <= row['aircraft_remaining_p50'] <= row['aircraft_remaining_p90'], 'carryover quantiles are unordered.')
        if row['variant'] != DELAY:
            check(row['departures_pushed_past_window_p50'] == 0, 'only delayed departures may be pushed beyond the window.')
        row['scenario'] = row['scenario'].lower()
    bundle['carryover'] = carry
    bundle['meta']['schema_version'] = 'native-p2-p3-v3'
    bundle['meta']['model_version'] = 'P2 month/weekday shrinkage mean + P3 parking comparisons (native adapter v3)'
    bundle['meta']['notes'] = (
        'Provisional ordinary, standard and delayed parking use P3 daily peak space units and the same opening inventory. '
        'Ordinary parking is simulated from P2 baseline flows; it is not Alan’s aircraft-count estimate. '
        'Carryover is unconstrained parking demand, not confirmed on-site aircraft. '
        'Run the pipeline verifier after every producer refresh; structural validation alone cannot establish a shared run.'
    )
    bundle['limitations'] = [
        'All parking comparisons are provisional model outputs, not observed occupancy or validated safe capacity.',
        'Ordinary parking uses the same P2 baseline and P3 space units as the event simulation.',
        'Delay starts on the declared date and applies to the declared share; it is not automatically a delay of every departure all week.',
        'Carryover assumes unlimited parking; remaining aircraft are demand, not confirmed parking after capacity restrictions.',
        'Reproduce all outputs together with the pipeline verifier after changing forecasts or assumptions.',
    ]
