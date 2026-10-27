"""Review provisional forecast sensitivity without changing release inputs.

The shared forecast uses a 10% assumed FBO share and zero observed bookings.
For that specific linear case, scaling the forecast totals is equivalent to
rerunning the demand model at another constant share. This is a planning
sensitivity, not an estimate of an FBO's actual traffic.
"""

import csv
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SHARES = (0.05, 0.10, 0.15)
SCENARIOS = ('Low', 'Medium', 'High')
EVENT_END = '2027-02-15'


def read_csv(path):
    with path.open(newline='', encoding='utf-8-sig') as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def input_share():
    ledger = read_csv(ROOT / 'sources' / 'assumptions.csv')
    return float(next(row['value'] for row in ledger if row['id'] == 'fbo_market_share'))


def forecast_sensitivity(totals, planning, share):
    """Scale the 10% forecast only while every reservation floor is zero."""
    if share <= 0 or share > 1:
        raise ValueError('FBO share must be between 0 and 1')
    if not planning or any(float(row[f'reserved_{target}']) != 0
                           for row in planning for target in ('arrivals', 'departures')):
        raise ValueError('Linear share sensitivity requires zero reservation floors')
    keys = {(row['date'], row['scenario']) for row in totals}
    dates = {row['date'] for row in totals}
    if len(dates) != 7 or len(keys) != 21 or any((day, scenario) not in keys
                                                for day in dates for scenario in SCENARIOS):
        raise ValueError('Expected seven dates and three scenarios in daily totals')
    factor = share / input_share()
    result = []
    for scenario in SCENARIOS:
        rows = [row for row in totals if row['scenario'] == scenario]
        event = [row for row in rows if row['date'] <= EVENT_END]

        def sum_flow(selected, prefix):
            return sum(float(row[f'{prefix}_{target}']) for row in selected
                       for target in ('arrivals', 'departures')) * factor

        baseline = sum_flow(event, 'baseline')
        predicted = sum_flow(event, 'expected')
        result.append(dict(
            assumed_fbo_share=f'{share:.2f}', scenario=scenario,
            event_five_day_baseline_movements=f'{baseline:.2f}',
            event_five_day_expected_movements=f'{predicted:.2f}',
            event_excess_percent=f'{100 * (predicted / baseline - 1):.1f}',
            week_expected_movements=f"{sum_flow(rows, 'expected'):.2f}",
            peak_daily_arrivals=f"{max(float(row['expected_arrivals']) for row in rows) * factor:.2f}",
            peak_daily_departures=f"{max(float(row['expected_departures']) for row in rows) * factor:.2f}",
            data_classification='assumption_scaled_estimate',
        ))
    return result


def analog_check(analogs, evidence):
    low = float(evidence['scenario_excess_scales']['low']['excess'])
    high = float(evidence['scenario_excess_scales']['high']['excess'])
    selected = [row for row in analogs if row['metric'] == 'air_taxi']
    if len(selected) != 3:
        raise ValueError('Expected three newer public air-taxi analogs')
    selected.append(dict(event='LVI_2022_LAX_anchor', airports='LAX', airport_count='1',
                         excess_vs_recent_controls=str(evidence['lax_five_day_control_adjusted_excess'])))
    result = []
    for row in sorted(selected, key=lambda item: item['event']):
        excess = float(row['excess_vs_recent_controls'])
        position = 'below_low' if excess < low else 'above_high' if excess > high else 'within_low_high'
        result.append(dict(event=row['event'], airports=row['airports'],
                           airport_count=row['airport_count'], air_taxi_excess_percent=f'{100 * excess:.1f}',
                           position=position,
                           comparison='LVI anchor uses its own control years' if row['event'].startswith('LVI_')
                           else 'recent non-host-year controls',
                           fbo_transfer_validated='no'))
    return result


def event_stress_cases(totals, evidence, host_excess):
    """Hold the model's daily event shape fixed while varying its five-day uplift."""
    medium = float(evidence['scenario_excess_scales']['medium']['excess'])
    bay = [row for row in host_excess if row['event'] == 'LX' and row['metric'] == 'air_taxi']
    if medium <= 0 or len(bay) != 1:
        raise ValueError('Missing medium or Bay Area air-taxi event evidence')
    bay_excess = float(bay[0]['excess'])
    event = [row for row in totals if row['scenario'] == 'Medium' and row['date'] <= EVENT_END]
    if len(event) != 5:
        raise ValueError('Expected five Medium event dates')
    baseline = sum(float(row[f'baseline_{target}']) for row in event
                   for target in ('arrivals', 'departures'))
    medium_total = sum(float(row[f'expected_{target}']) for row in event
                       for target in ('arrivals', 'departures'))
    cases = (('no_event_uplift', 0.0, 'counterfactual'),
             ('current_medium', medium, 'LVI LAX airport anchor'),
             ('current_high', medium * 2, 'double LVI anchor stress'),
             ('bay_area_LX_air_taxi', bay_excess, 'LX Bay Area airport analog'))
    return [dict(case=name, event_excess_percent=f'{100 * excess:.1f}',
                 five_day_expected_movements=f'{baseline + (medium_total - baseline) * excess / medium:.2f}',
                 assumed_fbo_share=f'{input_share():.2f}',
                 method='same_daily_shape_scaled_from_medium', evidence=source,
                 fbo_transfer_validated='no') for name, excess, source in cases]


