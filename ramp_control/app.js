import { getView, buildIllustration, dateLabel, su, pct, money, HOURS, clockLabel, restrictionAt, getDefaultView, securityPausedAt, getFlowPlan, getImpactGrid, formatSituationOutlookLine } from './model.js';
import { createLayout, buildPlacements } from './layout.js';
import { createStandViews, escapeHTML } from './views.js';

const $ = selector => document.querySelector(selector);
let data, view, snapshots, placements, layout, rampScene, standViews, selection = null;
const state = { scenario: null, situation: null, prepared: false, tick: 0, playing: false, phase: 0, instant: true };
const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');

function selectedDay() { return view.days[Math.floor(state.tick / HOURS)]; }
function activeSnapshot() { return snapshots[state.tick]; }

function renderControls() {
  const defaultDesc = (data.scenarios[data.default_scenario] || '').replace(/:\s*the forecast$/i, '');
  $('#forecast-advice-main').textContent = `Forecast used: ${data.default_scenario}, ${defaultDesc}`;
  const lowDesc = data.scenarios.Low.split('(')[0].trim();
  const highDesc = data.scenarios.High;
  $('#forecast-advice-range').textContent = `Range the model considered: Low ${lowDesc} to High ${highDesc}`;
  $('#date-select').innerHTML = data.days.map((day, index) => `<option value="${index}">${escapeHTML(dateLabel(day.date, true))}${day.date === data.meta.game_day ? ' · Game day' : day.date === data.meta.presidents_day ? ' · Holiday' : ''}</option>`).join('');
  $('#date-select').value = String(Math.floor(state.tick / HOURS));
  $('#prepared').checked = state.prepared;
  $('#view-context').textContent = `${state.scenario} · ${data.situations[state.situation]} · ${state.prepared ? 'prepared' : 'normal'} capacity`;
}

function isModelCall() {
  return state.situation === data.situation_outlook.base_case && state.scenario === data.default_scenario;
}

function renderModelCall() {
  $('#models-call-note').textContent = data.situation_outlook.base_case_note;
  $('#call-demand-line').textContent = `${data.default_scenario}, ${data.scenarios[data.default_scenario].replace(/:\s*the forecast$/i, '')}`;
  $('#demand-levels-list').textContent = Object.entries(data.demand_levels.labels).map(([level, meaning]) => `${level}: ${meaning}`).join(' · ');
  $('#call-situations-items').innerHTML = data.situation_outlook.items.map(item => {
    const line = formatSituationOutlookLine(item, data);
    return `<li><strong>${escapeHTML(line.full)}</strong><p>${escapeHTML(line.basis)}</p></li>`;
  }).join('');
  const preview = !isModelCall();
  $('#whatif-banner').hidden = !preview;
  $('#whatif-text').textContent = preview ? `What-if: ${data.situations[state.situation]}, ${state.scenario} demand. Not the model's call` : '';
  document.body.classList.toggle('preview-active', preview);
}

