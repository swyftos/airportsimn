import { getView, buildIllustration, dateLabel, su, pct, money, HOURS, clockLabel, restrictionAt } from './model.js';
import { createLayout, buildPlacements } from './layout.js';
import { createStandViews, escapeHTML } from './views.js';

const $ = selector => document.querySelector(selector);
let data, view, snapshots, placements, layout, rampScene, standViews, selection = null;
const state = { scenario: null, situation: null, prepared: false, tick: 0, playing: false, phase: 0, instant: true };
const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');

function selectedDay() { return view.days[Math.floor(state.tick / HOURS)]; }
function activeSnapshot() { return snapshots[state.tick]; }

function renderControls() {
  $('#scenario-options').innerHTML = Object.keys(data.scenarios).map(name => `<button type="button" data-scenario="${escapeHTML(name)}" aria-pressed="${state.scenario === name}" title="${escapeHTML(data.scenarios[name])}">${escapeHTML(name)}${name === data.default_scenario ? ' · forecast' : ''}</button>`).join('');
  $('#situation').innerHTML = Object.entries(data.situations).map(([key, label]) => `<option value="${escapeHTML(key)}">${escapeHTML(label)}</option>`).join('');
  $('#situation').value = state.situation;
  $('#date-select').innerHTML = data.days.map((day, index) => `<option value="${index}">${escapeHTML(dateLabel(day.date, true))}${day.date === data.meta.game_day ? ' · Game day' : day.date === data.meta.presidents_day ? ' · Holiday' : ''}</option>`).join('');
  $('#date-select').value = String(Math.floor(state.tick / HOURS));
  $('#prepared').checked = state.prepared;
  $('#view-context').textContent = `${state.scenario === data.default_scenario ? `${data.default_scenario} is the forecast` : `${state.scenario} is a plausible-range case`} · ${state.prepared ? 'prepared' : 'normal'} capacity`;
}

function renderSummary() {
  const capacity = data.capacity.ramp_su;
  let message;
  if (view.first) {
    message = `${dateLabel(view.first.date)} is the first day with median demand above the ${su(view.first.capacity)} ${state.prepared ? 'prepared' : 'normal'} capacity. The highest daily overflow chance is ${pct(view.worst.probability)} on ${dateLabel(view.worst.date)}.`;
  } else {
    message = `Median demand stays within ${state.prepared ? 'prepared' : 'normal'} capacity throughout the week. The highest daily overflow chance is still ${pct(view.worst.probability)} on ${dateLabel(view.worst.date)}.`;
  }
  $('#summary-copy').textContent = message;
  const ordinaryWorst = Math.max(...view.days.map(day => day.ordinary.prob_over_normal_capacity));
  $('#metrics').innerHTML = `
    <div class="metric"><span class="metric-label">First P50 over capacity</span><strong class="metric-value ${view.first ? 'critical' : ''}">${view.first ? escapeHTML(dateLabel(view.first.date, true)) : 'None'}</strong><small>${view.first ? `${su(view.first.parking_demand_su_p50)} vs ${su(view.first.capacity)}` : 'Median stays within space'}</small></div>
    <div class="metric"><span class="metric-label">Highest daily chance</span><strong class="metric-value critical">${pct(view.worst.probability)}</strong><small>${escapeHTML(dateLabel(view.worst.date, true))} · ${state.prepared ? 'prepared' : 'normal'} capacity</small></div>
    <div class="metric"><span class="metric-label">Peak median demand</span><strong class="metric-value">${su(view.peak.parking_demand_su_p50)}</strong><small>${escapeHTML(dateLabel(view.peak.date, true))} · P90 ${su(view.peak.parking_demand_su_p90)}</small></div>`;
  $('#panel-explain').textContent = `${view.aboveMedian.length} of ${view.days.length} days have P50 above the selected capacity. In an ordinary week, the highest daily chance above the ${su(capacity)} ramp is ${pct(ordinaryWorst)}. P10–P90 and daily probabilities come from the parking model.`;
  $('#strip-capacity').textContent = `RAMP ${su(capacity)}`;
}