def render_report(forecast, analogs, stress, backtest):
    base = [row for row in forecast if row['assumed_fbo_share'] == '0.10']
    model = next(row for row in backtest if row['model'] == 'model' and row['target'] == 'arrivals'
                 and row['window'] == 'all_2025_origins')
    weekday = next(row for row in backtest if row['model'] == 'weekday_mean_8w'
                   and row['target'] == 'arrivals' and row['window'] == 'all_2025_origins')
    newer = [row for row in analogs if not row['event'].startswith('LVI_')]
    inside = sum(row['position'] == 'within_low_high' for row in newer)
    lines = [
        '# The forecast team forecast sensitivity review', '',
        'Generated by `python forecast/main_forecast/sensitivity_review.py` from committed release outputs.',
        'This review does not replace the release forecast or validate demand at a specific FBO.', '',
        '## Assumed FBO share', '',
        'The current 10% share is an assumption. With zero supplied bookings, changing only this constant',
        'scales expected movements. It does **not** change the event uplift percentage or establish which',
        'share is correct. Parking capacity may also depend on the assumed share; the parking team owns that comparison.', '',
        '| Share | Low five-day movements | Medium five-day movements | High five-day movements |',
        '| ---: | ---: | ---: | ---: |',
    ]
    for share in SHARES:
        rows = {row['scenario']: row for row in forecast if row['assumed_fbo_share'] == f'{share:.2f}'}
        lines.append(f"| {share:.0%} | {rows['Low']['event_five_day_expected_movements']} | "
                     f"{rows['Medium']['event_five_day_expected_movements']} | "
                     f"{rows['High']['event_five_day_expected_movements']} |")
    lines += ['', 'At the 10% share, the modelled five-day excess over ordinary demand is ' +
              ', '.join(f"{row['scenario']} {row['event_excess_percent']}%" for row in base) +
              '. Five-day and seven-day totals and peak daily flows are in `sensitivity_forecast_totals.csv`.', '',
              '## Public event analogs', '',
              '| Event | Air-taxi excess | Relative to Low–High |',
              '| --- | ---: | --- |']
    positions = {'below_low': 'below Low', 'within_low_high': 'within Low–High',
                 'above_high': 'above High'}
    for row in analogs:
        lines.append(f"| {row['event'].replace('_', ' ')} | {row['air_taxi_excess_percent']}% | "
                     f"{positions[row['position']]} |")
    lines += ['', f'Only {inside} of {len(newer)} newer analogs falls within the current Low–High band.',
              'The LVI LAX row is the model anchor, so its inclusion is not an independent check.',
              'The analogs differ by market and airport coverage; New Orleans has only two airports in this',
              'extract. Their event excesses cannot be transferred directly to one FBO. See',
              '`calibration_evidence/README.md` for source and coverage details. The signed event',
              'metadata now identifies the source history as LAX GA plus air taxi; transferring its',
              'event response to the fictional FBO remains unvalidated.', '',
              '## Event stress case at the 10% share', '',
              '| Case | Five-day uplift | Estimated FBO movements |',
              '| --- | ---: | ---: |']
    for row in stress:
        lines.append(f"| {row['case'].replace('_', ' ')} | {row['event_excess_percent']}% | "
                     f"{row['five_day_expected_movements']} |")
    lines += ['', 'The Bay Area LX air-taxi case comes from',
              '`sources/airport_traffic/data/processed/superbowl_hosts_excess.csv`. It holds the LVI daily',
              'arrival/departure shape fixed and scales',
              'only its total uplift. It is a stress calculation, not a forecast of LAX or this FBO.', '',
              '## Historical backtest', '',
              f"The rolling 2025 test has {model['n']} daily arrival evaluations. Its airport-pattern WAPE is "
              f"{100 * float(model['wape']):.1f}% versus {100 * float(weekday['wape']):.1f}% for an eight-week "
              f"weekday mean; its nominal 90% rolling range covered {100 * float(model['coverage_90']):.1f}% "
              f"of {model['n_coverage']} evaluated days. Arrival and departure scores are equal because the "
              'input assigns an assumed 50/50 direction split. The scores test airport-level daily patterns',
              'after a constant share conversion. They do not test FBO capture, aircraft mix, event demand,',
              'or parking capacity.', '',
              '## Demo decision', '',
              'Keep Low, Medium, and High as conditional planning scenarios, not calibrated probabilities or',
              'a complete envelope. Show the share and event analog comparisons when presenting the forecast.',
              'Keep release status provisional pending the data team and team review.', '']
    return '\n'.join(lines)


def main(output_dir=HERE):
    if abs(input_share() - 0.10) > 1e-9:
        raise ValueError('This review expects the committed 10% input share; rerun the release first')
    totals = read_csv(HERE / 'daily_totals.csv')
    planning = read_csv(HERE / 'provisional_inputs' / 'planning_inputs.csv')
    evidence = json.loads((HERE / 'provisional_inputs' / 'event_evidence.json').read_text(encoding='utf-8'))
    analogs = read_csv(HERE / 'calibration_evidence' / 'super_bowl_analog_summary.csv')
    host_excess = read_csv(ROOT / 'sources' / 'airport_traffic' / 'data' / 'processed' /
                           'superbowl_hosts_excess.csv')
    backtest = read_csv(HERE / 'backtest_metrics.csv')
    forecast = [row for share in SHARES for row in forecast_sensitivity(totals, planning, share)]
    analog = analog_check(analogs, evidence)
    stress = event_stress_cases(totals, evidence, host_excess)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / 'sensitivity_forecast_totals.csv', forecast)
    write_csv(output_dir / 'analog_scenario_check.csv', analog)
    write_csv(output_dir / 'event_stress_cases.csv', stress)
    (output_dir / 'SENSITIVITY_REVIEW.md').write_text(
        render_report(forecast, analog, stress, backtest), encoding='utf-8', newline='\n')
    print(f'Wrote the forecast team sensitivity review to {output_dir}')


if __name__ == '__main__':
    main()