function renderImpactGrid() {
  $('#impact-grid-table thead').innerHTML = `<tr><th scope="col">Situation / status</th>${Object.entries(data.scenarios).map(([scenario, description]) => `<th scope="col">${escapeHTML(scenario)}<small>${escapeHTML(description)}</small></th>`).join('')}</tr>`;
  $('#impact-grid-lead').textContent = `The parking model evaluates ${data.situation_outlook.items.length * Object.keys(data.scenarios).length} combinations. Select a cell to preview its outcomes everywhere. The highlighted base case is the model's call.`;
  $('#impact-grid-tbody').innerHTML = getImpactGrid(data, state.situation, state.scenario).map(row => `<tr><th scope="row">${escapeHTML(row.label)}<small>${escapeHTML(row.status)}</small></th>${row.cells.map(cell => `<td class="${cell.isModelCall ? 'model-cell' : ''}"><button type="button" class="impact-cell" data-preview-situation="${cell.situation}" data-preview-scenario="${cell.scenario}" data-model-call="${cell.isModelCall}" aria-pressed="${cell.isActive}" aria-label="${escapeHTML(`${cell.situationLabel}, ${cell.scenario} demand${cell.isModelCall ? ", The model's call" : ', what-if preview'}. Peak P50 ${su(cell.peak_su)} on ${cell.peak_day_str}; ${cell.days_over_ramp} days above ramp; plan ${money(cell.plan_cost_usd)}; mean aircraft without a place, no plan ${cell.unaccommodated.no_plan.toFixed(1)}, with plan ${cell.unaccommodated.with_plan.toFixed(1)}.`)}">
    <span class="cell-status">${cell.isModelCall ? "The model's call" : 'What-if'}${cell.isActive ? ' · Current view' : ''}</span>
    <strong>P50 ${su(cell.peak_su)}</strong><span>Peak ${escapeHTML(cell.peak_day_str)}</span>
    <span>${cell.days_over_ramp} days above ramp</span><span>Plan ${money(cell.plan_cost_usd)}</span>
    <span>Without a place: ${cell.unaccommodated.no_plan.toFixed(1)} → ${cell.unaccommodated.with_plan.toFixed(1)}</span>
    <small>Mean aircraft · no plan → plan</small></button></td>`).join('')}</tr>`).join('');
}

