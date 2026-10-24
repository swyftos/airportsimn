/**
 * LAX FBO Super Bowl LXI Week Planner - Operational JavaScript
 * Week-first operational planning dashboard for LAX FBO private aviation
 * Landings and Departures only. No staffing, no fuel. Zero passenger data.
 * All factual statements strictly from agent_data.json.
 */

// Application State
const state = {
  data: null,
  scenario: 'Medium', // 'Low' | 'Medium' | 'High'
  simulatedNow: '2027-02-12T10:00',
  selectedDay: '2027-02-12',
  activeTab: 'view-week',
  heatmapMetric: 'total', // 'total' | 'arrivals' | 'departures'
  weatherSettings: {
    '2027-02-11': 'clear',
    '2027-02-12': 'clear',
    '2027-02-13': 'clear',
    '2027-02-14': 'clear',
    '2027-02-15': 'clear',
    '2027-02-16': 'clear',
    '2027-02-17': 'clear'
  },
  proposalStates: {}, // { [id]: { status: 'pending'|'acknowledged'|'dismissed', note: '' } }
  userMovements: [], // Array of flight objects
  theme: 'light',
  editingMovementId: null
};

// Storage Keys
const STORAGE_KEY_MOVEMENTS = 'lax_fbo_movements_v2';
const STORAGE_KEY_PROPOSALS = 'lax_fbo_proposals_v1';
const STORAGE_KEY_WEATHER = 'lax_fbo_weather_v1';
const STORAGE_KEY_THEME = 'lax_fbo_theme_v1';
const STORAGE_KEY_SCENARIO = 'lax_fbo_scenario_v1';

// Initialize Application
document.addEventListener('DOMContentLoaded', async () => {
  loadStoredPreferences();
  setupNavigation();
  setupControls();
  await loadData();
  renderAllViews();
});

// ---- Values derived from agent_data.json (no hard-coded windows, dates or shares) ----
function restriction() { return state.data.game_day_restriction; }
function isRestrictionDay(day) { return !!(day.security_restriction && restriction() && restriction().date === day.date); }
function clockToHours(t) { const [h, m] = t.split(':').map(Number); return h + m / 60; }
function restrictionLabel() { return `${restriction().start}–${restriction().end}`; }
function inRestriction(day, hourStart, hourEnd) {
  if (!isRestrictionDay(day)) return false;
  return Math.min(hourEnd, clockToHours(restriction().end)) > Math.max(hourStart, clockToHours(restriction().start));
}
function dayHourShares(day, target) {
  if (isRestrictionDay(day)) return restriction().hour_shares[target];
  return state.data.hourly_profile.shares[`${day.day_type}_${target}`];
}
// Busiest run of `len` consecutive hours for a share curve; returns start/end hour and its share of the day
function peakWindow(shares, len = 3) {
  let best = -1, start = 0;
  for (let h = 0; h + len <= 24; h++) {
    const v = shares.slice(h, h + len).reduce((a, b) => a + b, 0);
    if (v > best + 1e-12) { best = v; start = h; }
  }
  return { start, end: start + len, share: best };
}
function fmtHour(h) { return `${String(h).padStart(2, '0')}:00`; }
function fmtWindow(w) { return `${fmtHour(w.start)}–${fmtHour(w.end)}`; }
// Share of the restricted day's departures from the hour the window ends until midnight
function shareAfterRestriction(target) {
  const end = clockToHours(restriction().end);
  return restriction().hour_shares[target].reduce((a, v, h) => a + (h + 1 > end ? v : 0), 0);
}
function scenarioSensitivity(day) {
  const v = Object.values(day.scenarios);
  const varies = key => v.some(x => Math.abs(x[key] - v[0][key]) > 1e-9);
  return { arrivals: varies('expected_arrivals'), departures: varies('expected_departures') };
}
function scenarioNote(day) {
  const s = scenarioSensitivity(day);
  if (!s.arrivals && !s.departures) return 'Same in Low, Forecast and High: the model adds the Super Bowl effect from Thursday to Monday only (the window measured in 2022), so this day is the ordinary forecast in every scenario.';
  if (!s.arrivals) return 'Landings are the same in every scenario; only departures change (the model places the extra event departures on this day).';
  if (!s.departures) return 'Departures are the same in every scenario; only landings change (the model places the extra event arrivals on this day).';
  return '';
}
const WEATHER_NAMES = { clear: 'Clear', rain: 'Rain', heavy_rain: 'Heavy rain', heavy_fog: 'Heavy fog' };
function weatherName(type) { return WEATHER_NAMES[type] || type; }
function weatherProbLabel(type) { return `${(state.data.weather.february_probability[type] * 100).toFixed(1)}% of Feb days`; }
function signedPct(x) { const v = Math.round(x * 100); return `${v >= 0 ? '+' : ''}${v}%`; }

/**
 * Load local storage preferences and movements
 */
function loadStoredPreferences() {
  try {
    const savedMovements = localStorage.getItem(STORAGE_KEY_MOVEMENTS);
    if (savedMovements) {
      state.userMovements = JSON.parse(savedMovements);
    } else {
      state.userMovements = []; // the agent enters real movements; no invented data
    }

    const savedProposals = localStorage.getItem(STORAGE_KEY_PROPOSALS);
    if (savedProposals) {
      state.proposalStates = JSON.parse(savedProposals);
    }

    const savedWeather = localStorage.getItem(STORAGE_KEY_WEATHER);
    if (savedWeather) {
      state.weatherSettings = { ...state.weatherSettings, ...JSON.parse(savedWeather) };
    }

    const savedScenario = localStorage.getItem(STORAGE_KEY_SCENARIO);
    if (savedScenario && ['Low', 'Medium', 'High'].includes(savedScenario)) {
      state.scenario = savedScenario;
    }

    const savedTheme = localStorage.getItem(STORAGE_KEY_THEME);
    if (savedTheme) {
      state.theme = savedTheme;
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      state.theme = 'dark';
    }
    applyTheme(state.theme);
  } catch (err) {
    console.error('Error reading localStorage preferences:', err);
  }
}

function saveMovements() {
  try {
    localStorage.setItem(STORAGE_KEY_MOVEMENTS, JSON.stringify(state.userMovements));
  } catch (e) {
    console.error('Failed to save movements:', e);
  }
  updateNavCount();
}

function saveProposals() {
  try {
    localStorage.setItem(STORAGE_KEY_PROPOSALS, JSON.stringify(state.proposalStates));
  } catch (e) {
    console.error('Failed to save proposals:', e);
  }
}

function saveWeather() {
  try {
    localStorage.setItem(STORAGE_KEY_WEATHER, JSON.stringify(state.weatherSettings));
  } catch (e) {
    console.error('Failed to save weather:', e);
  }
}

function applyTheme(theme) {
  state.theme = theme;
  document.documentElement.setAttribute('data-theme', theme);
  const themeToggle = document.getElementById('theme-toggle');
  if (themeToggle) {
    const icon = themeToggle.querySelector('.theme-icon');
    const text = themeToggle.querySelector('.theme-text');
    if (theme === 'dark') {
      if (icon) icon.textContent = '☀️';
      if (text) text.textContent = 'Light';
    } else {
      if (icon) icon.textContent = '🌙';
      if (text) text.textContent = 'Dark';
    }
  }
  localStorage.setItem(STORAGE_KEY_THEME, theme);
}

/**
 * Fetch agent_data.json
 */
