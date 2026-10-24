import { getView, buildIllustration, dateLabel, su, pct, money } from './model.js';

const $ = selector => document.querySelector(selector);
const escapeHTML = value => String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
let data, view, snapshots, rampScene;
const state = { scenario: 'Medium', situation: 'standard', prepared: false, tick: 0, playing: false, lastFrame: 0, elapsed: 0 };
const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');

function selectedDay() { return view.days[Math.floor(state.tick / 24)]; }
function activeSnapshot() { return snapshots[state.tick]; }

function renderControls() {
  $('#scenario-options').innerHTML = Object.keys(data.scenarios).map(name => `<button type="button" data-scenario="${escapeHTML(name)}" aria-pressed="${state.scenario === name}">${escapeHTML(name)}${name === data.default_scenario ? ' · forecast' : ''}</button>`).join('');
  $('#situation').innerHTML = Object.entries(data.situations).map(([key, label]) => `<option value="${escapeHTML(key)}">${escapeHTML(label)}</option>`).join('');
  $('#situation').value = state.situation;
  $('#date-select').innerHTML = data.days.map((day, index) => `<option value="${index}">${escapeHTML(dateLabel(day.date, true))}${day.game_day ? ' · Game day' : day.presidents_day ? ' · Holiday' : ''}</option>`).join('');
  $('#date-select').value = String(Math.floor(state.tick / 24));
  $('#prepared').checked = state.prepared;
  $('#view-context').textContent = `${state.scenario === data.default_scenario ? 'Medium is the forecast' : `${state.scenario} is a plausible-range case`} · ${state.prepared ? 'prepared' : 'normal'} capacity`;
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
    const active = index === Math.floor(state.tick / 24);
    const status = day.parking_demand_su_p50 > day.capacity ? 'over' : day.probability < .1 ? 'safe' : '';
    const event = day.game_day ? 'GAME DAY' : day.presidents_day ? "PRESIDENTS' DAY" : '&nbsp;';
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
  const firstTick = data.days.findIndex(info => info.date === day.date) * 24;
  const hours = snapshots.slice(firstTick, firstTick + 24).map((snapshot, hour) => snapshot.used > day.capacity ? hour : -1).filter(hour => hour >= 0);
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
  const x = index => left + 45 + index * ((right - left - 90) / 6);
  const normal = data.capacity.ramp_su;
  const axis = [0, .5, 1].map(share => `<g><line x1="${left}" x2="${right}" y1="${y(max * share)}" y2="${y(max * share)}" stroke="var(--line)" stroke-width="1"/><text x="${left - 8}" y="${y(max * share) + 4}" text-anchor="end" fill="var(--muted)" font-size="10">${Math.round(max * share)}</text></g>`).join('');
  const normalY = y(normal);
  const normalLine = `<line x1="${left}" x2="${right}" y1="${normalY}" y2="${normalY}" stroke="var(--warning)" stroke-width="2"/><text x="${right - 2}" y="${normalY - 5}" text-anchor="end" fill="var(--warning)" font-size="10" font-weight="700">RAMP ${su(normal)}</text>`;
  const preparedLine = `<polyline points="${days.map((day, index) => `${x(index)},${y(day.capacity_prepared_su)}`).join(' ')}" fill="none" stroke="var(--ok)" stroke-width="2" stroke-dasharray="5 5"/><text x="${right}" y="${y(days.at(-1).capacity_prepared_su) - 7}" text-anchor="end" fill="var(--ok)" font-size="10" font-weight="700">PREPARED</text>`;
  const marks = days.map((day, index) => {
    const mid = x(index), p10 = y(day.parking_demand_su_p10), p50 = y(day.parking_demand_su_p50), p90 = y(day.parking_demand_su_p90), ordinary = y(day.ordinary.parking_demand_su_p50);
    const selected = Math.floor(state.tick / 24) === index;
    const criticalHeight = Math.max(0, Math.min(p10, y(day.capacity)) - p90);
    return `<g><title>${escapeHTML(dateLabel(day.date))}: P10 ${su(day.parking_demand_su_p10)}, P50 ${su(day.parking_demand_su_p50)}, P90 ${su(day.parking_demand_su_p90)}, ${pct(day.probability)} over selected capacity. Ordinary-week P50 ${su(day.ordinary.parking_demand_su_p50)}.</title><rect x="${mid - 37}" y="${top}" width="74" height="${bottom - top}" fill="${selected ? 'var(--accent)' : 'transparent'}" opacity="${selected ? '.055' : '0'}"/><rect x="${mid - 15}" y="${p90}" width="30" height="${p10 - p90}" rx="3" fill="#436b74" opacity=".72"/><rect x="${mid - 15}" y="${p90}" width="30" height="${criticalHeight}" rx="3" fill="var(--critical)" opacity=".53"/><line x1="${mid - 19}" x2="${mid + 19}" y1="${p50}" y2="${p50}" stroke="var(--text)" stroke-width="3"/><circle cx="${mid}" cy="${p50}" r="3.5" fill="var(--critical)"/><line x1="${mid - 11}" x2="${mid + 11}" y1="${ordinary}" y2="${ordinary}" stroke="var(--muted)" stroke-width="2"/><text x="${mid}" y="${bottom + 19}" text-anchor="middle" fill="${selected ? 'var(--text)' : 'var(--muted)'}" font-size="11" font-weight="${selected ? '800' : '600'}">${escapeHTML(day.weekday.slice(0, 3).toUpperCase())} ${Number(day.date.slice(-2))}</text></g>`;
  }).join('');
  $('#week-chart').innerHTML = `<title>Daily parking demand range and capacity</title><desc>P10 to P90 demand ranges with P50 and ordinary-week median for each day. The normal ramp is ${su(normal)}. Prepared capacity varies by plan.</desc>${axis}${marks}${normalLine}${preparedLine}<text x="5" y="12" fill="var(--muted)" font-size="10">su</text>`;
}

