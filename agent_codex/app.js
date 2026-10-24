const $ = (s, root = document) => root.querySelector(s);
const main = $('#main');
const H = 24;
let data;
let state = { scenario: 'Medium', day: '', now: '', view: 'today', editId: null, theme: localStorage.getItem('shift-theme') || 'dark', movements: readStore('shift-movements', []), weather: readStore('shift-weather', {}), proposals: readStore('shift-proposals', {}) };
function readStore(key, fallback) { try { const value = JSON.parse(localStorage.getItem(key)); return value && typeof value === 'object' ? value : fallback; } catch { return fallback; } }
function save(key, value) { localStorage.setItem(key, JSON.stringify(value)); }
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = value => Number(value).toFixed(1);
const pct = value => `${Math.round(value * 100)}%`;
const dateLabel = day => `${day.weekday.slice(0, 3)} ${Number(day.date.slice(-2))} Feb`;
const timeLabel = h => `${String(h).padStart(2, '0')}:00`;
const minuteLabel = minutes => `${String(Math.floor((minutes % 1440) / 60)).padStart(2,'0')}:${String(minutes % 60).padStart(2,'0')}`;
const weatherNames = {clear:'Clear',rain:'Rain',heavy_rain:'Heavy rain',heavy_fog:'Heavy fog'};
const movementNames = {arrival:'Arrival',departure:'Departure'};
const terminal = m => m.status === (m.type === 'arrival' ? 'landed' : 'departed');

fetch('agent_data.json').then(r => { if (!r.ok) throw Error('Data unavailable'); return r.json(); }).then(d => {
  data = d;
  state.day = d.days[0].date;
  state.now = `${String(peakHour(d.days[0], 'arrivals')).padStart(2,'0')}:00`;
  $('#now').value = state.now;
  $('#day').innerHTML = d.days.map(day => `<option value="${day.date}">${dateLabel(day)}</option>`).join('');
  document.body.dataset.theme = state.theme;
  updateThemeButton();
  render();
}).catch(error => { main.innerHTML = `<div class="card">Could not load agent_data.json. Run the site with <code>python3 -m http.server</code>.</div>`; console.error(error); });