async function loadData() {
  try {
    const res = await fetch('agent_data.json');
    if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load agent_data.json`);
    state.data = await res.json();

    // Populate metadata banners
    const metaNeverAllowed = document.getElementById('meta-never-allowed');
    if (metaNeverAllowed && state.data.meta && state.data.meta.never_allowed) {
      metaNeverAllowed.textContent = `Strict Limit: The tool will never ${state.data.meta.never_allowed.toLowerCase()} ${state.data.meta.human_in_command}`;
    }

    const metaPrivacy = document.getElementById('meta-privacy');
    if (metaPrivacy && state.data.meta && state.data.meta.privacy) {
      metaPrivacy.textContent = state.data.meta.privacy;
    }
  } catch (err) {
    console.error('Data loading error:', err);
    showToast('Failed to load agent_data.json. Ensure python3 -m http.server is running in agent_gemini/.', true);
  }
}

/**
 * Setup Tab Navigation and Events
 */
function setupNavigation() {
  const tabs = document.querySelectorAll('.nav-btn');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const targetViewId = tab.getAttribute('aria-controls');
      switchTab(targetViewId);
    });
  });

  const backBtn = document.getElementById('back-to-week-btn');
  if (backBtn) {
    backBtn.addEventListener('click', () => {
      switchTab('view-week');
    });
  }

  const jumpToAddBtn = document.getElementById('btn-jump-to-add');
  if (jumpToAddBtn) {
    jumpToAddBtn.addEventListener('click', () => {
      switchTab('view-movements');
      const formDate = document.getElementById('form-date');
      if (formDate) formDate.value = state.selectedDay;
      const formTime = document.getElementById('form-time');
      if (formTime) formTime.focus();
    });
  }
}

function switchTab(viewId) {
  state.activeTab = viewId;
  document.querySelectorAll('.tab-view').forEach(view => {
    if (view.id === viewId) {
      view.classList.add('active');
      view.removeAttribute('hidden');
    } else {
      view.classList.remove('active');
      view.setAttribute('hidden', 'true');
    }
  });

  document.querySelectorAll('.nav-btn').forEach(btn => {
    const isSelected = btn.getAttribute('aria-controls') === viewId;
    btn.setAttribute('aria-selected', isSelected ? 'true' : 'false');
    btn.classList.toggle('active', isSelected);
  });

  // Re-render relevant view
  if (viewId === 'view-day') {
    renderDayDetail();
  } else if (viewId === 'view-movements') {
    renderMovementsBoard();
  } else if (viewId === 'view-trust') {
    renderTrustView();
  } else if (viewId === 'view-week') {
    renderHeatmap();
    renderDayCards();
    renderProposals();
  }
}

/**
 * Setup Controls (Scenario, Time, Theme, Filters)
 */
function setupControls() {
  // Scenario selector
  const scenarioBtns = document.querySelectorAll('#scenario-selector .segment-btn');
  scenarioBtns.forEach(btn => {
    if (btn.dataset.scenario === state.scenario) btn.classList.add('active');
    else btn.classList.remove('active');

    btn.addEventListener('click', () => {
      scenarioBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.scenario = btn.dataset.scenario;
      localStorage.setItem(STORAGE_KEY_SCENARIO, state.scenario);
      showToast(`Scenario switched to ${state.scenario} (${state.data ? state.data.scenarios[state.scenario] : ''})`);
      renderAllViews();
    });
  });

  // Heatmap metric selector
  const heatmapMetricBtns = document.querySelectorAll('#heatmap-metric-selector .segment-btn');
  heatmapMetricBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      heatmapMetricBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.heatmapMetric = btn.dataset.metric;
      renderHeatmap();
    });
  });

  // Demo Time Selector
  const demoTimeSelect = document.getElementById('demo-time-select');
  if (demoTimeSelect) {
    demoTimeSelect.value = state.simulatedNow;
    demoTimeSelect.addEventListener('change', (e) => {
      state.simulatedNow = e.target.value;
      const day = e.target.value.split('T')[0];
      state.selectedDay = day;
      renderTopKPIs();
      if (state.activeTab === 'view-day') renderDayDetail();
      showToast(`Simulated time set to ${formatDateTime(state.simulatedNow)}`);
    });
  }

  // Theme Toggle
  const themeToggle = document.getElementById('theme-toggle');
  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const nextTheme = state.theme === 'dark' ? 'light' : 'dark';
      applyTheme(nextTheme);
    });
  }

  // Reset Weather button
  const resetWeatherBtn = document.getElementById('reset-weather-btn');
  if (resetWeatherBtn) {
    resetWeatherBtn.addEventListener('click', () => {
      Object.keys(state.weatherSettings).forEach(d => state.weatherSettings[d] = 'clear');
      saveWeather();
      renderAllViews();
      showToast('All daily weather conditions reset to Clear');
    });
  }

  // Movement Form
  const movementForm = document.getElementById('movement-form');
  if (movementForm) {
    movementForm.addEventListener('submit', handleMovementSubmit);
  }

  const cancelEditBtn = document.getElementById('btn-cancel-edit');
  if (cancelEditBtn) {
    cancelEditBtn.addEventListener('click', cancelMovementEdit);
  }

  // Movement Tools
  const clearMovementsBtn = document.getElementById('btn-clear-movements');
  if (clearMovementsBtn) {
    clearMovementsBtn.addEventListener('click', () => {
      if (confirm('Clear all logged movements? This cannot be undone.')) {
        state.userMovements = [];
        saveMovements();
        renderAllViews();
        showToast('All flight movements cleared');
      }
    });
  }

  const exportCsvBtn = document.getElementById('btn-export-csv');
  if (exportCsvBtn) {
    exportCsvBtn.addEventListener('click', exportMovementsToCsv);
  }

  const csvFileInput = document.getElementById('csv-file-input');
  if (csvFileInput) {
    csvFileInput.addEventListener('change', importMovementsFromCsv);
  }

  // Board Filters
  ['filter-date-select', 'filter-type-select', 'filter-status-select'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', renderMovementsBoard);
  });

  // Super Bowl Test Metric Filter
  const sbMetricFilter = document.getElementById('sb-metric-filter');
  if (sbMetricFilter) {
    sbMetricFilter.addEventListener('change', renderSuperBowlTestTable);
  }
}

/**
 * Re-render all views and KPIs
 */
function renderAllViews() {
  if (!state.data) return;
  updateNavCount();
  renderTopKPIs();
  renderHeatmap();
  renderDayCards();
  renderProposals();
  renderDayDetail();
  renderMovementsBoard();
  renderTrustView();
}

function updateNavCount() {
  const badge = document.getElementById('nav-flight-count');
  if (badge) badge.textContent = state.userMovements.length;
}

/**
 * Compute Weather Calculations & Carryovers
 * Formula: Effect = share_part91 * effect_part91 + share_part135 * effect_part135
 * Lost movements roll to the next day.
 */
function computeDailyWeatherImpacts() {
  if (!state.data) return [];
  const days = state.data.days;
  const weatherData = state.data.weather;
  const impacts = [];

  let carriedOverArrivals = 0;
  let carriedOverDepartures = 0;
  let carriedOverFromDay = null;

  for (let i = 0; i < days.length; i++) {
    const day = days[i];
    const scen = day.scenarios[state.scenario];
    const weather = state.weatherSettings[day.date] || 'clear';

    let effectPct = 0;
    let effectDetails = null;

    if (weather !== 'clear' && weatherData.effects[weather]) {
      const eff = weatherData.effects[weather];
      effectPct = (scen.share_part91 * eff.part91.effect) + (scen.share_part135 * eff.part135.effect);
      effectDetails = {
        weather,
        p91_share: scen.share_part91,
        p91_eff: eff.part91.effect,
        p135_share: scen.share_part135,
        p135_eff: eff.part135.effect,
        prob: weatherData.february_probability[weather]
      };
    }

    const baseArrivals = scen.expected_arrivals;
    const baseDepartures = scen.expected_departures;

    // Receive carryover from previous day
    const arrivalsBeforeWeather = baseArrivals + carriedOverArrivals;
    const departuresBeforeWeather = baseDepartures + carriedOverDepartures;

    let lostArrivals = 0;
    let lostDepartures = 0;
    let finalArrivals = arrivalsBeforeWeather;
    let finalDepartures = departuresBeforeWeather;

    if (effectPct < 0) {
      lostArrivals = arrivalsBeforeWeather * Math.abs(effectPct);
      lostDepartures = departuresBeforeWeather * Math.abs(effectPct);
      finalArrivals = arrivalsBeforeWeather - lostArrivals;
      finalDepartures = departuresBeforeWeather - lostDepartures;
    } else if (effectPct > 0) {
      finalArrivals = arrivalsBeforeWeather * (1 + effectPct);
      finalDepartures = departuresBeforeWeather * (1 + effectPct);
    }

    const factor = 1 + effectPct;
    const arrRange = scen.arrivals_range90.map(v => (v + carriedOverArrivals) * factor);
    const depRange = scen.departures_range90.map(v => (v + carriedOverDepartures) * factor);
    impacts.push({
      arrRange,
      depRange,
      weatherDeltaArr: finalArrivals - (baseArrivals + carriedOverArrivals),
      weatherDeltaDep: finalDepartures - (baseDepartures + carriedOverDepartures),
      date: day.date,
      weekday: day.weekday,
      weather,
      effectPct,
      effectDetails,
      carriedOverArrivals,
      carriedOverDepartures,
      carriedOverFromDay,
      finalArrivals,
      finalDepartures,
      lostArrivals,
      lostDepartures,
      day
    });

    // Lost movements roll to the following day
    carriedOverArrivals = lostArrivals;
    carriedOverDepartures = lostDepartures;
    carriedOverFromDay = lostArrivals + lostDepartures > 0 ? day.weekday : null;
  }

  return impacts;
}

/**
 * Top KPI Summary Bar
 */
function renderTopKPIs() {
  if (!state.data) return;
  const impacts = computeDailyWeatherImpacts();
  const scen = state.scenario;

  // Find peak arrival day
  let peakArrDay = impacts[0];
  impacts.forEach(d => {
    if (d.finalArrivals > peakArrDay.finalArrivals) peakArrDay = d;
  });

  const peakArrDayEl = document.getElementById('kpi-peak-arrival-day');
  const peakArrStatsEl = document.getElementById('kpi-peak-arrival-stats');
  if (peakArrDayEl && peakArrStatsEl) {
    const rawScen = peakArrDay.day.scenarios[scen];
    const pctVsOrd = Math.round(((peakArrDay.finalArrivals - rawScen.ordinary_arrivals) / rawScen.ordinary_arrivals) * 100);
    peakArrDayEl.textContent = `${peakArrDay.weekday} ${formatDateShort(peakArrDay.date)}`;
    peakArrStatsEl.textContent = `${peakArrDay.finalArrivals.toFixed(1)} arrivals (90% range ${peakArrDay.arrRange[0].toFixed(1)}–${peakArrDay.arrRange[1].toFixed(1)}) • ${signedPct(peakArrDay.finalArrivals / rawScen.ordinary_arrivals - 1)} vs ordinary (${rawScen.ordinary_arrivals.toFixed(1)})`;
    const w = peakWindow(dayHourShares(peakArrDay.day, 'arrivals'));
    const winEl = document.getElementById('kpi-peak-arrival-window');
    if (winEl) winEl.textContent = `${fmtWindow(w)} (${Math.round(w.share * 100)}% of the day's landings)`;
  }

  // Find peak departure day
  let peakDepDay = impacts[0];
  impacts.forEach(d => {
    if (d.finalDepartures > peakDepDay.finalDepartures) peakDepDay = d;
  });

  const peakDepDayEl = document.getElementById('kpi-peak-departure-day');
  const peakDepStatsEl = document.getElementById('kpi-peak-departure-stats');
  if (peakDepDayEl && peakDepStatsEl) {
    const rawScen = peakDepDay.day.scenarios[scen];
    const pctVsOrd = Math.round(((peakDepDay.finalDepartures - rawScen.ordinary_departures) / rawScen.ordinary_departures) * 100);
    peakDepDayEl.textContent = `${peakDepDay.weekday} ${formatDateShort(peakDepDay.date)}`;
    peakDepStatsEl.textContent = `${peakDepDay.finalDepartures.toFixed(1)} departures (90% range ${peakDepDay.depRange[0].toFixed(1)}–${peakDepDay.depRange[1].toFixed(1)}) • ${signedPct(peakDepDay.finalDepartures / rawScen.ordinary_departures - 1)} vs ordinary (${rawScen.ordinary_departures.toFixed(1)})`;
    const w = peakWindow(dayHourShares(peakDepDay.day, 'departures'));
    const winEl = document.getElementById('kpi-peak-departure-window');
    if (winEl) winEl.textContent = `${fmtWindow(w)} (${Math.round(w.share * 100)}% of the day's departures)`;
  }

  // Restriction card, from game_day_restriction
  const r = restriction(), rDay = impacts.find(d => d.date === r.date);
  const setText = (id, t) => { const el = document.getElementById(id); if (el) el.textContent = t; };
  setText('kpi-restriction-title', `Game-day restriction (${rDay ? rDay.weekday.slice(0, 3) + ' ' + formatDateShort(r.date) : r.date})`);
  setText('kpi-restriction-window', `${restrictionLabel()} local time`);
  setText('kpi-restriction-rule', `Assumption: ${r.status}`);
  if (rDay) {
    const after = shareAfterRestriction('departures');
    setText('kpi-restriction-after', `${r.end}–24:00: ${Math.round(after * 100)}% of the day's departures (~${(rDay.finalDepartures * after).toFixed(1)})`);
  }

  // Ramp space: the day with the highest chance the ramp is full
  const fri = impacts.reduce((a, d) => (d.day.scenarios[scen].prob_ramp_full > a.day.scenarios[scen].prob_ramp_full ? d : a), impacts[0]);
  if (fri) {
    const friScen = fri.day.scenarios[scen];
    const rampStats = document.getElementById('kpi-ramp-stats');
    const rampProb = document.getElementById('kpi-ramp-prob');
    const rampBadge = document.getElementById('kpi-ramp-badge');
    if (rampStats && rampProb) {
      rampStats.textContent = `P90: ${friScen.parking_su_p90.toFixed(1)} su vs ${friScen.ramp_capacity_su.toFixed(1)} cap`;
      rampProb.textContent = `${Math.round(friScen.prob_ramp_full * 100)}% chance the ramp is full (${fri.weekday.slice(0, 3)} ${formatDateShort(fri.date)}) • P50: ${friScen.parking_su_p50.toFixed(1)} su`;
      if (rampBadge) {
        if (friScen.prob_ramp_full > 0.7) {
          rampBadge.className = 'badge badge-critical';
          rampBadge.textContent = 'HIGH RAMP RISK';
        } else if (friScen.prob_ramp_full > 0.3) {
          rampBadge.className = 'badge badge-warning';
          rampBadge.textContent = 'CAPACITY RISK';
        } else {
          rampBadge.className = 'badge badge-ok';
          rampBadge.textContent = 'RAMP ADEQUATE';
        }
      }
    }
  }
}

/**
 * Hourly calculation for any day
 */
function getHourlyProfileForDay(dayObj, finalArrivals, finalDepartures) {
  const hourly = state.data.hourly_profile.shares;
  let arrShares, depShares;

  arrShares = dayHourShares(dayObj, 'arrivals');
  depShares = dayHourShares(dayObj, 'departures');

  const hours = [];
  for (let h = 0; h < 24; h++) {
    const arrExp = finalArrivals * arrShares[h];
    const depExp = finalDepartures * depShares[h];
    const isTfr = inRestriction(dayObj, h, h + 1);

    // Check user movements for this hour
    const userInHour = state.userMovements.filter(m => {
      if (m.date !== dayObj.date) return false;
      const hourInt = parseInt(m.time.split(':')[0], 10);
      return hourInt === h;
    });

    const userArrCount = userInHour.filter(m => m.type === 'arrival').length;
    const userDepCount = userInHour.filter(m => m.type === 'departure').length;

    hours.push({
      hour: h,
      arrShare: arrShares[h],
      depShare: depShares[h],
      arrExp,
      depExp,
      totalExp: arrExp + depExp,
      isTfr,
      userFlights: userInHour,
      userArrCount,
      userDepCount,
      hasUserFlight: userInHour.length > 0
    });
  }

  return hours;
}

/**
 * SECTION A: 7-Day x 24-Hour Calendar / Heatmap (The Core Landing Angle)
 */
function renderHeatmap() {
  if (!state.data) return;
  const container = document.getElementById('heatmap-container');
  if (!container) return;

  const impacts = computeDailyWeatherImpacts();
  const metric = state.heatmapMetric; // 'total' | 'arrivals' | 'departures'

  let html = `<table class="heatmap-table" role="grid" aria-label="7 days by 24 hours busy hours heatmap">
    <thead>
      <tr>
        <th class="heatmap-th heatmap-th-day">Day / Hour</th>`;

  for (let h = 0; h < 24; h++) {
    const hourStr = h.toString().padStart(2, '0');
    html += `<th class="heatmap-th heatmap-th-hour" scope="col">${hourStr}</th>`;
  }
  html += `</tr></thead><tbody>`;

  impacts.forEach(impact => {
    const day = impact.day;
    const hours = getHourlyProfileForDay(day, impact.finalArrivals, impact.finalDepartures);
    const dayLabel = `${day.weekday.slice(0, 3)} ${formatDateShort(day.date)}`;
    const isSelected = day.date === state.selectedDay;

    html += `<tr class="heatmap-row ${isSelected ? 'row-selected' : ''}" data-date="${day.date}">
      <th class="heatmap-th heatmap-th-day" scope="row">
        <div style="font-size:0.75rem; font-weight:700;">${dayLabel}</div>
        <div style="font-size:0.65rem; color:var(--text-muted); font-weight:normal;">${impact.weather !== 'clear' ? '🌧️ ' + impact.weather : '☀️ clear'}</div>
      </th>`;

    hours.forEach(h => {
      let val = h.totalExp;
      if (metric === 'arrivals') val = h.arrExp;
      else if (metric === 'departures') val = h.depExp;

      // Determine heat scale level (0 to 4 + peak)
      let heatClass = 'heat-level-0';
      if (val >= 1.0) heatClass = 'heat-level-peak';
      else if (val >= 0.7) heatClass = 'heat-level-4';
      else if (val >= 0.45) heatClass = 'heat-level-3';
      else if (val >= 0.2) heatClass = 'heat-level-2';
      else if (val >= 0.05) heatClass = 'heat-level-1';

      const tfrClass = h.isTfr ? 'is-tfr' : '';
      const userDot = h.hasUserFlight ? 'has-user-flight' : '';
      const hourFmt = `${h.hour.toString().padStart(2, '0')}:00`;

      html += `<td class="heatmap-td heatmap-cell ${heatClass} ${tfrClass} ${userDot}" 
        tabindex="0"
        role="gridcell"
        data-date="${day.date}"
        data-hour="${h.hour}"
        data-arr="${h.arrExp.toFixed(2)}"
        data-dep="${h.depExp.toFixed(2)}"
        data-total="${h.totalExp.toFixed(2)}"
        data-usercount="${h.userFlights.length}"
        data-istfr="${h.isTfr}"
        aria-label="${day.weekday} ${hourFmt}: ${val.toFixed(2)} ${metric}">
          <div class="cell-content">
            <span class="cell-val">${val >= 0.1 ? val.toFixed(1) : ''}</span>
          </div>
      </td>`;
    });

    html += `</tr>`;
  });

  html += `</tbody></table>`;
  container.innerHTML = html;

  // Add event listeners for heatmap cells and rows
  container.querySelectorAll('.heatmap-cell').forEach(cell => {
    cell.addEventListener('mouseenter', () => updateHeatmapInspector(cell));
    cell.addEventListener('focus', () => updateHeatmapInspector(cell));
    cell.addEventListener('click', () => {
      const date = cell.dataset.date;
      state.selectedDay = date;
      switchTab('view-day');
    });
  });

  container.querySelectorAll('.heatmap-row').forEach(row => {
    row.querySelector('.heatmap-th-day').addEventListener('click', () => {
      const date = row.dataset.date;
      state.selectedDay = date;
      switchTab('view-day');
    });
  });
}

function updateHeatmapInspector(cell) {
  const inspector = document.getElementById('heatmap-inspector');
  if (!inspector) return;

  const date = cell.dataset.date;
  const hour = parseInt(cell.dataset.hour, 10);
  const arr = parseFloat(cell.dataset.arr);
  const dep = parseFloat(cell.dataset.dep);
  const total = parseFloat(cell.dataset.total);
  const userCount = parseInt(cell.dataset.usercount, 10);
  const isTfr = cell.dataset.istfr === 'true';

  const dayObj = state.data.days.find(d => d.date === date);
  const hourLabel = `${hour.toString().padStart(2, '0')}:00 – ${(hour + 1).toString().padStart(2, '0')}:00 PST`;

  let userDetail = '';
  if (userCount > 0) {
    const flights = state.userMovements.filter(m => m.date === date && parseInt(m.time.split(':')[0], 10) === hour);
    const tails = flights.map(f => `${escapeHtml(f.tail || 'NoTail')} (${escapeHtml(f.type)})`).join(', ');
    userDetail = ` • <strong>${userCount} Logged Flight${userCount > 1 ? 's' : ''}:</strong> ${tails}`;
  }

  let tfrNotice = '';
  if (isTfr) {
    tfrNotice = ` • <span class="badge badge-restriction">TFR RESTRICTION: No GA Part 91</span>`;
  }

  inspector.innerHTML = `<div class="inspector-data-row">
    <span class="inspector-tag">${dayObj.weekday} ${formatDateShort(date)} at ${hourLabel}:</span>
    <span>Expected Landings: <strong>${arr.toFixed(2)}</strong></span>
    <span>Expected Departures: <strong>${dep.toFixed(2)}</strong></span>
    <span>Combined: <strong>${total.toFixed(2)} movements</strong></span>
    ${tfrNotice}
    ${userDetail}
    <span style="margin-left:auto; font-size:0.7rem; color:var(--brand-accent); font-weight:600;">Click cell to open 24h detail →</span>
  </div>`;
}

/**
 * SECTION B: 7 Days Operational Table & Per-Day Weather Scenarios
 */
function renderDayCards() {
  if (!state.data) return;
  const container = document.getElementById('days-cards-container');
  if (!container) return;

  const impacts = computeDailyWeatherImpacts();
  const scen = state.scenario;
  const peakArr = impacts.reduce((a, d) => (d.finalArrivals > a.finalArrivals ? d : a), impacts[0]);
  const peakDep = impacts.reduce((a, d) => (d.finalDepartures > a.finalDepartures ? d : a), impacts[0]);
  let html = '';

  impacts.forEach(impact => {
    const day = impact.day;
    const rawScen = day.scenarios[scen];
    const isSelected = day.date === state.selectedDay;

    // Badges
    const badges = [];
    if (day.game_day) badges.push('<span class="badge badge-restriction">GAME DAY</span>');
    if (day.presidents_day) badges.push('<span class="badge badge-peak-dep">PRESIDENTS\' DAY</span>');
    if (isRestrictionDay(day)) badges.push(`<span class="badge badge-restriction">PAUSE ${restrictionLabel()} (ASSUMED)</span>`);
    if (impact === peakArr) badges.push('<span class="badge badge-peak">BUSIEST ARRIVAL DAY</span>');
    if (impact === peakDep) badges.push('<span class="badge badge-peak-dep">BUSIEST DEPARTURE DAY</span>');

    // Weather impact description
    let weatherBadgeHtml = '';
    if (impact.weather !== 'clear') {
      const pctFormatted = (impact.effectPct * 100).toFixed(1);
      weatherBadgeHtml = `<div class="weather-spillover-alert">
        <span>⚠️ ${impact.weather.replace('_', ' ').toUpperCase()}: ${pctFormatted}% measured effect → landings ${impact.weatherDeltaArr.toFixed(1)}, departures ${impact.weatherDeltaDep.toFixed(1)} vs clear.</span>
        <span>${impact.lostArrivals.toFixed(1)} arr & ${impact.lostDepartures.toFixed(1)} dep shifted to next day.</span>
      </div>`;
    }

    // Carried over from yesterday notice
    let carryoverHtml = '';
    if (impact.carriedOverArrivals + impact.carriedOverDepartures > 0) {
      const totalCarried = (impact.carriedOverArrivals + impact.carriedOverDepartures).toFixed(1);
      carryoverHtml = `<div class="weather-spillover-alert" style="background:var(--brand-accent-subtle); border-color:var(--brand-accent-border); color:var(--brand-accent);">
        ⚡ +${totalCarried} delayed movements carried over from ${impact.carriedOverFromDay} (bad weather rule).
      </div>`;
    }

    // Parking indicator
    let rampBadgeClass = 'badge-ok';
    let rampStatusText = 'Capacity OK';
    if (rawScen.prob_ramp_full > 0.7) {
      rampBadgeClass = 'badge-critical';
      rampStatusText = 'High Ramp Risk';
    } else if (rawScen.prob_ramp_full > 0.3) {
      rampBadgeClass = 'badge-warning';
      rampStatusText = 'Moderate Ramp Risk';
    }

    // Peak windows: busiest 3 hours of the day's hour profile (game day uses the restriction shares)
    const wA = peakWindow(dayHourShares(day, 'arrivals')), wD = peakWindow(dayHourShares(day, 'departures'));
    const arrPeak = `${fmtWindow(wA)} (${Math.round(wA.share * 100)}% of landings)`;
    const depPeak = `${fmtWindow(wD)} (${Math.round(wD.share * 100)}% of departures)`;

    // Range visual bar calculations (0 to 20 scale)
    const maxScale = 20;
    const arrP10Pct = (impact.arrRange[0] / maxScale) * 100;
    const arrP90Pct = (impact.arrRange[1] / maxScale) * 100;
    const arrWidth = Math.max(4, arrP90Pct - arrP10Pct);
    const arrExpPct = (impact.finalArrivals / maxScale) * 100;
    const arrOrdPct = (rawScen.ordinary_arrivals / maxScale) * 100;

    const depP10Pct = (impact.depRange[0] / maxScale) * 100;
    const depP90Pct = (impact.depRange[1] / maxScale) * 100;
    const depWidth = Math.max(4, depP90Pct - depP10Pct);
    const depExpPct = (impact.finalDepartures / maxScale) * 100;
    const depOrdPct = (rawScen.ordinary_departures / maxScale) * 100;

    html += `
    <article class="day-card ${isSelected ? 'is-selected' : ''}" data-date="${day.date}">
      <!-- Col 1: Day & Weather -->
      <div class="day-col-meta">
        <div class="day-date-line">
          <div>
            <div class="day-name">${day.weekday}</div>
            <div class="day-date-sub">${formatDateLong(day.date)}</div>
          </div>
          <span class="badge ${day.day_type === 'weekend' ? 'badge-assumed' : 'badge-info'}">${day.day_type}</span>
        </div>

        <div class="day-badges-row">
          ${badges.join(' ')}
        </div>
        ${scenarioNote(day) ? `<div class="scenario-note">${scenarioNote(day)}</div>` : ''}

        <!-- Weather Box -->
        <div class="day-weather-box">
          <div class="weather-header">
            <span class="weather-label">Set Day Weather</span>
            <span class="weather-prob-tag">Feb Probabilities</span>
          </div>
          <select class="select-input select-sm weather-select" data-date="${day.date}" aria-label="Weather condition for ${day.weekday}">
            <option value="clear" ${impact.weather === 'clear' ? 'selected' : ''}>☀️ Clear (Baseline)</option>
            <option value="rain" ${impact.weather === 'rain' ? 'selected' : ''}>🌧️ Rain (${weatherProbLabel('rain')})</option>
            <option value="heavy_rain" ${impact.weather === 'heavy_rain' ? 'selected' : ''}>⛈️ Heavy rain (${weatherProbLabel('heavy_rain')})</option>
            <option value="heavy_fog" ${impact.weather === 'heavy_fog' ? 'selected' : ''}>🌫️ Heavy fog (${weatherProbLabel('heavy_fog')})</option>
          </select>
          ${weatherBadgeHtml}
          ${carryoverHtml}
        </div>
      </div>

      <!-- Col 2: Landings & Departures Range Comparison -->
      <div class="day-col-movements">
        <!-- Landings / Arrivals -->
        <div class="metric-bar-group">
          <div class="metric-bar-header">
            <span class="metric-title" style="color:var(--color-arrivals);">
              <span>🛬 Landings (Arrivals)</span>
            </span>
            <span class="metric-numbers">
              <span class="stat-expected">${impact.finalArrivals.toFixed(1)}</span>
              <span class="stat-range"> [90% range ${impact.arrRange[0].toFixed(1)}–${impact.arrRange[1].toFixed(1)}]</span>
              <span class="stat-ord"> vs Ord: ${rawScen.ordinary_arrivals.toFixed(1)}</span>
            </span>
          </div>
          <div class="range-track" title="90% range ${impact.arrRange[0].toFixed(1)}–${impact.arrRange[1].toFixed(1)} vs ordinary ${rawScen.ordinary_arrivals}. ${state.data.range_note}">
            <div class="range-band" style="left:${arrP10Pct}%; width:${arrWidth}%;"></div>
            <div class="range-marker-p50" style="left:${arrExpPct}%;" title="Expected: ${impact.finalArrivals.toFixed(1)}"></div>
            <div class="range-marker-ord" style="left:${arrOrdPct}%;" title="Ordinary Week: ${rawScen.ordinary_arrivals.toFixed(1)}"></div>
          </div>
        </div>

        <!-- Takeoffs / Departures -->
        <div class="metric-bar-group">
          <div class="metric-bar-header">
            <span class="metric-title" style="color:var(--color-departures);">
              <span>🛫 Takeoffs (Departures)</span>
            </span>
            <span class="metric-numbers">
              <span class="stat-expected">${impact.finalDepartures.toFixed(1)}</span>
              <span class="stat-range"> [90% range ${impact.depRange[0].toFixed(1)}–${impact.depRange[1].toFixed(1)}]</span>
              <span class="stat-ord"> vs Ord: ${rawScen.ordinary_departures.toFixed(1)}</span>
            </span>
          </div>
          <div class="range-track" title="90% range ${impact.depRange[0].toFixed(1)}–${impact.depRange[1].toFixed(1)} vs ordinary ${rawScen.ordinary_departures}. ${state.data.range_note}">
            <div class="range-band range-dep-band" style="left:${depP10Pct}%; width:${depWidth}%;"></div>
            <div class="range-marker-p50 range-marker-dep-p50" style="left:${depExpPct}%;" title="Expected: ${impact.finalDepartures.toFixed(1)}"></div>
            <div class="range-marker-ord" style="left:${depOrdPct}%;" title="Ordinary Week: ${rawScen.ordinary_departures.toFixed(1)}"></div>
          </div>
        </div>

        <!-- Ramp space secondary indicator -->
        <div class="ramp-mini-indicator">
          <span class="ramp-mini-text">Ramp: P50 <strong>${rawScen.parking_su_p50.toFixed(1)} su</strong> | P90 <strong>${rawScen.parking_su_p90.toFixed(1)} su</strong> (Ramp Cap: ${rawScen.ramp_capacity_su.toFixed(1)} su)</span>
          <span class="badge ${rampBadgeClass}">${rampStatusText} (${Math.round(rawScen.prob_ramp_full * 100)}%)</span>
        </div>
      </div>

      <!-- Col 3: Operational Peak Windows & Action -->
      <div class="day-col-action">
        <div class="peak-windows-box">
          <div class="peak-window-item">🛬 Inbound Window: <strong>${arrPeak}</strong></div>
          <div class="peak-window-item">🛫 Outbound Window: <strong>${depPeak}</strong></div>
          <div class="peak-window-item" style="color:var(--text-muted); font-size:0.7rem; margin-top:4px;">
            Part 91: ${Math.round(rawScen.share_part91 * 100)}% • Part 135: ${Math.round(rawScen.share_part135 * 100)}%
          </div>
        </div>

        <button type="button" class="btn btn-primary btn-open-day" data-date="${day.date}">
          Open Day Detail & Movements (24h) →
        </button>
      </div>
    </article>`;
  });

  container.innerHTML = html;

  // Add event listeners for day cards and weather selects
  container.querySelectorAll('.weather-select').forEach(select => {
    select.addEventListener('change', (e) => {
      const date = e.target.dataset.date;
      state.weatherSettings[date] = e.target.value;
      saveWeather();
      renderAllViews();
      showToast(`Weather on ${date} set to ${e.target.value}. Recalculated traffic and spillover.`);
    });
  });

  container.querySelectorAll('.btn-open-day').forEach(btn => {
    btn.addEventListener('click', () => {
      state.selectedDay = btn.dataset.date;
      switchTab('view-day');
    });
  });
}

/**
 * SECTION C: Day-Specific Operational Proposals
 */
function renderProposals() {
  if (!state.data) return;
  const container = document.getElementById('proposals-container');
  const countBadge = document.getElementById('proposals-count-badge');
  if (!container) return;

  const impacts = computeDailyWeatherImpacts();
  const scen = state.scenario;

  // Day-specific proposals generated from agent_data.json (busiest days found by calculation)
  const proposals = [];
  const peakArr = impacts.reduce((a, d) => (d.finalArrivals > a.finalArrivals ? d : a), impacts[0]);
  const peakDep = impacts.reduce((a, d) => (d.finalDepartures > a.finalDepartures ? d : a), impacts[0]);
  impacts.forEach(imp => {
    const day = imp.day, raw = day.scenarios[scen];
    const wA = peakWindow(dayHourShares(day, 'arrivals')), wD = peakWindow(dayHourShares(day, 'departures'));
    const label = `${day.weekday.slice(0, 3)} ${formatDateShort(day.date)}`;
    const vsA = signedPct(imp.finalArrivals / raw.ordinary_arrivals - 1), vsD = signedPct(imp.finalDepartures / raw.ordinary_departures - 1);
    if (imp === peakArr) proposals.push({ id: `prop-peak-arr-${day.date}`, date: day.date, dayLabel: `${label} (busiest arrivals)`,
      title: 'Busiest arrival day of the week', category: 'Arrivals',
      text: `${imp.finalArrivals.toFixed(1)} landings expected (90% range ${imp.arrRange[0].toFixed(1)}–${imp.arrRange[1].toFixed(1)}; ordinary ${raw.ordinary_arrivals.toFixed(1)}, ${vsA}). Busiest window ${fmtWindow(wA)} (${Math.round(wA.share * 100)}% of the day's landings). Proposal: reconfirm arrival reservations and ETAs for that window a day ahead; keep the board current.` });
    if (imp === peakDep) proposals.push({ id: `prop-peak-dep-${day.date}`, date: day.date, dayLabel: `${label} (busiest departures)`,
      title: `Busiest departure day of the week${day.presidents_day ? " (Presidents' Day)" : ''}`, category: 'Departures',
      text: `${imp.finalDepartures.toFixed(1)} departures expected (90% range ${imp.depRange[0].toFixed(1)}–${imp.depRange[1].toFixed(1)}; ordinary ${raw.ordinary_departures.toFixed(1)}, ${vsD}). Busiest window ${fmtWindow(wD)} (${Math.round(wD.share * 100)}% of the day's departures). Proposal: reconfirm ETDs the evening before and keep the departure board current from ${fmtHour(wD.start)}.` });
    if (isRestrictionDay(day)) {
      const r = restriction(), after = shareAfterRestriction('departures');
      proposals.push({ id: `prop-pause-${day.date}`, date: day.date, dayLabel: `${label} (game day)`,
        title: `Assumed pause ${restrictionLabel()}`, category: 'Game day',
        text: `No private movements are planned ${r.start}–${r.end} (${r.status}). Landings concentrate before it: busiest ${fmtWindow(wA)}. Proposal: confirm with the crews of aircraft due near the window when they will arrive or leave, and update the board. The actual restriction is set by the FAA notice, not by this tool.` });
      proposals.push({ id: `prop-after-${day.date}`, date: day.date, dayLabel: `${label} (after the pause)`,
        title: `Departure wave after ${r.end}`, category: 'Game day',
        text: `${Math.round(after * 100)}% of the day's departures (~${(imp.finalDepartures * after).toFixed(1)}) are planned between ${r.end} and midnight. Proposal: have the outbound list ready before ${r.end}: reconfirm each ETD and tail number. Air traffic control issues clearances and sequences departures.` });
    }
    if (imp !== peakArr && imp !== peakDep && !isRestrictionDay(day)) proposals.push({ id: `prop-day-${day.date}`, date: day.date, dayLabel: label,
      title: `${vsA} landings, ${vsD} departures vs an ordinary ${day.weekday}`, category: 'Day plan',
      text: `${imp.finalArrivals.toFixed(1)} landings and ${imp.finalDepartures.toFixed(1)} departures expected (ordinary ${raw.ordinary_arrivals.toFixed(1)} / ${raw.ordinary_departures.toFixed(1)}). Busiest landings ${fmtWindow(wA)}, departures ${fmtWindow(wD)}. Proposal: confirm ETAs and ETDs for those windows; keep the board current.` });
  });
  proposals.sort((a, b) => a.date.localeCompare(b.date));

  // Dynamic Weather Spillover Proposals
  impacts.forEach((imp, idx) => {
    if (imp.carriedOverArrivals + imp.carriedOverDepartures > 0) {
      const tot = (imp.carriedOverArrivals + imp.carriedOverDepartures).toFixed(1);
      proposals.push({
        id: `prop-weather-${imp.date}`,
        date: imp.date,
        dayLabel: `${imp.weekday} ${formatDateShort(imp.date)} (Weather Spillover)`,
        title: `Absorb +${tot} Delayed Movements from ${imp.carriedOverFromDay}`,
        category: 'Weather Delay Spillover',
        text: `Bad weather on ${imp.carriedOverFromDay} moved ${tot} movements into ${imp.weekday} (+${imp.carriedOverArrivals.toFixed(1)} landings, +${imp.carriedOverDepartures.toFixed(1)} departures). Proposal: confirm the new ETAs and ETDs of the delayed aircraft early in the day.`,
        actionHint: 'Weather contingency response.'
      });
    }
  });

  // Calculate pending count
  let pendingCount = 0;
  proposals.forEach(p => {
    const cur = state.proposalStates[p.id] || { status: 'pending', note: '' };
    if (cur.status === 'pending') pendingCount++;
  });
  if (countBadge) countBadge.textContent = `${pendingCount} Pending Review`;

  let html = '';
  proposals.forEach(prop => {
    const cur = state.proposalStates[prop.id] || { status: 'pending', note: '' };
    const statusClass = cur.status; // 'pending' | 'acknowledged' | 'dismissed'

    let statusBadge = '<span class="badge badge-warning">PENDING REVIEW</span>';
    if (cur.status === 'acknowledged') statusBadge = '<span class="badge badge-ok">ACKNOWLEDGED</span>';
    if (cur.status === 'dismissed') statusBadge = '<span class="badge" style="background:var(--text-muted); color:#fff;">DISMISSED</span>';

    html += `
    <div class="proposal-card ${statusClass}" id="${prop.id}">
      <div class="proposal-header">
        <div class="proposal-title-group">
          <span class="proposal-day-badge">${prop.dayLabel}</span>
          <span class="proposal-title">${prop.title}</span>
        </div>
        <div>
          ${statusBadge}
        </div>
      </div>

      <p class="proposal-desc">${prop.text}</p>

      <div class="proposal-actions">
        <div class="proposal-btns">
          <button type="button" class="btn btn-ok btn-sm btn-ack-prop" data-id="${prop.id}">
            ✅ Acknowledge
          </button>
          <button type="button" class="btn btn-secondary btn-sm btn-dismiss-prop" data-id="${prop.id}">
            Dismiss
          </button>
        </div>

        <div style="display:flex; align-items:center; gap:6px; flex:1; max-width:500px;">
          <input type="text" 
            class="form-input proposal-note-input" 
            data-id="${prop.id}" 
            placeholder="Operational note / agent initials..." 
            value="${escapeHtml(cur.note || '')}">
          <button type="button" class="btn btn-secondary btn-sm btn-save-note" data-id="${prop.id}">Save Note</button>
        </div>
      </div>
    </div>`;
  });

  container.innerHTML = html;

  // Add event listeners for proposals
  container.querySelectorAll('.btn-ack-prop').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.dataset.id;
      const noteInput = container.querySelector(`.proposal-note-input[data-id="${id}"]`);
      state.proposalStates[id] = {
        status: 'acknowledged',
        note: noteInput ? noteInput.value : ''
      };
      saveProposals();
      renderProposals();
      showToast('Proposal acknowledged by agent.');
    });
  });

  container.querySelectorAll('.btn-dismiss-prop').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.dataset.id;
      const noteInput = container.querySelector(`.proposal-note-input[data-id="${id}"]`);
      state.proposalStates[id] = {
        status: 'dismissed',
        note: noteInput ? noteInput.value : ''
      };
      saveProposals();
      renderProposals();
      showToast('Proposal dismissed.');
    });
  });

  container.querySelectorAll('.btn-save-note').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.dataset.id;
      const noteInput = container.querySelector(`.proposal-note-input[data-id="${id}"]`);
      const existing = state.proposalStates[id] || { status: 'pending', note: '' };
      existing.note = noteInput ? noteInput.value : '';
      state.proposalStates[id] = existing;
      saveProposals();
      showToast('Agent note saved.');
    });
  });
}

