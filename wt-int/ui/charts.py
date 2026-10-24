from datetime import datetime, timedelta
from html import escape
import plotly.graph_objects as go
import streamlit as st
from ui.theme import COLORS as C


def occupancy(before, baseline, cfg, case, after=None):
    times = [r['time'].strftime('%Y-%m-%dT%H:%M:%S') for r in before['hourly']]
    units = [r['units'] for r in before['hourly']]
    usable = before['usable_main']
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=times, y=[r['units'] for r in baseline['hourly']], name='Ordinary week',
                            line=dict(color=C['slate'], width=1.5, shape='hv'), hovertemplate='%{x|%a %d, %H:%M}<br>Ordinary: %{y:.1f} units<extra></extra>'))
    fig.add_trace(go.Scatter(x=times, y=units, name=case,
                            line=dict(color=C['blue'], width=2.5, shape='hv', dash='solid' if case == 'Expected forecast' else 'dash'),
                            hovertemplate='%{x|%a %d, %H:%M}<br>Event: %{y:.1f} units<extra></extra>'))
    fig.add_trace(go.Scatter(x=times, y=[usable]*len(times), line=dict(width=0), showlegend=False, hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=times, y=[max(usable, v) for v in units], fill='tonexty',
                            fillcolor='rgba(200,55,45,0.10)', fillpattern=dict(shape='/', fgcolor=C['red'], size=7, solidity=.12),
                            line=dict(width=0,shape='hv'), name='Shortage', hoverinfo='skip'))
    fig.add_hline(y=usable, line_dash='dash', line_color=C['asphalt'], line_width=1.4,
                  annotation_text=f'Main ramp: {usable:g} usable units', annotation_position='top left')
    limit = usable + cfg['overflow_limit_units']
    fig.add_hline(y=limit, line_dash='dash', line_color=C['yellow'], line_width=2,
                  annotation_text=f'Overflow limit: {limit:g} units', annotation_position='top left')
    if after:
        fig.add_hline(y=after['capacity'], line_color=C['green'], line_width=2,
                      annotation_text=f'With proposed plan: {after["capacity"]:g} units', annotation_position='bottom right')
    game = cfg['game_day'] + 'T12:00:00'
    fig.add_shape(type='line', x0=game, x1=game, y0=0, y1=1, yref='paper', line=dict(color=C['line'], width=1, dash='dot'))
    fig.add_annotation(x=game,y=1.03,yref='paper',text='Game day',showarrow=False,font=dict(size=12,color=C['slate']))
    if before['first_shortage']:
        fig.add_annotation(x=before['first_shortage'].strftime('%Y-%m-%dT%H:%M:%S'), y=usable, text='First shortage',
                           showarrow=True, arrowhead=0, ax=-25, ay=42, font=dict(size=12,color=C['red']), bgcolor=C['paper'])
    fig.update_layout(height=310, margin=dict(l=12,r=20,t=42,b=52), paper_bgcolor=C['paper'], plot_bgcolor=C['paper'],
                      font=dict(family='Barlow, sans-serif',size=13,color=C['asphalt']),
                      legend=dict(orientation='h',x=0,y=-.28,font=dict(size=12)), hovermode='x unified',
                      yaxis=dict(title='Parking units',range=[0,max(limit,max(units),max(r['units'] for r in baseline['hourly']))*1.18],gridcolor=C['line'],zeroline=False),
                      xaxis=dict(tickmode='array',tickvals=[times[i*24+12] for i in range(cfg['window_days'])],
                                 ticktext=[before['hourly'][i*24]['time'].strftime('%a %d') for i in range(cfg['window_days'])],
                                 range=[times[0],times[-1]],showgrid=False))
    return fig


def hour_strip(result, cfg):
    """168 actual hourly peaks. Outline encodes over-capacity without color alone."""
    html = '<div class="strip-wrap"><div class="ramp-strip"><span></span>'
    for h in range(24):
        html += f'<span>{h:02d}</span>' if h % 3 == 0 else '<span></span>'
    for day in range(cfg['window_days']):
        rows = result['hourly'][day*24:(day+1)*24]
        html += f'<span class="strip-label">{rows[0]["time"].strftime("%a %d")}</span>'
        for row in rows:
            ratio = row['units']/result['capacity'] if result['capacity'] else 0
            over = row['units'] > result['capacity']
            color = C['red'] if over else C['blue'] if ratio >= .7 else C['line']
            title = f'{row["time"].strftime("%a %H:%M")}: {row["units"]:g}/{result["capacity"]:g} units' + (' — over capacity' if over else '')
            style = f'background:{color};' + (f'outline:1px solid {C["red"]};outline-offset:1px;' if over else '')
            html += f'<span class="hour-cell" role="img" aria-label="{escape(title)}" title="{escape(title)}" style="{style}"></span>'
    st.markdown(html + '</div></div>', unsafe_allow_html=True)
    st.caption('Each square is one hour. Gray: below 70% of usable space. Blue: 70–100%. Red with outline: over capacity. Scroll sideways on small screens.')