function renderFlowPlan() {
  const flow = getFlowPlan(data, state.situation, state.scenario);
  const sizeCounts = counts => Object.keys(data.aircraft.sizes).map(size => `<span>${counts[size]} ${escapeHTML(size)}</span>`).join('');
  $('#flow-plan-tbody').innerHTML = flow.rows.map(row => {
    const actions = row.activePlanActions.map(action => `<li><strong>Recommend:</strong> ${escapeHTML(action.action)} · ${money(action.cost_usd)}<small>Approval required: ${escapeHTML(action.approver)}</small></li>`);
    const levers = row.activeLevers.map(lever => `<li><strong>Offer:</strong> ${escapeHTML(lever.action)}<p>${escapeHTML(lever.rationale)}</p><small>Approval required: ${escapeHTML(lever.approver)} · Take-up ${escapeHTML(flow.take_up_status)}</small></li>`);
    if (row.pauseInstruction) actions.unshift(`<li class="pause-instruction"><strong>Recommend:</strong> ${escapeHTML(row.pauseInstruction)}<small>Named operations manager approval required.</small></li>`);
    return `<tr data-flow-date="${row.date}"><th scope="row">${escapeHTML(dateLabel(row.date, true))}${row.game_day ? '<small>Game day</small>' : row.presidents_day ? "<small>Presidents’ Day</small>" : ''}</th>
      <td><strong class="risk-${row.risk_level.toLowerCase()}">${escapeHTML(row.risk_level)}</strong><small>${escapeHTML(row.demand_meaning)}</small></td>
      <td class="size-counts" data-counts="arrivals">${sizeCounts(row.arrivals)}</td><td class="size-counts" data-counts="departures">${sizeCounts(row.departures)}</td>
      <td class="size-counts" data-counts="at_peak"><strong>${row.at_peak.total} aircraft</strong>${sizeCounts(row.at_peak)}</td>
      <td><strong>${su(row.peak_su)} / ${su(row.ramp_su)}</strong><small>P50 / ramp</small><small>P10–P90: ${su(row.peak_p10)}–${su(row.peak_p90)}</small></td>
      <td class="flow-actions"><ul>${actions.concat(levers).join('') || '<li>No additional preparation recommended.</li>'}</ul></td></tr>`;
  }).join('');
  $('#lever-not-recommended').textContent = flow.not_recommended;
  $('#lever-human-in-command').textContent = `${flow.human_in_command} ${flow.note}`;
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
    return `<button type="button" class="day-button ${status}" data-day="${index}" aria-pressed="${active}" aria-label="${escapeHTML(dateLabel(day.date))}: ${escapeHTML(day.risk_level)} demand (${escapeHTML(data.demand_levels.labels[day.risk_level])}); ${pct(day.probability)} chance of exceeding ${su(day.capacity)}; P50 ${su(day.parking_demand_su_p50)}, P90 ${su(day.parking_demand_su_p90)}"><span class="day-name">${escapeHTML(day.weekday.slice(0, 3))}<b>${Number(day.date.slice(-2))}</b></span><span class="day-event">${event}</span><span class="day-demand risk-${day.risk_level.toLowerCase()}" title="${escapeHTML(data.demand_levels.labels[day.risk_level])}">${escapeHTML(day.risk_level)}</span><span class="day-prob">${pct(day.probability)}</span><span class="day-bar"><i style="width:${Math.max(3, day.probability / maxProbability * 100)}%"></i></span></button>`;
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

  const actions = plan.actions;
  const currentDecisions = actions.map(action => ({ action, record: readDecision(decisionKey(action.id)) }));
  const anyDecided = currentDecisions.some(d => d.record.choice);
  const savedName = localStorage.getItem('ramp-control/manager-name') || '';

  if (anyDecided) {
    const deciderName = currentDecisions.find(d => d.record.name)?.record.name || savedName || 'Manager';
    const deciderTime = currentDecisions.find(d => d.record.time)?.record.time || 'time not recorded';
    const approvedList = currentDecisions.filter(d => d.record.choice === 'approved');
    const dateRange = actions.length > 0 && actions[0].dates.length > 0
      ? `${Number(actions[0].dates[0].slice(-2))}–${Number(actions[0].dates.at(-1).slice(-2))} ${new Date(actions[0].dates[0] + 'T12:00:00Z').toLocaleString('en-US', { month: 'short', timeZone: 'UTC' })}`
      : '';

    let confirmationText = '';
    if (approvedList.length > 0) {
      const summaryList = approvedList.map(d => {
        if (d.action.id === 'tow_packing') return 'tow-in packing';
        if (d.action.id === 'overflow_apron') return d.action.action;
        return d.action.action.toLowerCase();
      });
      const summary = summaryList.length === 2 ? `${summaryList[0]} and ${summaryList[1]}` : summaryList.join(', ');
      confirmationText = `Approved by ${escapeHTML(deciderName)} at ${escapeHTML(deciderTime)}: ${escapeHTML(summary)} active ${escapeHTML(dateRange)}`;
    } else {
      confirmationText = `Rejected by ${escapeHTML(deciderName)} at ${escapeHTML(deciderTime)}: plan rejected (normal ramp capacity only)`;
    }

    $('#actions').innerHTML = `
      <div class="decision-card decided">
        <div class="confirmation-banner" role="status" aria-live="polite">
          <p class="confirmation-line">${confirmationText}</p>
          <button type="button" class="btn-undo" id="btn-undo-plan">Undo</button>
        </div>
        <details class="expert-actions-details">
          <summary class="expert-toggle">Change one action</summary>
          <div class="expert-actions-list">
            ${actions.map(action => renderExpertActionRow(action)).join('')}
          </div>
        </details>
      </div>`;
    return;
  }

  $('#actions').innerHTML = `
    <div class="decision-card single-recommendation-card">
      <div class="recommendation-header">
        <p class="section-kicker">HUMAN IN COMMAND</p>
        <h3>The model recommends</h3>
      </div>
      <div class="recommended-actions">
        ${actions.map(action => `
          <div class="recommended-action-item">
            <div class="rec-action-head">
              <strong>${escapeHTML(action.action)}</strong>
              <span class="action-cost">${money(action.cost_usd)}</span>
            </div>
            <div class="rec-action-meta">
              <span>Approver: ${escapeHTML(action.approver)}</span>
              <span>${escapeHTML(dateLabel(action.dates[0], true))}–${escapeHTML(dateLabel(action.dates.at(-1), true))}</span>
            </div>
            <p class="rec-action-rationale">${escapeHTML(action.rationale)}</p>
          </div>
        `).join('')}
      </div>
      <div class="decision-form">
        <div class="decision-inputs">
          <label class="input-wrap">
            <span class="sr-only">Manager name</span>
            <input id="manager-name-input" class="manager-input" type="text" maxlength="80" placeholder="Manager name" value="${escapeHTML(savedName)}" required>
          </label>
          <label class="input-wrap">
            <span class="sr-only">Decision note</span>
            <input id="decision-note-input" class="note-input" type="text" maxlength="240" placeholder="Decision note (optional)">
          </label>
        </div>
        <div class="plan-decision-buttons">
          <button type="button" id="approve-plan-btn" class="plan-decision-btn btn-approve">Approve plan</button>
          <button type="button" id="reject-plan-btn" class="plan-decision-btn btn-reject">Reject plan</button>
        </div>
        <div id="plan-validation" class="validation" aria-live="polite"></div>
      </div>
      <details class="expert-actions-details">
        <summary class="expert-toggle">Change one action</summary>
        <div class="expert-actions-list">
          ${actions.map(action => renderExpertActionRow(action)).join('')}
        </div>
      </details>
    </div>`;
}