/**
 * VIEW 2: DAY DETAIL VIEW (24h Timeline & Reality Check)
 */
function renderDayDetail() {
  if (!state.data) return;
  const day = state.data.days.find(d => d.date === state.selectedDay);
  if (!day) return;

  const impacts = computeDailyWeatherImpacts();
  const impact = impacts.find(d => d.date === state.selectedDay) || impacts[0];
  const scen = state.scenario;
  const rawScen = day.scenarios[scen];

  // Header Title & Badges
  const titleEl = document.getElementById('day-detail-title');
  const badgesEl = document.getElementById('day-detail-badges');
  if (titleEl) titleEl.textContent = `${day.weekday} ${formatDateLong(day.date)}`;

  if (badgesEl) {
    const b = [];
    if (day.game_day) b.push('<span class="badge badge-restriction">GAME DAY</span>');
    if (day.presidents_day) b.push('<span class="badge badge-peak-dep">PRESIDENTS\' DAY</span>');
    if (isRestrictionDay(day)) b.push(`<span class="badge badge-restriction">PAUSE ${restrictionLabel()} (ASSUMED)</span>`);
    b.push(`<span class="badge ${impact.weather !== 'clear' ? 'badge-warning' : 'badge-ok'}">Weather: ${weatherName(impact.weather)}</span>`);
    const sens = scenarioSensitivity(day);
    if (!sens.arrivals && !sens.departures) b.push('<span class="badge badge-info">SAME IN ALL SCENARIOS</span>');
    badgesEl.innerHTML = b.join(' ');
  }

  // Day Selector Pills
  const pillContainer = document.getElementById('day-pill-selector');
  if (pillContainer) {
    let pillsHtml = '';
    state.data.days.forEach(d => {
      const isAct = d.date === state.selectedDay;
      pillsHtml += `<button type="button" class="day-pill-btn ${isAct ? 'active' : ''}" data-date="${d.date}">
        ${d.weekday.slice(0, 3)} ${formatDateShort(d.date)}
      </button>`;
    });
    pillContainer.innerHTML = pillsHtml;
    pillContainer.querySelectorAll('.day-pill-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        state.selectedDay = btn.dataset.date;
        renderDayDetail();
      });
    });
  }

  // Booked vs Forecast Comparison (Reality Check)
  const realityContainer = document.getElementById('reality-comparison-container');
  if (realityContainer) {
    const dayMovements = state.userMovements.filter(m => m.date === state.selectedDay);
    const bookedArr = dayMovements.filter(m => m.type === 'arrival').length;
    const bookedDep = dayMovements.filter(m => m.type === 'departure').length;

    const expArr = impact.finalArrivals;
    const expDep = impact.finalDepartures;

    const unannouncedArr = Math.max(0, Math.round(expArr - bookedArr));
    const unannouncedDep = Math.max(0, Math.round(expDep - bookedDep));

    realityContainer.innerHTML = `
      <div class="reality-line">
        <span><strong>Landings:</strong> ${bookedArr} booked vs ~${expArr.toFixed(1)} expected</span>
        <span class="reality-guidance">Plan for ~${unannouncedArr} unannounced landing${unannouncedArr !== 1 ? 's' : ''}</span>
      </div>
      <div class="reality-line">
        <span><strong>Departures:</strong> ${bookedDep} booked vs ~${expDep.toFixed(1)} expected</span>
        <span class="reality-guidance">Plan for ~${unannouncedDep} unannounced departure${unannouncedDep !== 1 ? 's' : ''}</span>
      </div>
    `;
  }

  const noteEl = document.getElementById('timeline-scenario-note');
  if (noteEl) { const n = scenarioNote(day); noteEl.textContent = n; noteEl.hidden = !n; }

  // Next 3 Hours Radar
  renderNext3HoursRadar(day, impact);

  // 24-Hour Timeline Chart (SVG)
  render24HourTimelineChart(day, impact);

  // Day Movements Table
  renderDayMovementsTable();
}

