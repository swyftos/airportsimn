"""Deterministic, unconstrained daily inventory experiments over validated P2 inputs.

This is deliberately separate from P3's Monte Carlo forecast. It reproduces the
early-departure / arrival-peak / late-departure convention, conserving aircraft by
category. No aircraft is accepted, refused, repositioned, or assigned a stand.
"""
import hashlib
import json
import math
from .contracts import ContractError, DATES, SCENARIOS

CATEGORIES = ('light_jet', 'midsize_jet', 'large_jet')
KEYS = {'light_jet': 'light', 'midsize_jet': 'midsize', 'large_jet': 'large'}
HOLIDAY = '2027-02-15'


def finite(value, label, low=0, high=10000):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not low <= value <= high:
        raise ContractError(f'{label} must be a finite number between {low} and {high}.')
    return float(value)


def parameters(bundle):
    if not bundle or not bundle.get('native') or bundle['meta']['airport'] != 'LAX':
        raise ContractError('What-if planning requires the validated LAX P2/P3 team release. Sample and imported contracts do not supply category inventory assumptions.')
    ledger = {a['id']: a for a in bundle['assumptions']}
    needed = ['initial_transient_aircraft', 'dep_share_before_peak'] + [p + k for p in ('mix_', 'su_') for k in KEYS.values()]
    result = {}
    for key in needed:
        try:
            value = float(ledger[key]['value'])
        except (KeyError, ValueError, TypeError) as exc:
            raise ContractError('What-if assumption unavailable: ' + key) from exc
        result[key] = finite(value, key)
    if not 0 <= result['dep_share_before_peak'] <= 1 or abs(sum(result['mix_' + k] for k in KEYS.values()) - 1) > 1e-6:
        raise ContractError('Opening aircraft mix must sum to one and departure share must lie between zero and one.')
    if any(result['su_' + k] <= 0 for k in KEYS.values()):
        raise ContractError('Aircraft footprint weights must be positive.')
    return result, [ledger[k] for k in needed]


def settings(value):
    allowed = {'scenario', 'days', 'holiday_arrival_pct', 'delay_departures', 'extra_capacity_units'}
    if not isinstance(value, dict) or set(value) - allowed:
        raise ContractError('Unsupported what-if settings.')
    scenario = value.get('scenario', 'medium')
    if not isinstance(scenario, str) or scenario not in SCENARIOS:
        raise ContractError('Choose low, medium or high demand.')
    days = value.get('days', {})
    if not isinstance(days, dict) or set(days) - set(DATES):
        raise ContractError('Day overrides must fall within February 11–17, 2027.')
    normalized = {}
    for date, override in days.items():
        if not isinstance(override, dict) or set(override) - {'scenario', 'arrivals', 'departures'}:
            raise ContractError('Each day accepts only scenario, arrivals and departures.')
        selected = override.get('scenario', scenario)
        if not isinstance(selected, str) or selected not in SCENARIOS:
            raise ContractError('Invalid daily demand scenario.')
        normalized[date] = {'scenario': selected}
        for field in ('arrivals', 'departures'):
            if field in override:
                normalized[date][field] = finite(override[field], date + ' ' + field, high=5000)
    delay = value.get('delay_departures', False)
    if not isinstance(delay, bool):
        raise ContractError('Departure delay must be true or false.')
    return {'scenario': scenario, 'days': normalized,
            'holiday_arrival_pct': finite(value.get('holiday_arrival_pct', 0), 'Additional holiday arrival sensitivity', -100, 100),
            'delay_departures': delay,
            'extra_capacity_units': finite(value.get('extra_capacity_units', 0), 'Proposed extra capacity', high=500)}