function renderDayStrip() {
  const maxProbability = Math.max(...view.days.map(day => day.probability), .01);
  $('#day-strip').innerHTML = view.days.map((day, index) => {
    const active = index === Math.floor(state.tick / HOURS);
    const status = day.parking_demand_su_p50 > day.capacity ? 'over' : day.probability < .1 ? 'safe' : '';
    const event = day.date === data.meta.game_day ? 'GAME DAY' : day.date === data.meta.presidents_day ? "PRESIDENTS' DAY" : '&nbsp;';
    return `<button type="button" class="day-button ${status}" data-day="${index}" aria-pressed="${active}" aria-label="${escapeHTML(dateLabel(day.date))}: ${pct(day.probability)} chance of exceeding ${su(day.capacity)}; P50 ${su(day.parking_demand_su_p50)}, P90 ${su(day.parking_demand_su_p90)}"><span class="day-name">${escapeHTML(day.weekday.slice(0, 3))}<b>${Number(day.date.slice(-2))}</b></span><span class="day-event">${event}</span><span class="day-prob">${pct(day.probability)}</span><span class="day-bar"><i style="width:${Math.max(3, day.probability / maxProbability * 100)}%"></i></span></button>`;
  }).join('');
}

function renderSelectedDay() {
  const day = selectedDay();
  const relation = day.parking_demand_su_p50 > day.capacity ? 'P50 exceeds space' : 'P50 within space';
  $('#selected-day').innerHTML = `<strong>${escapeHTML(dateLabel(day.date))}</strong><span class="risk">${pct(day.probability)} chance above ${su(day.capacity)}</span><span>P10 ${su(day.parking_demand_su_p10)} · P50 ${su(day.parking_demand_su_p50)} · P90 ${su(day.parking_demand_su_p90)}</span><span>${relation}</span>`;
  $('#hourly-answer').textContent = `Illustrated hours above selected space: ${illustratedHours(day)}. Hourly probabilities are not modeled.`;
}

function illustratedHours(day) {
  const firstTick = data.days.findIndex(info => info.date === day.date) * HOURS;
  const hours = snapshots.slice(firstTick, firstTick + HOURS).map((snapshot, hour) => snapshot.used > day.capacity ? hour : -1).filter(hour => hour >= 0);
  if (!hours.length) return 'none';
  const ranges = [];
  let start = hours[0], end = start;
  for (const hour of hours.slice(1)) {
    if (hour === end + 1) end = hour;
    else { ranges.push([start, end]); start = end = hour; }
  }
  ranges.push([start, end]);
  return ranges.map(([from, to]) => from === to ? `${String(from).padStart(2, '0')}:00` : `${String(from).padStart(2, '0')}:00–${String(to).padStart(2, '0')}:00`).join(', ');
}