/**
 * Render Next 3 Hours Radar Window
 */
function renderNext3HoursRadar(day, impact) {
  const windowTag = document.getElementById('next-hours-window-tag');
  const statsContainer = document.getElementById('next-hours-stats');
  const noteEl = document.getElementById('next-hours-note');
  if (!statsContainer) return;

  // Exact window: from the simulated minute for 180 minutes, prorating partial hours and crossing midnight
  const [simDate, simTime] = state.simulatedNow.split('T');
  const dates = state.data.days.map(d => d.date);
  const impacts = computeDailyWeatherImpacts();
  const startIdx = dates.indexOf(simDate);
  let nextArrExp = 0, nextDepExp = 0, nextBookedArr = 0, nextBookedDep = 0, inTfrWindow = false, outside = false;
  if (startIdx === -1) {
    outside = true;
  } else {
    const start = startIdx * 24 + clockToHours(simTime || '10:00'), end = start + 3;
    for (let t = Math.floor(start); t < end; t++) {
      const dIdx = Math.floor(t / 24), h = t % 24;
      if (dIdx >= dates.length) { outside = true; break; }
      const portion = Math.min(end, t + 1) - Math.max(start, t);
      const imp = impacts[dIdx];
      const hr = getHourlyProfileForDay(imp.day, imp.finalArrivals, imp.finalDepartures)[h];
      nextArrExp += hr.arrExp * portion;
      nextDepExp += hr.depExp * portion;
      const inWin = m => { const mt = dIdx * 24 + clockToHours(m.time); return m.date === dates[dIdx] && mt >= start && mt < end; };
      nextBookedArr += hr.userFlights.filter(m => m.type === 'arrival' && inWin(m)).length;
      nextBookedDep += hr.userFlights.filter(m => m.type === 'departure' && inWin(m)).length;
      if (inRestriction(imp.day, Math.max(start, t) - dIdx * 24, Math.min(end, t + 1) - dIdx * 24)) inTfrWindow = true;
    }
    const endAbs = start + 3, endIdx = Math.floor(endAbs / 24), endClock = endAbs - endIdx * 24;
    const hhmm = x => `${String(Math.floor(x)).padStart(2, '0')}:${String(Math.round((x % 1) * 60)).padStart(2, '0')}`;
    const endDay = endIdx < dates.length ? formatDateShort(dates[endIdx]) : 'after the planning week';
    if (windowTag) windowTag.textContent = `${formatDateShort(simDate)} ${hhmm(start - startIdx * 24)} – ${endIdx !== startIdx ? endDay + ' ' : ''}${hhmm(endClock)}`;
  }
  if (outside && windowTag && startIdx === -1) windowTag.textContent = 'Outside the planning week';
  // Booked flights are certain, so the expectation never shows fewer movements than are already booked
  nextArrExp = Math.max(nextArrExp, nextBookedArr);
  nextDepExp = Math.max(nextDepExp, nextBookedDep);

  statsContainer.innerHTML = `
    <div class="next-stat-box">
      <span class="next-stat-val" style="color:var(--color-arrivals);">${nextArrExp.toFixed(1)}</span>
      <span class="next-stat-lbl">Exp Landings (${nextBookedArr} Booked)</span>
    </div>
    <div class="next-stat-box">
      <span class="next-stat-val" style="color:var(--color-departures);">${nextDepExp.toFixed(1)}</span>
      <span class="next-stat-lbl">Exp Takeoffs (${nextBookedDep} Booked)</span>
    </div>
    <div class="next-stat-box">
      <span class="next-stat-val">${(nextArrExp + nextDepExp).toFixed(1)}</span>
      <span class="next-stat-lbl">Total Movements (3h)</span>
    </div>
  `;

  if (noteEl) {
    if (outside) {
      noteEl.textContent = 'Part of this window is outside the planning week (11–17 Feb); only the covered hours are counted.';
    } else if (inTfrWindow) {
      noteEl.textContent = `The assumed pause ${restrictionLabel()} falls in this window: no private movements are planned during it (${restriction().status}).`;
    } else if (nextArrExp + nextDepExp >= 2.0) {
      noteEl.textContent = `Busy window: about ${nextArrExp.toFixed(1)} landings and ${nextDepExp.toFixed(1)} departures expected. Confirm ETAs and ETDs and keep the board current.`;
    } else {
      noteEl.textContent = 'Quiet window. Keep the board current as confirmations come in.';
    }
  }
}

