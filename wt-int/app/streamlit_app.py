"""RampReady: Super Bowl LXI ramp planning for a fictional Van Nuys FBO.

AI assists, people decide. This app plans; it authorizes no aircraft movement.
"""
from __future__ import annotations

import copy
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import briefing
import data_access as da
import decisions

st.set_page_config(page_title="RampReady", page_icon="✈️", layout="wide")

BANNER = "Planning aid only. Authorizes no aircraft movement. Final decision: the manager."
DISRUPTIONS = {"fog": "Fog: Saturday arrivals shifted 6 h", "extended_stay": "Extended stay: 30% stay to Monday noon",
               "airspace": "Airspace restriction: no movement for 3 h"}


# ---------- data ----------

@st.cache_data(show_spinner="Running Monte Carlo…")
def run_scenario(scenario: str, cfg: dict, disruption: str | None = None):
    fc = da.forecast(scenario, cfg)
    if disruption:
        fc = da.disrupt(fc, disruption, cfg)
    occ = da.occupancy(fc, cfg)
    if occ["occupancy_up_p50"].isna().all():
        raise da.ModelUnavailable("model.occupancy returns no values yet (skeleton).")
    return fc, occ, da.recommendations(occ, cfg)


@st.cache_data
def run_baseline(cfg: dict):
    return da.occupancy(da.forecast("baseline", cfg), cfg)


def guarded(fn, *args, **kwargs):
    """Show a clear notice instead of crashing while a model piece is still a skeleton."""
    try:
        return fn(*args, **kwargs)
    except da.ModelUnavailable as exc:
        st.info(f"Not available yet: {exc}")
    except Exception as exc:  # integration day: surface, don't crash the whole app
        st.warning(f"{type(exc).__name__}: {exc}")
    return None


# ---------- charts ----------

def occupancy_chart(occ: pd.DataFrame, base: pd.DataFrame | None = None, title: str = "", height: int = 380):
    fig = go.Figure()
    t = occ["timestamp"]
    fig.add_trace(go.Scatter(x=t, y=occ["occupancy_up_p90"], line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=t, y=occ["occupancy_up_p10"], fill="tonexty", line=dict(width=0),
                             fillcolor="rgba(37,99,235,0.18)", name="P10–P90 range"))
    fig.add_trace(go.Scatter(x=t, y=occ["occupancy_up_p50"], line=dict(color="#2563eb", width=2.5), name="Super Bowl P50"))
    if base is not None:
        # baseline is the same calendar week without the event: align on position
        fig.add_trace(go.Scatter(x=t, y=base["occupancy_up_p50"].to_numpy()[: len(t)],
                                 line=dict(color="#6b7280", width=1.5, dash="dot"), name="Ordinary week P50"))
    fig.add_trace(go.Scatter(x=t, y=occ["capacity_up"], line=dict(color="#dc2626", width=2), name="Capacity"))
    fig.update_layout(title=title, height=height, yaxis_title="Parking units (PU)", hovermode="x unified",
                      margin=dict(l=10, r=10, t=40, b=10), legend=dict(orientation="h", y=-0.15))
    return fig


def kpis(occ: pd.DataFrame):
    peak = occ.loc[occ["occupancy_up_p50"].idxmax()]
    over = int((occ["occupancy_up_p90"] > occ["capacity_up"]).sum())
    c = st.columns(4)
    c[0].metric("Peak occupancy (P50)", f"{peak['occupancy_up_p50']:.0f} PU",
                help=f"P10 {peak['occupancy_up_p10']:.0f} · P90 {peak['occupancy_up_p90']:.0f}")
    c[1].metric("Peak time", peak["timestamp"].strftime("%a %d %H:00"))
    c[2].metric("Hours over capacity (P90)", over)
    c[3].metric("Max ramp agents needed", int(occ["staff_needed"].max()))


# ---------- tabs ----------

def tab_week(cfg, scenario):
    res = guarded(run_scenario, scenario, cfg)
    if not res:
        return
    _, occ, _ = res
    base = guarded(run_baseline, cfg)
    if base is not None and base["occupancy_up_p50"].isna().all():
        base = None
    kpis(occ)
    st.plotly_chart(occupancy_chart(occ, base, f"Ramp occupancy, scenario {scenario}"), use_container_width=True)
    if "occupancy_unserved_up_p90" in occ and occ["occupancy_unserved_up_p90"].max() > 0:
        st.caption(f"Unserved demand peaks at {occ['occupancy_unserved_up_p50'].max():.0f} PU (P50), "
                   f"{occ['occupancy_unserved_up_p90'].max():.0f} PU (P90): aircraft the manager would need to redirect.")