function renderChart() {
  const days = view.days;
  const max = Math.ceil(Math.max(...days.flatMap(day => [day.parking_demand_su_p90, day.capacity_prepared_su])) / 5) * 5;
  const left = 42, right = 664, top = 15, bottom = 201;
  const y = value => bottom - value / max * (bottom - top);
  const x = index => left + 45 + index * ((right - left - 90) / Math.max(1, days.length - 1));
  const normal = data.capacity.ramp_su;
  const axis = [0, .5, 1].map(share => `<g><line x1="${left}" x2="${right}" y1="${y(max * share)}" y2="${y(max * share)}" stroke="var(--line)" stroke-width="1"/><text x="${left - 8}" y="${y(max * share) + 4}" text-anchor="end" fill="var(--muted)" font-size="10">${Math.round(max * share)}</text></g>`).join('');
  const normalY = y(normal);
  const normalLine = `<line x1="${left}" x2="${right}" y1="${normalY}" y2="${normalY}" stroke="var(--warning)" stroke-width="2"/><text x="${right - 2}" y="${normalY - 5}" text-anchor="end" fill="var(--warning)" font-size="10" font-weight="700">RAMP ${su(normal)}</text>`;
  const preparedLine = `<polyline points="${days.map((day, index) => `${x(index)},${y(day.capacity_prepared_su)}`).join(' ')}" fill="none" stroke="var(--ok)" stroke-width="2" stroke-dasharray="5 5"/><text x="${right}" y="${y(days.at(-1).capacity_prepared_su) - 7}" text-anchor="end" fill="var(--ok)" font-size="10" font-weight="700">PREPARED</text>`;
  const marks = days.map((day, index) => {
    const mid = x(index), p10 = y(day.parking_demand_su_p10), p50 = y(day.parking_demand_su_p50), p90 = y(day.parking_demand_su_p90), ordinary = y(day.ordinary.parking_demand_su_p50);
    const selected = Math.floor(state.tick / HOURS) === index;
    const criticalHeight = Math.max(0, Math.min(p10, y(day.capacity)) - p90);
    return `<g tabindex="0" role="button" data-chart-day="${index}" aria-label="${escapeHTML(dateLabel(day.date))}: P50 ${su(day.parking_demand_su_p50)}, P10 ${su(day.parking_demand_su_p10)}, P90 ${su(day.parking_demand_su_p90)}. Select day."><title>${escapeHTML(dateLabel(day.date))}: P10 ${su(day.parking_demand_su_p10)}, P50 ${su(day.parking_demand_su_p50)}, P90 ${su(day.parking_demand_su_p90)}, ${pct(day.probability)} over selected capacity. Ordinary-week P50 ${su(day.ordinary.parking_demand_su_p50)}.</title><rect x="${mid - 37}" y="${top}" width="74" height="${bottom - top}" fill="${selected ? 'var(--accent)' : 'transparent'}" opacity="${selected ? '.055' : '0'}"/><rect x="${mid - 15}" y="${p90}" width="30" height="${p10 - p90}" rx="3" fill="#436b74" opacity=".72"/><rect x="${mid - 15}" y="${p90}" width="30" height="${criticalHeight}" rx="3" fill="var(--critical)" opacity=".53"/><line x1="${mid - 19}" x2="${mid + 19}" y1="${p50}" y2="${p50}" stroke="var(--text)" stroke-width="3"/><circle cx="${mid}" cy="${p50}" r="3.5" fill="var(--critical)"/><line x1="${mid - 11}" x2="${mid + 11}" y1="${ordinary}" y2="${ordinary}" stroke="var(--muted)" stroke-width="2"/><text x="${mid}" y="${bottom + 19}" text-anchor="middle" fill="${selected ? 'var(--text)' : 'var(--muted)'}" font-size="11" font-weight="${selected ? '800' : '600'}">${escapeHTML(day.weekday.slice(0, 3).toUpperCase())} ${Number(day.date.slice(-2))}</text></g>`;
  }).join('');
  $('#week-chart').innerHTML = `<title>Daily parking demand range and capacity</title><desc>P10 to P90 demand ranges with P50 and ordinary-week median for each day. The normal ramp is ${su(normal)}. Prepared capacity varies by plan.</desc>${axis}${marks}${normalLine}${preparedLine}<text x="5" y="12" fill="var(--muted)" font-size="10">su</text>`;
}

function renderTable() {
  $('#forecast-table').innerHTML = view.days.map((day, index) => `<tr class="${index === Math.floor(state.tick / HOURS) ? 'active' : ''}"><th scope="row">${escapeHTML(dateLabel(day.date, true))}${day.date === data.meta.game_day ? ' · Game' : day.date === data.meta.presidents_day ? ' · Holiday' : ''}</th><td>${day.parking_demand_su_p10.toFixed(1)}</td><td class="${day.parking_demand_su_p50 > day.capacity ? 'danger' : ''}">${day.parking_demand_su_p50.toFixed(1)}</td><td>${day.parking_demand_su_p90.toFixed(1)}</td><td>${day.capacity.toFixed(1)}</td><td class="${day.probability >= .5 ? 'danger' : ''}">${pct(day.probability)}</td><td>${day.ordinary.parking_demand_su_p50.toFixed(1)}</td><td>${day.arrivals_p50.toFixed(1)} / ${day.departures_p50.toFixed(1)}</td><td>${illustratedHours(day)}</td></tr>`).join('');
}