/**
 * Hand-Rolled Responsive SVG 24-Hour Timeline Chart
 * Shows paired bars for Landings vs Departures, 90% uncertainty indicators, and TFR overlay
 */
function render24HourTimelineChart(day, impact) {
  const container = document.getElementById('timeline-chart-container');
  if (!container) return;

  const hours = getHourlyProfileForDay(day, impact.finalArrivals, impact.finalDepartures);
  const width = 850;
  const height = 260;
  const padding = { top: 25, right: 20, bottom: 40, left: 45 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  // Y-axis scale fixed per day across Low / Forecast / High, so switching scenario only moves what really changes
  const shA = dayHourShares(day, 'arrivals'), shD = dayHourShares(day, 'departures');
  let maxVal = Math.max(0.5, ...Object.values(day.scenarios).map(v =>
    Math.max(v.expected_arrivals * Math.max(...shA), v.expected_departures * Math.max(...shD))));
  hours.forEach(h => {
    maxVal = Math.max(maxVal, h.arrExp, h.depExp, h.userArrCount, h.userDepCount);
  });
  maxVal = Math.ceil(maxVal * 10) / 10 + 0.2; // Round up cleanly

  const colW = chartW / 24;
  const barW = Math.max(3, colW * 0.35);

  let svg = `<svg class="svg-timeline" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="24-hour landings and departures timeline">
    <defs>
      <pattern id="tfr-stripe" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <line x1="0" y1="0" x2="0" y2="8" stroke="rgba(100, 116, 139, 0.4)" stroke-width="3" />
      </pattern>
    </defs>`;

  // Grid lines
  const yTicks = 4;
  for (let i = 0; i <= yTicks; i++) {
    const val = (maxVal / yTicks) * i;
    const y = padding.top + chartH - (val / maxVal) * chartH;
    svg += `<line x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}" stroke="var(--border-subtle)" stroke-width="1" />
      <text x="${padding.left - 8}" y="${y + 4}" font-size="10" fill="var(--text-muted)" text-anchor="end">${val.toFixed(1)}</text>`;
  }

  // TFR Shaded Window on Sunday (14:30 to 20:30)
  if (isRestrictionDay(day)) {
    const tfrX = padding.left + (clockToHours(restriction().start) * colW);
    const tfrW = (clockToHours(restriction().end) - clockToHours(restriction().start)) * colW;
    svg += `<rect x="${tfrX}" y="${padding.top}" width="${tfrW}" height="${chartH}" fill="url(#tfr-stripe)" />
      <rect x="${tfrX}" y="${padding.top}" width="${tfrW}" height="20" fill="rgba(217, 119, 6, 0.15)" />
      <text x="${tfrX + tfrW / 2}" y="${padding.top + 14}" font-size="10" font-weight="bold" fill="var(--status-warning)" text-anchor="middle">
        Assumed pause ${restrictionLabel()}
      </text>`;
  }

  // Render Bars for each of the 24 hours
  hours.forEach(h => {
    const xBase = padding.left + (h.hour * colW);
    const xArr = xBase + (colW * 0.12);
    const xDep = xArr + barW + 2;

    const arrH = (h.arrExp / maxVal) * chartH;
    const depH = (h.depExp / maxVal) * chartH;

    const yArr = padding.top + chartH - arrH;
    const yDep = padding.top + chartH - depH;

    // Landings bar (Blue)
    svg += `<rect x="${xArr}" y="${yArr}" width="${barW}" height="${arrH}" rx="2" fill="var(--color-arrivals)">
      <title>Hour ${h.hour}:00 - Exp Landings: ${h.arrExp.toFixed(2)}</title>
    </rect>`;

    // Departures bar (Teal)
    svg += `<rect x="${xDep}" y="${yDep}" width="${barW}" height="${depH}" rx="2" fill="var(--color-departures)">
      <title>Hour ${h.hour}:00 - Exp Takeoffs: ${h.depExp.toFixed(2)}</title>
    </rect>`;

    // User flight dots/badges if flights entered
    if (h.userArrCount > 0) {
      svg += `<circle cx="${xArr + barW / 2}" cy="${Math.max(padding.top + 10, yArr - 6)}" r="3.5" fill="var(--status-warning)">
        <title>${h.userArrCount} booked landing(s)</title>
      </circle>`;
    }
    if (h.userDepCount > 0) {
      svg += `<circle cx="${xDep + barW / 2}" cy="${Math.max(padding.top + 10, yDep - 6)}" r="3.5" fill="var(--status-warning)">
        <title>${h.userDepCount} booked takeoff(s)</title>
      </circle>`;
    }

    // X-axis Hour Label
    const hourFmt = h.hour.toString().padStart(2, '0');
    if (h.hour % 2 === 0) {
      svg += `<text x="${xBase + colW / 2}" y="${height - padding.bottom + 16}" font-size="9" fill="var(--text-muted)" text-anchor="middle">${hourFmt}</text>`;
    }
  });

  // X Axis Label
  svg += `<text x="${width / 2}" y="${height - 8}" font-size="11" font-weight="600" fill="var(--text-secondary)" text-anchor="middle">Hour of Day (PST America/Los_Angeles)</text>`;
  // Y Axis Label
  svg += `<text transform="rotate(-90)" x="${-(height / 2)}" y="14" font-size="11" font-weight="600" fill="var(--text-secondary)" text-anchor="middle">Movements / Hour</text>`;

  svg += `</svg>`;
  container.innerHTML = svg;
}

/**
 * Render Day Movements Table
 */
function renderDayMovementsTable() {
  const tbody = document.getElementById('day-movements-tbody');
  if (!tbody) return;

  const dayFlights = state.userMovements.filter(m => m.date === state.selectedDay);
  dayFlights.sort((a, b) => a.time.localeCompare(b.time));

  if (dayFlights.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:24px; color:var(--text-muted);">
      No flights recorded for ${formatDateLong(state.selectedDay)}. Use "+ Add Flight Movement" above to add real shift traffic.
    </td></tr>`;
    return;
  }

  let html = '';
  dayFlights.forEach(f => {
    const isArr = f.type === 'arrival';
    const typeBadge = isArr 
      ? '<span class="badge" style="background:var(--color-arrivals-bg); color:var(--color-arrivals);">🛬 Arrival</span>'
      : '<span class="badge" style="background:var(--color-departures-bg); color:var(--color-departures);">🛫 Departure</span>';

    let statusBadge = `<span class="badge badge-info">${f.status.toUpperCase()}</span>`;
    if (f.status === 'landed' || f.status === 'departed') statusBadge = `<span class="badge badge-ok">${f.status.toUpperCase()}</span>`;

    let quickActionBtn = '';
    if (isArr && f.status !== 'landed') {
      quickActionBtn = `<button type="button" class="btn btn-ok btn-sm btn-quick-status" data-id="${f.id}" data-status="landed">Mark Landed</button>`;
    } else if (!isArr && f.status !== 'departed') {
      quickActionBtn = `<button type="button" class="btn btn-ok btn-sm btn-quick-status" data-id="${f.id}" data-status="departed">Mark Departed</button>`;
    }

    html += `<tr>
      <td><strong>${f.time} PST</strong></td>
      <td>${typeBadge}</td>
      <td><strong>${f.tail ? escapeHtml(f.tail) : '<span style="color:var(--text-muted)">Unspecified</span>'}</strong></td>
      <td><span class="badge badge-secondary">${f.size.toUpperCase()}</span></td>
      <td>${statusBadge}</td>
      <td>
        <div class="table-actions">
          ${quickActionBtn}
          <button type="button" class="btn btn-secondary btn-sm btn-edit-mov" data-id="${f.id}">Edit</button>
          <button type="button" class="btn btn-danger btn-sm btn-del-mov" data-id="${f.id}">Del</button>
        </div>
      </td>
    </tr>`;
  });

  tbody.innerHTML = html;
  attachMovementActionListeners(tbody);
}

/**
 * VIEW 3: FULL FLIGHT MOVEMENT BOARD (CRUD + Filters)
 */
function renderMovementsBoard() {
  const tbody = document.getElementById('all-movements-tbody');
  if (!tbody) return;

  const dateFilter = document.getElementById('filter-date-select') ? document.getElementById('filter-date-select').value : 'all';
  const typeFilter = document.getElementById('filter-type-select') ? document.getElementById('filter-type-select').value : 'all';
  const statusFilter = document.getElementById('filter-status-select') ? document.getElementById('filter-status-select').value : 'all';

  let list = [...state.userMovements];
  if (dateFilter !== 'all') list = list.filter(m => m.date === dateFilter);
  if (typeFilter !== 'all') list = list.filter(m => m.type === typeFilter);
  if (statusFilter !== 'all') list = list.filter(m => m.status === statusFilter);

  list.sort((a, b) => {
    if (a.date !== b.date) return a.date.localeCompare(b.date);
    return a.time.localeCompare(b.time);
  });

  if (list.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:32px; color:var(--text-muted);">
      No movements match current filter criteria. Use form above to log flight movements.
    </td></tr>`;
    return;
  }

  let html = '';
  list.forEach(f => {
    const isArr = f.type === 'arrival';
    const typeBadge = isArr 
      ? '<span class="badge" style="background:var(--color-arrivals-bg); color:var(--color-arrivals);">🛬 Arrival</span>'
      : '<span class="badge" style="background:var(--color-departures-bg); color:var(--color-departures);">🛫 Departure</span>';

    let statusBadge = `<span class="badge badge-info">${f.status.toUpperCase()}</span>`;
    if (f.status === 'landed' || f.status === 'departed') statusBadge = `<span class="badge badge-ok">${f.status.toUpperCase()}</span>`;

    let quickActionBtn = '';
    if (isArr && f.status !== 'landed') {
      quickActionBtn = `<button type="button" class="btn btn-ok btn-sm btn-quick-status" data-id="${f.id}" data-status="landed">Mark Landed</button>`;
    } else if (!isArr && f.status !== 'departed') {
      quickActionBtn = `<button type="button" class="btn btn-ok btn-sm btn-quick-status" data-id="${f.id}" data-status="departed">Mark Departed</button>`;
    }

    html += `<tr>
      <td>${formatDateShort(f.date)}</td>
      <td><strong>${f.time} PST</strong></td>
      <td>${typeBadge}</td>
      <td><strong>${f.tail ? escapeHtml(f.tail) : '<span style="color:var(--text-muted)">Unspecified</span>'}</strong></td>
      <td><span class="badge badge-secondary">${f.size.toUpperCase()}</span></td>
      <td>${statusBadge}</td>
      <td>
        <div class="table-actions">
          ${quickActionBtn}
          <button type="button" class="btn btn-secondary btn-sm btn-edit-mov" data-id="${f.id}">Edit</button>
          <button type="button" class="btn btn-danger btn-sm btn-del-mov" data-id="${f.id}">Del</button>
        </div>
      </td>
    </tr>`;
  });

  tbody.innerHTML = html;
  attachMovementActionListeners(tbody);
}

function attachMovementActionListeners(container) {
  container.querySelectorAll('.btn-quick-status').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.dataset.id;
      const newStatus = btn.dataset.status;
      const flight = state.userMovements.find(m => m.id === id);
      if (flight) {
        flight.status = newStatus;
        saveMovements();
        renderAllViews();
        showToast(`Flight ${flight.tail || 'movement'} marked as ${newStatus}.`);
      }
    });
  });

  container.querySelectorAll('.btn-del-mov').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.dataset.id;
      state.userMovements = state.userMovements.filter(m => m.id !== id);
      saveMovements();
      renderAllViews();
      showToast('Movement removed from shift log.');
    });
  });

  container.querySelectorAll('.btn-edit-mov').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.dataset.id;
      startMovementEdit(id);
    });
  });
}