def tab_plan(cfg, scenario):
    res = guarded(run_scenario, scenario, cfg)
    if not res:
        return
    recs = decisions.apply_statuses(res[2], scenario)
    if not recs:
        st.info("No recommendation produced for this scenario yet.")
    st.caption("Every recommendation stays PROPOSED until a person approves, modifies or rejects it.")
    for rec in recs:
        with st.container(border=True):
            top = st.columns([5, 1, 1])
            top[0].markdown(f"**{rec['id']} · {rec['category']}** — {rec['action']}")
            top[1].markdown(f"confidence: `{rec['confidence']}`")
            top[2].markdown(f"**{rec['status']}**")
            st.caption(f"Rule: {rec['rule']}")
            note = st.text_input("Note", value=rec["human_note"], key=f"note-{scenario}-{rec['id']}",
                                 label_visibility="collapsed", placeholder="Note (required to modify or reject)")
            b = st.columns(3)
            for col, status in zip(b, decisions.STATUSES):
                if col.button(status.title(), key=f"{status}-{scenario}-{rec['id']}", use_container_width=True):
                    if status != "APPROVED" and not note.strip():
                        st.error("Add a note explaining the change or the rejection.")
                    else:
                        decisions.record(rec, status, note)
                        st.rerun()
    with st.expander("Decision log"):
        st.dataframe(decisions.load_log(), use_container_width=True, hide_index=True)


def tab_scenarios(cfg):
    cols = st.columns(3)
    plans = {}
    for col, sc in zip(cols, da.SCENARIOS):
        with col:
            res = guarded(run_scenario, sc, cfg)
            if not res:
                continue
            occ, recs = res[1], res[2]
            plans[sc] = recs
            st.plotly_chart(occupancy_chart(occ, title=sc.title(), height=260), use_container_width=True)
            st.metric("Peak P50 / P90", f"{occ['occupancy_up_p50'].max():.0f} / {occ['occupancy_up_p90'].max():.0f} PU")
            for r in recs:
                st.markdown(f"- {r['action']}")
    if plans:
        st.subheader("How the plan changes")
        rows = {}
        for sc, recs in plans.items():
            for r in recs:
                rows.setdefault(r["category"], {})[sc] = "; ".join(
                    x["action"] for x in recs if x["category"] == r["category"])
        st.dataframe(pd.DataFrame(rows).T.reindex(columns=da.SCENARIOS), use_container_width=True)


def tab_impact(cfg, scenario):
    st.subheader(f"Naive plan vs RampReady plan, scenario {scenario}")
    cmp_ = guarded(da.compare_plans, scenario, cfg)
    if cmp_:
        metrics = {k: v for k, v in cmp_.items() if isinstance(v, dict)}
        if metrics:
            st.dataframe(pd.DataFrame(metrics), use_container_width=True)
        series = {k: v for k, v in cmp_.items() if isinstance(v, pd.DataFrame)}
        for name, df in series.items():
            st.line_chart(df, height=260)
        if not metrics and not series:
            st.json(cmp_)
    st.subheader("Forecast accuracy on a hidden synthetic week")
    bt = guarded(da.backtest, cfg)
    if bt:
        c = st.columns(3)
        c[0].metric("MAPE, daily arrivals", f"{bt['mape']:.1%}" if bt["mape"] <= 1 else f"{bt['mape']:.1f}%")
        c[1].metric("Hours inside P10–P90", f"{bt['coverage_p10_p90']:.0%}", help="Target ≈ 80%")
        c[2].metric("Peak occupancy error", f"{bt['peak_error_up']:.1f} PU")
        st.caption("Validated on synthetic data. With real history (Super Bowl LVI, LA 2022) the same method applies.")


def tab_disruption(cfg, scenario):
    kind = st.radio("Disruption", list(DISRUPTIONS), format_func=DISRUPTIONS.get, horizontal=True)
    if not st.button("Simulate disruption", type="primary"):
        return
    before = guarded(run_scenario, scenario, cfg)
    after = guarded(run_scenario, scenario, cfg, kind)
    if not (before and after):
        return
    c = st.columns(2)
    c[0].plotly_chart(occupancy_chart(before[1], title="Before", height=300), use_container_width=True)
    c[1].plotly_chart(occupancy_chart(after[1], title=f"After: {kind}", height=300), use_container_width=True)
    old = {r["category"] + r["action"] for r in before[2]}
    new = {r["category"] + r["action"] for r in after[2]}
    changed = [r for r in after[2] if r["category"] + r["action"] not in old]
    dropped = [r for r in before[2] if r["category"] + r["action"] not in new]
    st.subheader("What changes in the plan")
    if not changed and not dropped:
        st.write("No change to the recommended plan.")
    for r in changed:
        st.markdown(f"🆕 {r['action']}  \n<small>{r['rule']}</small>", unsafe_allow_html=True)
    for r in dropped:
        st.markdown(f"~~{r['action']}~~")