function renderPlan() {
  const plan = view.plan;
  $('#plan-impact').innerHTML = `<h3>Modeled effect</h3><div class="impact-top"><div><span>Without plan</span><strong>${plan.aircraft_not_accommodated_mean.no_plan.toFixed(1)}</strong><small>mean aircraft needing another parking decision</small></div><div><span>With plan</span><strong style="color:var(--ok)">${plan.aircraft_not_accommodated_mean.with_plan.toFixed(1)}</strong><small>mean aircraft needing another parking decision</small></div></div><div class="impact-stat"><span>Plan cost</span><strong>${money(plan.plan_cost_usd)}</strong></div><div class="impact-stat"><span>Chance plan pays off</span><strong>${pct(plan.prob_plan_pays_off)}</strong></div><div class="impact-stat"><span>Selected capacity on ${escapeHTML(dateLabel(selectedDay().date, true))}</span><strong>${su(selectedDay().capacity)}</strong></div><p class="impact-note">The dataset calls these “aircraft not accommodated.” Here they are a planning shortfall for a manager to resolve; the simulator never refuses an aircraft. The cost and probability come from the selected model plan.</p>`;
  $('#actions').innerHTML = `<h3>Record a human decision</h3>${plan.actions.map(action => {
    const key = decisionKey(action.id);
    const record = readDecision(key);
    return `<div class="action-card" data-action="${escapeHTML(action.id)}"><div class="action-head"><div><strong>${escapeHTML(action.action)}</strong><small>Approver role: ${escapeHTML(action.approver)} · ${escapeHTML(dateLabel(action.dates[0], true))}–${escapeHTML(dateLabel(action.dates.at(-1), true))}</small></div><span class="action-cost">${money(action.cost_usd)}</span></div><p class="action-rationale">${escapeHTML(action.rationale)}</p><div class="approval-fields"><input class="person" type="text" maxlength="80" placeholder="Manager name" aria-label="Manager name for ${escapeHTML(action.action)}" value="${escapeHTML(record.name || '')}"><input class="note" type="text" maxlength="240" placeholder="Decision note" aria-label="Decision note for ${escapeHTML(action.action)}" value="${escapeHTML(record.note || '')}"></div><div class="action-buttons"><button type="button" data-choice="approved" class="${record.choice === 'approved' ? 'selected' : ''}">Approve</button><button type="button" data-choice="rejected" class="${record.choice === 'rejected' ? 'selected' : ''}">Reject</button><span class="decision-status">${record.choice ? `${escapeHTML(record.choice)} by ${escapeHTML(record.name)}` : 'Awaiting decision'}</span></div><div class="validation" aria-live="polite"></div></div>`;
  }).join('')}`;
}

function decisionKey(id) { return `ramp-control/${state.situation}/${state.scenario}/${id}`; }
function readDecision(key) { try { const record = JSON.parse(localStorage.getItem(key) || '{}'); return record && typeof record === 'object' ? { choice: ['approved', 'rejected'].includes(record.choice) ? record.choice : '', name: typeof record.name === 'string' ? record.name : '', note: typeof record.note === 'string' ? record.note : '' } : {}; } catch { return {}; } }
function saveDecision(actionCard, choice) {
  const name = actionCard.querySelector('.person').value.trim();
  const note = actionCard.querySelector('.note').value.trim();
  const message = actionCard.querySelector('.validation');
  if (!name || !note) { message.textContent = 'Enter a manager name and a note to record this decision.'; return; }
  const key = decisionKey(actionCard.dataset.action);
  try { localStorage.setItem(key, JSON.stringify({ choice, name, note })); }
  catch { message.textContent = 'This browser could not save the decision locally.'; return; }
  message.textContent = 'Saved on this device.';
  actionCard.querySelectorAll('[data-choice]').forEach(button => button.classList.toggle('selected', button.dataset.choice === choice));
  actionCard.querySelector('.decision-status').textContent = `${choice} by ${name}`;
  rebuildPlacements(); state.instant = true; renderClock();
}