function renderExpertActionRow(action) {
  const key = decisionKey(action.id);
  const record = readDecision(key);
  return `
    <div class="expert-action-row" data-action="${escapeHTML(action.id)}">
      <div class="expert-row-info">
        <strong>${escapeHTML(action.action)}</strong>
        <small>${money(action.cost_usd)} · ${escapeHTML(action.approver)}</small>
      </div>
      <div class="expert-row-controls">
        <button type="button" data-expert-choice="approved" class="${record.choice === 'approved' ? 'selected' : ''}">Approve</button>
        <button type="button" data-expert-choice="rejected" class="${record.choice === 'rejected' ? 'selected' : ''}">Reject</button>
      </div>
    </div>`;
}

function decisionKey(id) { return `ramp-control/${state.situation}/${state.scenario}/${id}`; }
function readDecision(key) {
  try {
    const record = JSON.parse(localStorage.getItem(key) || '{}');
    return record && typeof record === 'object' ? {
      choice: ['approved', 'rejected'].includes(record.choice) ? record.choice : '',
      name: typeof record.name === 'string' ? record.name : '',
      note: typeof record.note === 'string' ? record.note : '',
      time: typeof record.time === 'string' ? record.time : ''
    } : {};
  } catch { return {}; }
}

function executePlanDecision(choice) {
  const nameInput = $('#manager-name-input');
  const noteInput = $('#decision-note-input');
  const valMsg = $('#plan-validation');
  const name = nameInput ? nameInput.value.trim() : (localStorage.getItem('ramp-control/manager-name') || '');
  const note = noteInput ? noteInput.value.trim() : '';

  if (!name) {
    if (valMsg) valMsg.textContent = 'Enter a manager name to record this decision.';
    nameInput?.focus();
    return;
  }

  try { localStorage.setItem('ramp-control/manager-name', name); } catch {}

  const now = new Date();
  const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  const actions = data.parking[state.situation].plans[state.scenario].actions;

  for (const action of actions) {
    const key = decisionKey(action.id);
    try {
      localStorage.setItem(key, JSON.stringify({ choice, name, note, time }));
    } catch {}
  }

  rebuildPlacements();
  state.instant = true;
  renderPlan();
  renderClock();
}

function undoPlanDecision() {
  const actions = data.parking[state.situation].plans[state.scenario].actions;
  for (const action of actions) {
    const key = decisionKey(action.id);
    try { localStorage.removeItem(key); } catch {}
  }
  rebuildPlacements();
  state.instant = true;
  renderPlan();
  renderClock();
}