function handleMovementSubmit(e) {
  e.preventDefault();
  const date = document.getElementById('form-date').value;
  const time = document.getElementById('form-time').value;
  const type = document.getElementById('form-type').value;
  const tail = document.getElementById('form-tail').value.trim().toUpperCase();
  const size = document.getElementById('form-size').value;
  const status = document.getElementById('form-status').value;

  if (state.editingMovementId) {
    const flight = state.userMovements.find(m => m.id === state.editingMovementId);
    if (flight) {
      flight.date = date;
      flight.time = time;
      flight.type = type;
      flight.tail = tail;
      flight.size = size;
      flight.status = status;
      showToast('Movement updated successfully.');
    }
    cancelMovementEdit();
  } else {
    const newMovement = {
      id: 'm-' + Date.now().toString(36) + Math.random().toString(36).substr(2, 4),
      date,
      time,
      type,
      tail,
      size,
      status
    };
    state.userMovements.push(newMovement);
    showToast(`Added ${type} for ${tail || 'unspecified tail'} at ${time}.`);
  }

  saveMovements();
  renderAllViews();

  // Reset form time slightly forward for convenient rapid logging
  const [hh, mm] = time.split(':').map(Number);
  const nextHour = (hh + 1) % 24;
  document.getElementById('form-time').value = `${nextHour.toString().padStart(2, '0')}:${mm.toString().padStart(2, '0')}`;
  document.getElementById('form-tail').value = '';
}

