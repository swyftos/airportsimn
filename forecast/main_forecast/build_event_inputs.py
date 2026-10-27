"""FAA ATADS/OPSNET anchored scenarios, with explicit unvalidated FBO transfer."""
from datetime import date, timedelta
from pathlib import Path
from forecast_model import load_history, load_holiday_history, fit_and_evaluate, read_csv

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[1]/'sources/airport_traffic/data/processed'
# Five-day operations excess per scenario, from FAA counts around Super Bowl LVI (control-adjusted).
# Low: LAX GA, the modeled Part 91 scope. GA mixes in non-FBO flying (training was banned under the
# event TFR), so Medium uses LAX air taxi as the analog for event-driven business-jet demand.
# High doubles Medium as a stress case.
EVENT_EXCESS = {'low': ('general_aviation', 1), 'medium': ('air_taxi', 1), 'high': ('air_taxi', 2)}

def build(history_path, holiday_path=None):
    surge = read_csv(DATA/'superbowl_lvi_surge.csv')
    lax = {r['metric']: float(r['excess_2022']) for r in surge if r['locid']=='LAX'}
    regional = next(r for r in surge if r['metric']=='air_taxi' and r['locid']=='ALL6')
    profile = {int(r['offset']): r for r in read_csv(DATA/'superbowl_lvi_daily_profile.csv')}
    scenario_excess = {s: lax[metric]*k for s,(metric,k) in EVENT_EXCESS.items()}
    excess = scenario_excess['medium']
    assert 0 < scenario_excess['low'] <= excess < 1
    fitted, _ = fit_and_evaluate(load_history(history_path), .9,
                                 load_holiday_history(holiday_path) if holiday_path else None)
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
    # FAA counts takeoffs plus landings. Each event aircraft lands once before the game and leaves once
    # after it, so the five-day excess splits into equal extra arrivals and departures (aircraft are
    # conserved and accumulate on the ramp). Pre-game days and half of game day carry arrivals; the other
    # half of game day and Monday carry departures, each spread by the FAA daily shape.
    extra = {i: baseline[i]*shape[i]*scale for i in range(5)}
    timing = {'arrivals': {0: extra[0], 1: extra[1], 2: extra[2], 3: extra[3]/2},
              'departures': {3: extra[3]/2, 4: extra[4]}}
    half = sum(extra.values())/2
    base = {t: {i: sum(fitted[c,t][0].predict(d) for c in categories) for i,d in enumerate(days)}
            for t in timing}
    directional = {t: {i: 1 + half*timing[t].get(i, 0)/sum(timing[t].values())/base[t][i] for i in range(7)}
                   for t in timing}
    plan=[]
    for i,d in enumerate(days):
        for c in categories:
            r=dict(date=str(d),aircraft_category=c,event_indicator=int(i<5),
                   reserved_arrivals=0,reserved_departures=0,reservation_show_rate=0,
                   reservation_class='synthetic',
                   assumption_source='FAA ATADS/OPSNET; PROVISIONAL_ASSUMPTIONS.md; regional timing and LAX aggregate transferred to fictional FBO; no bookings supplied')
            for t in ('arrivals','departures'):
                for s,e in scenario_excess.items():
                    r[f'{t}_multiplier_{s}']=1+e/excess*(directional[t][i]-1)
            plan.append(r)
    evidence=dict(source='FAA ATADS/OPSNET',source_url='https://aspm.faa.gov/opsnet/sys/Airport.asp',
                  retrieval_date='2026-10-23',repository_delivery='PR 17 (not the data source)',
                  metric='airport-wide operations (takeoffs plus landings): GA for Low, air taxi for Medium/High',
                  lax_five_day_control_adjusted_excess=excess,
                  lax_ga_five_day_control_adjusted_excess=lax['general_aviation'],
                  six_airport_five_day_control_adjusted_excess=float(regional['excess_2022']),
                  regional_monday_raw_same_weekday_ratio=float(profile[1]['ratio']),
                  observed_directional_split=False,observed_aircraft_size_split=False,
                  method='Regional positive daily excess shape normalized to LAX five-day control-adjusted excess, weighted by forecast baseline movements.',
                  scenario_excess_scales={s: dict(metric=m, factor=k, excess=round(scenario_excess[s],4))
                                          for s,(m,k) in EVENT_EXCESS.items()},
                  direction_assumption='FAA table has no directional split. Aircraft conservation: extra arrivals = extra departures = half the five-day excess operations; arrivals Thu-Sat plus half of game day, departures half of game day plus Monday.',
                  scope_transfer='History combines LAX GA and air taxi (Part 91 + Part 135). Air-taxi airport event response is applied to the estimated fictional-FBO mix in Medium/High; transfer is unvalidated.',
                  shoulders='Tuesday and Wednesday set to ordinary baseline; conservative boundary assumption.',
                  reservations='Zero synthetic placeholders, show rate zero; no observed bookings or claim of zero actual reservations.',
                  daily=[dict(date=str(d),medium_operations_multiplier=multipliers[i],
                              medium_arrivals_multiplier=directional['arrivals'][i],
                              medium_departures_multiplier=directional['departures'][i]) for i,d in enumerate(days)],
                  evaluation='Allocation diagnostics only; not independent observed daily FBO accuracy.',
                  status='provisional_pending_data_review')
    return plan,evidence