function renderTable() {
  $('#forecast-table').innerHTML = view.days.map((day, index) => `<tr class="${index === Math.floor(state.tick / 24) ? 'active' : ''}"><th scope="row">${escapeHTML(dateLabel(day.date, true))}${day.game_day ? ' · Game' : day.presidents_day ? ' · Holiday' : ''}</th><td>${day.parking_demand_su_p10.toFixed(1)}</td><td class="${day.parking_demand_su_p50 > day.capacity ? 'danger' : ''}">${day.parking_demand_su_p50.toFixed(1)}</td><td>${day.parking_demand_su_p90.toFixed(1)}</td><td>${day.capacity.toFixed(1)}</td><td class="${day.probability >= .5 ? 'danger' : ''}">${pct(day.probability)}</td><td>${day.ordinary.parking_demand_su_p50.toFixed(1)}</td><td>${day.arrivals_p50.toFixed(1)} / ${day.departures_p50.toFixed(1)}</td><td>${illustratedHours(day)}</td></tr>`).join('');
}

function renderPlan() {
  const plan = view.plan;
  $('#plan-impact').innerHTML = `<h3>Modeled effect</h3><div class="impact-top"><div><span>Without plan</span><strong>${plan.aircraft_not_accommodated_mean.no_plan.toFixed(1)}</strong><small>mean aircraft needing another parking decision</small></div><div><span>With plan</span><strong style="color:var(--ok)">${plan.aircraft_not_accommodated_mean.with_plan.toFixed(1)}</strong><small>mean aircraft needing another parking decision</small></div></div><div class="impact-stat"><span>Plan cost</span><strong>${money(plan.plan_cost_usd)}</strong></div><div class="impact-stat"><span>Chance plan pays off</span><strong>${pct(plan.prob_plan_pays_off)}</strong></div><div class="impact-stat"><span>Selected capacity on ${escapeHTML(dateLabel(selectedDay().date, true))}</span><strong>${su(selectedDay().capacity)}</strong></div><p class="impact-note">The dataset calls these “aircraft not accommodated.” Here they are a planning shortfall for a manager to resolve; the simulator never refuses an aircraft. The cost and probability come from the selected model plan.</p>`;
  $('#actions').innerHTML = `<h3>Record a human decision</h3>${plan.actions.map(action => {
    const key = decisionKey(action.id);
    const record = readDecision(key);
    return `<div class="action-card" data-action="${escapeHTML(action.id)}"><div class="action-head"><div><strong>${escapeHTML(action.action)}</strong><small>Approver role: ${escapeHTML(action.approver)} · ${escapeHTML(dateLabel(action.dates[0], true))}–${escapeHTML(dateLabel(action.dates.at(-1), true))}</small></div><span class="action-cost">${money(action.cost_usd)}</span></div><div class="approval-fields"><input class="person" type="text" maxlength="80" placeholder="Manager name" aria-label="Manager name for ${escapeHTML(action.action)}" value="${escapeHTML(record.name || '')}"><input class="note" type="text" maxlength="240" placeholder="Decision note" aria-label="Decision note for ${escapeHTML(action.action)}" value="${escapeHTML(record.note || '')}"></div><div class="action-buttons"><button type="button" data-choice="approved" class="${record.choice === 'approved' ? 'selected' : ''}">Approve</button><button type="button" data-choice="rejected" class="${record.choice === 'rejected' ? 'selected' : ''}">Reject</button><span class="decision-status">${record.choice ? `${escapeHTML(record.choice)} by ${escapeHTML(record.name)}` : 'Awaiting decision'}</span></div><div class="validation" aria-live="polite"></div></div>`;
  }).join('')}`;
}