def _numeric_leaves(d, path=()):
    for k, v in d.items():
        if isinstance(v, dict):
            yield from _numeric_leaves(v, path + (k,))
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            yield path + (k,), v


def _set(d, path, value):
    for k in path[:-1]:
        d = d[k]
    d[path[-1]] = value


def tab_assumptions(cfg_file):
    st.caption("All numbers are synthetic assumptions for a prototype. Edit them here; every tab recomputes.")
    edited = st.session_state.setdefault("cfg", copy.deepcopy(cfg_file))
    groups: dict[str, list] = {}
    for path, _ in _numeric_leaves(cfg_file):
        groups.setdefault(path[0], []).append(path)
    for group, paths in groups.items():
        with st.expander(group.replace("_", " ").title(), expanded=False):
            cols = st.columns(3)
            for i, path in enumerate(paths):
                cur = edited
                for k in path:
                    cur = cur[k]
                val = cols[i % 3].number_input(" › ".join(path[1:]) or path[0], value=cur,
                                               key="cfg-" + ".".join(map(str, path)))
                _set(edited, path, val)
    if st.button("Reset to file values"):
        st.session_state["cfg"] = copy.deepcopy(cfg_file)
        st.rerun()
    st.subheader("Limits")
    st.markdown(
        "- All data is synthetic; accuracy figures validate the method, not real-world performance.\n"
        "- Demand drivers are simplified; a real deployment calibrates on historical events.\n"
        "- 2027 airspace programs are not published yet; they are adjustable constraints.\n"
        "- One FBO, one airport; regional competition is a market-share parameter.")


def tab_briefing(cfg, scenario):
    res = guarded(run_scenario, scenario, cfg)
    if not res:
        return
    occ = res[1]
    recs = decisions.apply_statuses(res[2], scenario)
    facts = briefing.summarize(occ, recs, scenario)
    text, source = briefing.generate(facts)
    st.markdown(text)
    st.caption("Written by an LLM from the numbers below only." if source == "llm"
               else "Template briefing (no LLM key set). Same numbers, same rules.")
    with st.expander("Numbers given to the briefing"):
        st.json(facts)
    st.download_button("Export Ramp Readiness Brief", export_brief(facts, recs, text),
                       file_name=f"ramp_readiness_brief_{scenario}.md", mime="text/markdown")


def export_brief(facts: dict, recs: list[dict], text: str) -> str:
    lines = [f"# Ramp Readiness Brief — scenario {facts['scenario']}",
             f"_Generated {datetime.now():%Y-%m-%d %H:%M}. {BANNER}_", "", text, "", "## Decisions", "",
             "| ID | Category | Action | Status | Note |", "|---|---|---|---|---|"]
    lines += [f"| {r['id']} | {r['category']} | {r['action']} | {r['status']} | {r['human_note']} |" for r in recs]
    return "\n".join(lines)


# ---------- page ----------

def main():
    st.warning(f"⚠️ {BANNER}")
    st.title("RampReady · Super Bowl LXI")
    st.caption("Horizon Ridge Aviation (fictional FBO) · Van Nuys (KVNY) · Tue Feb 9 → Mon Feb 15, 2027")

    da.ensure_data()
    try:
        cfg_file = da.load_cfg()
    except da.ModelUnavailable as exc:
        st.error(str(exc))
        st.stop()
    cfg = st.session_state.get("cfg", cfg_file)
    scenario = st.sidebar.radio("Scenario", da.SCENARIOS, index=1, format_func=str.title)
    st.sidebar.caption("AI assists. People decide.")

    tabs = st.tabs(["Week view", "Recommended plan", "Scenarios", "Impact", "Disruption",
                    "Assumptions & limits", "Briefing"])
    with tabs[0]:
        tab_week(cfg, scenario)
    with tabs[1]:
        tab_plan(cfg, scenario)
    with tabs[2]:
        tab_scenarios(cfg)
    with tabs[3]:
        tab_impact(cfg, scenario)
    with tabs[4]:
        tab_disruption(cfg, scenario)
    with tabs[5]:
        tab_assumptions(cfg_file)
    with tabs[6]:
        tab_briefing(cfg, scenario)


main()
