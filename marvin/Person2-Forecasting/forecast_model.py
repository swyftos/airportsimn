"""Person 2: explainable FBO demand forecasting. Python 3.10+, numpy, pandas.
Run without arguments for a reproducible SYNTHETIC demonstration.
See README.md for input contracts, uncertainty limitations, and real-data use.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
from datetime import date
import numpy as np
import pandas as pd

START = pd.Timestamp('2027-02-11')
FEATURES = ['intercept', 'trend_years', 'annual_sin', 'annual_cos'] + [f'weekday_{i}' for i in range(1, 7)] + ['log_lag7', 'log_mean28']
# Assumed incremental demand over normal; not measured LAX event coefficients.
ARRIVAL_LIFT = np.array([1.10, 1.50, 1.70, .85, .25, .10, .05])
DEPARTURE_LIFT = np.array([.15, .20, .30, .85, 2.00, .80, .25])
SCENARIOS = {'Low': .70, 'Medium': 1.00, 'High': 1.40}
EXCLUDED = {2020, 2021, 2022}
CLASSIFICATIONS = {'verified_public', 'estimated_benchmark', 'synthetic'}


def write_csv(frame, path):
    frame.to_csv(path, index=False, float_format='%.4f')


def demo_data(out, rng):
    """Fictional FBO, not reconstructed LAWA or actual Super Bowl observations."""
    rows = []
    for cat, level in [('light', 4.5), ('super_midsize', 5.5), ('large', 3.0)]:
        for d in pd.date_range('2023-01-01', '2025-12-31'):
            seasonal = 1 + .14 * np.sin(2 * np.pi * d.dayofyear / 365.25)
            weekday = [1.04, .94, .98, 1.10, 1.22, .88, .84][d.weekday()]
            mean = level * seasonal * weekday * (1 + .05 * (d.year - 2023))
            rows.append(dict(date=d, aircraft_category=cat,
                             arrivals=int(rng.poisson(mean)), departures=int(rng.poisson(mean * .98)),
                             traffic_scope='fbo', data_classification='synthetic', source='Seeded fictional FBO generator'))
    history = pd.DataFrame(rows)
    bookings = []
    for k, d in enumerate(pd.date_range(START, periods=7)):
        for cat, level in [('light', 4.5), ('super_midsize', 5.5), ('large', 3.0)]:
            bookings.append(dict(date=d, aircraft_category=cat,
                                 reserved_arrivals=int(round(level * (1 + ARRIVAL_LIFT[k]) * .65)),
                                 reserved_departures=int(round(level * (1 + DEPARTURE_LIFT[k]) * .65)),
                                 as_of_date='2026-10-23', data_classification='synthetic'))
    reservations = pd.DataFrame(bookings)
    write_csv(history, out / 'historical_traffic_demo.csv')
    write_csv(reservations, out / 'simulated_reservations.csv')
    return history, reservations


def load_history(path):
    h = pd.read_csv(path)
    required = {'date', 'aircraft_category', 'arrivals', 'departures', 'traffic_scope', 'data_classification', 'source'}
    if not required.issubset(h):
        raise ValueError(f'Historical input missing columns: {sorted(required-set(h))}')
    h['date'] = pd.to_datetime(h.date, errors='raise').dt.normalize()
    h = h[~h.date.dt.year.isin(EXCLUDED)].copy()
    if h.empty or h.date.max() >= START:
        raise ValueError('History must be nonempty and precede February 11, 2027.')
    if not h.data_classification.isin(CLASSIFICATIONS).all():
        raise ValueError('Invalid historical data classification.')
    if not h.traffic_scope.isin(['fbo', 'airport']).all() or h.traffic_scope.nunique() != 1:
        raise ValueError('Use one traffic_scope: fbo or airport. Never mix airport and FBO counts.')
    if h[['aircraft_category', 'source']].isna().any().any():
        raise ValueError('Aircraft category and source must not be missing.')
    if h.duplicated(['date', 'aircraft_category']).any():
        raise ValueError('Duplicate date/category rows: aggregate consistently before training.')
    for c in ['arrivals', 'departures']:
        h[c] = pd.to_numeric(h[c], errors='raise')
        if not np.isfinite(h[c]).all() or (h[c] < 0).any() or (h[c] % 1 != 0).any():
            raise ValueError('Historical outcomes must be finite, nonnegative integer movements.')
    for cat, g in h.groupby('aircraft_category'):
        if len(g) < 210:
            raise ValueError(f'{cat}: need at least 210 daily records for training/calibration/test.')
    return h.sort_values(['aircraft_category', 'date'])


def features(d, values, origin):
    lag = values.get(d - pd.Timedelta(days=7))
    recent = [values[d-pd.Timedelta(days=i)] for i in range(1, 29) if d-pd.Timedelta(days=i) in values]
    if lag is None or len(recent) < 21:
        return None
    phase = 2*np.pi*d.dayofyear/365.25
    return np.array([1., (d-origin).days/365.25, np.sin(phase), np.cos(phase)] +
                    [float(d.weekday()==i) for i in range(1, 7)] + [np.log1p(lag), np.log1p(np.mean(recent))])


def ridge(X, y):
    mu, sd = X.mean(axis=0), X.std(axis=0)
    mu[0], sd[0] = 0., 1.
    sd[sd < 1e-8] = 1.
    Z = (X-mu)/sd
    penalty = np.eye(X.shape[1])*20.
    penalty[0, 0] = 0.
    standardized = np.linalg.solve(Z.T@Z+penalty, Z.T@y)
    beta = standardized/sd
    beta[0] -= np.sum(standardized*mu/sd)
    return beta


def train(g, direction):
    values = dict(zip(g.date, g[direction]))
    origin = g.date.min()
    samples = [(d, features(d, values, origin), float(values[d])) for d in sorted(values)]
    samples = [(d,x,y) for d,x,y in samples if x is not None]
    n = len(samples)
    if n < 180:
        raise ValueError('Insufficient contiguous daily history after exclusions and lag construction.')
    cut, cal_end = int(n*.65), int(n*.82)
    X = np.stack([x for _,x,_ in samples]); y = np.log1p([y for _,_,y in samples])
    beta = ridge(X[:cut], y[:cut])
    # Evaluate disjoint seven-day forecast blocks. No actual values from within a
    # block enter its predictors. Calibration and test periods remain separate.
    def rolling(block_samples):
        rows = []
        dates = [d for d,_,_ in block_samples]
        i = 0
        while i < len(dates):
            first = dates[i]
            known = {d:v for d,v in values.items() if d < first}
            end = first + pd.Timedelta(days=6)
            block = [d for d in dates[i:] if d <= end]
            if len(block) != 7:
                i += max(1,len(block)); continue
            naive = {w:np.mean([v for d,v in known.items() if d.weekday()==w and d>=first-pd.Timedelta(days=56)]) for w in range(7)}
            for horizon,d in enumerate(block,1):
                x = features(d,known,origin)
                if x is None: break
                pred = max(0.,float(np.expm1(np.clip(x@beta,0,15))))
                rows.append(dict(date=d, horizon=horizon, actual=values[d], predicted=pred,
                                 baseline=naive[d.weekday()], log_error=np.log1p(values[d])-np.log1p(pred)))
                known[d]=pred
            i+=len(block)
        return pd.DataFrame(rows)
    calibration, test = rolling(samples[cut:cal_end]), rolling(samples[cal_end:])
    if len(calibration)<14 or len(test)<14:
        raise ValueError('Need at least two complete seven-day calibration and test blocks.')
    # Split-conformal radius for ordinary-week log-count prediction intervals.
    scores=np.abs(calibration.log_error.to_numpy())
    rank=min(len(scores),math.ceil((len(scores)+1)*.90))
    q=float(np.sort(scores)[rank-1])
    test['lower90']=np.maximum(0,np.expm1(np.log1p(test.predicted)-q))
    test['upper90']=np.expm1(np.log1p(test.predicted)+q)
    test['covered90']=(test.actual>=test.lower90)&(test.actual<=test.upper90)
    # Refit on all history after the untouched historical evaluation is recorded.
    fitted=ridge(X,y)
    residuals=y-X@fitted
    return dict(beta=fitted,X=X,y=y,residuals=residuals,values=values,origin=origin,
                q=q,test=test,train_end=samples[cut-1][0],cal_end=samples[cal_end-1][0])


def predict_baseline(model, beta=None):
    beta=model['beta'] if beta is None else beta
    values=model['values'].copy(); result=[]
    # Walk the entire gap recursively; never reuse stale lags as target-day data.
    for d in pd.date_range(max(values)+pd.Timedelta(days=1), START+pd.Timedelta(days=6)):
        x=features(d,values,model['origin'])
        if x is None:
            raise ValueError('History must end with at least 28 sufficiently complete daily records.')
        pred=max(0.,float(np.expm1(np.clip(x@beta,0,15))))
        values[d]=pred
        if d>=START: result.append((pred,x))
    return result


def predict_many(model, betas):
    """Vectorized recursive baseline paths, one row per bootstrap fit."""
    last=max(model['values'])
    days=pd.date_range(last-pd.Timedelta(days=27),last)
    if any(d not in model['values'] for d in days):
        raise ValueError('The final 28 historical days must be complete for recursive forecasting.')
    buffer=np.tile([model['values'][d] for d in days],(len(betas),1)).astype(float)
    results=[]
    for d in pd.date_range(last+pd.Timedelta(days=1),START+pd.Timedelta(days=6)):
        phase=2*np.pi*d.dayofyear/365.25
        fixed=[1.,(d-model['origin']).days/365.25,np.sin(phase),np.cos(phase)]+[float(d.weekday()==i) for i in range(1,7)]
        x=np.column_stack([np.tile(fixed,(len(betas),1)),np.log1p(buffer[:,-7]),np.log1p(buffer.mean(axis=1))])
        pred=np.maximum(0,np.expm1(np.clip(np.sum(x*betas,axis=1),0,15)))
        buffer=np.column_stack([buffer[:,1:],pred])
        if d>=START: results.append(pred)
    return np.array(results).T


def validate_reservations(r, categories, as_of):
    required={'date','aircraft_category','reserved_arrivals','reserved_departures','as_of_date','data_classification'}
    if not required.issubset(r): raise ValueError(f'Reservation columns required: {sorted(required)}')
    r=r.copy();r['date']=pd.to_datetime(r.date).dt.normalize();r['as_of_date']=pd.to_datetime(r.as_of_date).dt.normalize()
    if r.duplicated(['date','aircraft_category']).any(): raise ValueError('Duplicate reservation aggregates.')
    if not r.aircraft_category.isin(categories).all(): raise ValueError('Reservation category missing from history.')
    if (r.as_of_date>as_of).any() or (r.as_of_date>r.date).any(): raise ValueError('Reservation snapshots cannot postdate the forecast issue date or operation date.')
    if not r.data_classification.isin(CLASSIFICATIONS).all(): raise ValueError('Invalid reservation provenance.')
    for col in ['reserved_arrivals','reserved_departures']:
        r[col]=pd.to_numeric(r[col]);
        if not np.isfinite(r[col]).all() or (r[col]<0).any() or (r[col]%1!=0).any(): raise ValueError('Reservation counts must be nonnegative integers.')
    return r


def run(args):
    out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    rng=np.random.default_rng(args.seed)
    as_of=pd.Timestamp(args.as_of).normalize()
    if as_of>=START: raise ValueError('Issue date must precede the planning window.')
    if args.draws<100: raise ValueError('Use at least 100 uncertainty draws.')
    if not 0<=args.booking_show_rate<=1 or args.la_premium<0: raise ValueError('Invalid show rate or LA premium.')
    if args.history:
        h=load_history(args.history)
        r=pd.read_csv(args.reservations) if args.reservations else pd.DataFrame(columns=['date','aircraft_category','reserved_arrivals','reserved_departures','as_of_date','data_classification'])
    else:
        if args.reservations: raise ValueError('Provide --history when supplying external reservations.')
        h,r=demo_data(out,rng)
    if h.date.max()>as_of: raise ValueError('Historical records after issue date would leak future data.')
    scope=h.traffic_scope.iloc[0]
    if scope=='airport' and args.fbo_share is None: raise ValueError('Airport history requires an explicit assumed --fbo-share; movements are not FBO demand.')
    share=1. if scope=='fbo' else args.fbo_share
    if not 0<share<=1: raise ValueError('FBO share must be in (0,1].')
    r=validate_reservations(r,h.aircraft_category.unique(),as_of)
    booking_map={(row.date,row.aircraft_category):row for row in r.itertuples()}
    baseline_map={}
    if args.baseline:
        b=pd.read_csv(args.baseline); required={'date','aircraft_category','arrivals','departures','traffic_scope','data_classification'}
        if not required.issubset(b): raise ValueError('baseline.csv needs date, aircraft_category, arrivals, departures, traffic_scope, data_classification.')
        b['date']=pd.to_datetime(b.date)
        if b.duplicated(['date','aircraft_category']).any() or not (b.traffic_scope=='fbo').all(): raise ValueError('Baseline must have unique daily FBO category rows.')
        if not b.data_classification.isin(CLASSIFICATIONS).all(): raise ValueError('Invalid baseline provenance.')
        for col in ['arrivals','departures']:
            b[col]=pd.to_numeric(b[col]);
            if not np.isfinite(b[col]).all() or (b[col]<0).any(): raise ValueError('Invalid baseline counts.')
        baseline_map={(row.date,row.aircraft_category):row for row in b.itertuples()}
    predictions=[];uncertainty=[];effects=[];eval_rows=[];metric_rows=[];coefficients=[]
    for cat,g in h.groupby('aircraft_category'):
        for direction in ['arrivals','departures']:
            model=train(g,direction)
            baseline=predict_baseline(model)
            # Seven-day moving-block residual bootstrap for model mean uncertainty.
            # Conditional on the specified event assumptions, not a guarantee.
            bootstrap=[]
            for _ in range(args.draws):
                n=len(model['residuals']); sampled=[]
                while len(sampled)<n:
                    pos=int(rng.integers(0,max(1,n-6)));sampled.extend(model['residuals'][pos:pos+7])
                beta=ridge(model['X'],model['X']@model['beta']+np.array(sampled[:n]))
                bootstrap.append(beta)
            boot=predict_many(model,np.array(bootstrap))*share
            test=model['test'].copy();test['aircraft_category']=cat;test['direction']=direction
            test['data_classification']='synthetic' if (g.data_classification=='synthetic').any() else ('verified_public' if (g.data_classification=='verified_public').all() else 'estimated_or_mixed_input')
            eval_rows.extend(test.to_dict('records'))
            mae=float(np.mean(np.abs(test.actual-test.predicted)));naive=float(np.mean(np.abs(test.actual-test.baseline)))
            metric_rows.append(dict(aircraft_category=cat,direction=direction,scope=scope,
                evaluation_data=test.data_classification.iloc[0],n_test=len(test),model_mae=mae,baseline_mae=naive,
                improvement_pct=100*(naive-mae)/naive if naive else None,interval_coverage90=float(test.covered90.mean()),
                train_end=str(model['train_end'].date()),calibration_end=str(model['cal_end'].date()),
                evaluation_note='ordinary weeks; not validation of Super Bowl uplift or FBO capture share'))
            coefficients.extend(dict(aircraft_category=cat,direction=direction,feature=name,log_count_coefficient=float(value)) for name,value in zip(FEATURES,model['beta']))
            lift_profile=ARRIVAL_LIFT if direction=='arrivals' else DEPARTURE_LIFT
            for k,(base,x) in enumerate(baseline):
                d=START+pd.Timedelta(days=k);base*=share
                booking=booking_map.get((d,cat));reserved=float(getattr(booking,'reserved_'+direction,0))
                ordinary=getattr(baseline_map[(d,cat)],direction) if (d,cat) in baseline_map else base
                for scenario,factor in SCENARIOS.items():
                    multiplier=1+lift_profile[k]*(1+args.la_premium)*factor
                    event=base*multiplier
                    expected=max(event,reserved*args.booking_show_rate)
                    # Point forecast floor prevents adding bookings twice to total demand.
                    mean_draw=np.maximum(boot[:,k]*multiplier,reserved*args.booking_show_rate)
                    mean_lo,mean_hi=np.quantile(mean_draw,[.05,.95])
                    # Future count residuals + assumed event uncertainty + booking show uncertainty.
                    # Ordinary-week conformal calibration does not guarantee event-week coverage.
                    eps=rng.choice(model['test'].log_error.to_numpy(),args.draws,replace=True)
                    event_draw=1+lift_profile[k]*(1+args.la_premium)*factor*rng.triangular(.7,1.,1.3,args.draws)
                    residual_base=np.maximum(0,np.expm1(np.log1p(boot[:,k]/share)+eps))*share
                    booked_draw=rng.binomial(int(reserved),args.booking_show_rate,size=args.draws)
                    draws=np.maximum(residual_base*event_draw,booked_draw)
                    lo,hi=np.quantile(draws,[.05,.95]);lo=min(lo,expected);hi=max(hi,expected)
                    key=dict(date=str(d.date()),scenario=scenario,aircraft_category=cat,direction=direction)
                    predictions.append(dict(**key,expected_movements=expected,normal_fbo_baseline=ordinary,
                        learned_normal_forecast=base,event_multiplier=multiplier,reserved_movements=reserved,
                        booking_show_rate=args.booking_show_rate,additional_vs_baseline=expected-ordinary,
                        increase_pct=100*(expected/ordinary-1) if ordinary>0 else None,
                        input_provenance='synthetic_demo' if not args.history else 'user_supplied_history',
                        forecast_status='assumption_based_event_projection',traffic_scope='fictional_fbo'))
                    uncertainty.append(dict(**key,expected_movements=expected,
                        lower90_mean=mean_lo,upper90_mean=mean_hi,lower90_prediction=lo,upper90_prediction=hi,
                        confidence_level=.90,uncertainty_method='moving_block_bootstrap_plus_residual_and_event_simulation',
                        event_coverage_validated=False,history_gap_days=(START-g.date.max()).days-1,
                        limitation='conditional mean CI; event prediction range unvalidated; no protection against structural change'))
                    effects.append(dict(**key,normal_forecast=base,event_addition=event-base,
                        booking_floor_addition=expected-event,expected_movements=expected,
                        explanation='normal + assumed event lift + max(0, expected bookings - event-adjusted normal)'))
    write_csv(pd.DataFrame(predictions),out/'demand_predictions.csv')
    write_csv(pd.DataFrame(uncertainty),out/'uncertainty_results.csv')
    write_csv(pd.DataFrame(effects),out/'prediction_explanations.csv')
    write_csv(pd.DataFrame(coefficients),out/'model_coefficients.csv')
    write_csv(pd.DataFrame(eval_rows),out/'backtest_predictions.csv')
    write_csv(pd.DataFrame(metric_rows),out/'evaluation_metrics.csv')
    p=pd.DataFrame(predictions)
    daily=p.groupby(['date','scenario','direction'],as_index=False)[['expected_movements','normal_fbo_baseline','additional_vs_baseline']].sum()
    daily['increase_pct']=100*(daily.expected_movements/daily.normal_fbo_baseline-1)
    write_csv(daily,out/'daily_summary.csv')
    report=dict(planning_window=['2027-02-11','2027-02-17'],issue_date=str(as_of.date()),seed=args.seed,
        demo=not bool(args.history),history_years=sorted(h.date.dt.year.unique().astype(int).tolist()),
        excluded_years=sorted(EXCLUDED),source_scope=scope,fbo_capture_share=share,
        assumptions=dict(la_incremental_lift_premium=args.la_premium,booking_show_rate=args.booking_show_rate,
            event_arrival_lift=ARRIVAL_LIFT.tolist(),event_departure_lift=DEPARTURE_LIFT.tolist(),scenario_factors=SCENARIOS),
        model='separate category/direction ridge regressions on log1p counts; chronological seven-day backtesting',
        external_baseline_role='comparison reference only; does not override the learned forecast',
        privacy='aggregate aircraft counts only; no passenger identities or aircraft owner data',
        limits=['All demo history and reservations are synthetic.',
          'No verified event-week daily outcomes are supplied; event uplift accuracy is not measurable.',
          'Excluded 2022 is not used for training or validation, including the LA Super Bowl.',
          'Historical test metrics do not validate February 2027 long-gap extrapolation.',
          'Confidence bounds concern conditional model means; prediction ranges also include assumed event uncertainty.',
          'No operational action or individual reservation decision is authorized.'],metrics=metric_rows)
    (out/'model_report.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
    print(f'Created {len(predictions)} category/direction/scenario forecasts in {out.resolve()}')
    print('SYNTHETIC DEMO: historical metrics are simulated performance only.' if not args.history else 'See model_report.json for provenance and validation limits.')


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--history',help='Person 1 daily historical_traffic.csv')
    p.add_argument('--reservations',help='Aggregate reservation snapshots known at issue date')
    p.add_argument('--baseline',help='Optional Person 1 daily FBO baseline for comparison')
    p.add_argument('--output-dir',default=str(Path(__file__).resolve().parent))
    p.add_argument('--as-of',default='2026-10-23')
    p.add_argument('--fbo-share',type=float,default=None)
    p.add_argument('--la-premium',type=float,default=.20,help='Assumed extra event lift versus reference profile; not measured')
    p.add_argument('--booking-show-rate',type=float,default=.90)
    p.add_argument('--draws',type=int,default=200)
    p.add_argument('--seed',type=int,default=42)
    return p

if __name__=='__main__':
    run(parser().parse_args())