function startMovementEdit(id) {
  const flight = state.userMovements.find(m => m.id === id);
  if (!flight) return;

  state.editingMovementId = id;
  switchTab('view-movements');

  document.getElementById('form-movement-id').value = flight.id;
  document.getElementById('form-date').value = flight.date;
  document.getElementById('form-time').value = flight.time;
  document.getElementById('form-type').value = flight.type;
  document.getElementById('form-tail').value = flight.tail || '';
  document.getElementById('form-size').value = flight.size;
  document.getElementById('form-status').value = flight.status;

  const saveBtn = document.getElementById('btn-save-movement');
  const cancelBtn = document.getElementById('btn-cancel-edit');
  if (saveBtn) saveBtn.textContent = 'Save Movement Changes';
  if (cancelBtn) cancelBtn.removeAttribute('hidden');

  document.getElementById('form-time').focus();
}

function cancelMovementEdit() {
  state.editingMovementId = null;
  const form = document.getElementById('movement-form');
  if (form) form.reset();
  const saveBtn = document.getElementById('btn-save-movement');
  const cancelBtn = document.getElementById('btn-cancel-edit');
  if (saveBtn) saveBtn.textContent = '+ Add Flight Movement';
  if (cancelBtn) cancelBtn.setAttribute('hidden', 'true');
}