function decisionKey(id) { return `ramp-control/${state.situation}/${state.scenario}/${id}`; }
function readDecision(key) { try { return JSON.parse(localStorage.getItem(key) || '{}'); } catch { return {}; } }
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
}

function renderClock() {
  const day = selectedDay(), hour = state.tick % 24, snapshot = activeSnapshot();
  $('#scrub').value = String(state.tick);
  $('#clock-face').textContent = `${dateLabel(day.date, true)} · ${String(hour).padStart(2, '0')}:00`;
  $('#movement').textContent = `${snapshot.arrivals} illustrated arrivals · ${snapshot.departures} departures this hour`;
  const totalCapacity = day.capacity;
  let used = snapshot.used, waiting = Math.max(0, used - totalCapacity);
  if (rampScene) {
    const placement = rampScene.update(snapshot, state.prepared, day.capacity_prepared_su);
    used = placement.ramp + placement.remote + placement.waiting;
    waiting = placement.waiting;
  }
  $('#gauge-value').textContent = `${su(used)} / ${su(totalCapacity)}`;
  $('#gauge-fill').style.width = `${Math.min(100, used / totalCapacity * 100)}%`;
  $('.gauge').classList.toggle('overflow', waiting > 0);
  $('#gauge-detail').textContent = waiting > 0 ? `${su(waiting)} in manager-decision area · illustrative` : 'Illustrated aircraft within selected capacity';
  $('#ramp-label').textContent = `${su(data.capacity.ramp_su)} normal${state.prepared ? ` · ${su(data.capacity.ramp_su * (1 + data.capacity.tow_packing_gain))} packed` : ''}`;
  $('#remote-label').textContent = state.prepared ? `${su(Math.max(0, day.capacity_prepared_su - data.capacity.ramp_su * (1 + data.capacity.tow_packing_gain)))} leased for this day` : 'Plan required';
}

function renderAll() {
  view = getView(data, state.situation, state.scenario, state.prepared);
  renderControls(); renderSummary(); renderDayStrip(); renderSelectedDay(); renderChart(); renderTable(); renderPlan(); renderClock();
}

function changeTick(tick) {
  state.tick = Math.max(0, Math.min(data.days.length * 24 - 1, tick));
  $('#date-select').value = String(Math.floor(state.tick / 24));
  renderDayStrip(); renderSelectedDay(); renderChart(); renderTable(); renderClock();
  const capacityStat = $('#plan-impact .impact-stat:last-of-type strong');
  if (capacityStat) capacityStat.textContent = su(selectedDay().capacity);
  const capacityLabel = $('#plan-impact .impact-stat:last-of-type span');
  if (capacityLabel) capacityLabel.textContent = `Selected capacity on ${dateLabel(selectedDay().date, true)}`;
}