function decisions() {
  return Object.fromEntries(data.parking[state.situation].plans[state.scenario].actions.map(action => [action.id, readDecision(decisionKey(action.id))]));
}
function rebuildPlacements() {
  placements = buildPlacements(data, state.situation, state.scenario, snapshots, layout, decisions());
  standViews?.setLedger(placements);
}
function syncFollowControl() {
  const frame = placements[state.tick];
  const plane = selection?.aircraftId ? frame.placed.find(p => p.id === selection.aircraftId)
    || frame.movements.find(m => m.type === 'departure' && m.plane.id === selection.aircraftId)?.plane
    : frame.placed.find(p => p.standId === selection?.standId);
  $('[data-camera="follow"]').disabled = !plane || !rampScene;
}
function select(value) {
  selection = value;
  standViews?.select(value); rampScene?.select(value); syncFollowControl();
}
function hover(value) { standViews?.highlight(value); rampScene?.highlight(value); }

function renderClock() {
  const day = selectedDay(), snapshot = activeSnapshot(), placement = placements[state.tick];
  $('#scrub').value = String(state.tick);
  $('#scrub').setAttribute('aria-valuetext', `${dateLabel(day.date)} ${clockLabel(snapshot.hour)}`);
  $('#movement').textContent = `${snapshot.arrivals} illustrated arrivals · ${snapshot.departures} departures this hour`;
  const used = snapshot.used, waiting = placement.sums.waiting, totalCapacity = placement.capacity.total;
  $('#gauge-value').textContent = `${su(used)} / ${su(totalCapacity)}`;
  $('#gauge-fill').style.width = `${Math.min(100, used / totalCapacity * 100)}%`;
  $('.gauge').classList.toggle('overflow', waiting > 0);
  $('#gauge-detail').textContent = waiting > 0 ? `${su(waiting)} awaiting a manager decision` : 'Illustrated demand within approved space';
  const waitingCount = placement.placed.filter(plane => plane.area === 'waiting').length;
  $('#waiting-count').textContent = `${waitingCount} aircraft`;
  $('#waiting-space').textContent = `${su(waiting)} · illustrative`;
  $('.waiting-readout').classList.toggle('has-waiting', waitingCount > 0);
  $('#hud-short').textContent = `${dateLabel(day.date, true)} · ${pct(day.probability)} daily chance over ${state.prepared ? 'prepared' : 'ramp'} space`;
  $('#hud-answer').textContent = `${dateLabel(day.date)}: median demand ${day.parking_demand_su_p50 > day.capacity ? 'exceeds' : 'fits within'} ${su(day.capacity)} of ${state.prepared ? 'proposed prepared' : 'normal ramp'} space, with a ${pct(day.probability)} daily chance of exceeding it.`;
  $('#hud-range').textContent = `Modeled demand: P50 ${su(day.parking_demand_su_p50)} · P10–P90 ${su(day.parking_demand_su_p10)}–${su(day.parking_demand_su_p90)}. Clock and positions are illustrative; approvals control the gauge.`;
  $('#ramp-label').textContent = `${su(data.capacity.ramp_su)}${placement.capacity.packed ? ` + ${su(placement.capacity.packed)} packed` : ''}`;
  $('#remote-label').textContent = placement.capacity.remote ? `${su(placement.capacity.remote)} approved today` : 'No approved space today';
  const pause = restrictionAt(data, state.situation, day.date);
  $('#restriction-note').hidden = !pause;
  $('#restriction-note').textContent = pause ? `Assumed security pause: ${pause.start}–${pause.end}. ${pause.status}. Placeholder movements in intersecting hourly bins are held outside this window; daily totals are preserved.` : '';
  rampScene?.update(placement); standViews?.update(placement);
  rampScene?.setForecast(view.days, snapshot.dayIndex); syncFollowControl(); syncProgress();
}
function syncProgress() {
  const hour = state.tick % HOURS + (motionQuery.matches ? 0 : state.phase);
  $('#clock-face').textContent = `${dateLabel(selectedDay().date, true)} · ${clockLabel(hour)}`;
  standViews?.setTime(hour);
  rampScene?.setProgress(state.instant || motionQuery.matches ? 1 : state.phase, hour);
}
function renderAll() {
  view = getView(data, state.situation, state.scenario, state.prepared);
  renderControls(); renderSummary(); renderDayStrip(); renderSelectedDay(); renderChart(); renderTable(); renderPlan(); renderClock();
}
function changeTick(tick, animated = false) {
  const previousDay = Math.floor(state.tick / HOURS);
  state.tick = Math.max(0, Math.min(snapshots.length - 1, Math.floor(tick)));
  state.phase = 0; state.instant = !animated;
  $('#date-select').value = String(Math.floor(state.tick / HOURS));
  if (!animated || previousDay !== Math.floor(state.tick / HOURS)) {
    renderDayStrip(); renderSelectedDay(); renderChart(); renderTable();
    const capacityStat = $('#plan-impact .impact-stat:last-of-type strong');
    if (capacityStat) capacityStat.textContent = su(selectedDay().capacity);
    const capacityLabel = $('#plan-impact .impact-stat:last-of-type span');
    if (capacityLabel) capacityLabel.textContent = `Selected capacity on ${dateLabel(selectedDay().date, true)}`;
  }
  renderClock();
}
function setPlaying(value) {
  state.playing = value;
  if (value) { state.instant = false; if (state.tick === snapshots.length - 1 && state.phase >= 1) changeTick(0, true); }
  $('#play').textContent = value ? 'Ⅱ' : '▶';
  $('#play').setAttribute('aria-label', value ? 'Pause time lapse' : 'Play time lapse');
  $('#play').setAttribute('aria-pressed', String(value));
}
function advance(delta) {
  if (!state.playing || document.hidden) return;
  const secondsPerHour = { slow: 10, normal: 5, fast: 1.5 }[$('#speed').value];
  const phase = state.phase + delta / secondsPerHour;
  if (phase >= 1) {
    if (state.tick === snapshots.length - 1) { state.phase = 1; syncProgress(); setPlaying(false); return; }
    changeTick(state.tick + 1, true); state.phase = phase % 1;
  } else state.phase = phase;
  syncProgress();
}
function resetSimulation() {
  setPlaying(false); state.phase = 0; state.instant = true;
  snapshots = buildIllustration(data, state.situation, state.scenario);
  rebuildPlacements(); select(null); hover(null); renderAll();
}
function bindEvents() {
  $('#scenario-options').addEventListener('click', event => {
    const button = event.target.closest('[data-scenario]'); if (!button) return;
    state.scenario = button.dataset.scenario; resetSimulation();
  });
  $('#situation').addEventListener('change', event => { state.situation = event.target.value; resetSimulation(); });
  $('#date-select').addEventListener('change', event => { setPlaying(false); changeTick(Number(event.target.value) * HOURS + state.tick % HOURS); });
  $('#prepared').addEventListener('change', event => { state.prepared = event.target.checked; renderAll(); });
  $('#day-strip').addEventListener('click', event => { const button = event.target.closest('[data-day]'); if (button) { setPlaying(false); changeTick(Number(button.dataset.day) * HOURS + state.tick % HOURS); } });
  const chartSelect = event => { const mark = event.target.closest('[data-chart-day]'); if (mark) { setPlaying(false); changeTick(Number(mark.dataset.chartDay) * HOURS + state.tick % HOURS); } };
  $('#week-chart').addEventListener('click', chartSelect);
  $('#week-chart').addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); chartSelect(event); } });
  $('#scrub').addEventListener('input', event => { setPlaying(false); changeTick(Number(event.target.value)); });
  $('#play').addEventListener('click', () => setPlaying(!state.playing));
  $('#actions').addEventListener('click', event => { const button = event.target.closest('[data-choice]'); if (button) saveDecision(button.closest('.action-card'), button.dataset.choice); });
  $('.camera-controls').addEventListener('click', event => {
    const button = event.target.closest('[data-camera]'); if (!button) return;
    rampScene?.preset(button.dataset.camera);
    document.querySelectorAll('[data-camera]').forEach(control => control.setAttribute('aria-pressed', String(control === button)));
  });
  $('#auto-orbit').addEventListener('click', () => rampScene?.setAutoOrbit($('#auto-orbit').getAttribute('aria-pressed') !== 'true'));
  $('#fullscreen').addEventListener('click', toggleFullscreen);
  document.addEventListener('fullscreenchange', syncFullscreen);
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && $('#scene-stage').classList.contains('fullscreen-fallback')) {
      $('#scene-stage').classList.remove('fullscreen-fallback'); syncFullscreen();
    }
  });
  $('#theme-toggle').addEventListener('click', () => {
    const light = document.documentElement.dataset.theme !== 'light';
    document.documentElement.dataset.theme = light ? 'light' : 'dark';
    $('#theme-toggle').setAttribute('aria-label', `Switch to ${light ? 'dark' : 'light'} theme`);
    try { localStorage.setItem('ramp-control/theme', light ? 'light' : 'dark'); } catch {}
  });
  motionQuery.addEventListener('change', () => { setPlaying(false); state.instant = true; rampScene?.setAutoOrbit(false); $('#auto-orbit').disabled = motionQuery.matches || !rampScene; syncProgress(); });
  document.addEventListener('visibilitychange', () => { if (document.hidden) setPlaying(false); });
  window.addEventListener('storage', event => {
    if (event.key === null || event.key.startsWith('ramp-control/')) { rebuildPlacements(); renderPlan(); renderClock(); }
  });
}
function syncFullscreen() {
  const active = Boolean(document.fullscreenElement) || $('#scene-stage').classList.contains('fullscreen-fallback');
  $('#fullscreen').textContent = active ? 'Exit fullscreen' : 'Fullscreen';
  $('#fullscreen').setAttribute('aria-pressed', String(active));
  document.body.classList.toggle('scene-expanded', active);
}
async function toggleFullscreen() {
  const stage = $('#scene-stage');
  if (document.fullscreenElement) await document.exitFullscreen();
  else if (stage.classList.contains('fullscreen-fallback')) stage.classList.remove('fullscreen-fallback');
  else {
    try {
      if (stage.requestFullscreen && document.fullscreenEnabled) await stage.requestFullscreen();
      else stage.classList.add('fullscreen-fallback');
    } catch { stage.classList.add('fullscreen-fallback'); }
  }
  syncFullscreen();
}
function selectSkylineDay(index) {
  setPlaying(false);
  const busiest = snapshots.slice(index * HOURS, (index + 1) * HOURS).reduce((best, item) => item.used > best.used ? item : best);
  changeTick(busiest.tick);
  document.querySelectorAll('[data-camera]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.camera === 'ramp')));
  $('#scene-control-status').textContent = `Showing ${dateLabel(selectedDay().date)} at its busiest illustrated hour, ${clockLabel(busiest.hour)}.`;
}
function fallbackLoop() {
  let request = 0, previous = 0;
  const frame = timestamp => {
    request = 0; if (document.hidden) return;
    if (previous) advance(Math.min((timestamp - previous) / 1000, .1));
    previous = timestamp; request = requestAnimationFrame(frame);
  };
  const visibility = () => {
    if (document.hidden) { cancelAnimationFrame(request); request = 0; previous = 0; }
    else if (!request) request = requestAnimationFrame(frame);
  };
  document.addEventListener('visibilitychange', visibility); visibility();
}
async function main() {
  try {
    const response = await fetch('./parking_data.json');
    if (!response.ok) throw new Error('The supplied parking data could not be loaded.');
    data = await response.json();
    state.scenario = data.default_scenario; state.situation = Object.keys(data.situations)[0];
    const savedTheme = (() => { try { return localStorage.getItem('ramp-control/theme'); } catch { return null; } })();
    const theme = savedTheme === 'light' || savedTheme === 'dark' ? savedTheme : window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    document.documentElement.dataset.theme = theme;
    $('#theme-toggle').setAttribute('aria-label', `Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`);
    snapshots = buildIllustration(data, state.situation, state.scenario);
    layout = createLayout(data, snapshots);
    standViews = createStandViews(data, layout, { onSelect: select, onHover: hover, onSeek: tick => { setPlaying(false); changeTick(tick); }, situation: () => state.situation, scenario: () => state.scenario });
    rebuildPlacements();
    const firstOver = getView(data, state.situation, state.scenario, false).first;
    if (firstOver) {
      const firstDay = data.days.findIndex(day => day.date === firstOver.date);
      const daySnapshots = snapshots.slice(firstDay * HOURS, (firstDay + 1) * HOURS);
      const busiest = daySnapshots.reduce((best, item) => item.used > best.used ? item : best);
      state.tick = busiest.tick;
    }
    $('#scrub').min = '0'; $('#scrub').max = String(snapshots.length - 1);
    $('#fbo-name').textContent = `${data.meta.fbo} / Parking operations`;
    $('#planning-window').textContent = data.meta.planning_window.map(date => dateLabel(date)).join(' — ');
    $('#timezone-label').textContent = `Local time · ${data.meta.timezone}`;
    $('#question-heading').textContent = data.meta.question;
    document.title = `Ramp Control · ${data.meta.fbo} · ${data.meta.planning_window.join(' – ')}`;
    $('#timeline-start').textContent = `${dateLabel(data.days[0].date, true)} · ${clockLabel(snapshots[0].hour)}`;
    $('#timeline-end').textContent = `${dateLabel(data.days.at(-1).date, true)} · ${clockLabel(snapshots.at(-1).hour + 1)}`;
    $('#capacity-derivation').textContent = data.capacity.derivation;
    $('#human-rule').textContent = data.meta.human_in_command;
    $('#model-description').textContent = data.meta.how_to_read;
    $('#hourly-assumption').textContent = data.hourly_profile.note;
    $('#aircraft-assumptions').textContent = `${data.aircraft.space_unit}. Size mix: ${Object.entries(data.aircraft.sizes).map(([name, size]) => `${name} ${pct(size.share)} (${su(size.su)})`).join('; ')}. Opening count: ${data.aircraft.opening_aircraft}; average stay: ${data.aircraft.stays.average_days} days. ${data.aircraft.stays.class}.`;
    $('#footer-source').textContent = `Supplied parking_data.json · generated ${data.meta.generated_utc}`;
    $('#hud-outlook').open = !window.matchMedia('(max-width: 480px)').matches;
    $('#auto-orbit').disabled = true;
    renderAll(); bindEvents();
    try {
      const { createRampScene } = await import('./scene.js');
      rampScene = createRampScene($('#scene'), data, layout, { onSelect: select, onPositions: positions => standViews.updatePositions(positions), onFrame: advance,
        onDaySelect: selectSkylineDay,
        onAutoOrbitChange: enabled => $('#auto-orbit').setAttribute('aria-pressed', String(enabled)) });
      $('#auto-orbit').disabled = motionQuery.matches;
      renderClock();
    } catch {
      $('#scene').replaceChildren(); $('#scene-fallback').hidden = false;
      document.querySelectorAll('[data-camera]').forEach(button => { button.disabled = true; });
      fallbackLoop();
    }
  } catch (error) {
    $('#summary-copy').textContent = `${error.message} Open this folder through your site’s HTTP hosting to load the supplied JSON.`;
    $('#scene-fallback').hidden = false;
  }
}
main();
