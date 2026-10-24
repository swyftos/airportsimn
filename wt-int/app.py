"""Run from repository root: python -m streamlit run wt-int/app.py."""
from __future__ import annotations

import copy
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'nazar'))
from engine import (config, dates, bounds, source_snapshot, arrival_counts, generate_visits,
                    parse_visits, visits_csv, simulate, preparation, digest, Visit)
from readiness.storage import ReviewStore
from ui.theme import apply_theme, safety
from ui.components import (header, shortage_headline, metric_row, fmt_time, action_row,
                           error_state, empty_state, status_chip)
from ui.charts import occupancy, hour_strip

st.set_page_config(page_title='RampReady | Parking preparation', layout='wide', initial_sidebar_state='collapsed')
apply_theme()
safety()
cfg = config()
LABELS = {'Expected forecast':'Medium', 'Lower demand':'Low', 'Higher demand':'High'}
SOURCE_LABELS = {'Event rehearsal (synthetic)':'demo', "Marvin’s latest private-only case":'marvin', 'Upload visit CSV':'upload'}
store = ReviewStore(Path(os.environ.get('FBO_REVIEW_DIR', str(HERE / '.state'))))


@st.cache_data(show_spinner=False)
def calculate(records, cfg, delay, overflow, unavailable):
    visits = [Visit(r['visit_id'],r['category'],datetime.fromisoformat(r['arrival']),datetime.fromisoformat(r['departure']),r['status']) for r in records]
    return simulate(visits, cfg, delay, overflow, unavailable)


def get_result(visits, cfg, delay=0, overflow=0, unavailable=0):
    return calculate([v.record() for v in visits],cfg,delay,overflow,unavailable)


if 'account' not in st.session_state:
    st.markdown('### RampReady')
    st.title('Know the parking gap. Prepare the week.')
    st.write(f"A seven-day preparation desk for {cfg['operator']}, a fictional FBO at {cfg['airport']}.")
    st.caption('Demo accounts. Not real sign-in. Use only pseudonymous aircraft visits; no passenger or owner information.')
    account_name = st.selectbox('Choose a demo account', [f"{a['name']} — {a['role']}" for a in cfg['demo_accounts']])
    if st.button('Open planning desk',type='primary'):
        st.session_state.account = cfg['demo_accounts'][[f"{a['name']} — {a['role']}" for a in cfg['demo_accounts']].index(account_name)]
        st.rerun()
    st.stop()

account = st.session_state.account
top = st.empty()
forecast_tab, plan_tab, data_tab, review_tab = st.tabs(['Week ahead', 'Preparation plan', 'Data & assumptions', 'Review history'])

with data_tab:
    st.subheader('Choose the evidence behind the plan')
    source_label = st.selectbox('Planning dataset', list(SOURCE_LABELS), key='data_source')
    source = SOURCE_LABELS[source_label]
    st.caption('Changing the source recalculates the plan and invalidates reviews for the previous inputs. No source silently falls back to sample data.')
    uploaded = st.file_uploader('Upload visits',type=['csv']) if source == 'upload' else None
    st.markdown('**Demo profile**')
    st.write(f"{account['name']} · {account['role']} · {cfg['operator']}")
    st.caption('Roles are selected from server-configured demo accounts. Reviews are local planning records; this is not production identity management.')
    if st.button('Switch demo account'):
        del st.session_state['account']
        st.rerun()
    st.markdown('**Source and method**')
    st.write('The rehearsal uses synthetic private-aircraft visits. Marvin mode reads his newly merged private-only daily arrival requests. Hourly arrival times, aircraft size and stays are synthesized explicitly in both modes.')
    st.write('Marvin’s GA source is an airport-category proxy, not an observed private fleet or FBO customer count. His 50% eligibility and 20% capture are assumptions. We do not use the source’s “can land” field as an authorization or reinterpret it as runway capacity.')
    st.write('The hourly adapter uses requested arrivals and an assumed dwell distribution. Its departures and occupancy are recomputed from those synthetic stays; they are not Marvin’s daily departure forecast or Elia’s Monte Carlo outputs.')
    source_info = st.empty()
    st.markdown('**Weather evidence**')
    st.write('February weather is not predicted here. The weather test applies user-selected disruption assumptions to parking; it is not a visibility, wind or flight-safety forecast.')
    st.markdown('[Aviation Weather Center: TAF scope and 24–30 hour horizons](https://aviationweather.gov/help/data/) · [NOAA: interpreting monthly and seasonal outlooks](https://www.climate.gov/news-features/understanding-climate/understanding-noaas-monthly-and-seasonal-climate-outlooks)')
    st.caption('A future live feed must retain issue time, valid-from/to times, airport and source. Never present a current observation as weather for the event week.')