function setPlaying(value) {
  state.playing = value;
  state.lastFrame = 0; state.elapsed = 0;
  $('#play').textContent = value ? 'Ⅱ' : '▶';
  $('#play').setAttribute('aria-label', value ? 'Pause time lapse' : 'Play time lapse');
  if (value) requestAnimationFrame(advance);
}
function advance(timestamp) {
  if (!state.playing) return;
  if (document.hidden) { setPlaying(false); return; }
  if (state.lastFrame) state.elapsed += timestamp - state.lastFrame;
  state.lastFrame = timestamp;
  const durations = { slow: 1100, normal: 520, fast: 180 };
  const duration = durations[$('#speed').value];
  if (state.elapsed >= duration) {
    const steps = Math.floor(state.elapsed / duration);
    state.elapsed %= duration;
    if (state.tick + steps >= data.days.length * 24 - 1) { changeTick(data.days.length * 24 - 1); setPlaying(false); return; }
    changeTick(state.tick + steps);
  }
  requestAnimationFrame(advance);
}

function bindEvents() {
  $('#scenario-options').addEventListener('click', event => {
    const button = event.target.closest('[data-scenario]'); if (!button) return;
    state.scenario = button.dataset.scenario;
    snapshots = buildIllustration(data, state.situation, state.scenario);
    renderAll();
  });
  $('#situation').addEventListener('change', event => {
    state.situation = event.target.value;
    snapshots = buildIllustration(data, state.situation, state.scenario);
    renderAll();
  });
  $('#date-select').addEventListener('change', event => changeTick(Number(event.target.value) * 24 + 12));
  $('#prepared').addEventListener('change', event => { state.prepared = event.target.checked; renderAll(); });
  $('#day-strip').addEventListener('click', event => { const button = event.target.closest('[data-day]'); if (button) changeTick(Number(button.dataset.day) * 24 + 12); });
  $('#scrub').addEventListener('input', event => { setPlaying(false); changeTick(Number(event.target.value)); });
  $('#play').addEventListener('click', () => setPlaying(!state.playing));
  $('#actions').addEventListener('click', event => { const button = event.target.closest('[data-choice]'); if (button) saveDecision(button.closest('.action-card'), button.dataset.choice); });
  $('#theme-toggle').addEventListener('click', () => {
    const light = document.documentElement.dataset.theme !== 'light';
    document.documentElement.dataset.theme = light ? 'light' : 'dark';
    $('#theme-toggle').setAttribute('aria-label', `Switch to ${light ? 'dark' : 'light'} theme`);
    try { localStorage.setItem('ramp-control/theme', light ? 'light' : 'dark'); } catch {}
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden && state.playing) setPlaying(false); });
}

async function main() {
  try {
    const response = await fetch('./parking_data.json');
    if (!response.ok) throw new Error(`Data request failed (${response.status})`);
    data = await response.json();
    state.scenario = data.default_scenario;
    const savedTheme = (() => { try { return localStorage.getItem('ramp-control/theme'); } catch { return null; } })();
    if (savedTheme === 'light') { document.documentElement.dataset.theme = 'light'; $('#theme-toggle').setAttribute('aria-label', 'Switch to dark theme'); }
    snapshots = buildIllustration(data, state.situation, state.scenario);
    const firstOver = getView(data, state.situation, state.scenario, false).first;
    if (firstOver) {
      const firstDay = data.days.findIndex(day => day.date === firstOver.date);
      const firstHour = snapshots.slice(firstDay * 24, (firstDay + 1) * 24).findIndex(snapshot => snapshot.used > firstOver.capacity);
      state.tick = firstDay * 24 + (firstHour >= 0 ? firstHour : 12);
    }
    renderAll(); bindEvents();
    $('#capacity-derivation').textContent = data.capacity.derivation;
    $('#human-rule').textContent = data.meta.human_in_command;
    $('#footer-source').textContent = `Supplied parking_data.json · generated ${data.meta.generated_utc}`;
    try {
      const { createRampScene } = await import('./scene.js');
      rampScene = createRampScene($('#scene'), data);
      renderClock();
    } catch (error) {
      $('#scene-fallback').hidden = false;
      console.warn('3D illustration unavailable:', error);
    }
  } catch (error) {
    $('#summary-copy').textContent = `Parking model could not be loaded: ${error.message}. Serve this folder with python3 -m http.server.`;
    $('#scene-fallback').hidden = false;
    console.error(error);
  }
}
main();
