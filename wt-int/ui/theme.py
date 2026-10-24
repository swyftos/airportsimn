import streamlit as st

COLORS = dict(concrete='#ECEAE4', paper='#F8F7F3', asphalt='#1E2327', slate='#5E6A71',
              line='#D3D0C7', yellow='#E8B400', blue='#1F5A7A', red='#C8372D', green='#2F7D5B')


def apply_theme():
    tokens = ';'.join(f'--{k}:{v}' for k, v in COLORS.items())
    st.markdown('''<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600&family=Barlow+Semi+Condensed:wght@500;600&display=swap');
:root {''' + tokens + ''';}
html, body, [class*="css"], [data-testid="stApp"] {font-family:Barlow,system-ui,sans-serif; font-variant-numeric:tabular-nums;}
[data-testid="stAppViewContainer"] {background:var(--concrete);}
[data-testid="stHeader"] {background:transparent;height:0;}
#MainMenu, footer, [data-testid="stToolbar"] {display:none;}
.stMainBlockContainer {max-width:1200px;padding-top:1.2rem;padding-bottom:5rem;}
h1,h2,h3, [data-testid="stMetricValue"] {font-family:'Barlow Semi Condensed',system-ui,sans-serif!important;font-weight:600!important;letter-spacing:-.025em;}
h1 {font-size:32px!important;line-height:1.15!important;max-width:850px;}
h2 {font-size:22px!important;} h3 {font-size:20px!important;}
p, label, [data-testid="stMarkdownContainer"] {font-family:Barlow,system-ui,sans-serif;}
[data-testid="stCaptionContainer"] {color:var(--slate);}
[data-testid="stVerticalBlock"] {gap:.75rem;}
[data-testid="stMetric"] {border-top:1px solid var(--line);padding:12px 0;}
[data-testid="stMetricValue"] {font-size:32px;}
[data-testid="stMetricLabel"] {color:var(--slate);font-size:13px;}
[data-testid="stExpander"] {border:1px solid var(--line);border-radius:6px;background:var(--paper);box-shadow:none;}
[data-testid="stExpander"] summary {font-size:15px;}
[data-testid="stButton"] button, [data-testid="stDownloadButton"] button {border-radius:6px;box-shadow:none;font-weight:600;min-height:42px;}
button[kind="primary"] {background:var(--asphalt)!important;color:var(--paper)!important;border:1px solid var(--asphalt)!important;}
button[kind="primary"]:hover {background:var(--slate)!important;}
button:focus-visible,input:focus-visible,summary:focus-visible,a:focus-visible {outline:2px solid var(--yellow)!important;outline-offset:3px;}
[data-baseweb="tab-list"] {border-bottom:1px solid var(--line);gap:24px;}
[data-baseweb="tab"] {font-family:Barlow,system-ui,sans-serif;font-weight:500;}
[data-baseweb="tab-highlight"] {background-color:var(--asphalt);}
[data-testid="stPlotlyChart"] {border:1px solid var(--line);border-radius:6px;background:var(--paper);}
[data-testid="stAlert"] {border-radius:6px;}
.topbar {display:flex;justify-content:space-between;align-items:center;gap:24px;border-bottom:2px solid var(--asphalt);padding:0 0 20px;margin-bottom:8px;}
.brand {font-family:'Barlow Semi Condensed',sans-serif;font-size:22px;font-weight:600;display:flex;align-items:center;gap:12px;}
.mark {display:inline-flex;align-items:center;justify-content:center;background:var(--asphalt);color:var(--paper);border-radius:6px;width:38px;height:38px;font-size:19px;border-bottom:3px solid var(--yellow);}
.operator {font-size:15px;color:var(--slate);margin-top:3px;}
.account {text-align:right;font-size:15px;}.account small {display:block;color:var(--slate);font-size:13px;}
.meta {display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap;color:var(--slate);font-size:13px;margin:4px 0 8px;}
.chip {display:inline-block;padding:4px 8px;border:1px solid var(--line);border-radius:4px;color:var(--asphalt);font-size:13px;background:var(--paper);}
.chip.good {color:var(--green);border-color:var(--green);}.chip.gap {color:var(--red);border-color:var(--red);}
.headline {margin:12px 0 8px;font-family:'Barlow Semi Condensed',sans-serif;font-size:32px;font-weight:600;line-height:1.15;max-width:920px;}
.subline {font-size:15px;color:var(--slate);margin:0 0 12px;}
.safety {position:fixed;bottom:0;left:0;right:0;padding:10px 24px;border-top:1px solid var(--line);background:var(--paper);color:var(--slate);font-size:13px;z-index:99;text-align:center;}
.ramp-strip {display:grid;grid-template-columns:72px repeat(24,1fr);gap:3px;align-items:center;font-size:12px;color:var(--slate);min-width:520px;}
.hour-cell {height:15px;border-radius:2px;background:var(--line);}
.strip-wrap {overflow-x:auto;padding:16px 0;border-bottom:1px solid var(--line);}
.strip-label {color:var(--asphalt);font-weight:500;}
.help-note {border-left:3px solid var(--yellow);padding:12px 16px;background:var(--paper);font-size:15px;color:var(--asphalt);}
.plan-action {border-top:1px solid var(--line);padding:16px 0;display:grid;grid-template-columns:1fr 170px;gap:16px;}
.plan-action strong {font-weight:600;font-size:17px;}.plan-action p {font-size:15px;color:var(--slate);margin:6px 0 0;}
.plan-action small {font-size:13px;color:var(--slate);}
@media (max-width:640px) {
 .st-key-forecast-visual > div:has(> .st-key-scenario-controls) {order:-1;}
 .stMainBlockContainer {padding:1rem 1rem 5rem;}.topbar {gap:12px;align-items:flex-start;}.brand{font-size:20px;}.operator{font-size:13px;}.account{font-size:13px;}
 .headline,h1{font-size:28px!important;}.safety{font-size:11px;padding:8px 12px;}.plan-action{grid-template-columns:1fr;}
}
@media (prefers-reduced-motion:no-preference){button {transition:background-color .12s ease;}}
</style>''', unsafe_allow_html=True)


def safety():
    st.markdown('<div class="safety">Planning aid. Nothing here moves an aircraft, reserves space or spends money.</div>', unsafe_allow_html=True)