function dayAt(index) { return data.days[index]; }
function selectedIndex() { return data.days.findIndex(d => d.date === state.day); }
function shares(day, type) { return day.game_day ? data.game_day_restriction.hour_shares[type] : data.hourly_profile.shares[`${day.day_type}_${type}`]; }
function peakHour(day, type) { const arr = shares(day, type); return arr.indexOf(Math.max(...arr)); }
function topWindow(day, type) { const arr = shares(day, type); const starts = Array.from({length:H-2}, (_, i) => i); starts.sort((a,b) => (arr[b]+arr[b+1]+arr[b+2])-(arr[a]+arr[a+1]+arr[a+2])); return `${timeLabel(starts[0])}–${timeLabel(starts[0]+3)}`; }
function weatherMultiplier(base, weather) {
  if (weather === 'clear') return 1;
  const effects = data.weather.effects[weather];
  return 1 + base.share_part91 * effects.part91.effect + base.share_part135 * effects.part135.effect;
}
function plans() {
  let carryA = 0, carryD = 0;
  return data.days.map(day => {
    const base = day.scenarios[state.scenario], weather = state.weather[day.date] || 'clear';
    const mult = weatherMultiplier(base, weather);
    const inA = carryA, inD = carryD;
    const ownA = base.expected_arrivals * mult, ownD = base.expected_departures * mult;
    carryA = Math.max(0, base.expected_arrivals - ownA);
    carryD = Math.max(0, base.expected_departures - ownD);
    return {day, base, weather, mult, inA, inD, lostA:carryA, lostD:carryD,
      a:ownA + inA, d:ownD + inD,
      ar:base.arrivals_range90.map(x => Math.max(0,x*mult+inA)),
      dr:base.departures_range90.map(x => Math.max(0,x*mult+inD))};
  });
}
function movementsFor(date) { return state.movements.filter(m => m.date === date).sort((a,b) => a.time.localeCompare(b.time) || a.type.localeCompare(b.type)); }
function count(date, type) { return movementsFor(date).filter(m => m.type === type).length; }
function currentPlan() { return plans()[selectedIndex()]; }
function hourly(plan) {
  const booked = movementsFor(plan.day.date);
  return Array.from({length:H}, (_,h) => {
    const a = plan.a * shares(plan.day,'arrivals')[h];
    const d = plan.d * shares(plan.day,'departures')[h];
    return {h,a,d,ar:plan.ar.map(x=>x*shares(plan.day,'arrivals')[h]),dr:plan.dr.map(x=>x*shares(plan.day,'departures')[h]),
      ba:booked.filter(m=>m.type==='arrival'&&Number(m.time.slice(0,2))===h).length,
      bd:booked.filter(m=>m.type==='departure'&&Number(m.time.slice(0,2))===h).length};
  });
}
function nextWindow() {
  const start = Number(state.now.slice(0,2))*60 + Number(state.now.slice(3,5));
  const end = Math.min(start + 180, (data.days.length-selectedIndex())*1440);
  const ps = plans();
  let a=0,d=0;
  for(let minute=start;minute<end;){
    const index=selectedIndex()+Math.floor(minute/1440), h=Math.floor((minute%1440)/60);
    const boundary=Math.min(end,Math.floor(minute/60+1)*60),fraction=(boundary-minute)/60;
    a+=ps[index].a*shares(ps[index].day,'arrivals')[h]*fraction;
    d+=ps[index].d*shares(ps[index].day,'departures')[h]*fraction;
    minute=boundary;
  }
  const upcoming=state.movements.filter(m=>{
    const offset=data.days.findIndex(day=>day.date===m.date)-selectedIndex();
    if(offset<0)return false;
    const minute=offset*1440+Number(m.time.slice(0,2))*60+Number(m.time.slice(3,5));
    return minute>=start&&minute<end;
  }).sort((x,y)=>x.date.localeCompare(y.date)||x.time.localeCompare(y.time));
  return {a,d,upcoming,end,truncated:end<start+180,label:`${minuteLabel(start)}–${minuteLabel(end)}${end>=1440?' next day':''}`};
}
function updateThemeButton(){ $('#theme').textContent = state.theme === 'dark' ? '☼' : '☾'; $('#theme').setAttribute('aria-label', `Switch to ${state.theme === 'dark' ? 'light' : 'dark'} theme`); }
function render() {
  $('#scenario').value = state.scenario; $('#day').value = state.day; $('#now').value = state.now; $('#top-weather').value = state.weather[state.day] || 'clear';
  document.querySelectorAll('.tab').forEach(b => { const active = b.dataset.view === state.view; b.classList.toggle('active',active); active ? b.setAttribute('aria-current','page') : b.removeAttribute('aria-current'); });
  main.innerHTML = state.view === 'today' ? todayView() : state.view === 'week' ? weekView() : evidenceView();
}
function weatherSelect(date) {
  const selected = state.weather[date] || 'clear';
  return `<select class="weather-select" data-date="${date}" aria-label="Weather for ${date}">${Object.entries(weatherNames).map(([value,label]) => `<option value="${value}" ${selected===value?'selected':''}>${label}${value==='clear'?'':` · ${pct(data.weather.february_probability[value])} Feb`}</option>`).join('')}</select>`;
}
function todayView() {
  const plan = currentPlan(), hours = hourly(plan), nowHour = Number(state.now.slice(0,2)), next = nextWindow();
  const arrivals = count(plan.day.date,'arrival'), departures = count(plan.day.date,'departure');
  const peak = [...hours].sort((a,b)=>b.a-a.a)[0];
  const peakHours = new Set([...hours].sort((a,b)=>b.a-a.a).slice(0,3).map(x=>x.h));
  const upcoming = next.upcoming;
  const gap = Math.max(0, plan.a - arrivals);
  const max = Math.max(...hours.map(x=>Math.max(x.ar[1],x.dr[1],x.ba,x.bd)),.1);
  const bookedLine = `${arrivals} arrivals booked, about ${fmt(plan.a)} expected: plan for about ${fmt(gap)} more unannounced arrival${gap===1?'':'s'}.`;
  return `<section class="hero" aria-label="Today summary">
    <div class="hero-main"><div class="eyebrow">TODAY / ${dateLabel(plan.day)} / ${state.scenario} CASE</div><h1 class="page-title">The desk, at a glance.</h1><div class="hero-message">${esc(bookedLine)}</div>
      <div class="hero-stats"><div class="metric"><b class="arrival-text">${fmt(plan.a)}</b><small>Expected landings<br>90% ${fmt(plan.ar[0])}–${fmt(plan.ar[1])} · ordinary ${fmt(plan.base.ordinary_arrivals)}</small></div><div class="metric"><b class="departure-text">${fmt(plan.d)}</b><small>Expected departures<br>90% ${fmt(plan.dr[0])}–${fmt(plan.dr[1])} · ordinary ${fmt(plan.base.ordinary_departures)}</small></div><div class="metric"><b>${timeLabel(peak.h)}</b><small>Busiest landing hour<br>${fmt(peak.a)} expected landings</small></div></div>
      <p class="fine">Adjusted expected = scenario forecast × weighted weather effect + previous day's delayed movements. 90% range uses the same factor and carry. Booked gap = max(0, expected arrivals − entered arrivals). All figures are aircraft movements.</p>
    </div><div class="hero-aside card"><div><div class="eyebrow">${next.truncated?'TO PLAN END':'NEXT 3 HOURS'} · ${next.label}</div><div class="big">${upcoming.length} booked movements</div><p class="fine">${fmt(next.a)} expected landings · ${fmt(next.d)} expected departures from the placeholder curve, prorated for partial hours.</p></div><div>${upcoming.length ? upcoming.slice(0,4).map(m=>`<div class="next-item"><span>${m.date!==state.day?esc(dateLabel(data.days.find(x=>x.date===m.date)))+' · ':''}${esc(m.time)} · <span class="${m.type==='arrival'?'arrival-text':'departure-text'}">${movementNames[m.type]}</span> ${esc(m.tail||'Tail pending')}</span><strong>${esc(m.status)}</strong></div>`).join('') : '<div class="empty">No entered movements in this window.</div>'}</div></div></section>
    <div class="grid"><div class="stack"><section class="card"><div class="section-head"><div><h2 class="section-title">24-hour movement timeline</h2><div class="section-note">Forecast spread by hour · live entries replace the placeholder for covered hours</div></div><span class="badge warn">Placeholder hourly shape</span></div>
      <div class="legend"><span><i style="background:var(--arrival)"></i>Landings</span><span><i style="background:var(--departure)"></i>Departures</span><span>□ 90% spread</span><span>│ Entered count</span></div>
      <div class="timeline" role="img" aria-label="Hourly forecast and booked aircraft movements">${hours.map(x => hourRow(x,max,nowHour,peakHours)).join('')}</div><div class="timeline-axis"><span>0</span><span>${fmt(max/2)}</span><span>${fmt(max)} aircraft / hour</span></div><p class="fine">Highlighted rows are the three busiest landing hours. Hour value = adjusted daily expected × the day's hour share. Outline = daily 90% bounds × hour share. The curve is a placeholder, not observed hourly traffic. Entered counts are shown in place of the estimate for hours they cover.</p><details><summary>Hourly values and ranges</summary><div class="table-wrap"><table class="test-table"><thead><tr><th>Hour</th><th>Land forecast · 90%</th><th>Land entered</th><th>Depart forecast · 90%</th><th>Depart entered</th></tr></thead><tbody>${hours.map(x=>`<tr><td>${timeLabel(x.h)}</td><td>${fmt(x.a)} · ${fmt(x.ar[0])}–${fmt(x.ar[1])}</td><td>${x.ba}</td><td>${fmt(x.d)} · ${fmt(x.dr[0])}–${fmt(x.dr[1])}</td><td>${x.bd}</td></tr>`).join('')}</tbody></table></div></details>
      ${plan.day.game_day?`<div class="callout warning">Assumed game-day restriction: no private movements 14:30–20:30, based on the Super Bowl LVI advisory. The supplied release curve places blocked movements after 20:30. This is not a published 2027 TFR.</div>`:''}
      </section><section class="card"><div class="section-head"><div><h2 class="section-title">Day conditions</h2><div class="section-note">Weather changes this day and rolls lost movements to tomorrow.</div></div></div><div class="weather-row"><strong>${dateLabel(plan.day)}</strong>${weatherSelect(plan.day.date)}</div><div class="weather-info fine">${plan.weather==='clear'?'Clear: no weather adjustment.':`Measured weighted effect: ${pct(plan.mult-1)} on this day's own movements. Lost today: ${fmt(plan.lostA+plan.lostD)} moves to tomorrow.`} ${plan.inA+plan.inD>0?`+${fmt(plan.inA+plan.inD)} movements moved from ${dateLabel(dayAt(selectedIndex()-1))}.`:''}</div><p class="fine">Factor = 1 + Part 91 share × measured effect + Part 135 share × measured effect. A negative effect's lost movements shift one day forward. February weather probabilities appear in the selector.</p></section></div>
    <div class="stack"><section class="card" id="entry-card"><div class="section-head"><div><h2 class="section-title">Quick movement entry</h2><div class="section-note">Keyboard first · press Alt + N to focus time</div></div><span class="badge ok">Local only</span></div>
      <form id="entry-form"><div class="form-grid"><div class="field"><label for="entry-time">Time · Pacific</label><input id="entry-time" name="time" type="time" required></div><div class="field"><label for="entry-type">Movement</label><select id="entry-type" name="type"><option value="arrival">Landing</option><option value="departure">Departure</option></select></div><div class="field"><label for="entry-tail">Tail number · optional</label><input id="entry-tail" name="tail" type="text" maxlength="20" autocomplete="off" placeholder="e.g. N123AB"></div><div class="field"><label for="entry-size">Aircraft size</label><select id="entry-size" name="size"><option value="light">Light</option><option value="midsize">Midsize</option><option value="large">Large</option></select></div><div class="field full"><label for="entry-status">Status</label><select id="entry-status" name="status"><option value="expected">Expected</option><option value="confirmed">Confirmed</option><option value="landed">Landed</option><option value="departed">Departed</option></select></div></div><div class="form-actions"><button class="button primary" type="submit">${state.editId?'Save edit':'Add movement'} ↵</button>${state.editId?'<button class="button ghost" type="button" data-action="cancel-edit">Cancel edit</button>':''}</div></form><p class="fine">No passenger data is entered or stored. This board does not authorize a movement or accept, refuse or cancel an aircraft.</p></section>
      <section class="card"><div class="section-head"><div><h2 class="section-title">Live arrivals / departures</h2><div class="section-note">${arrivals} landings · ${departures} departures entered</div></div><div class="board-tools"><button class="button ghost" data-action="import">Import CSV</button><button class="button ghost" data-action="export">Export CSV</button></div></div><div class="board-list">${movementsFor(plan.day.date).length ? movementsFor(plan.day.date).map(boardRow).join('') : '<div class="empty">No aircraft entered yet. Add one above or import a CSV.</div>'}</div></section>
      <section class="card"><h2 class="section-title">Shift cue</h2><p class="subtitle">${esc(proposalText(plan, plans()))}</p><p class="fine">Suggestions support the agent's judgment. Confirm timing and PPR through normal procedures.</p></section></div></div>`;
}
function hourRow(x,max,nowHour,peakHours) {
  const coveredA=x.ba>0, coveredD=x.bd>0;
  const bar=(type,value,range,booked) => `<div class="bar-track" style="color:var(--${type})"><div class="bar-range" style="left:${Math.min(100,range[0]/max*100)}%;width:${Math.min(100,(range[1]-range[0])/max*100)}%"></div><div class="bar-fill ${type}" style="width:${Math.min(100,(booked||value)/max*100)}%"></div>${booked?`<div class="booked-dot" style="left:${Math.min(99,booked/max*100)}%"></div>`:''}</div>`;
  const label=`${timeLabel(x.h)}: landings ${coveredA?x.ba+' entered':fmt(x.a)+' forecast'}, 90% ${fmt(x.ar[0])} to ${fmt(x.ar[1])}; departures ${coveredD?x.bd+' entered':fmt(x.d)+' forecast'}, 90% ${fmt(x.dr[0])} to ${fmt(x.dr[1])}`;
  return `<div class="hour-row ${peakHours.has(x.h)?'peak':''} ${x.h===nowHour?'current':''}" title="${esc(label)}" aria-label="${esc(label)}"><div class="hour-label">${timeLabel(x.h)}</div><div class="bars">${bar('arrival',x.a,x.ar,x.ba)}${bar('departure',x.d,x.dr,x.bd)}</div><div class="hour-numbers"><span class="arrival-text">${coveredA?x.ba:fmt(x.a)}</span><span class="departure-text">${coveredD?x.bd:fmt(x.d)}</span></div></div>`;
}
function boardRow(m) {
  const done = terminal(m);
  const inRestriction=m.date===data.game_day_restriction.date&&m.time>=data.game_day_restriction.start&&m.time<data.game_day_restriction.end;
  return `<div class="board-row"><strong>${esc(m.time)}</strong><span class="${m.type==='arrival'?'arrival-text':'departure-text'}">${m.type==='arrival'?'LAND':'DEPART'}</span><div><strong>${esc(m.tail||'Tail pending')}</strong><div class="muted">${esc(m.size)} · ${esc(m.status)}${inRestriction?' · Review assumed restriction':''}</div></div><div class="row-actions">${done?'':`<button class="button" data-action="complete" data-id="${esc(m.id)}">Mark ${m.type==='arrival'?'landed':'departed'}</button>`}<button class="button" data-action="edit" data-id="${esc(m.id)}">Edit</button><button class="button danger" data-action="delete" data-id="${esc(m.id)}">Delete entry</button></div></div>`;
}
function weekView() {
  const ps=plans(), busiestA=ps.reduce((a,b)=>a.a>b.a?a:b), busiestD=ps.reduce((a,b)=>a.d>b.d?a:b);
  const max=Math.max(...ps.map(p=>Math.max(p.ar[1],p.dr[1])));
  return `<div class="eyebrow">WEEK PLAN / 11–17 FEB 2027</div><h1 class="page-title">The whole week, one scan.</h1><p class="subtitle">Select a day to open its desk view. Forecasts are aircraft movements per day; outlines and values include the 90% range.</p>
    <section class="hero" style="margin-top:18px"><div class="hero-main"><div class="eyebrow">BUSIEST LANDING DAY</div><div class="hero-message">${dateLabel(busiestA.day)} · ${fmt(busiestA.a)} landings</div><p class="subtitle">90% ${fmt(busiestA.ar[0])}–${fmt(busiestA.ar[1])} · ordinary ${fmt(busiestA.base.ordinary_arrivals)} · peak window ${topWindow(busiestA.day,'arrivals')}</p></div><div class="card"><div class="eyebrow">BUSIEST DEPARTURE DAY</div><div class="hero-message">${dateLabel(busiestD.day)} · ${fmt(busiestD.d)}</div><p class="subtitle">90% ${fmt(busiestD.dr[0])}–${fmt(busiestD.dr[1])} · ordinary ${fmt(busiestD.base.ordinary_departures)} · peak ${topWindow(busiestD.day,'departures')}</p></div></section>
    <div class="section-head"><div><h2 class="section-title">Daily movement outlook</h2><div class="section-note">Blue landings · amber departures · □ 90% range · │ ordinary week</div></div><span class="badge">${state.scenario} scenario</span></div><div class="week-grid">${ps.map(p=>weekCard(p,max)).join('')}</div>
    <p class="fine">Bar fill = adjusted expected ÷ largest upper 90% bound in this view. Each range is printed on its card. Adjusted expected = scenario forecast × weather factor + movements delayed from yesterday. Ordinary values come directly from the data and remain a fixed comparison.</p>
    <div class="grid" style="margin-top:20px"><section class="card"><div class="section-head"><div><h2 class="section-title">Weather by day</h2><div class="section-note">Measured effects are weighted by each day's Part 91 / Part 135 share.</div></div></div><div class="weather-list">${ps.map(p=>`<div class="weather-row"><strong>${dateLabel(p.day)}</strong>${weatherSelect(p.day.date)}</div>`).join('')}</div><p class="fine">${ps.filter(p=>p.inA+p.inD>0).map(p=>`+${fmt(p.inA+p.inD)} movements moved from ${dateLabel(dayAt(data.days.indexOf(p.day)-1))} to ${dateLabel(p.day)}.`).join(' ') || 'No delayed movements selected.'} ${ps.at(-1).lostA+ps.at(-1).lostD>0?`${fmt(ps.at(-1).lostA+ps.at(-1).lostD)} movements shift beyond this planning window.`:''}</p></section>
    <section class="card"><div class="section-head"><div><h2 class="section-title">Day-specific proposals</h2><div class="section-note">Acknowledge or dismiss with a note; your action is saved locally.</div></div></div><div class="proposal-list">${ps.map((p,i)=>proposalCard(p,ps,i)).join('')}</div></section></div>
    <section class="card" style="margin-top:16px"><h2 class="section-title">Parking · secondary indicator</h2><p class="subtitle">${ps.map(p=>`${dateLabel(p.day)}: ${fmt(p.base.parking_su_p50)} su median / ${fmt(p.base.parking_su_p90)} su P90`).join(' · ')}</p><p class="fine">Normal ramp capacity: ${fmt(ps[0].base.ramp_capacity_su)} su. This indicator comes from the scenario data; weather is not applied to parking.</p></section>`;
}
function weekCard(p,max) {
  const width = (x)=>`${Math.max(0,Math.min(100,x/max*100))}%`;
  const mini=(value,range,ordinary,color)=>`<div class="mini-line"><div class="mini-track"><span class="mini-fill" style="width:${width(value)};background:var(--${color})"></span><span class="mini-range" style="left:${width(range[0])};width:${width(range[1]-range[0])}"></span><span class="mini-ordinary" style="left:${width(ordinary)}"></span></div><small class="${color}-text">${fmt(value)}</small></div>`;
  return `<article class="day-card ${p.day.date===state.day?'selected':''}" data-open-day="${p.day.date}" tabindex="0" role="button" aria-label="Open ${dateLabel(p.day)} desk view"><div class="date">${dateLabel(p.day)}</div><div class="flags">${p.day.game_day?'<span class="badge warn">Game day</span>':p.day.presidents_day?'<span class="badge">Presidents’ Day</span>':'<span class="badge">Planning day</span>'}</div><div class="mini-bars">${mini(p.a,p.ar,p.base.ordinary_arrivals,'arrival')}${mini(p.d,p.dr,p.base.ordinary_departures,'departure')}</div><div class="range">Land 90% ${fmt(p.ar[0])}–${fmt(p.ar[1])}<br>Depart 90% ${fmt(p.dr[0])}–${fmt(p.dr[1])}</div><div class="ordinary">Ordinary ${fmt(p.base.ordinary_arrivals)} in / ${fmt(p.base.ordinary_departures)} out</div>${p.inA+p.inD>0?`<div class="fine">+${fmt(p.inA+p.inD)} moved from prior day</div>`:''}<div class="fine">Peak land ${topWindow(p.day,'arrivals')}<br>Peak out ${topWindow(p.day,'departures')}</div></article>`;
}
function proposalText(p,ps) {
  const i=ps.indexOf(p), biggestA=ps.reduce((a,b)=>a.a>b.a?a:b), biggestD=ps.reduce((a,b)=>a.d>b.d?a:b);
  if(p.day.game_day) return `Check arrival and departure timing before the assumed 14:30–20:30 pause; reconfirm late PPR/slot details for the release wave after 20:30.`;
  if(p.day.presidents_day) return `Prepare the departure board for the Presidents' Day wave around ${topWindow(p.day,'departures')}; reconfirm ETDs and any PPR/slot details.`;
  if(p.inA+p.inD>0) return `Weather shifted about ${fmt(p.inA+p.inD)} movements from yesterday. Reconfirm landing and departure times before updating the board.`;
  if(p===biggestA) return `Keep the arrival board ready for the week's busiest landing day; reconfirm ETAs and PPR details around ${topWindow(p.day,'arrivals')}.`;
  if(p===biggestD) return `Check ETDs and slot details before the week's busiest departure window, ${topWindow(p.day,'departures')}.`;
  if(p.weather!=='clear') return `Watch weather-driven timing changes today and reconfirm movements expected to shift into ${i+1<ps.length?dateLabel(ps[i+1].day):'the following day'}.`;
  return `Review arrival ETAs around ${topWindow(p.day,'arrivals')} and departure ETDs around ${topWindow(p.day,'departures')}; update the live board as confirmations arrive.`;
}
function proposalCard(p,ps,i) {
  const record=state.proposals[p.day.date]||{};
  return `<article class="proposal"><header><h3>${dateLabel(p.day)}</h3><span class="badge ${record.status==='acknowledged'?'ok':''}">${record.status||'Open'}</span></header><p>${esc(proposalText(p,ps))}</p><div class="proposal-actions"><input aria-label="Note for ${dateLabel(p.day)}" data-proposal-note="${p.day.date}" value="${esc(record.note||'')}" placeholder="Add a note"><button class="button" data-action="proposal" data-date="${p.day.date}" data-status="acknowledged">Acknowledge</button><button class="button ghost" data-action="proposal" data-date="${p.day.date}" data-status="dismissed">Dismiss</button></div></article>`;
}
function evidenceView() {
  const a=data.accuracy, metrics=a.rolling_backtest_2025_wape;
  const events=data.super_bowl_test.filter(x=>x.metric==='air_taxi');
  return `<div class="eyebrow">EVIDENCE / LIMITS</div><h1 class="page-title">Know what the board knows.</h1><p class="subtitle">The daily model is estimated. Hourly timing is a placeholder until movements are entered.</p><div class="evidence-grid" style="margin-top:18px"><section class="card"><h2 class="section-title">Forecast accuracy</h2><div class="hero-stats"><div class="metric"><b>${pct(metrics.model)}</b><small>Rolling 2025 daily error · model</small></div><div class="metric"><b>${pct(a.coverage_90)}</b><small>Observed coverage of 90% range</small></div></div><p class="fine">${esc(a.note)}</p><div class="assumption-row"><span>Last week</span><strong>${pct(metrics.naive_last_week)}</strong></div><div class="assumption-row"><span>Last year</span><strong>${pct(metrics.seasonal_naive_last_year)}</strong></div><div class="assumption-row"><span>8-week weekday mean</span><strong>${pct(metrics.weekday_mean_8w)}</strong></div><div class="assumption-row"><span>Overall mean</span><strong>${pct(metrics.overall_mean)}</strong></div><p class="fine">WAPE compares absolute daily error with actual movements. The model beats these four simple baselines in this backtest.</p></section>
    <section class="card"><h2 class="section-title">Eight-city Super Bowl test</h2><p class="fine">Air taxi excess versus ordinary traffic in eight host markets. Outcomes vary widely; the LAX scenario should not be treated as certainty.</p><div class="table-wrap"><table class="test-table"><thead><tr><th>Game</th><th>Airport group</th><th>Excess</th><th>vs scenario</th></tr></thead><tbody>${events.map(x=>`<tr><td>${esc(x.event)}</td><td>${esc(x.airports)}</td><td>${pct(Number(x.excess))}</td><td>${esc(x.position.replaceAll('_',' '))}</td></tr>`).join('')}</tbody></table></div><p class="fine">Rows use the air taxi metric from the supplied multi-metric test. ${data.super_bowl_test.length} metric rows are in the source data.</p></section>
    <section class="card"><h2 class="section-title">Assumptions and provenance</h2>${data.key_assumptions.map(x=>`<div class="assumption-row"><span>${esc(x.name)}</span><span>${esc(x.value)}</span><span class="badge">${esc(x.class)}</span></div>`).join('')}<p class="fine">Hourly shares: ${esc(data.hourly_profile.note)} Game-day restriction: ${esc(data.game_day_restriction.status)}.</p><h3 class="section-title" style="margin-top:22px">Scenario basis</h3>${Object.entries(data.scenarios).map(([name,description])=>`<div class="assumption-row"><strong>${esc(name)}</strong><span>${esc(description)}</span></div>`).join('')}<h3 class="section-title" style="margin-top:22px">Weather effects <span class="badge ok">Measured</span></h3><p class="fine">Effect on movements, with 95% confidence interval. February probability is the chance of each condition.</p><div class="table-wrap"><table class="test-table"><thead><tr><th>Weather</th><th>Feb chance</th><th>Part 91 effect · 95%</th><th>Part 135 effect · 95%</th></tr></thead><tbody>${Object.entries(data.weather.effects).map(([key,value])=>`<tr><td>${esc(weatherNames[key])}</td><td>${pct(data.weather.february_probability[key])}</td><td>${pct(value.part91.effect)} · ${pct(value.part91.ci95[0])} to ${pct(value.part91.ci95[1])}</td><td>${pct(value.part135.effect)} · ${pct(value.part135.ci95[0])} to ${pct(value.part135.ci95[1])}</td></tr>`).join('')}</tbody></table></div></section>
    <section class="card"><h2 class="section-title">Human in command</h2><p class="subtitle">${esc(data.meta.human_in_command)}</p><div class="callout warning" style="margin-top:16px"><strong>What decision should AI never be allowed to make?</strong><br>${esc(data.meta.never_allowed)}</div><p class="fine">${esc(data.meta.privacy)}</p><h3 class="section-title" style="margin-top:24px">Sources</h3>${data.sources.map(s=>`<div class="source-row"><a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.name)} ↗</a></div>`).join('')}<p class="fine">${esc(data.weather.source)}.</p></section></div>`;
}

