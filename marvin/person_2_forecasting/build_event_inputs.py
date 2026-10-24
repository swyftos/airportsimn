"""FAA ATADS/OPSNET anchored scenarios, with explicit unvalidated FBO transfer."""
from datetime import date, timedelta
from pathlib import Path
from forecast_model import load_history, fit_and_evaluate, read_csv

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[1]/'alan/elia_output/data/processed'
EVENT_EXCESS_SCALES = {'low': 0.0, 'medium': 1.0, 'high': 2.0}

def build(history_path):
    surge = read_csv(DATA/'superbowl_lvi_surge.csv')
    lax = next(r for r in surge if r['metric']=='air_taxi' and r['locid']=='LAX')
    regional = next(r for r in surge if r['metric']=='air_taxi' and r['locid']=='ALL6')
    profile = {int(r['offset']): r for r in read_csv(DATA/'superbowl_lvi_daily_profile.csv')}
    excess = float(lax['excess_2022'])
    assert 0 < excess < 1
    fitted, _ = fit_and_evaluate(load_history(history_path), .9)
    days = [date(2027,2,11)+timedelta(days=i) for i in range(7)]
    categories = sorted({key[0] for key in fitted})
    baseline = {i: sum(fitted[c,t][0].predict(d) for c in categories
                       for t in ('arrivals','departures')) for i,d in enumerate(days)}
    # Regional raw excess supplies timing only. Normalize to LAX's control-adjusted
    # five-day excess using the forecast's baseline weights, not unweighted daily ratios.
    shape = {i: max(0, float(profile[i-3]['air_taxi'])/float(profile[i-3]['baseline'])-1)
             for i in range(5)}
    denominator = sum(baseline[i]*shape[i] for i in range(5))
    if denominator <= 0:
        raise ValueError('FAA profile has no positive event shape')
    scale = excess*sum(baseline[i] for i in range(5))/denominator
    multipliers = {i: 1 + shape[i]*scale if i < 5 else 1.0 for i in range(7)}
    plan=[]
    for i,d in enumerate(days):
        for c in categories:
            r=dict(date=str(d),aircraft_category=c,event_indicator=int(i<5),
                   reserved_arrivals=0,reserved_departures=0,reservation_show_rate=0,
                   reservation_class='synthetic',
                   assumption_source='FAA ATADS/OPSNET; PROVISIONAL_ASSUMPTIONS.md; regional timing and LAX aggregate transferred to fictional FBO; no bookings supplied')
            for t in ('arrivals','departures'):
                for s,k in EVENT_EXCESS_SCALES.items():
                    r[f'{t}_multiplier_{s}']=1+k*(multipliers[i]-1)
            plan.append(r)
    evidence=dict(source='FAA ATADS/OPSNET',source_url='https://aspm.faa.gov/opsnet/sys/Airport.asp',
                  retrieval_date='2026-10-23',repository_delivery='PR 17 (not the data source)',
                  metric='airport-wide air-taxi operations: takeoffs plus landings',
                  lax_five_day_control_adjusted_excess=excess,
                  six_airport_five_day_control_adjusted_excess=float(regional['excess_2022']),
                  regional_monday_raw_same_weekday_ratio=float(profile[1]['ratio']),
                  observed_directional_split=False,observed_aircraft_size_split=False,
                  method='Regional positive daily excess shape normalized to LAX five-day control-adjusted excess, weighted by forecast baseline movements.',
                  scenario_excess_scales=EVENT_EXCESS_SCALES,
                  direction_assumption='Same multiplier on arrivals and departures; FAA table has no directional split.',
                  scope_transfer='Apply air-taxi proxy uplift to GA+air-taxi FBO allocation; unvalidated.',
                  shoulders='Tuesday and Wednesday set to ordinary baseline; conservative boundary assumption.',
                  reservations='Zero synthetic placeholders, show rate zero; no observed bookings or claim of zero actual reservations.',
                  daily=[dict(date=str(d),medium_multiplier=multipliers[i]) for i,d in enumerate(days)],
                  evaluation='Allocation diagnostics only; not independent observed daily FBO accuracy.',
                  status='provisional_pending_Alan_review')
    return plan,evidence