with forecast_tab:
    st.caption(f"Super Bowl LXI planning week · {bounds(cfg)[0].strftime('%d %b')}–{(bounds(cfg)[1]-timedelta(days=1)).strftime('%d %b %Y')} · {cfg['airport']}")
    hero = st.container()
    with st.container(key='forecast-visual'):
        chart = st.container(key='occupancy-chart')
        with st.container(key='scenario-controls'):
            controls = st.columns([3,2])
            with controls[0]:
                label = st.radio('Demand case',list(LABELS),horizontal=True,key='case',disabled=source=='upload')
                st.caption('Expected is the model’s central case. Lower and higher are alternatives, not confidence bounds.')
            with controls[1]:
                delay = st.slider('Departures run late by 0–6 hours',0,6,0,key='delay')
    st.button('Preview preparation plan',type='primary',key='preview',on_click=lambda: st.session_state.update(show_plan=True))
    plan_inline = st.container()
    with st.expander('Why this forecast'):
        why = st.container()
    with st.expander('Bookings and overlapping stays'):
        bookings = st.container()
    with st.expander('Weather disruption test'):
        weather = st.toggle('Test weather-related disruption',key='weather')
        st.caption('Assumption only. Set departure delay above; it is applied once. Aircraft remain parked longer even if no extra aircraft arrive.')
        unavailable = st.slider('Main-ramp units temporarily unavailable all week',0,15,0,key='unavailable',disabled=not weather) if weather else 0
        st.write('This test does not predict cancellations or automatically change arrival counts. Use daily what-if settings for a separate timing or demand assumption.')
    with st.expander('Assumptions and daily what-if'):
        capacity_cols = st.columns(2)
        main = capacity_cols[0].number_input('Main-ramp units (synthetic)',min_value=20,max_value=120,value=int(cfg['main_ramp_units']),step=1)
        proposed = capacity_cols[1].slider('Proposed overflow units',0,int(cfg['overflow_limit_units']),int(cfg['overflow_limit_units']),key='overflow')
        cfg = copy.deepcopy(cfg)
        cfg['main_ramp_units'] = main
        st.caption(f"{cfg['protected_reserve_units']} protected reserve units are always excluded. Aircraft weights: " + ', '.join(f'{k} {v:g}' for k,v in cfg['weights'].items()) + '. Space units are not physical stands.')
        holiday = st.slider('Additional Presidents Day arrivals (%) — assumption',-50,50,0,5,disabled=source=='upload',key='holiday')
        st.caption('No measured holiday uplift is built in. A manual arrivals override below takes precedence over the holiday adjustment.')
        daily_edit = st.toggle('Try a different demand case or arrival count for one day',disabled=source=='upload')
        overrides = {}
        if daily_edit and source != 'upload':
            day = st.selectbox('Day to change',dates(cfg),format_func=lambda x:datetime.fromisoformat(x).strftime('%A %d %b'))
            case_override = st.selectbox('Demand case for that day',['Use week case',*LABELS])
            overrides[day] = {'scenario': LABELS[case_override] if case_override != 'Use week case' else LABELS[label]}
            if st.checkbox('Enter an exact arrivals count'):
                overrides[day]['arrivals'] = st.number_input('Aircraft arrivals on selected day',0,100,20,1)
        st.caption('One day’s extra visits remain in the model until their assumed departure. Future-day counts are unchanged; parking carries forward.')
        st.write('Stay assumptions: ' + ', '.join(f"{cfg['stay_mix'][k]:.0%} {k.replace('_',' ')} ({cfg['stay_hours'][k]}h)" for k in cfg['stay_mix']) + f". The busy-week rehearsal extends non-drop-and-go pregame stays to at least {cfg['demo']['event_overnight_min_hours']}h. These are generated visit behaviors, not measured fleet ratios.")
    with st.expander('Advanced settings and exports'):
        advanced = st.container()

