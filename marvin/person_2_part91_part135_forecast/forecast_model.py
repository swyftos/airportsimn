"""Explainable FBO forecasting from observed FAA daily counts, Part 91 and Part 135. Python 3.10+; standard library only."""
import argparse, csv, json, math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

TARGETS = ('arrivals', 'departures')
SCENARIOS = ('Low', 'Medium', 'High')
EXCLUDED = {2020, 2021, 2022}
ROOT = Path(__file__).resolve().parents[2]
FAA_DAILY = ROOT/'alan/elia_output/data/processed/opsnet_lax_daily.csv'
SURGE = ROOT/'alan/elia_output/data/processed/superbowl_lvi_surge.csv'
SURGE_PROFILE = ROOT/'alan/elia_output/data/processed/superbowl_lvi_daily_profile.csv'
# Observed FAA tower categories: general aviation for Part 91, air taxi for Part 135. Air taxi also holds
# cargo feeders and small commuter flights, GA holds training and positioning, hence the eligibility filter.
PART_COLUMNS = {'part91': 'general_aviation', 'part135': 'air_taxi'}
PRIVATE_ELIGIBLE = {'part91': 0.50, 'part135': 0.50}  # Placeholders, not measured; Part 91 value is Alan's.
FBO_CAPTURE_SHARE = 0.20  # Team assumption; 0.50 x 0.20 = fbo_market_share 0.10 in alan/assumptions.csv.
ARRIVAL_SHARE = 0.5
# Five-day operations excess around Super Bowl LVI, control-adjusted (FAA): Low = LAX GA, Medium = LAX air
# taxi, High = twice Medium. Same scenarios as the main forecast (marvin/person_2_forecasting).
EVENT_EXCESS = {'low': ('general_aviation', 1), 'medium': ('air_taxi', 1), 'high': ('air_taxi', 2)}
AIRCRAFT_MIX = {'light_jet': 0.47, 'midsize_jet': 0.33, 'large_jet': 0.20}

def presidents_day(year):
    d = date(year, 2, 15)  # third Monday of February
    return d + timedelta(days=-d.weekday() % 7)

HOLIDAYS = {'presidents_day': presidents_day}