def simulate(bundle, request):
    p, _ = parameters(bundle)
    lookup = {(r['date'], r['scenario'], r['category'], r['direction']): r['expected'] for r in bundle['category_ranges']}
    sizes = {c: p['su_' + KEYS[c]] for c in CATEGORIES}
    mix = {c: p['mix_' + KEYS[c]] for c in CATEGORIES}
    capacity = {}
    for date in DATES:
        values = {r['capacity_units'] for r in bundle['resources'] if r['date'] == date and r['variant'] == 'standard'}
        if len(values) != 1:
            raise ContractError('Physical parking capacity must agree across demand scenarios.')
        capacity[date] = finite(values.pop(), 'On-site capacity')
    incoming, outgoing = [], []
    for date in DATES:
        override = request['days'].get(date, {})
        scenario = override.get('scenario', request['scenario'])
        vectors = []
        for direction in ('arrivals', 'departures'):
            try:
                counts = {c: finite(lookup[(date, scenario, c, direction)], 'P2 expected ' + direction) for c in CATEGORIES}
            except KeyError as exc:
                raise ContractError('Missing category forecast for what-if planning.') from exc
            if direction in override:
                total = sum(counts.values())
                counts = {c: override[direction] * (counts[c] / total if total else mix[c]) for c in CATEGORIES}
            if direction == 'arrivals' and date == HOLIDAY:
                counts = {c: n * (1 + request['holiday_arrival_pct'] / 100) for c, n in counts.items()}
            vectors.append(counts)
        incoming.append(vectors[0]); outgoing.append(vectors[1])
    pushed = sum(outgoing[-1].values()) if request['delay_departures'] else 0
    if request['delay_departures']:
        outgoing = [{c: 0 for c in CATEGORIES}] + outgoing[:-1]
    inventory = {c: p['initial_transient_aircraft'] * mix[c] for c in CATEGORIES}
    rows = []
    for index, date in enumerate(DATES):
        opening = sum(inventory.values())
        arr, dep = incoming[index], outgoing[index]
        early = {c: min(inventory[c], dep[c] * p['dep_share_before_peak']) for c in CATEGORIES}
        peak = {c: inventory[c] - early[c] + arr[c] for c in CATEGORIES}
        late = {c: min(peak[c], dep[c] - early[c]) for c in CATEGORIES}
        inventory = {c: max(0, peak[c] - late[c]) for c in CATEGORIES}
        # Opening inventory can be larger than the assumed arrival peak.
        opening_by_cat = {c: peak[c] - arr[c] + early[c] for c in CATEGORIES}
        peak_vector = max((opening_by_cat, peak), key=lambda v: sum(v[c] * sizes[c] for c in CATEGORIES))
        units = sum(peak_vector[c] * sizes[c] for c in CATEGORIES)
        total_capacity = capacity[date] + request['extra_capacity_units']
        departures = sum(early.values()) + sum(late.values())
        rows.append({'date': date, 'scenario': request['days'].get(date, {}).get('scenario', request['scenario']),
                     'opening_aircraft': opening, 'arrivals': sum(arr.values()),
                     'planned_departures': sum(dep.values()), 'departures': departures,
                     'unmatched_departures': max(0, sum(dep.values()) - departures),
                     'closing_aircraft': sum(inventory.values()),
                     'peak_aircraft': max(opening, sum(peak.values())),
                     'aircraft_at_space_peak': sum(peak_vector.values()),
                     'category_at_space_peak': peak_vector, 'parking_units': units,
                     'capacity_units': capacity[date], 'proposed_capacity_units': total_capacity,
                     'gap_units': max(0, units - total_capacity), 'headroom_units': total_capacity - units,
                     'arrivals_by_category': arr, 'departures_by_category': {c: early[c] + late[c] for c in CATEGORIES},
                     'closing_by_category': inventory.copy()})
    peak = max(rows, key=lambda r: r['parking_units'])
    summary = {'peak_date': peak['date'], 'peak_units': peak['parking_units'],
               'peak_aircraft': max(r['peak_aircraft'] for r in rows),
               'first_shortage': next((r['date'] for r in rows if r['gap_units'] > 1e-9), None),
               'days_over_capacity': sum(r['gap_units'] > 1e-9 for r in rows),
               'max_gap_units': max(r['gap_units'] for r in rows),
               'opening_aircraft': rows[0]['opening_aircraft'], 'remaining_aircraft': rows[-1]['closing_aircraft'],
               'total_arrivals': sum(r['arrivals'] for r in rows), 'total_departures': sum(r['departures'] for r in rows),
               'unmatched_departures': sum(r['unmatched_departures'] for r in rows),
               'departure_requests_shifted_beyond_window': pushed}
    return {'rows': rows, 'summary': summary}


def plan(bundle, value):
    normalized = settings(value)
    p, evidence = parameters(bundle)
    base = settings({'scenario': normalized['scenario']})
    reference, modified = simulate(bundle, base), simulate(bundle, normalized)
    for row, original in zip(modified['rows'], reference['rows']):
        row['reference_parking_units'] = original['parking_units']
        row['delta_parking_units'] = row['parking_units'] - original['parking_units']
        row['delta_closing_aircraft'] = row['closing_aircraft'] - original['closing_aircraft']
    result = {'source_version': bundle['version'], 'airport': 'LAX', 'fbo': bundle['meta']['fbo_name'],
              'window_start': DATES[0], 'window_end': DATES[-1], 'timezone': 'America/Los_Angeles',
              'source_classification': bundle['meta']['data_classification'],
              'release_review': bundle.get('release_review'),
              'method': 'Deterministic daily inventory sensitivity; P2 point forecasts and P3 opening/mix/footprint assumptions. Unconstrained parking demand, not the P3 Monte Carlo forecast.',
              'settings': normalized, 'reference': reference, **modified,
              'assumptions': evidence, 'departure_share_before_peak': p['dep_share_before_peak'],
              'drop_and_go_ratio': None, 'same_day_ratio': None, 'overnight_ratio': None,
              'holiday_status': 'Not independently estimated. Zero means no additional adjustment to the supplied forecast, not no holiday effect.',
              'limitations': [
                  'Private/business aviation focus: airport air-taxi and general-aviation categories are proxies, not exclusively private jets or observed FBO bookings.',
                  'Daily approximation, not hourly occupancy, safe parking geometry, runway throughput or landing/departure authorization.',
                  'No confidence intervals or exceedance probabilities are calculated for edited plans. Forecast probabilities must not be applied to these results.',
                  'Opening aircraft are already on the ground before the window. Remaining aircraft carry beyond February 17; they do not disappear.',
                  'Departures are limited by aircraft available in each category. Unmatched requests are reported and require input review; they are not flights the app cancels.',
                  'A daily scenario changes both arrival and departure inputs. Changing arrivals alone leaves later departure inputs unchanged; a visit-level dwell model is needed to infer new departure dates.',
                  'Drop-and-go, same-day and overnight ratios cannot be inferred from aggregate arrivals/departures. Linked visit records or documented assumptions are still needed.',
                  'Additional Presidents Day sensitivity affects February 15 arrivals only; prevent double-counting any holiday effect already in event assumptions.',
                  'The 24-hour experiment shifts all seven days of departure requests by one day. It is separate from the forecast tab’s supplied partial-delay variant.',
                  'Physical capacity is unchanged across demand cases. Proposed extra capacity is an unverified planning assumption; no space is reserved.',
              ]}
    result['plan_id'] = hashlib.sha256(json.dumps({'version': bundle['version'], 'settings': normalized, 'method': 'daily-inventory-v1'}, sort_keys=True).encode()).hexdigest()
    return result
