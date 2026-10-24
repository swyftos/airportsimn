"""Explainable FBO forecasting. Python 3.10+; standard library only."""
import argparse, csv, json, math, random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

TARGETS = ('arrivals', 'departures')
SCENARIOS = ('Low', 'Medium', 'High')
EXCLUDED = {2020, 2021, 2022}

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
        if d.year in EXCLUDED:
            continue
        if not 2016 <= d.year <= 2025:
            raise ValueError('History must be within 2016-2025')
        key = (d, r['aircraft_category'])
        if key in seen or not r['aircraft_category'].strip():
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
    def predict(self, d):
        w = self.weekday[d.weekday()]
        parent = sum(w) / len(w) if w else self.mean
        v = self.seasonal[d.month, d.weekday()]
        return (sum(v) + 14 * parent) / (len(v) + 14)

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
    for c in sorted({r['aircraft_category'] for r in history}):
        rows = [r for r in history if r['aircraft_category'] == c]
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
            fitted[c,t] = model, radius, provenance
            mae = sum(abs(r[t]-model.predict(r['date'])) for r in test)/len(test)
            base_mae = sum(abs(r[t]-model.mean) for r in test)/len(test)
            covered = sum(max(0,model.predict(r['date'])-radius) <= r[t] <= model.predict(r['date'])+radius for r in test)/len(test)
            metrics.append(dict(aircraft_category=c, target=t, data_class=provenance,
                evaluation_type='historical_observed' if provenance == 'observed' else 'non_observed_demonstration',
                train_rows=len(train), calibration_rows=len(cal), test_rows=len(test),
                train_end=str(train[-1]['date']), calibration_start=str(cut1), test_start=str(cut2),
                model_mae=round(mae,4), historical_mean_mae=round(base_mae,4),
                improvement_percent=round(100*(base_mae-mae)/base_mae,2) if base_mae else '',
                nominal_coverage=coverage, test_coverage=round(covered,4), baseline_radius=round(radius,4)))
    return fitted, metrics

def forecast(history, planning, coverage=.9):
    if not .5 <= coverage < 1:
        raise ValueError('coverage must be in [0.5,1)')
    fitted, metrics = fit_and_evaluate(history, coverage)
    predictions, uncertainty, seen = [], [], set()
    categories = {k[0] for k in fitted}
    dates = {date(2027,2,11)+timedelta(days=i) for i in range(7)}
    for r in planning:
        d, c = date.fromisoformat(r['date']), r['aircraft_category']
        if (d,c) in seen or d not in dates or c not in categories:
            raise ValueError('Duplicate or unsupported planning date/category')
        seen.add((d,c))
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
                model, radius, provenance = fitted[c,t]
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
                uncertainty.append(dict(date=str(d), scenario=s, aircraft_category=c, target=t,
                    expected=round(pred,3), lower=lower, upper=upper, nominal_baseline_coverage=coverage,
                    baseline_radius=round(radius,4), interval_type='assumption_scaled_planning_range',
                    event_coverage_validated=False, historical_data_class=provenance))
            predictions.append(out)
    if seen != {(d,c) for d in dates for c in categories}:
        raise ValueError('Planning requires every date/category combination exactly once')
    return predictions, uncertainty, metrics

def make_demo(folder):
    rng = random.Random(42)
    history, planning = [], []
    categories = {'light_jet':7, 'midsize_jet':5, 'large_jet':3}
    d = date(2016,1,1)
    while d <= date(2025,12,31):
        if d.year not in EXCLUDED:
            for c, mean in categories.items():
                season = 1 + .15*math.cos(2*math.pi*(d.month-2)/12)
                weekday = 1.2 if d.weekday() in (0,4,6) else .85
                r = dict(date=str(d), aircraft_category=c, scope='fbo', data_class='synthetic', source='seed_42_demo_not_real_LAX_data')
                for t in TARGETS:
                    r[t] = max(0,round(rng.gauss(mean*season*weekday,math.sqrt(mean))))
                history.append(r)
        d += timedelta(days=1)
    ap, dp = [1.25,1.6,2.2,1.8,1.1,1,1], [1,1,1.1,1.3,2.5,1.8,1.2]
    for i in range(7):
        for c, mean in categories.items():
            r = dict(date=str(date(2027,2,11)+timedelta(days=i)), aircraft_category=c, event_indicator=1,
                reserved_arrivals=round(mean*ap[i]*.8), reserved_departures=round(mean*dp[i]*.8),
                reservation_show_rate=.9, reservation_class='synthetic', assumption_source='illustrative_not_empirical_event_uplift')
            for t, profile in [('arrivals',ap),('departures',dp)]:
                for s, scale in [('low',.5),('medium',1),('high',1.6)]:
                    r[f'{t}_multiplier_{s}'] = round(1+(profile[i]-1)*scale,3)
            planning.append(r)
    write_csv(folder/'demo_historical_traffic.csv',history)
    write_csv(folder/'demo_planning_inputs.csv',planning)
    return folder/'demo_historical_traffic.csv', folder/'demo_planning_inputs.csv'

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--demo', action='store_true')
    p.add_argument('--history',type=Path)
    p.add_argument('--planning',type=Path)
    p.add_argument('--output-dir',type=Path,default=Path('.'))
    p.add_argument('--coverage',type=float,default=.9)
    args = p.parse_args()
    if args.demo and (args.history or args.planning):
        p.error('Do not combine --demo with supplied inputs')
    if not args.demo and not (args.history and args.planning):
        p.error('Provide --history and --planning, or explicitly choose --demo')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    if args.demo:
        args.history,args.planning = make_demo(args.output_dir)
    history = load_history(args.history)
    forecasts,intervals,metrics = forecast(history,read_csv(args.planning),args.coverage)
    for name, rows in [('demand_predictions.csv',forecasts),('uncertainty_results.csv',intervals),('evaluation_metrics.csv',metrics)]:
        write_csv(args.output_dir/name,rows)
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
        seed=42 if args.demo else None,history_file=str(args.history),planning_file=str(args.planning),
        historical_data_classes=sorted({r['data_class'] for r in history}),nominal_baseline_coverage=args.coverage,
        uncertainty='Baseline split-conformal intervals scaled by assumed multipliers; event coverage not validated',
        caution='Estimated or synthetic inputs do not establish observed FBO accuracy. Human review required.')
    (args.output_dir/'run_metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print(f'Wrote {len(forecasts)} scenario/category forecasts to {args.output_dir}')

if __name__ == '__main__':
    main()
