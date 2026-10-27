"""Send directional and timing assumptions through the existing parking model.

These are counterfactual planning cases. No FBO direction or booking data exists
to assign probabilities to them. Shared release outputs are never rewritten.
"""

import csv
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'parking'))
import parking_optimizer as po  # noqa: E402


SCENARIOS = ('Low', 'Medium', 'High')
TARGETS = ('arrivals', 'departures')


def prediction_components(path=HERE / 'demand_predictions.csv'):
    with path.open(newline='', encoding='utf-8-sig') as handle:
        rows = list(csv.DictReader(handle))
    result = {}
    for row in rows:
        category = po.CATEGORY_ALIASES.get(row['aircraft_category'], row['aircraft_category'])
        for target in TARGETS:
            key = (row['date'], row['scenario'], category, target)
            result[key] = (float(row[f'baseline_{target}']), float(row[f'incremental_{target}']))
    if len(result) != 7 * 3 * 3 * 2:
        raise ValueError('Expected complete seven-day/category/scenario forecast')
    return result


def shifted_increments(components):
    dates = sorted({key[0] for key in components})
    moved = defaultdict(float)
    for (day, scenario, category, target), (_, increment) in components.items():
        destination = date.fromisoformat(day)
        if increment > 0 and target == 'arrivals' and day != dates[0]:
            destination -= timedelta(days=1)
        elif increment > 0 and target == 'departures' and day != dates[-1]:
            destination += timedelta(days=1)
        key = (destination.isoformat(), scenario, category, target)
        if key not in components:
            raise ValueError('Timing shift leaves the seven-day window')
        moved[key] += increment
    return moved


def transform(demand, components, case):
    """Preserve P2 totals for the timing case and daily total operations for split cases."""
    if case not in ('arrivals_40_percent', 'arrivals_60_percent',
                    'early_arrivals_late_departures'):
        raise ValueError(f'Unknown planning case: {case}')
    shifted = shifted_increments(components) if case == 'early_arrivals_late_departures' else None
    result = demand.copy(deep=True)
    result.attrs = demand.attrs.copy()
    for column in ('expected_movements', 'lower90_prediction', 'upper90_prediction',
                   'baseline_radius'):
        if column in result.columns:
            result[column] = result[column].astype(float)
    for index, row in result.iterrows():
        key = (row['date'], row['scenario'], row['aircraft_category'], row['direction'])
        baseline, increment = components[key]
        if shifted is not None:
            expected = baseline + shifted[key]
        else:
            other = 'departures' if row['direction'] == 'arrivals' else 'arrivals'
            other_base = components[key[:3] + (other,)][0]
            arrival_share = .4 if case == 'arrivals_40_percent' else .6
            fraction = arrival_share if row['direction'] == 'arrivals' else 1 - arrival_share
            expected = (baseline + other_base) * fraction + increment
        old = float(row['expected_movements'])
        if old <= 0 or expected <= 0:
            raise ValueError('Cannot scale a zero-valued planning range')
        factor = expected / old
        for column in ('expected_movements', 'lower90_prediction', 'upper90_prediction',
                       'baseline_radius'):
            if column in result.columns:
                result.at[index, column] = float(row[column]) * factor
    if shifted is None:
        fraction = .4 if case == 'arrivals_40_percent' else .6
        result.attrs['baseline_first_day_arrivals'] *= fraction / .5
    return result


def evaluate(demand, assumptions, components, mc_runs=2000):
    output = []
    for case in ('current', 'arrivals_40_percent', 'arrivals_60_percent',
                 'early_arrivals_late_departures'):
        candidate = demand if case == 'current' else transform(demand, components, case)
        a = assumptions.copy()
        a['mc_runs'] = mc_runs
        if case.startswith('arrivals_'):
            a['initial_transient_aircraft'] = round(
                candidate.attrs['baseline_first_day_arrivals'] * a['opening_dwell_days'], 1)
        table, recommendations = po.run(candidate, a, variant='standard')
        for scenario in SCENARIOS:
            summary = recommendations[scenario]['summary']
            days = table[table['scenario'] == scenario]
            output.append(dict(case=case, scenario=scenario,
                               peak_day=summary['peak_day'],
                               peak_parking_su_p50=summary['peak_parking_demand_su_p50'],
                               peak_parking_su_p90=summary['peak_parking_demand_su_p90'],
                               max_prob_over_normal_capacity=round(
                                   float(days['prob_over_normal_capacity'].max()), 3),
                               overall_risk=summary['overall_risk'],
                               opening_aircraft=a['initial_transient_aircraft'],
                               mc_runs=mc_runs, classification='assumption_stress_not_observed'))
    return output


def render_report(rows):
    lines = [
        '# The forecast team directional and event timing stress', '',
        'The 2027 forecast assumes a 50/50 ordinary arrival/departure split. These cases keep the',
        'same airport operations and event extra movements while changing that ordinary split to',
        '40/60 or 60/40. Opening inventory changes with first-day ordinary arrivals. The timing',
        'case moves event extra arrivals one day earlier and extra departures one day later, within',
        'the seven-day window. It preserves the weekly total in each direction and aircraft category.',
        'Each case uses the existing parking model and 2,000 Monte Carlo runs. Its P2 planning ranges',
        'are scaled with the new point forecasts; they are not newly calibrated intervals.', '',
        '| Case | Scenario | Peak day | Peak P50 space units | Peak P90 | Max probability over normal ramp |',
        '| --- | --- | --- | ---: | ---: | ---: |',
    ]
    for row in rows:
        lines.append(f"| {row['case'].replace('_', ' ')} | {row['scenario']} | {row['peak_day']} | "
                     f"{row['peak_parking_su_p50']:.1f} | {row['peak_parking_su_p90']:.1f} | "
                     f"{100 * row['max_prob_over_normal_capacity']:.1f}% |")
    lines += ['', 'These are model stress results for a fictional FBO. FAA airport counts do not',
              'measure this FBO’s arrival/departure split, reservation timing, parking capacity,',
              'or actual overflow probability. The parking team’s action approval rules still apply. Do not',
              'interpret the case names as forecast probabilities.', '']
    return '\n'.join(lines)


def write(path, rows):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def main(output_dir=HERE):
    rows = evaluate(po.load_demand(), po.load_assumptions(), prediction_components())
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write(output_dir / 'operational_stress.csv', rows)
    (output_dir / 'OPERATIONAL_STRESS.md').write_text(
        render_report(rows), encoding='utf-8', newline='\n')
    print(f'Wrote {len(rows)} directional and timing stress results')


if __name__ == '__main__':
    main()