/**
 * CSV Import / Export
 */
function exportMovementsToCsv() {
  if (state.userMovements.length === 0) {
    showToast('No movements to export.', true);
    return;
  }

  const header = ['date', 'time', 'type', 'tail_number', 'aircraft_size', 'status'];
  const rows = state.userMovements.map(m => [
    m.date,
    m.time,
    m.type,
    m.tail || '',
    m.size,
    m.status
  ]);

  const csvContent = 'data:text/csv;charset=utf-8,' + [header.join(','), ...rows.map(r => r.join(','))].join('\n');
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement('a');
  link.setAttribute('href', encodedUri);
  link.setAttribute('download', `lax_fbo_movements_sb_lxi_${state.selectedDay}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  showToast('Downloaded movements CSV file.');
}

function importMovementsFromCsv(e) {
  const file = e.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (evt) => {
    try {
      const text = evt.target.result;
      const lines = text.split(/\r?\n/).filter(line => line.trim().length > 0);
      if (lines.length < 2) throw new Error('CSV is empty or missing headers');

      const headers = lines[0].split(',').map(h => h.trim().toLowerCase());
      const dateIdx = headers.indexOf('date');
      const timeIdx = headers.indexOf('time');
      const typeIdx = headers.indexOf('type');
      const tailIdx = headers.indexOf('tail_number') !== -1 ? headers.indexOf('tail_number') : headers.indexOf('tail');
      const sizeIdx = headers.indexOf('aircraft_size') !== -1 ? headers.indexOf('aircraft_size') : headers.indexOf('size');
      const statusIdx = headers.indexOf('status');

      if (dateIdx === -1 || timeIdx === -1 || typeIdx === -1) throw new Error('CSV needs date, time and type columns');
      const dates = state.data.days.map(d => d.date);
      let imported = 0, skipped = 0;
      for (let i = 1; i < lines.length; i++) {
        const parts = lines[i].split(',').map(p => p.trim());
        const date = parts[dateIdx] || '', time = parts[timeIdx] || '', type = (parts[typeIdx] || '').toLowerCase();
        const tail = tailIdx !== -1 ? (parts[tailIdx] || '').toUpperCase() : '';
        const size = sizeIdx !== -1 ? (parts[sizeIdx] || '').toLowerCase() : 'midsize';
        const status = statusIdx !== -1 ? (parts[statusIdx] || '').toLowerCase() : 'expected';
        const valid = dates.includes(date) && /^([01]\d|2[0-3]):[0-5]\d$/.test(time) && ['arrival', 'departure'].includes(type)
          && /^[A-Z0-9-]{0,10}$/.test(tail) && ['light', 'midsize', 'large'].includes(size)
          && ['expected', 'confirmed', 'landed', 'departed'].includes(status);
        if (!valid) { skipped++; continue; }
        state.userMovements.push({ id: 'imp-' + Date.now().toString(36) + i, date, time, type, tail, size, status });
        imported++;
      }

      saveMovements();
      renderAllViews();
      showToast(`Imported ${imported} movements${skipped ? ` (${skipped} invalid rows skipped)` : ''}.`, imported === 0 && skipped > 0);
    } catch (err) {
      console.error('CSV parse error:', err);
      showToast('Failed to import CSV: Invalid format.', true);
    }
  };
  reader.readAsText(file);
  e.target.value = ''; // Reset input
}

/**
 * VIEW 4: MODEL ACCURACY, TRUST & SOURCES
 */
function renderTrustView() {
  if (!state.data) return;

  // Forecast accuracy backtest bars
  const acc = state.data.accuracy;
  const backtestContainer = document.getElementById('backtest-bars');
  if (backtestContainer && acc && acc.rolling_backtest_2025_wape) {
    const wape = acc.rolling_backtest_2025_wape;
    const items = [
      { name: 'Our Model (Backtest)', val: wape.model, isModel: true },
      { name: 'Weekday Mean (8-Week)', val: wape.weekday_mean_8w, isModel: false },
      { name: 'Seasonal Naive (Last Year)', val: wape.seasonal_naive_last_year, isModel: false },
      { name: 'Overall Mean Baseline', val: wape.overall_mean, isModel: false },
      { name: 'Naive (Last Week)', val: wape.naive_last_week, isModel: false }
    ];

    let html = '';
    const maxVal = 0.25;
    items.forEach(it => {
      const pct = (it.val * 100).toFixed(1);
      const widthPct = (it.val / maxVal) * 100;
      html += `
      <div class="backtest-row">
        <div class="backtest-row-header">
          <span style="${it.isModel ? 'color:var(--status-ok); font-weight:800;' : ''}">${it.name}</span>
          <span><strong>${pct}% WAPE</strong></span>
        </div>
        <div class="backtest-bar-track">
          <div class="backtest-bar-fill ${it.isModel ? 'is-model' : ''}" style="width:${widthPct}%;"></div>
        </div>
      </div>`;
    });
    backtestContainer.innerHTML = html;
  }

  // Super Bowl Test Table
  renderSuperBowlTestTable();

  // Key Assumptions Table
  const assumptionsTbody = document.getElementById('assumptions-tbody');
  if (assumptionsTbody && state.data.key_assumptions) {
    let html = '';
    state.data.key_assumptions.forEach(a => {
      let badgeClass = 'badge-assumed';
      if (a.class.includes('measured')) badgeClass = 'badge-measured';
      else if (a.class.includes('placeholder')) badgeClass = 'badge-placeholder';
      else if (a.class.includes('estimated')) badgeClass = 'badge-estimated';

      html += `<tr>
        <td><strong>${escapeHtml(a.name)}</strong></td>
        <td><code>${escapeHtml(a.value)}</code></td>
        <td><span class="badge ${badgeClass}">${escapeHtml(a.class.toUpperCase())}</span></td>
      </tr>`;
    });
    assumptionsTbody.innerHTML = html;
  }

  // Sources List
  const sourcesList = document.getElementById('sources-list');
  if (sourcesList && state.data.sources) {
    let html = '';
    state.data.sources.forEach(s => {
      html += `<li class="source-item">
        <span class="source-name">${escapeHtml(s.name)}</span>
        <a class="source-url" href="${s.url}" target="_blank" rel="noopener noreferrer">${escapeHtml(s.url)} ↗</a>
      </li>`;
    });
    sourcesList.innerHTML = html;
  }
}

function renderSuperBowlTestTable() {
  const tbody = document.getElementById('sb-test-tbody');
  const filterEl = document.getElementById('sb-metric-filter');
  if (!tbody || !state.data || !state.data.super_bowl_test) return;

  const metricFilter = filterEl ? filterEl.value : 'all';
  let rows = state.data.super_bowl_test;
  if (metricFilter !== 'all') {
    rows = rows.filter(r => r.metric === metricFilter);
  }

  let html = '';
  rows.forEach(r => {
    const excessPct = (parseFloat(r.excess) * 100).toFixed(1);
    const isPositive = parseFloat(r.excess) > 0;

    let posBadge = '<span class="badge badge-info">LOW TO MED</span>';
    if (r.position === 'above_high') posBadge = '<span class="badge badge-critical">ABOVE HIGH</span>';
    else if (r.position === 'below_low') posBadge = '<span class="badge badge-warning">BELOW LOW</span>';
    else if (r.position === 'medium_to_high') posBadge = '<span class="badge badge-ok">MED TO HIGH</span>';

    html += `<tr>
      <td><strong>${r.event}</strong></td>
      <td>${r.game_sunday}</td>
      <td><code>${r.airports}</code></td>
      <td><span class="badge badge-secondary">${r.metric.replace('_', ' ').toUpperCase()}</span></td>
      <td style="font-weight:700; color:${isPositive ? 'var(--status-critical)' : 'var(--text-muted)'};">
        ${isPositive ? '+' : ''}${excessPct}%
      </td>
      <td>${posBadge}</td>
    </tr>`;
  });

  tbody.innerHTML = html;
}

/**
 * Utility Helpers
 */
function formatDateShort(dateStr) {
  const parts = dateStr.split('-');
  if (parts.length < 3) return dateStr;
  const day = parseInt(parts[2], 10);
  return `${day} Feb`;
}

function formatDateLong(dateStr) {
  const parts = dateStr.split('-');
  if (parts.length < 3) return dateStr;
  const day = parseInt(parts[2], 10);
  return `${day} February 2027`;
}

function formatDateTime(dtStr) {
  const [d, t] = dtStr.split('T');
  return `${formatDateShort(d)} at ${t} PST`;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function showToast(msg, isError = false) {
  const toast = document.getElementById('toast');
  if (!toast) return;

  toast.textContent = msg;
  toast.style.background = isError ? 'var(--status-critical)' : 'var(--text-primary)';
  toast.style.color = isError ? '#fff' : 'var(--bg-app)';
  toast.removeAttribute('hidden');

  if (window._toastTimeout) clearTimeout(window._toastTimeout);
  window._toastTimeout = setTimeout(() => {
    toast.setAttribute('hidden', 'true');
  }, 3200);
}