$('#scenario').addEventListener('change',e=>{ state.scenario=e.target.value;render(); });
$('#day').addEventListener('change',e=>{ state.day=e.target.value;state.editId=null;render(); });
$('#top-weather').addEventListener('change',e=>{state.weather[state.day]=e.target.value;save('shift-weather',state.weather);render();});
$('#now').addEventListener('change',e=>{ state.now=e.target.value;render(); });
$('#theme').addEventListener('click',()=>{state.theme=state.theme==='dark'?'light':'dark';document.body.dataset.theme=state.theme;localStorage.setItem('shift-theme',state.theme);updateThemeButton();});
$('.tabs').addEventListener('click',e=>{const b=e.target.closest('[data-view]');if(!b)return;state.view=b.dataset.view;state.editId=null;render();window.scrollTo({top:0,behavior:'instant'});});
main.addEventListener('change',e=>{if(e.target.matches('.weather-select')){state.weather[e.target.dataset.date]=e.target.value;save('shift-weather',state.weather);render();}});
main.addEventListener('change',e=>{if(e.target.id==='entry-type'){const status=$('#entry-status');for(const option of status.options){if(option.value==='landed')option.disabled=e.target.value!=='arrival';if(option.value==='departed')option.disabled=e.target.value!=='departure';}if(status.selectedOptions[0]?.disabled)status.value='expected';}});
main.addEventListener('submit',e=>{if(e.target.id!=='entry-form')return;e.preventDefault();const form=new FormData(e.target);const type=form.get('type');const status=form.get('status');const m={id:state.editId||String(Date.now())+Math.random().toString(36).slice(2),date:state.day,time:form.get('time'),type,tail:String(form.get('tail')||'').trim().toUpperCase(),size:form.get('size'),status};if(!m.time)return;if((type==='arrival'&&status==='departed')||(type==='departure'&&status==='landed')){alert('Use Landed for arrivals or Departed for departures.');return;}if(state.editId){state.movements=state.movements.map(x=>x.id===state.editId?m:x);}else state.movements.push(m);save('shift-movements',state.movements);state.editId=null;render();$('#entry-time')?.focus();});
main.addEventListener('click',e=>{
  const day=e.target.closest('[data-open-day]');if(day){state.day=day.dataset.openDay;state.view='today';render();window.scrollTo({top:0,behavior:'instant'});return;}
  const b=e.target.closest('[data-action]');if(!b)return;
  const action=b.dataset.action,id=b.dataset.id,m=state.movements.find(x=>x.id===id);
  if(action==='edit'&&m){state.editId=id;state.day=m.date;render();const form=$('#entry-form');for(const field of ['time','type','tail','size','status'])form.elements[field].value=m[field];$('#entry-time').focus();$('#entry-card').scrollIntoView({block:'center'});}
  if(action==='cancel-edit'){state.editId=null;render();}
  if(action==='complete'&&m){m.status=m.type==='arrival'?'landed':'departed';save('shift-movements',state.movements);render();}
  if(action==='delete'&&m){if(!confirm(`Delete local board entry for ${m.type} at ${m.time}${m.tail?' · '+m.tail:''}? This does not cancel the aircraft movement.`))return;state.movements=state.movements.filter(x=>x.id!==id);save('shift-movements',state.movements);render();}
  if(action==='export')exportCSV();
  if(action==='import')$('#csv-file').click();
  if(action==='proposal'){const date=b.dataset.date,note=$(`[data-proposal-note="${date}"]`)?.value||'';state.proposals[date]={status:b.dataset.status,note};save('shift-proposals',state.proposals);render();}
});
main.addEventListener('keydown',e=>{const card=e.target.closest('[data-open-day]');if(card&&(e.key==='Enter'||e.key===' ')){e.preventDefault();card.click();}});
document.addEventListener('keydown',e=>{if(e.altKey&&e.key.toLowerCase()==='n'){e.preventDefault();state.view='today';render();$('#entry-time').focus();}});