try:
    raw_rows, metadata, source_hash = source_snapshot(cfg) if source == 'marvin' else (None,None,digest({'source':source,'config':cfg}))
    if source == 'upload':
        if uploaded is None:
            with hero:
                empty_state('No bookings loaded. Upload a CSV in Data & assumptions or choose the rehearsal dataset.')
            start, _ = bounds(cfg)
            template = [Visit('V-0412','light',start+timedelta(hours=10),start+timedelta(hours=14),'Recorded reservation')]
            with data_tab:
                st.download_button('Download visit CSV template',visits_csv(template),'visit-template.csv','text/csv')
            st.stop()
        raw = uploaded.getvalue()
        visits = parse_visits(raw,cfg)
        source_hash = digest(raw.hex())
        ordinary_counts = cfg['demo']['ordinary_arrivals']
        baseline_visits = generate_visits(cfg,ordinary_counts,'demo',True)
        baseline_note = 'Ordinary baseline is the synthetic rehearsal comparator; uploaded visits do not establish an ordinary-week baseline.'
    else:
        counts, ordinary_counts = arrival_counts(cfg,source,LABELS[label],raw_rows,overrides,holiday)
        if source == 'marvin':
            cfg['marvin_opening_aircraft'] = round(float(raw_rows[0]['ordinary_baseline_arrivals']) * 1.1)
        visits = generate_visits(cfg,counts,source)
        baseline_visits = generate_visits(cfg,ordinary_counts,source,True)
        baseline_note = 'Ordinary baseline and event demand use the same size and dwell assumptions; rehearsal event stays include the disclosed minimum dwell.'
    before = get_result(visits,cfg,delay,0,unavailable)
    after = get_result(visits,cfg,delay,proposed,unavailable)
    baseline = get_result(baseline_visits,cfg,0,0,unavailable)
except (ValueError,KeyError,OSError,UnicodeError,StopIteration) as exc:
    with hero:
        error_state(f'Cannot calculate this source: {exc}. Check the file or select the labeled rehearsal dataset.')
    st.stop()

input_key = digest(dict(config=cfg,source=source,source_hash=source_hash,case=LABELS[label],delay=delay,overflow=proposed,
                        holiday=holiday,overrides=overrides,weather=weather,unavailable=unavailable,visits=[v.record() for v in visits],
                        engine_hash=digest((HERE/'engine.py').read_text())))
changed = st.session_state.get('input_key') not in (None,input_key)
if st.session_state.get('source_hash') != source_hash:
    st.session_state.loaded_at = datetime.now(ZoneInfo(cfg['timezone'])).strftime('%d %b, %H:%M')
    st.session_state.source_hash = source_hash
st.session_state.input_key = input_key
with top.container():
    header(cfg,account,source,st.session_state.loaded_at)
with hero:
    shortage_headline(before,label)
    if changed:
        st.caption('Inputs changed. Forecast and preparation plan recalculated; earlier reviews require review again.')
    if weather:
        st.caption(f'Weather what-if active: {delay}h departure delay and {unavailable} unavailable units. No weather probability is implied.')
with chart:
    st.plotly_chart(occupancy(before,baseline,cfg,label),use_container_width=True,config={'displayModeBar':False})
    st.caption(('Synthetic demo data.' if source=='demo' else ('Synthetic hourly stays; Marvin’s estimated daily arrivals.' if source=='marvin' else 'Uploaded visit inputs.')) + f" Hourly peak parking units. {cfg['main_ramp_units']} total units less {cfg['protected_reserve_units']} protected reserve" + (f' and {unavailable} temporarily unavailable' if unavailable else '') + f". Presidents Day is {datetime.fromisoformat(cfg['holiday']).strftime('%A %d %b')}.")