function executeExpertDecision(actionId, choice) {
  const nameInput = $('#manager-name-input');
  const savedName = localStorage.getItem('ramp-control/manager-name') || '';
  const name = nameInput ? nameInput.value.trim() || savedName : savedName;
  if (!name) {
    const valMsg = $('#plan-validation');
    if (valMsg) valMsg.textContent = 'Enter a manager name above before recording decisions.';
    nameInput?.focus();
    return;
  }
  try { localStorage.setItem('ramp-control/manager-name', name); } catch {}

  const now = new Date();
  const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  const key = decisionKey(actionId);
  try {
    localStorage.setItem(key, JSON.stringify({ choice, name, note: '', time }));
  } catch {}

  rebuildPlacements();
  state.instant = true;
  renderPlan();
  renderClock();
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
  const hour = state.tick % HOURS + state.phase;
  $('#scrub').value = String(state.tick + state.phase);
  $('#scrub').setAttribute('aria-valuetext', `${dateLabel(day.date)} ${clockLabel(hour)}`);
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
  $('#hud-view-context').textContent = `${isModelCall() ? "The model's call" : 'What-if preview'} · ${state.scenario} · ${data.situations[state.situation]}`;
  $('#hud-short').textContent = `${dateLabel(day.date, true)} · ${pct(day.probability)} daily chance over ${state.prepared ? 'prepared' : 'ramp'} space`;
  $('#hud-answer').textContent = `${dateLabel(day.date)}: median demand ${day.parking_demand_su_p50 > day.capacity ? 'exceeds' : 'fits within'} ${su(day.capacity)} of ${state.prepared ? 'proposed prepared' : 'normal ramp'} space, with a ${pct(day.probability)} daily chance of exceeding it.`;
  $('#hud-range').textContent = `Modeled demand: P50 ${su(day.parking_demand_su_p50)} · P10–P90 ${su(day.parking_demand_su_p10)}–${su(day.parking_demand_su_p90)}. Clock and positions are illustrative; approvals control the gauge.`;
  $('#ramp-label').textContent = `${su(data.capacity.ramp_su)}${placement.capacity.packed ? ` + ${su(placement.capacity.packed)} packed` : ''}`;
  $('#remote-label').textContent = placement.capacity.remote ? `${su(placement.capacity.remote)} approved today` : 'No approved space today';

  const rampCount = placement.placed.filter(plane => plane.area === 'ramp' || plane.area === 'packed' || plane.area === 'remote').length;
  const rampEl = $('#hud-ramp-count');
  if (rampEl) rampEl.textContent = `Aircraft on the ramp now: ${rampCount}`;

  const peakData = data.ramp_aircraft?.by_situation?.[state.situation]?.[state.scenario]?.[day.date]?.at_peak_p50;
  if (peakData) {
    const a = Math.round(peakData.light);
    const b = Math.round(peakData.midsize);
    const c = Math.round(peakData.large);
    const peakTotal = a + b + c;
    const peakEl = $('#hud-peak-count');
    const daySnapshots = snapshots.slice(snapshot.dayIndex * HOURS, (snapshot.dayIndex + 1) * HOURS);
    const busiest = daySnapshots.reduce((acc, f) => f.used > acc.used ? f : acc);
    const busiestCount = busiest.fleet.length;
    if (peakEl) {
      if (busiestCount !== peakTotal) {
        peakEl.textContent = `on the ramp at peak: ${busiestCount}, model median: ${peakTotal} (${a} light, ${b} midsize, ${c} large)`;
      } else {
        peakEl.textContent = `Model median at today's peak: ${peakTotal} (${a} light, ${b} midsize, ${c} large)`;
      }
    }
  }

  const pause = restrictionAt(data, state.situation, day.date);
  $('#restriction-note').hidden = !pause;
  $('#restriction-note').textContent = pause ? `Security pause (${pause.status}): ${pause.start}–${pause.end}. ${pause.basis} Illustrated timing keeps movements outside this window; daily totals are preserved.` : '';
  rampScene?.update(placement); standViews?.update(placement);
  rampScene?.setForecast(view.days, snapshot.dayIndex); syncFollowControl(); syncProgress();
}
function syncProgress() {
  const hour = state.tick % HOURS + state.phase;
  $('#clock-face').textContent = `${dateLabel(selectedDay().date, true)} · ${clockLabel(hour)}`;
  $('#scrub').value = String(state.tick + state.phase);
  $('#scrub').setAttribute('aria-valuetext', `${dateLabel(selectedDay().date)} ${clockLabel(hour)}`);
  $('#pause-stage-banner').hidden = !securityPausedAt(data, state.situation, selectedDay().date, hour);
  standViews?.setTime(hour);
  rampScene?.setProgress(state.instant || motionQuery.matches ? 1 : state.phase, hour);
}
function renderAll() {
  view = getView(data, state.situation, state.scenario, state.prepared);
  renderControls(); renderModelCall(); renderImpactGrid(); renderFlowPlan(); renderSummary(); renderDayStrip(); renderSelectedDay(); renderChart(); renderTable(); renderPlan(); renderClock();
}
function changeTick(tick, animated = false) {
  const previousDay = Math.floor(state.tick / HOURS);
  const newTick = Math.max(0, Math.min(snapshots.length - 1, Math.floor(tick)));
  const fractional = Math.max(0, Math.min(0.999999, tick - newTick));
  state.tick = newTick;
  state.phase = animated ? 0 : fractional;
  state.instant = !animated && fractional === 0;
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
  const secondsPerHour = { realtime: 60, slow: 12, normal: 4, fast: 2 }[$('#speed').value] || 4;
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
  $('#impact-grid-tbody').addEventListener('click', event => {
    const button = event.target.closest('[data-preview-situation]');
    if (!button) return;
    state.situation = button.dataset.previewSituation;
    state.scenario = button.dataset.previewScenario;
    resetSimulation();
    document.querySelector(`[data-preview-situation="${state.situation}"][data-preview-scenario="${state.scenario}"]`)?.focus({ preventScroll: true });
  });
  $('#whatif-back-btn').addEventListener('click', () => {
    Object.assign(state, getDefaultView(data)); resetSimulation();
    document.querySelector('[data-model-call="true"]')?.focus({ preventScroll: true });
  });
  new ResizeObserver(() => {
    document.documentElement.style.setProperty('--preview-height', `${$('#whatif-banner').getBoundingClientRect().height}px`);
  }).observe($('#whatif-banner'));
  $('#date-select').addEventListener('change', event => { setPlaying(false); changeTick(Number(event.target.value) * HOURS + state.tick % HOURS); });
  $('#prepared').addEventListener('change', event => { state.prepared = event.target.checked; renderAll(); });
  $('#day-strip').addEventListener('click', event => { const button = event.target.closest('[data-day]'); if (button) { setPlaying(false); changeTick(Number(button.dataset.day) * HOURS + state.tick % HOURS); } });
  const chartSelect = event => { const mark = event.target.closest('[data-chart-day]'); if (mark) { setPlaying(false); changeTick(Number(mark.dataset.chartDay) * HOURS + state.tick % HOURS); } };
  $('#week-chart').addEventListener('click', chartSelect);
  $('#week-chart').addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); chartSelect(event); } });
  $('#scrub').addEventListener('input', event => { setPlaying(false); changeTick(Number(event.target.value)); });
  $('#play').addEventListener('click', () => setPlaying(!state.playing));
  $('#actions').addEventListener('click', event => {
    if (event.target.closest('#approve-plan-btn')) { executePlanDecision('approved'); return; }
    if (event.target.closest('#reject-plan-btn')) { executePlanDecision('rejected'); return; }
    if (event.target.closest('#btn-undo-plan')) { undoPlanDecision(); return; }
    const expertBtn = event.target.closest('[data-expert-choice]');
    if (expertBtn) {
      const row = expertBtn.closest('.expert-action-row');
      if (row) executeExpertDecision(row.dataset.action, expertBtn.dataset.expertChoice);
    }
  });
  $('#hud-toggle')?.addEventListener('click', () => {
    const hud = $('#scene-hud');
    if (!hud) return;
    const collapsed = hud.classList.toggle('is-collapsed');
    $('#hud-toggle').setAttribute('aria-expanded', String(!collapsed));
    $('#hud-toggle').textContent = collapsed ? 'Expand' : 'Collapse';
  });
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
  const banner = $('#whatif-banner');
  if (active) $('#scene-stage').prepend(banner);
  else document.body.prepend(banner);
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
    Object.assign(state, getDefaultView(data));
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