function csvCell(value){return `"${String(value??'').replaceAll('"','""')}"`;}
function exportCSV(){const fields=['date','time','type','tail','size','status'];const csv=[fields.join(','),...state.movements.map(m=>fields.map(f=>csvCell(m[f])).join(','))].join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='shift-board-movements.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function parseCSV(text){const rows=[];let row=[],cell='',quoted=false;for(let i=0;i<text.length;i++){const c=text[i];if(quoted){if(c==='"'&&text[i+1]==='"'){cell+='"';i++;}else if(c==='"')quoted=false;else cell+=c;}else if(c==='"')quoted=true;else if(c===','){row.push(cell);cell='';}else if(c==='\n'){row.push(cell.replace(/\r$/,''));rows.push(row);row=[];cell='';}else cell+=c;}if(cell||row.length){row.push(cell.replace(/\r$/,''));rows.push(row);}return rows;}
$('#csv-file').addEventListener('change',async e=>{const file=e.target.files[0];if(!file)return;try{const rows=parseCSV(await file.text());const header=rows.shift().map(x=>x.trim().toLowerCase());const required=['date','time','type','tail','size','status'];if(required.some(x=>!header.includes(x)))throw Error('CSV needs date,time,type,tail,size,status columns.');let added=0,skipped=0;for(const row of rows){if(row.every(x=>!x.trim()))continue;const obj=Object.fromEntries(required.map(x=>[x,(row[header.indexOf(x)]||'').trim()]));if(!data.days.some(d=>d.date===obj.date)||!/^([01]\d|2[0-3]):[0-5]\d$/.test(obj.time)||!['arrival','departure'].includes(obj.type)||!['light','midsize','large'].includes(obj.size)||!['expected','confirmed','landed','departed'].includes(obj.status)||(obj.type==='arrival'&&obj.status==='departed')||(obj.type==='departure'&&obj.status==='landed')){skipped++;continue;}state.movements.push({...obj,id:String(Date.now())+Math.random().toString(36).slice(2),tail:obj.tail.slice(0,20).toUpperCase()});added++;}save('shift-movements',state.movements);render();alert(`Imported ${added} movements${skipped?`; skipped ${skipped} invalid rows`:''}.`);}catch(err){alert(err.message);}e.target.value='';});