with why:
    st.write({'demo':'The busy-week rehearsal is ready to explore. Synthetic arrival counts and stays deliberately test how the plan handles a busy ramp.',
              'marvin':'Latest merged private-only plan: 2025 GA-category operations → assumed eligible fraction → assumed FBO capture → arrivals → synthetic hourly stays.',
              'upload':'Uploaded visit arrival and departure times drive occupancy directly. Demand case buttons do not add unbooked visits to an uploaded manifest.'}[source])
    metric_row([('Visits arriving this week',sum(r['arrivals'] for r in before['daily']),'Includes all arrivals; nothing is denied by the simulator.'),
                ('Already parked at opening',before['opening_aircraft'],'Explicit opening visits, not an empty ramp.'),
                ('Remaining after the week',before['closing_aircraft'],'These visits continue beyond the visible window.')])
    status_counts = pd.Series([v.status for v in visits]).value_counts().rename_axis('Input class').reset_index(name='Visits')
    st.dataframe(status_counts,hide_index=True,use_container_width=True)
    st.caption('No recorded reservations are supplied in the demo or Marvin source. Synthetic bookings are examples, not customer commitments. Fractional daily expectations are rounded to individual visits for this rehearsal.')
    st.caption(baseline_note)
    st.dataframe(pd.DataFrame(before['daily']).rename(columns={'date':'Date','arrivals':'Arrivals','departures':'Departures','closing_aircraft':'Aircraft at midnight','peak_units':'Peak units','peak_gap':'Peak shortage'}),hide_index=True,use_container_width=True)
    hour_strip(before,cfg)
    st.caption(f'Input fingerprint: {input_key[:12]}. No claim of real-world forecasting accuracy is made.')

with bookings:
    inspect_time = st.selectbox('Inspect an hour', [r['time'] for r in before['hourly']],
                               index=next(i for i,r in enumerate(before['hourly']) if r['time'] <= before['peak_time'] < r['time']+timedelta(hours=1)),
                               format_func=fmt_time)
    matches = [v for v in before['visits'] if v.arrival < inspect_time+timedelta(hours=1) and v.departure > inspect_time]
    st.caption('Visits overlapping this hour. Arrival/departure boundaries inside an hour may mean they are not all parked simultaneously.')
    if matches:
        table = pd.DataFrame([{'Visit':v.visit_id,'Size':v.category,'Units':cfg['weights'][v.category],
                              'Arrival':fmt_time(v.arrival),'Departure':fmt_time(v.departure),'Input class':v.status} for v in matches])
        st.dataframe(table,hide_index=True,use_container_width=True)
    else:
        empty_state('No visits overlap this hour. Choose a busier hour or inspect the daily table.')

actions = preparation(before,after,cfg,proposed)
history = store.history(input_key)
latest = {}
for review in history:
    if not review['stale']:
        latest.setdefault(review['recommendation_id'],{'approve':'Approved','modify':'Modified','reject':'Rejected'}[review['decision']])
affected_days = sum(r['peak_gap'] > 0 for r in before['daily'])
cost_days = cfg['window_days']
cost = proposed * cfg['illustrative_rate_per_unit_day'] * cost_days

def show_plan(full=False):
    st.subheader('A preparation plan for human review')
    st.write(f"{before['peak_gap']:g}-unit peak shortfall across {affected_days} days. Propose {proposed:g} additional units for the full planning week. Remaining shortfall: **{after['peak_gap']:g} units**.")
    if after['peak_gap']:
        st.markdown(f'<div class="help-note">Allowed overflow is not enough. Remaining shortage: {after["peak_gap"]:g} units. Investigate partner capacity or voluntary timing changes with the appropriate people.</div>',unsafe_allow_html=True)
    elif not before['peak_gap']:
        st.caption('No extra capacity is required by this case. Set proposed overflow to zero to avoid an unnecessary illustrative cost.')
    st.caption('Template briefing (AI service unavailable). All figures come from the numerical engine. No model-generated numbers or external AI key are required.')
    for action in actions:
        action_row(action,latest.get(action['id'],'Proposed'))
    if full:
        comparisons = [('First shortage',fmt_time(before['first_shortage']),fmt_time(after['first_shortage'])),
                       ('Peak shortage (units)',f"{before['peak_gap']:g}",f"{after['peak_gap']:g}"),
                       ('Hours over capacity',f"{before['shortage_hours']:.1f}",f"{after['shortage_hours']:.1f}"),
                       ('Shortage unit-hours',f"{before['shortage_unit_hours']:.1f}",f"{after['shortage_unit_hours']:.1f}"),
                       ('Illustrative cost','$0',f'${cost:,.0f}')]
        st.dataframe(pd.DataFrame(comparisons,columns=['Measure','Before preparation','With proposed plan']),hide_index=True,use_container_width=True)
        st.caption(f'Identical aircraft demand in both columns. Shortage unit-hours are unmet parking demand over time, not rejected aircraft or service delays. Illustrative cost: {proposed} units × ${cfg["illustrative_rate_per_unit_day"]}/unit/day × {cost_days} days. No quote or partner availability is supplied.')
        st.plotly_chart(occupancy(before,baseline,cfg,label,after),use_container_width=True,key='plan_chart',config={'displayModeBar':False})