def read_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def write_csv(path, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def number(row, key):
    v = float(row[key])
    if not math.isfinite(v) or v < 0:
        raise ValueError(f'{key} must be finite and nonnegative')
    return v

def load_history(path):
    rows, seen = [], set()
    for r in read_csv(path):
        d = date.fromisoformat(r['date'])
        if d.year in EXCLUDED or d.year < 2023:
            continue
        if not 2016 <= d.year <= 2025:
            raise ValueError('History must be within 2016-2025')
        part = r.get('operation_part')
        if part not in PART_COLUMNS:
            raise ValueError('History must identify part91 or part135; part121 is excluded')
        key = (d, r['aircraft_category'], part)
        if key in seen or r['aircraft_category'] not in AIRCRAFT_MIX:
            raise ValueError(f'Duplicate or invalid key: {key}')
        seen.add(key)
        if r['scope'] != 'fbo':
            raise ValueError('Convert airport-wide data to documented FBO estimates first')
        if r['data_class'] not in ('observed', 'estimated', 'synthetic') or not r['source'].strip():
            raise ValueError('History needs valid data_class and source')
        r = dict(r, date=d)
        for t in TARGETS:
            r[t] = number(r, t)
        rows.append(r)
    if not rows:
        raise ValueError('No usable history')
    return sorted(rows, key=lambda r: r['date'])

class SeasonalModel:
    """Month/weekday mean shrunk toward weekday mean using 14 prior days."""
    def __init__(self, rows, target):
        self.mean = sum(r[target] for r in rows) / len(rows)
        self.weekday, self.seasonal = defaultdict(list), defaultdict(list)
        for r in rows:
            d = r['date']
            self.weekday[d.weekday()].append(r[target])
            self.seasonal[d.month, d.weekday()].append(r[target])
        # Holiday effect learned from training days: observed / ordinary prediction.
        self.holiday = {}
        for name, rule in HOLIDAYS.items():
            ratios = [r[target] / self.ordinary(r['date']) for r in rows
                      if r['date'] == rule(r['date'].year) and self.ordinary(r['date']) > 0]
            self.holiday[name] = sum(ratios) / len(ratios) if ratios else 1.0
    def ordinary(self, d):
        w = self.weekday[d.weekday()]
        parent = sum(w) / len(w) if w else self.mean
        v = self.seasonal[d.month, d.weekday()]
        return (sum(v) + 14 * parent) / (len(v) + 14)
    def predict(self, d):
        factor = next((self.holiday[n] for n, rule in HOLIDAYS.items() if d == rule(d.year)), 1.0)
        return self.ordinary(d) * factor

def conformal_radius(residuals, coverage):
    rank = math.ceil((len(residuals) + 1) * coverage)
    if rank > len(residuals):
        raise ValueError('Insufficient calibration days for requested coverage')
    return sorted(residuals)[rank - 1]

def fit_and_evaluate(history, coverage):
    fitted, metrics = {}, []
    dates = sorted({r['date'] for r in history})
    if len(dates) < 180:
        raise ValueError('At least 180 historical dates required')
    cut1, cut2 = dates[int(len(dates)*.6)], dates[int(len(dates)*.8)]
    for c, part in sorted({(r['aircraft_category'], r['operation_part']) for r in history}):
        rows = [r for r in history if r['aircraft_category'] == c and r['operation_part'] == part]
        train = [r for r in rows if r['date'] < cut1]
        cal = [r for r in rows if cut1 <= r['date'] < cut2]
        test = [r for r in rows if r['date'] >= cut2]
        if min(map(len, (train, cal, test))) < 30:
            raise ValueError(f'Insufficient split data for {c}')
        provenance = '|'.join(sorted({r['data_class'] for r in rows}))
        for t in TARGETS:
            model = SeasonalModel(train, t)
            radius = conformal_radius([abs(r[t]-model.predict(r['date'])) for r in cal], coverage)
            # Freeze the calibrated model: refitting changes residuals.
            fitted[c,part,t] = model, radius, provenance
            mae = sum(abs(r[t]-model.predict(r['date'])) for r in test)/len(test)
            base_mae = sum(abs(r[t]-model.mean) for r in test)/len(test)
            covered = sum(max(0,model.predict(r['date'])-radius) <= r[t] <= model.predict(r['date'])+radius for r in test)/len(test)
            metrics.append(dict(aircraft_category=c, target=t, data_class=provenance,
                evaluation_type='historical_observed' if provenance == 'observed' else 'non_observed_demonstration',
                train_rows=len(train), calibration_rows=len(cal), test_rows=len(test),
                train_end=str(train[-1]['date']), calibration_start=str(cut1), test_start=str(cut2),
                model_mae=round(mae,4), historical_mean_mae=round(base_mae,4),
                improvement_percent=round(100*(base_mae-mae)/base_mae,2) if base_mae else '',
                nominal_coverage=coverage, test_coverage=round(covered,4), baseline_radius=round(radius,4),
                operation_part=part))
    return fitted, metrics

def forecast_parts(history, planning, coverage=.9):
    if not .5 <= coverage < 1:
        raise ValueError('coverage must be in [0.5,1)')
    fitted, metrics = fit_and_evaluate(history, coverage)
    part_predictions, predictions, uncertainty, seen = [], [], [], set()
    categories = {k[0] for k in fitted}
    parts = set(PART_COLUMNS)
    dates = {date(2027,2,11)+timedelta(days=i) for i in range(7)}
    for r in planning:
        d, c, part = date.fromisoformat(r['date']), r['aircraft_category'], r.get('operation_part')
        if part not in parts or (d,c,part) in seen or d not in dates or c not in categories:
            raise ValueError('Duplicate or unsupported planning date/category/Part')
        seen.add((d,c,part))
        if r['reservation_class'] not in ('synthetic','estimated','observed') or not r['assumption_source'].strip():
            raise ValueError('Planning inputs need provenance and assumption_source')
        for t in TARGETS:
            ms = [number(r,f'{t}_multiplier_{s.lower()}') for s in SCENARIOS]
            if ms != sorted(ms) or min(ms) < 1:
                raise ValueError('Multipliers must satisfy 1 <= Low <= Medium <= High')
        event, show = number(r,'event_indicator'), number(r,'reservation_show_rate')
        if event not in (0,1) or show > 1:
            raise ValueError('event_indicator must be binary; show rate must be <= 1')
        for s in SCENARIOS:
            out = dict(date=str(d), scenario=s, aircraft_category=c, forecast_scope='fictional_fbo',
                       event_indicator=int(event), reservation_class=r['reservation_class'], assumption_source=r['assumption_source'])
            for t in TARGETS:
                model, radius, provenance = fitted[c,part,t]
                base = model.predict(d)
                mult = 1 + event*(number(r,f'{t}_multiplier_{s.lower()}')-1)
                floor = number(r,f'reserved_{t}')*show
                pred = max(base*mult, floor)
                # Reservations overlap total demand; never add them twice.
                # They don't narrow uncertainty: cancellation uncertainty remains.
                lower = math.floor(max(0,base-radius)*mult)
                upper = math.ceil(max((base+radius)*mult,pred+radius*mult))
                out.update({f'baseline_{t}':round(base,3), f'expected_{t}':round(pred,3),
                    f'incremental_{t}':round(pred-base,3), f'{t}_multiplier':mult,
                    f'{t}_reservation_floor':round(floor,3), f'{t}_reservation_adjustment':round(pred-base*mult,3),
                    f'{t}_lower':lower, f'{t}_upper':upper, 'historical_data_class':provenance})
            part_predictions.append(dict(out, operation_part=part))
    if seen != {(d,c,part) for d in dates for c in categories for part in parts}:
        raise ValueError('Planning requires every date/category/Part combination exactly once')
    by_key = defaultdict(list)
    for row in part_predictions:
        by_key[row['date'],row['scenario'],row['aircraft_category']].append(row)
    for (day, scenario, category), rows in sorted(by_key.items()):
        out = dict(date=day, scenario=scenario, aircraft_category=category,
                   forecast_scope='fictional_fbo', event_indicator=rows[0]['event_indicator'],
                   reservation_class='|'.join(sorted({r['reservation_class'] for r in rows})),
                   assumption_source='|'.join(sorted({r['assumption_source'] for r in rows})))
        for t in TARGETS:
            for key in (f'baseline_{t}', f'expected_{t}', f'incremental_{t}'):
                out[key] = round(sum(r[key] for r in rows),3)
            baseline = out[f'baseline_{t}']
            out[f'{t}_multiplier'] = round(sum(r[f'baseline_{t}']*r[f'{t}_multiplier'] for r in rows)/baseline,6) if baseline else 1
            for key in (f'{t}_reservation_floor', f'{t}_reservation_adjustment'):
                out[key] = round(sum(r[key] for r in rows),3)
            out[f'{t}_lower'] = sum(r[f'{t}_lower'] for r in rows)
            out[f'{t}_upper'] = sum(r[f'{t}_upper'] for r in rows)
            provenance = '|'.join(sorted({r['historical_data_class'] for r in rows}))
            out['historical_data_class'] = provenance
            uncertainty.append(dict(date=day, scenario=scenario, aircraft_category=category, target=t,
                expected=out[f'expected_{t}'], lower=out[f'{t}_lower'], upper=out[f'{t}_upper'],
                nominal_baseline_coverage=coverage,
                baseline_radius=round(sum(fitted[category,p,t][1] for p in parts),4),
                interval_type='sum_of_part_assumption_scaled_ranges',
                event_coverage_validated=False, historical_data_class=provenance))
        predictions.append(out)
    return predictions, uncertainty, metrics, part_predictions

def forecast(history, planning, coverage=.9):
    predictions, uncertainty, metrics, _ = forecast_parts(history, planning, coverage)
    return predictions, uncertainty, metrics

def build_faa_inputs(folder):
    """History from observed FAA daily counts x assumed shares; planning multipliers from measured LVI excess."""
    history = []
    for day in read_csv(FAA_DAILY):
        if not 2023 <= int(day['date'][:4]) <= 2025:
            continue
        for part, column in PART_COLUMNS.items():
            fbo = float(day[column]) * PRIVATE_ELIGIBLE[part] * FBO_CAPTURE_SHARE
            for c, mix in AIRCRAFT_MIX.items():
                r = dict(date=day['date'], aircraft_category=c, operation_part=part, scope='fbo', data_class='estimated',
                         source=f"{day['source']};metric={column};x{PRIVATE_ELIGIBLE[part]}_eligible_x{FBO_CAPTURE_SHARE}_capture_x{mix}_mix")
                for t in TARGETS:
                    r[t] = round(fbo * (ARRIVAL_SHARE if t == 'arrivals' else 1-ARRIVAL_SHARE) * mix, 6)
                history.append(r)
    write_csv(folder/'historical_traffic.csv', history)
    fitted, _ = fit_and_evaluate(load_history(folder/'historical_traffic.csv'), .9)
    days = [date(2027,2,11)+timedelta(days=i) for i in range(7)]
    base = {t: [sum(fitted[k][0].predict(d) for k in fitted if k[2] == t) for d in days] for t in TARGETS}
    lax = {r['metric']: float(r['excess_2022']) for r in read_csv(SURGE) if r['locid'] == 'LAX'}
    excess = {s: lax[metric]*k for s, (metric, k) in EVENT_EXCESS.items()}
    profile = {int(r['offset']): r for r in read_csv(SURGE_PROFILE)}
    # Regional air-taxi daily shape Thu-Mon, scaled so five-day movements rise by the scenario excess.
    # Aircraft conservation: extra arrivals Thu-Sat and half of game day, the same extra departures after.
    shape = [max(0, float(profile[i-3]['air_taxi'])/float(profile[i-3]['baseline'])-1) for i in range(5)]
    total = [base['arrivals'][i]+base['departures'][i] for i in range(5)]
    extra = [total[i]*shape[i]*sum(total)/sum(t*w for t, w in zip(total, shape)) for i in range(5)]
    timing = {'arrivals': {0: extra[0], 1: extra[1], 2: extra[2], 3: extra[3]/2},
              'departures': {3: extra[3]/2, 4: extra[4]}}
    unit = {t: [timing[t].get(i, 0)/sum(timing[t].values())*sum(extra)/2/base[t][i] for i in range(7)]
            for t in TARGETS}  # multiplier - 1 per unit of excess
    planning = []
    for i, d in enumerate(days):
        for part in PART_COLUMNS:
            for c in AIRCRAFT_MIX:
                r = dict(date=str(d), aircraft_category=c, operation_part=part, event_indicator=int(i < 5),
                         reserved_arrivals=0, reserved_departures=0, reservation_show_rate=0,
                         reservation_class='synthetic',
                         assumption_source='FAA ATADS/OPSNET Super Bowl LVI excess (Low LAX GA, Medium LAX air taxi, High 2x); no bookings supplied')
                for t in TARGETS:
                    for s, e in excess.items():
                        r[f'{t}_multiplier_{s}'] = round(1 + e*unit[t][i], 6)
                planning.append(r)
    write_csv(folder/'planning_inputs.csv', planning)
    return folder/'historical_traffic.csv', folder/'planning_inputs.csv'

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--faa', action='store_true', help='Build history and planning inputs from the FAA files')
    p.add_argument('--history',type=Path)
    p.add_argument('--planning',type=Path)
    p.add_argument('--output-dir',type=Path,default=Path('.'))
    p.add_argument('--coverage',type=float,default=.9)
    args = p.parse_args()
    if args.faa and (args.history or args.planning):
        p.error('Do not combine --faa with supplied inputs')
    if not args.faa and not (args.history and args.planning):
        p.error('Provide --history and --planning, or choose --faa')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    if args.faa:
        args.history,args.planning = build_faa_inputs(args.output_dir)
    history = load_history(args.history)
    forecasts,intervals,metrics,part_forecasts = forecast_parts(history,read_csv(args.planning),args.coverage)
    for name, rows in [('demand_predictions.csv',forecasts),('uncertainty_results.csv',intervals),('evaluation_metrics.csv',metrics)]:
        write_csv(args.output_dir/name,rows)
    write_csv(args.output_dir/'part_demand_predictions.csv', part_forecasts)
    totals = []
    for d in sorted({r['date'] for r in forecasts}):
        for s in SCENARIOS:
            subset = [r for r in forecasts if r['date']==d and r['scenario']==s]
            r = dict(date=d,scenario=s)
            for t in TARGETS:
                for prefix in ('baseline_','expected_','incremental_'):
                    r[prefix+t] = round(sum(v[prefix+t] for v in subset),3)
            totals.append(r)
    write_csv(args.output_dir/'daily_totals.csv',totals)
    metadata = dict(model='month_weekday_shrinkage_mean',prior_days=14,excluded_years=sorted(EXCLUDED),
        seed=None,history_file=args.history.name,planning_file=args.planning.name,
        historical_data_classes=sorted({r['data_class'] for r in history}),nominal_baseline_coverage=args.coverage,
        uncertainty='Baseline split-conformal intervals scaled by assumed multipliers; event coverage not validated',
        caution='History: observed FAA daily LAX counts 2023-2025 (GA for Part 91, air taxi for Part 135) x placeholder 50% eligibility x 20% capture. Not observed FBO counts. Holdout metrics measure the daily airport pattern. Event scenarios from FAA LVI excess; event ranges unvalidated. No bookings supplied.')
    (args.output_dir/'run_metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print(f'Wrote {len(forecasts)} scenario/category forecasts from FAA history to {args.output_dir}')

if __name__ == '__main__':
    main()
