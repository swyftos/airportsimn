"""Deterministic, timezone-aware visit rehearsal. No movement permissions or AI math.

Marvin's arrival counts remain a daily source. Intraday times, size and dwell are
explicit synthetic assumptions; this engine does not reproduce P3's simulation.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import random
import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCENARIOS = ('Low', 'Medium', 'High')


@dataclass(frozen=True)
class Visit:
    visit_id: str
    category: str
    arrival: datetime
    departure: datetime
    status: str

    def record(self):
        return {**asdict(self), 'arrival': self.arrival.isoformat(), 'departure': self.departure.isoformat()}


def config():
    value = yaml.safe_load((HERE / 'assumptions.yaml').read_text())
    for name in ('aircraft_mix', 'stay_mix'):
        if not math.isclose(sum(value[name].values()), 1):
            raise ValueError(f'{name} must sum to one.')
    return value


def bounds(cfg):
    start = datetime.fromisoformat(cfg['window_start']).replace(tzinfo=ZoneInfo(cfg['timezone']))
    return start, start + timedelta(days=cfg['window_days'])


def dates(cfg):
    start, _ = bounds(cfg)
    return [(start + timedelta(days=i)).date().isoformat() for i in range(cfg['window_days'])]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def source_snapshot(cfg):
    """Read the actual merged source; never silently substitute demo data."""
    path = ROOT / cfg['marvin_path']
    raw = path.read_bytes()
    rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    keys = [(r['date'], r['scenario']) for r in rows]
    expected = {(day, case) for day in dates(cfg) for case in SCENARIOS}
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError('Marvin source must contain exactly one row per day and demand case.')
    for row in rows:
        for field in ('requested_land', 'ordinary_baseline_arrivals'):
            number = float(row[field])
            if not math.isfinite(number) or number < 0 or number > 5000:
                raise ValueError(f'Invalid {field} in Marvin source.')
    metadata_raw = (ROOT / cfg['marvin_metadata_path']).read_bytes()
    return rows, json.loads(metadata_raw), hashlib.sha256(raw + metadata_raw).hexdigest()


def arrival_counts(cfg, source, scenario, rows=None, overrides=None, holiday_pct=0):
    if scenario not in SCENARIOS:
        raise ValueError('Unknown demand case.')
    if source not in ('demo', 'marvin'):
        raise ValueError('Choose a supported arrival source.')
    if not math.isfinite(float(holiday_pct)) or not -100 <= holiday_pct <= 100:
        raise ValueError('Holiday adjustment must be between -100 and 100 percent.')
    overrides = overrides or {}
    result, ordinary = [], []
    for index, day in enumerate(dates(cfg)):
        selected = overrides.get(day, {}).get('scenario', scenario)
        if selected not in SCENARIOS:
            raise ValueError('Unknown daily demand case.')
        if source == 'marvin':
            row = next(r for r in rows if r['date'] == day and r['scenario'] == selected)
            value = float(row['requested_land'])
            baseline = float(row['ordinary_baseline_arrivals'])
        else:
            total = cfg['demo']['daily_arrivals'][index]
            estimated = round(total * cfg['demo']['estimated_fraction'])
            value = total - estimated + estimated * cfg['demo']['scenario_additional_factor'][selected]
            baseline = cfg['demo']['ordinary_arrivals'][index]
        if day == cfg['holiday']:
            value *= 1 + holiday_pct / 100
        if overrides.get(day, {}).get('arrivals') is not None:
            value = float(overrides[day]['arrivals'])
        if not math.isfinite(value) or not 0 <= value <= 5000:
            raise ValueError(f'{day}: arrivals must be between 0 and 5000.')
        result.append(int(math.floor(value + 0.5)))
        ordinary.append(int(math.floor(baseline + 0.5)))
    return result, ordinary


def generate_visits(cfg, counts, source='demo', ordinary=False):
    """Stable synthetic hourly stays, including opening stock and carryover.

    Arrival counts are rounded once for individual synthetic visits. The same
    per-day prefix persists when a case adds visits; no random rerun drift.
    """
    start, _ = bounds(cfg)
    opening = cfg['demo']['opening_aircraft'] if source == 'demo' else cfg.get('marvin_opening_aircraft', 2)
    visits = []
    sizes, weights = list(cfg['aircraft_mix']), list(cfg['aircraft_mix'].values())
    stays, stay_weights = list(cfg['stay_mix']), list(cfg['stay_mix'].values())
    for i in range(opening):
        rng = random.Random(700 + i)
        visits.append(Visit(f'V-{i+1:04d}', rng.choices(sizes, weights)[0], start - timedelta(hours=18 + i),
                            start + timedelta(hours=8 + 4 * (i % 5)), 'Synthetic opening inventory'))
    for day, count in enumerate(counts):
        for i in range(count):
            rng = random.Random(2027 + day * 10000 + i)
            arrival = start + timedelta(days=day, hours=cfg['arrival_hours'][i % len(cfg['arrival_hours'])])
            category = rng.choices(sizes, weights)[0]
            stay = rng.choices(stays, stay_weights)[0]
            duration = cfg['stay_hours'][stay]
            if source == 'demo' and not ordinary and stay != 'drop_and_go' and day <= 3:
                duration = max(duration, cfg['demo']['event_overnight_min_hours'])
            fixed_booking_count = round(cfg['demo']['daily_arrivals'][day] * (1 - cfg['demo']['estimated_fraction']))
            status = 'Synthetic booking' if source == 'demo' and i < fixed_booking_count else 'Estimated, not yet booked'
            visits.append(Visit(f'V-{1000 + day * 6000 + i:05d}', category, arrival,
                                arrival + timedelta(hours=duration), status))
    return visits


def parse_visits(raw, cfg):
    if len(raw) > 2_000_000:
        raise ValueError('CSV exceeds 2 MB. Upload a smaller visit file.')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    columns = {'visit_id', 'category', 'arrival', 'departure', 'status'}
    if set(reader.fieldnames or []) != columns:
        raise ValueError('Use only these CSV columns: visit_id, category, arrival, departure, status. Download the template below.')
    result, seen = [], set()
    for line, row in enumerate(reader, start=2):
        try:
            if not re.fullmatch(r'V-\d{3,9}', row['visit_id']) or row['visit_id'] in seen:
                raise ValueError('use unique pseudonymous IDs such as V-0412')
            if row['category'] not in cfg['weights']:
                raise ValueError('category must be light, midsize or large')
            if row['status'] not in ('Recorded reservation', 'Estimated, not yet booked'):
                raise ValueError('status must be Recorded reservation or Estimated, not yet booked')
            tz = ZoneInfo(cfg['timezone'])
            arrival, departure = [datetime.fromisoformat(row[k]) for k in ('arrival', 'departure')]
            arrival = arrival.replace(tzinfo=tz) if arrival.tzinfo is None else arrival.astimezone(tz)
            departure = departure.replace(tzinfo=tz) if departure.tzinfo is None else departure.astimezone(tz)
            if departure <= arrival:
                raise ValueError('departure is before or equal to arrival; fix the dates and upload again')
            result.append(Visit(row['visit_id'], row['category'], arrival, departure, row['status']))
            seen.add(row['visit_id'])
            if len(result) > 10000:
                raise ValueError('maximum 10,000 visits')
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f'Row {line}: {exc}.') from exc
    if not result:
        raise ValueError('No bookings loaded. Add visit rows or load the sample dataset.')
    return result


def visits_csv(visits):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=['visit_id', 'category', 'arrival', 'departure', 'status'])
    writer.writeheader()
    writer.writerows(v.record() for v in visits)
    return stream.getvalue()


def simulate(visits, cfg, delay=0, overflow=0, unavailable=0):
    """Exact event sweep within each hour; departure at t frees space at t.

    Every arrival remains in unconstrained demand. Overflow changes capacity,
    never suppresses visits. Protected reserve is never used by the plan.
    """
    main = float(cfg['main_ramp_units'])
    reserve = float(cfg['protected_reserve_units'])
    if not 0 <= reserve < main or not 0 <= unavailable < main - reserve or not 0 <= overflow <= cfg['overflow_limit_units'] or not 0 <= delay <= 6:
        raise ValueError('Capacity, reserve, overflow or delay is outside its allowed range.')
    usable = main - reserve - unavailable
    capacity = usable + overflow
    start, end = bounds(cfg)
    adjusted = [replace(v, departure=v.departure + timedelta(hours=delay)) for v in visits]
    events = {}
    inventory = 0.0
    for v in adjusted:
        units = cfg['weights'][v.category]
        if v.arrival < start < v.departure:
            inventory += units
        for time, delta in ((v.arrival, units), (v.departure, -units)):
            if start <= time < end and not (delta < 0 and time == start):
                events[time] = events.get(time, 0) + delta
    for i in range(cfg['window_days'] * 24 + 1):
        events.setdefault(start + timedelta(hours=i), 0)
    times = sorted(events)
    hourly = [{'time': start + timedelta(hours=i), 'units': 0.0, 'shortage_unit_hours': 0.0,
               'shortage_hours': 0.0} for i in range(cfg['window_days'] * 24)]
    first, peak, peak_time = None, 0, start
    for t, nxt in zip(times, times[1:]):
        inventory += events[t]
        if inventory < -1e-8:
            raise ValueError('Inventory became negative. Check visit intervals.')
        index = int((t - start).total_seconds() // 3600)
        duration = (nxt - t).total_seconds() / 3600
        gap = max(0, inventory - capacity)
        row = hourly[index]
        row['units'] = max(row['units'], inventory)
        row['shortage_unit_hours'] += gap * duration
        row['shortage_hours'] += duration if gap > 1e-8 else 0
        if inventory > peak:
            peak, peak_time = inventory, t
        if gap > 1e-8 and first is None:
            first = t
    daily = []
    for day in range(cfg['window_days']):
        a, b = start + timedelta(days=day), start + timedelta(days=day+1)
        rows = hourly[day*24:(day+1)*24]
        daily.append({'date': a.date().isoformat(), 'arrivals': sum(a <= v.arrival < b for v in adjusted),
                      'departures': sum(a <= v.departure < b for v in adjusted),
                      'closing_aircraft': sum(v.arrival < b < v.departure for v in adjusted),
                      'peak_units': max(r['units'] for r in rows),
                      'peak_gap': max(0, max(r['units'] for r in rows) - capacity)})
    return {'hourly': hourly, 'daily': daily, 'first_shortage': first, 'peak_units': peak,
            'peak_time': peak_time, 'peak_gap': max(0, peak - capacity), 'capacity': capacity,
            'usable_main': usable, 'shortage_hours': sum(r['shortage_hours'] for r in hourly),
            'shortage_unit_hours': sum(r['shortage_unit_hours'] for r in hourly),
            'closing_aircraft': sum(v.arrival < end < v.departure for v in adjusted),
            'opening_aircraft': sum(v.arrival < start < v.departure for v in adjusted),
            'visits': adjusted}


def preparation(before, after, cfg, overflow):
    """Only allowed, human-owned proposals. Uses calculated numbers verbatim."""
    start, _ = bounds(cfg)
    first = before['first_shortage']
    deadline = ((first - timedelta(hours=24)) if first else start - timedelta(days=1)).isoformat()
    actions = [dict(id='verify-visits', action='Verify arrival and departure estimates', owner='Reservations coordinator',
                    deadline=deadline, reason='Confirm stays that overlap the peak; contact the appropriate operator through normal procedures.'),
               dict(id='verify-ramp', action='Check usable space and aircraft suitability', owner='Operations supervisor',
                    deadline=deadline, reason=f'Validate {before["usable_main"]:g} usable units. Keep {cfg["protected_reserve_units"]:g} reserve units protected.')]
    if before['peak_gap'] > 0:
        actions.append(dict(id='check-overflow', action=f'Investigate {overflow:g} units of overflow' if overflow else 'Investigate overflow options',
                            owner='Manager', deadline=deadline,
                            reason=f'Peak shortfall is {before["peak_gap"]:g} units. Verify availability, dates, access, suitability and price before any arrangement.'))
    if after['peak_gap'] > 0:
        actions.append(dict(id='residual-gap', action='Escalate the remaining parking gap', owner='Manager', deadline=deadline,
                            reason=f'{after["peak_gap"]:g} units remain uncovered. Discuss partner options and voluntary timing changes; no movement is authorized.'))
    return actions