if st.session_state.get('show_plan'):
    with plan_inline:
        show_plan()
        st.caption('Open Preparation plan for before/after measurements, export and human review.')

with plan_tab:
    show_plan(full=True)
    st.subheader('Record a planning review')
    st.caption('Approval records a planning judgment only. It does not book space, spend money or instruct aircraft movement. Modify requests a change; edit assumptions and review the recalculated version before relying on it.')
    permitted = [a for a in actions if account['role']=='Manager' or a['owner']==account['role']]
    if permitted:
        with st.form('review_form',clear_on_submit=True):
            action_id = st.selectbox('Action to review',[a['id'] for a in permitted],format_func=lambda x:next(a['action'] for a in permitted if a['id']==x))
            decision = st.radio('Planning decision',['Approve','Modify','Reject'],horizontal=True)
            note = st.text_area('Required review note',max_chars=1500,placeholder='What did you verify, or what should change?')
            submitted = st.form_submit_button('Save review')
            if submitted:
                if not note.strip():
                    st.error('Add a review note before saving.')
                else:
                    store.add(input_key,LABELS[label],f'delay-{delay}',action_id,decision.lower(),note.strip(),account['name'],{'role':account['role'],'source':source,'weather':weather})
                    st.session_state.review_saved = True
                    st.rerun()
    if st.session_state.pop('review_saved',False):
        st.success('Review saved for this exact plan version.')
    export = {'plan_version':input_key,'source':source,'source_fingerprint':source_hash,'classification':'Planning rehearsal; synthetic stays unless uploaded',
              'operator':cfg['operator'],'airport':cfg['airport'],'config':cfg,'scenario':LABELS[label], 'delay_hours':delay,
              'weather_test':weather,'unavailable_units':unavailable,'proposed_overflow':proposed,'holiday_pct':holiday,'daily_overrides':overrides,
              'before':{k:v for k,v in before.items() if k!='visits'},'after':{k:v for k,v in after.items() if k!='visits'},
              'actions':actions,'reviews':[r for r in history if not r['stale']],'illustrative_cost':cost,
              'safety':'Planning aid. Nothing here moves an aircraft, reserves space or spends money.'}
    st.download_button('Export preparation plan',json.dumps(export,indent=2,default=str),'rampready-plan.json','application/json')

with advanced:
    st.download_button('Export modeled visits',visits_csv(before['visits']),'rampready-visits.csv','text/csv')
    st.caption('This export includes the selected departure delay. Do not re-upload it and apply the same delay again. Synthetic input classes intentionally cannot be uploaded as recorded reservations without explicitly changing their classification.')
    st.json({'plan_version':input_key,'source_fingerprint':source_hash,'case':LABELS[label],'weather_test':weather},expanded=False)
with source_info.container():
    if metadata:
        st.json(metadata,expanded=False)
        st.caption(f"Read directly from {cfg['marvin_path']}. The source’s 75-unit estimate is replaced by this app’s explicitly synthetic, editable capacity assumption; its original daily arrival requests are preserved.")
    else:
        st.caption('Synthetic rehearsal assumptions are stored in wt-int/assumptions.yaml. No live aviation data or real reservations are represented.')
with review_tab:
    st.subheader('Human planning reviews')
    if not history:
        empty_state('No reviews yet. Preview a preparation plan, choose an action and save a review with a note.')
    for item in history:
        with st.container(border=True):
            st.markdown(f"**{item['decision'].capitalize()} · {item['recommendation_id']}**")
            if item['stale']:
                st.warning('Out of date. Inputs changed after this review. Review again.')
            else:
                st.caption('Current plan version')
            st.write(item['note'])
            st.caption(f"{item['reviewer']} · {item['reviewed_at']} · Plan {item['version'][:12]}")
