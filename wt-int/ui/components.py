from html import escape
from datetime import datetime
import streamlit as st


def fmt_time(value):
    return value.strftime('%a %d %b, %H:%M') if value else 'None this week'


def status_chip(text, style=''):
    return f'<span class="chip {escape(style)}">{escape(text)}</span>'


def data_badge(source):
    return status_chip({'demo':'Synthetic demo data', 'marvin':'Marvin source + synthetic stays', 'upload':'Uploaded visits'}[source])


def header(cfg, account, source, refreshed):
    st.markdown(f'''<div class="topbar"><div><div class="brand"><span class="mark">R</span> RampReady</div>
<div class="operator">{escape(cfg['operator'])} · {escape(cfg['airport'])} (fictional FBO)</div></div>
<div class="account">{escape(account['name'])}<small>{escape(account['role'])}</small><small>Demo account</small></div></div>
<div class="meta">{data_badge(source)}<span>Inputs loaded {escape(refreshed)} · All times local</span></div>''', unsafe_allow_html=True)


def shortage_headline(result, label):
    if result['first_shortage']:
        text = f"Parking demand exceeds usable space {fmt_time(result['first_shortage'])}."
        sub = f"Peak shortfall: {result['peak_gap']:g} units on {fmt_time(result['peak_time'])}. {label} under the current assumptions."
        chip = status_chip('Preparation needed', 'gap')
    else:
        text = f'{label} fits within usable main-ramp capacity all week.'
        sub = f"Peak demand is {result['peak_units']:g} of {result['usable_main']:g} usable units. Continue verifying arrival and departure estimates."
        chip = status_chip('Within modeled capacity', 'good')
    st.markdown(f'{chip}<div class="headline">{escape(text)}</div><p class="subline">{escape(sub)}</p>', unsafe_allow_html=True)


def metric_row(items):
    for col, (label, value, help_text) in zip(st.columns(len(items)), items):
        col.metric(label, value, help=help_text)


def empty_state(text):
    st.info(text)


def error_state(text):
    st.error(text)


def action_row(action, status):
    deadline = datetime.fromisoformat(action['deadline']).strftime('%a %d %b, %H:%M')
    st.markdown(f'''<div class="plan-action"><div><strong>{escape(action['action'])}</strong>
<p>{escape(action['reason'])}</p></div><div>{status_chip(status)}<br><small>{escape(action['owner'])}<br>By {deadline}</small></div></div>''', unsafe_allow_html=True)
