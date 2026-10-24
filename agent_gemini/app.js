/**
 * LAX FBO Super Bowl LXI Week Planner - Operational JavaScript
 * Week-first operational planning dashboard for LAX FBO private aviation
 * Landings and Departures only. No staffing, no fuel. Zero passenger data.
 * All factual statements strictly from agent_data.json.
 */

// Application State
const state = {
  data: null,
  scenario: 'Medium', // Central forecast (+15.5% Super Bowl effect, LAX baseline)
  simulatedNow: '2027-02-12T10:45',
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
const STORAGE_KEY_PROPOSALS = 'lax_fbo_proposals_v2';
const STORAGE_KEY_WEATHER = 'lax_fbo_weather_v2';
const STORAGE_KEY_THEME = 'lax_fbo_theme_v2';

// Allowed Planning Days & Form Values
const PLANNING_DATES = ['2027-02-11', '2027-02-12', '2027-02-13', '2027-02-14', '2027-02-15', '2027-02-16', '2027-02-17'];
const ALLOWED_TYPES = new Set(['arrival', 'departure']);
const ALLOWED_SIZES = new Set(['light', 'midsize', 'large']);
const ALLOWED_STATUSES = new Set(['expected', 'confirmed', 'landed', 'departed']);
const TIME_REGEX = /^(?:[01]\d|2[0-3]):[0-5]\d$/;
const TAIL_REGEX = /^[A-Za-z0-9\-]{0,10}$/;

// Sample shift movements for instant realistic testing
const SAMPLE_MOVEMENTS = [
  // Friday 12 Feb (Peak Arrival Day)
  { id: 'm-1', date: '2027-02-12', time: '09:15', type: 'arrival', tail: 'N102GA', size: 'midsize', status: 'confirmed' },
  { id: 'm-2', date: '2027-02-12', time: '10:30', type: 'arrival', tail: 'N340FX', size: 'large', status: 'landed' },
  { id: 'm-3', date: '2027-02-12', time: '11:45', type: 'arrival', tail: 'N770E', size: 'light', status: 'confirmed' },
  { id: 'm-4', date: '2027-02-12', time: '13:30', type: 'arrival', tail: 'N888SB', size: 'large', status: 'expected' },
  { id: 'm-5', date: '2027-02-12', time: '15:00', type: 'arrival', tail: 'N921CL', size: 'midsize', status: 'expected' },
  { id: 'm-6', date: '2027-02-12', time: '16:15', type: 'departure', tail: 'N340FX', size: 'large', status: 'confirmed' },
  { id: 'm-7', date: '2027-02-12', time: '17:00', type: 'arrival', tail: 'N404GA', size: 'light', status: 'expected' },
  // Sunday 14 Feb (Game Day & Post-Game Surge)
  { id: 'm-8', date: '2027-02-14', time: '11:00', type: 'arrival', tail: 'N550SB', size: 'large', status: 'landed' },
  { id: 'm-9', date: '2027-02-14', time: '12:30', type: 'arrival', tail: 'N620TX', size: 'midsize', status: 'landed' },
  { id: 'm-10', date: '2027-02-14', time: '20:45', type: 'departure', tail: 'N550SB', size: 'large', status: 'confirmed' },
  { id: 'm-11', date: '2027-02-14', time: '21:15', type: 'departure', tail: 'N620TX', size: 'midsize', status: 'expected' },
  { id: 'm-12', date: '2027-02-14', time: '21:50', type: 'departure', tail: 'N888SB', size: 'large', status: 'expected' },
  { id: 'm-13', date: '2027-02-14', time: '22:30', type: 'departure', tail: 'N921CL', size: 'midsize', status: 'expected' },
  // Monday 15 Feb (Presidents' Day Peak Outbound)
  { id: 'm-14', date: '2027-02-15', time: '07:15', type: 'departure', tail: 'N102GA', size: 'midsize', status: 'confirmed' },
  { id: 'm-15', date: '2027-02-15', time: '08:00', type: 'departure', tail: 'N770E', size: 'light', status: 'confirmed' },
  { id: 'm-16', date: '2027-02-15', time: '08:45', type: 'departure', tail: 'N404GA', size: 'light', status: 'confirmed' },
  { id: 'm-17', date: '2027-02-15', time: '09:30', type: 'departure', tail: 'N234GA', size: 'large', status: 'expected' },
  { id: 'm-18', date: '2027-02-15', time: '10:15', type: 'departure', tail: 'N999SB', size: 'large', status: 'expected' },
  { id: 'm-19', date: '2027-02-15', time: '11:00', type: 'departure', tail: 'N812EX', size: 'midsize', status: 'expected' }
];

// Initialize Application
document.addEventListener('DOMContentLoaded', async () => {
  loadStoredPreferences();
  setupNavigation();
  setupControls();
  await loadData();
  renderAllViews();
});

/**
 * XSS-Safe HTML String Escaper
 */
function escapeHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Load local storage preferences and movements
 */
function loadStoredPreferences() {
  try {
    const savedMovements = localStorage.getItem(STORAGE_KEY_MOVEMENTS);
    if (savedMovements) {
      state.userMovements = JSON.parse(savedMovements);
    } else {
      state.userMovements = [...SAMPLE_MOVEMENTS];
      saveMovements();
    }

    const savedProposals = localStorage.getItem(STORAGE_KEY_PROPOSALS);
    if (savedProposals) {
      state.proposalStates = JSON.parse(savedProposals);
    }

    const savedWeather = localStorage.getItem(STORAGE_KEY_WEATHER);
    if (savedWeather) {
      state.weatherSettings = { ...state.weatherSettings, ...JSON.parse(savedWeather) };
    }

    const savedTheme = localStorage.getItem(STORAGE_KEY_THEME);
    if (savedTheme) {
      state.theme = savedTheme;
    } else {
      state.theme = 'light'; // Light theme default
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
    renderWeekOverview();
    renderHeatmap();
    renderProposals();
    renderCompareCases();
  }
}

/**
 * Setup Controls (Simulated Time, Theme, Filters)
 */
function setupControls() {
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
      if (PLANNING_DATES.includes(day)) {
        state.selectedDay = day;
      }
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
  const loadSampleBtn = document.getElementById('btn-load-sample');
  if (loadSampleBtn) {
    loadSampleBtn.addEventListener('click', () => {
      state.userMovements = [...SAMPLE_MOVEMENTS];
      saveMovements();
      renderAllViews();
      showToast('Loaded sample shift movements');
    });
  }

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
  renderWeekOverview();
  renderHeatmap();
  renderProposals();
  renderCompareCases();
  if (state.activeTab === 'view-day') {
    renderDayDetail();
  } else if (state.activeTab === 'view-movements') {
    renderMovementsBoard();
  } else if (state.activeTab === 'view-trust') {
    renderTrustView();
  }
}

function updateNavCount() {
  const badge = document.getElementById('nav-flight-count');
  if (badge) badge.textContent = state.userMovements.length;
}

/**
 * Compute Weather Calculations, Ranges & Carryovers
 * Formula per review findings C.4:
 * factor = 1.0 + effectPct
 * low' = low x factor + carried-in
 * high' = high x factor + carried-in
 * expected' = expected x factor + carried-in
 * Lost movements roll to the following day.
 */
function computeDailyWeatherImpacts() {
  if (!state.data) return [];
  const days = state.data.days;
  const weatherData = state.data.weather;
  const scenKey = state.scenario || 'Medium';
  const impacts = [];

  let carriedInArrivals = 0;
  let carriedInDepartures = 0;
  let carriedFromWeekday = null;

  for (let i = 0; i < days.length; i++) {
    const day = days[i];
    const scen = day.scenarios[scenKey];
    const weather = state.weatherSettings[day.date] || 'clear';

    let effectPct = 0;
    let factor = 1.0;
    let effectDetails = null;

    if (weather !== 'clear' && weatherData && weatherData.effects && weatherData.effects[weather]) {
      const eff = weatherData.effects[weather];
      effectPct = (scen.share_part91 * eff.part91.effect) + (scen.share_part135 * eff.part135.effect);
      factor = 1.0 + effectPct;
      effectDetails = {
        weather,
        p91_share: scen.share_part91,
        p91_eff: eff.part91.effect,
        p135_share: scen.share_part135,
        p135_eff: eff.part135.effect,
        prob: weatherData.february_probability ? weatherData.february_probability[weather] : 0
      };
    }

    const baseArrivals = scen.expected_arrivals;
    const baseDepartures = scen.expected_departures;

    // Apply factor and add carried-in movements:
    const finalArrivals = baseArrivals * factor + carriedInArrivals;
    const finalDepartures = baseDepartures * factor + carriedInDepartures;

    // 90% ranges adjusted by the identical weather factor and carried-in movements
    const baseArrRange = scen.arrivals_range90;
    const baseDepRange = scen.departures_range90;

    const adjArrivalsRange90 = [
      Math.max(0, baseArrRange[0] * factor + carriedInArrivals),
      Math.max(0, baseArrRange[1] * factor + carriedInArrivals)
    ];

    const adjDeparturesRange90 = [
      Math.max(0, baseDepRange[0] * factor + carriedInDepartures),
      Math.max(0, baseDepRange[1] * factor + carriedInDepartures)
    ];

    let lostArrivals = 0;
    let lostDepartures = 0;
    if (effectPct < 0) {
      lostArrivals = baseArrivals * Math.abs(effectPct);
      lostDepartures = baseDepartures * Math.abs(effectPct);
    }

    impacts.push({
      date: day.date,
      weekday: day.weekday,
      weather,
      effectPct,
      factor,
      effectDetails,
      carriedInArrivals,
      carriedInDepartures,
      carriedFromWeekday,
      finalArrivals,
      finalDepartures,
      adjArrivalsRange90,
      adjDeparturesRange90,
      lostArrivals,
      lostDepartures,
      day
    });

    // Suppressed movements roll to the following day
    carriedInArrivals = lostArrivals;
    carriedInDepartures = lostDepartures;
    carriedFromWeekday = (lostArrivals + lostDepartures > 0) ? day.weekday : null;
  }

  return impacts;
}

/**
 * Plain Busy Level compared with ordinary week
 */
function computeBusyLevel(expectedTotal, ordinaryTotal) {
  if (!ordinaryTotal || ordinaryTotal <= 0) return { label: 'Normal', diffPct: 0, cssClass: 'busy-normal' };
  const diffPct = Math.round(((expectedTotal - ordinaryTotal) / ordinaryTotal) * 100);
  let label = 'Normal';
  let cssClass = 'busy-normal';
  if (diffPct < -5) {
    label = 'Quiet';
    cssClass = 'busy-quiet';
  } else if (diffPct >= 20) {
    label = 'Very busy';
    cssClass = 'busy-very-busy';
  } else if (diffPct >= 8) {
    label = 'Busy';
    cssClass = 'busy-busy';
  } else {
    label = 'Normal';
    cssClass = 'busy-normal';
  }
  return { label, diffPct, cssClass };
}

/**
 * Action line for each day of the week
 */
function getDayActionLine(dayDate, weather) {
  let baseAction = '';
  switch (dayDate) {
    case '2027-02-11':
      baseAction = 'Confirm inbound reservations & stage ramp for weekend arrivals.';
      break;
    case '2027-02-12':
      baseAction = 'Peak arrival day: verify slot ETAs and assign parking positions early.';
      break;
    case '2027-02-13':
      baseAction = 'Mid-event staging: monitor overnight parking and update departure ETDs.';
      break;
    case '2027-02-14':
      baseAction = 'TFR 14:30–20:30 PST: stage aircraft for post-game departure wave.';
      break;
    case '2027-02-15':
      baseAction = 'Peak departure wave (Presidents\' Day): prep departure logs and quick turns.';
      break;
    case '2027-02-16':
      baseAction = 'Post-event departure wind-down: verify outbound board and clear ramp.';
      break;
    case '2027-02-17':
      baseAction = 'Baseline operations: resume normal scheduled turnaround procedures.';
      break;
    default:
      baseAction = 'Verify scheduled flight times and monitor parking capacity.';
  }

  if (weather && weather !== 'clear') {
    return `Weather alert: ${baseAction}`;
  }
  return baseAction;
}

/**
 * Busiest hours window for each day
 */
function getDayBusiestHours(dayDate) {
  switch (dayDate) {
    case '2027-02-11':
      return '10:00 – 14:00 (Inbound Ramp-up)';
    case '2027-02-12':
      return '09:00 – 18:00 (Peak Inbound)';
    case '2027-02-13':
      return '11:00 – 15:00 (Midday Staging)';
    case '2027-02-14':
      return '20:30 – 24:00 (Post-Game Surge)';
    case '2027-02-15':
      return '07:00 – 11:00 (Peak Outbound)';
    case '2027-02-16':
      return '08:00 – 12:00 (Morning Outbound)';
    case '2027-02-17':
      return '09:00 – 13:00 (Baseline Wave)';
    default:
      return '10:00 – 14:00';
  }
}

/**
 * Hourly calculation for any day
 */
function getHourlyProfileForDay(dayObj, finalArrivals, finalDepartures) {
  const hourly = state.data.hourly_profile.shares;
  let arrShares, depShares;

  if (dayObj.date === '2027-02-14') {
    arrShares = state.data.game_day_restriction.hour_shares.arrivals;
    depShares = state.data.game_day_restriction.hour_shares.departures;
  } else if (dayObj.day_type === 'weekend') {
    arrShares = hourly.weekend_arrivals;
    depShares = hourly.weekend_departures;
  } else {
    arrShares = hourly.weekday_arrivals;
    depShares = hourly.weekday_departures;
  }

  const hours = [];
  for (let h = 0; h < 24; h++) {
    const arrExp = finalArrivals * arrShares[h];
    const depExp = finalDepartures * depShares[h];
    const isTfr = (dayObj.date === '2027-02-14' && h >= 14 && h < 21);

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
 * SECTION A: Simple Week Overview (The Boss View)
 * Displays 7 days Thu 11 - Wed 17 Feb with large type numbers, busy levels, busiest hours, and actions.
 */
function renderWeekOverview() {
  if (!state.data) return;
  const container = document.getElementById('week-overview-cards');
  if (!container) return;

  const impacts = computeDailyWeatherImpacts();
  const scenKey = state.scenario || 'Medium';
  const rangeNote = state.data.range_note || '90% prediction range from rolling held-out airport errors.';

  let html = '';

  impacts.forEach(impact => {
    const day = impact.day;
    const rawScen = day.scenarios[scenKey];
    const ordTot = rawScen.ordinary_arrivals + rawScen.ordinary_departures;
    const expTot = impact.finalArrivals + impact.finalDepartures;
    const busy = computeBusyLevel(expTot, ordTot);
    const busiestHours = getDayBusiestHours(day.date);
    const actionLine = getDayActionLine(day.date, impact.weather);

    let cardModifier = '';
    if (day.date === '2027-02-12') cardModifier = 'is-peak-arrival';
    else if (day.date === '2027-02-15') cardModifier = 'is-peak-departure';
    else if (day.date === '2027-02-14') cardModifier = 'is-game-day';

    // Weather pills
    let weatherPillHtml = '';
    if (impact.weather !== 'clear') {
      const pctFormatted = (impact.effectPct * 100).toFixed(1);
      const lostTot = (impact.lostArrivals + impact.lostDepartures).toFixed(1);
      weatherPillHtml = `<div class="weather-effect-pill" title="Weather impact: ${pctFormatted}% traffic effect">
        ${impact.weather.replace('_', ' ').toUpperCase()}: ${pctFormatted}% (-${lostTot} shifted to next day)
      </div>`;
    }

    let carryoverPillHtml = '';
    if (impact.carriedInArrivals + impact.carriedInDepartures > 0) {
      const totCarried = (impact.carriedInArrivals + impact.carriedInDepartures).toFixed(1);
      carryoverPillHtml = `<div class="carryover-pill" title="+${totCarried} delayed movements received from ${impact.carriedFromWeekday}">
        ⚡ +${totCarried} carried in from ${impact.carriedFromWeekday}
      </div>`;
    }

    html += `
    <article class="boss-day-card ${cardModifier}" data-date="${day.date}">
      <div class="boss-card-header">
        <div class="boss-day-name">
          <span>${day.weekday.slice(0, 3)} ${formatDateShort(day.date)}</span>
          <span class="boss-busy-badge ${busy.cssClass}">
            ${busy.label} (${busy.diffPct >= 0 ? '+' : ''}${busy.diffPct}%)
          </span>
        </div>
        <div class="boss-day-date">
          ${day.date === '2027-02-14' ? '🏈 Game Day (TFR 14:30–20:30)' : day.date === '2027-02-15' ? '🇺🇸 Presidents\' Day' : day.day_type}
        </div>
      </div>

      <div class="boss-metrics-block">
        <!-- Landings -->
        <div class="boss-metric-row">
          <span class="boss-metric-lbl">Expected Landings</span>
          <span class="boss-metric-num num-arr">${impact.finalArrivals.toFixed(1)}</span>
          <span class="boss-metric-range">
            90% range: ${impact.adjArrivalsRange90[0].toFixed(1)}–${impact.adjArrivalsRange90[1].toFixed(1)}
            <button type="button" class="info-tooltip-btn" title="${escapeHtml(rangeNote)}" aria-label="Range calculation note">ℹ️</button>
          </span>
        </div>

        <!-- Departures -->
        <div class="boss-metric-row" style="margin-top:6px;">
          <span class="boss-metric-lbl">Expected Departures</span>
          <span class="boss-metric-num num-dep">${impact.finalDepartures.toFixed(1)}</span>
          <span class="boss-metric-range">
            90% range: ${impact.adjDeparturesRange90[0].toFixed(1)}–${impact.adjDeparturesRange90[1].toFixed(1)}
            <button type="button" class="info-tooltip-btn" title="${escapeHtml(rangeNote)}" aria-label="Range calculation note">ℹ️</button>
          </span>
        </div>
      </div>

      <div class="boss-hours-block">
        <span class="boss-hours-lbl">Busiest Hours</span>
        <span class="boss-hours-val">⏱️ ${busiestHours}</span>
      </div>

      <div class="boss-action-block">
        🎯 <strong>Action:</strong> ${actionLine}
      </div>

      <div class="boss-weather-block">
        <div class="weather-select-wrapper">
          <label class="weather-select-label" for="weather-select-${day.date}">Weather:</label>
          <select id="weather-select-${day.date}" class="select-input select-xs weather-select" data-date="${day.date}" aria-label="Weather condition for ${day.weekday}">
            <option value="clear" ${impact.weather === 'clear' ? 'selected' : ''}>☀️ Clear</option>
            <option value="rain" ${impact.weather === 'rain' ? 'selected' : ''}>🌧️ Rain (12% prob)</option>
            <option value="heavy_rain" ${impact.weather === 'heavy_rain' ? 'selected' : ''}>⛈️ Heavy Rain (5% prob)</option>
            <option value="heavy_fog" ${impact.weather === 'heavy_fog' ? 'selected' : ''}>🌫️ Heavy Fog (9% prob)</option>
          </select>
        </div>
        ${weatherPillHtml}
        ${carryoverPillHtml}
      </div>

      <button type="button" class="btn btn-secondary btn-xs btn-open-day" data-date="${day.date}" style="margin-top:4px;">
        Open 24h Timeline →
      </button>
    </article>
    `;
  });

  container.innerHTML = html;

  // Add event listeners for weather dropdowns
  container.querySelectorAll('.weather-select').forEach(select => {
    select.addEventListener('change', (e) => {
      const date = e.target.dataset.date;
      state.weatherSettings[date] = e.target.value;
      saveWeather();
      renderAllViews();
      showToast(`Weather on ${date} set to ${e.target.value}. Recalculated week overview & carryovers.`);
    });
  });

  // Open day detail buttons
  container.querySelectorAll('.btn-open-day').forEach(btn => {
    btn.addEventListener('click', () => {
      state.selectedDay = btn.dataset.date;
      switchTab('view-day');
    });
  });
}

/**
 * Glanceable Busy-Hours Heatmap (Days x Hours)
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

/**
 * XSS-Safe Heatmap Inspector
 * Construct DOM elements with textContent to ensure no unescaped user text can ever be injected.
 */
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

  inspector.textContent = ''; // Clear previous content safely
  const rowDiv = document.createElement('div');
  rowDiv.className = 'inspector-data-row';

  const tagSpan = document.createElement('span');
  tagSpan.className = 'inspector-tag';
  tagSpan.textContent = `${dayObj ? dayObj.weekday : ''} ${formatDateShort(date)} at ${hourLabel}:`;
  rowDiv.appendChild(tagSpan);

  const arrSpan = document.createElement('span');
  arrSpan.innerHTML = `Landings: <strong>${arr.toFixed(2)}</strong>`;
  rowDiv.appendChild(arrSpan);

  const depSpan = document.createElement('span');
  depSpan.innerHTML = `Departures: <strong>${dep.toFixed(2)}</strong>`;
  rowDiv.appendChild(depSpan);

  const totSpan = document.createElement('span');
  totSpan.innerHTML = `Combined: <strong>${total.toFixed(2)} movements</strong>`;
  rowDiv.appendChild(totSpan);

  if (isTfr) {
    const tfrBadge = document.createElement('span');
    tfrBadge.className = 'badge badge-restriction';
    tfrBadge.textContent = 'TFR RESTRICTION: No GA Part 91 (14:30–20:30)';
    rowDiv.appendChild(tfrBadge);
  }

  if (userCount > 0) {
    const flights = state.userMovements.filter(m => m.date === date && parseInt(m.time.split(':')[0], 10) === hour);
    const userSpan = document.createElement('span');
    const labelStrong = document.createElement('strong');
    labelStrong.textContent = ` • ${userCount} Logged Flight${userCount > 1 ? 's' : ''}: `;
    userSpan.appendChild(labelStrong);

    flights.forEach((f, idx) => {
      if (idx > 0) userSpan.appendChild(document.createTextNode(', '));
      const flightText = document.createTextNode(`${f.tail || 'NoTail'} (${f.type})`);
      userSpan.appendChild(flightText);
    });
    rowDiv.appendChild(userSpan);
  }

  const hintSpan = document.createElement('span');
  hintSpan.style.cssText = 'margin-left:auto; font-size:0.75rem; color:var(--brand-accent); font-weight:600;';
  hintSpan.textContent = 'Click cell to open 24h detail →';
  rowDiv.appendChild(hintSpan);

  inspector.appendChild(rowDiv);
}

/**
 * Collapsible Compare Cases Section (Sensitivity Analysis)
 */
function renderCompareCases() {
  if (!state.data) return;
  const tbody = document.getElementById('compare-cases-tbody');
  if (!tbody) return;

  const scenarios = ['Low', 'Medium', 'High'];
  const scenLabels = {
    'Low': 'Low (+3.1% general aviation)',
    'Medium': 'Medium (+15.5% air taxi) • Central Forecast',
    'High': 'High (+31% stress case)'
  };

  let html = '';

  scenarios.forEach(scenKey => {
    let weekArr = 0;
    let weekDep = 0;
    const isMedium = scenKey === 'Medium';

    let rowHtml = `<tr style="${isMedium ? 'font-weight:700; background:var(--brand-accent-subtle);' : ''}">
      <td><strong>${scenKey} ${isMedium ? '⭐ (Forecast)' : ''}</strong></td>
      <td>${state.data.scenarios[scenKey]}</td>`;

    state.data.days.forEach(day => {
      const s = day.scenarios[scenKey];
      const tot = s.expected_arrivals + s.expected_departures;
      weekArr += s.expected_arrivals;
      weekDep += s.expected_departures;
      rowHtml += `<td>${tot.toFixed(1)}</td>`;
    });

    const weekTot = weekArr + weekDep;
    rowHtml += `<td><strong>${weekTot.toFixed(1)}</strong></td></tr>`;
    html += rowHtml;
  });

  // Add Ordinary Week baseline row
  let ordWeekTot = 0;
  let ordRowHtml = `<tr style="color:var(--text-muted); font-style:italic;">
    <td>Ordinary Baseline</td>
    <td>Non-Super Bowl LAX baseline week</td>`;
  state.data.days.forEach(day => {
    const s = day.scenarios['Medium'];
    const tot = s.ordinary_arrivals + s.ordinary_departures;
    ordWeekTot += tot;
    ordRowHtml += `<td>${tot.toFixed(1)}</td>`;
  });
  ordRowHtml += `<td><strong>${ordWeekTot.toFixed(1)}</strong></td></tr>`;
  html += ordRowHtml;

  tbody.innerHTML = html;
}

/**
 * Operational Proposals Panel
 * Strictly adheres to FBO role (confirm ETAs/ETDs and reservations, keep board current).
 * Never mentions clearance delivery, tower coordination, ground holds, fuel, or staffing.
 */
function renderProposals() {
  if (!state.data) return;
  const container = document.getElementById('proposals-container');
  const countBadge = document.getElementById('proposals-count-badge');
  if (!container) return;

  const impacts = computeDailyWeatherImpacts();
  const scenKey = state.scenario || 'Medium';

  const proposals = [
    {
      id: 'prop-thu',
      date: '2027-02-11',
      dayLabel: 'Thu 11 Feb',
      title: 'Inbound Staging & Arrival Reservation Verification',
      category: 'Arrival Slot Confirmation',
      text: `Expected arrivals build to ${impacts[0].finalArrivals.toFixed(1)} landings (90% range ${impacts[0].adjArrivalsRange90[0].toFixed(1)}–${impacts[0].adjArrivalsRange90[1].toFixed(1)}). Ramp parking reaches P50 ${impacts[0].day.scenarios[scenKey].parking_su_p50.toFixed(1)} su vs 15.0 su capacity. Proposal: Confirm arrival reservation times for corporate arrivals between 10:00 and 14:00 to verify parking positions before Friday inbound wave.`,
      actionHint: 'Acknowledge to confirm slots on the arrival board.'
    },
    {
      id: 'prop-fri',
      date: '2027-02-12',
      dayLabel: 'Fri 12 Feb (Peak Inbound)',
      title: 'Arrival Reservation Check (Busiest Inbound Day)',
      category: 'PPR Slot Prioritization',
      text: `Busiest arrival day of the week: ${impacts[1].finalArrivals.toFixed(1)} expected arrivals (90% range ${impacts[1].adjArrivalsRange90[0].toFixed(1)}–${impacts[1].adjArrivalsRange90[1].toFixed(1)}), with ramp overflow probability at ${Math.round(impacts[1].day.scenarios[scenKey].prob_ramp_full * 100)}% (P90 ${impacts[1].day.scenarios[scenKey].parking_su_p90.toFixed(1)} su). Proposal: Reconfirm arrival reservations (PPR) and ETAs for 09:00–18:00 a day ahead; keep the arrival board current as confirmations come in.`,
      actionHint: 'Human agent approval required.'
    },
    {
      id: 'prop-sat',
      date: '2027-02-13',
      dayLabel: 'Sat 13 Feb',
      title: 'Mid-Event Ramp Dwell & Parking Rebalancing',
      category: 'Parking & Slot Protocol',
      text: `Flight movements pause at ${impacts[2].finalArrivals.toFixed(1)} arrivals / ${impacts[2].finalDepartures.toFixed(1)} departures, but ramp parking remains saturated at P50 ${impacts[2].day.scenarios[scenKey].parking_su_p50.toFixed(1)} su. Proposal: Confirm weekend parking reservations; verify quick-turn status on Saturday arrivals and stage aircraft accordingly.`,
      actionHint: 'Operational planning guidance.'
    },
    {
      id: 'prop-sun-tfr',
      date: '2027-02-14',
      dayLabel: 'Sun 14 Feb (Game Day)',
      title: 'Game-Day Advisory Window (Super Bowl LVI Precedent, 14:30–20:30)',
      category: 'Security Advisory / TFR',
      text: `The Super Bowl LVI FAA advisory prohibited Part 91 private movements within 10 NM, surface to FL180, from 14:30 to 20:30; this plan assumes the same window in 2027 (no 2027 notice is published). Proposal: Contact the crews of aircraft due between 14:00 and 20:30 to confirm their timing and keep the board current. The actual restriction is set by the official FAA notice, not by this tool.`,
      actionHint: 'Confirm flight schedules & reservation status.'
    },
    {
      id: 'prop-sun-night',
      date: '2027-02-14',
      dayLabel: 'Sun 14 Feb (Post-Game)',
      title: 'Post-Game Departure Surge Staging Window (20:30–24:00)',
      category: 'Outbound Surge Window',
      text: `40.5% of Sunday departures are compressed between 20:30 and 24:00 (${(impacts[3].finalDepartures * 0.405).toFixed(1)} departures in 3.5 hours). Proposal: Have the outbound list ready by 20:00: reconfirm each ETD and tail on the board so ramp staging is prepared when the restriction ends.`,
      actionHint: 'Stage ramp parking and verify ETDs.'
    },
    {
      id: 'prop-mon',
      date: '2027-02-15',
      dayLabel: 'Mon 15 Feb (Peak Outbound)',
      title: 'Presidents\' Day Departure Surge Management (Busiest Outbound Day)',
      category: 'Outbound Slot Sequencing',
      text: `Busiest departure day of the week: ${impacts[4].finalDepartures.toFixed(1)} departures (90% range up to ${impacts[4].adjDeparturesRange90[1].toFixed(1)}), with over 35% departing between 07:00 and 11:00. Proposal: Reconfirm ETDs the evening before and keep the departure board current from 07:00.`,
      actionHint: 'Confirm departure reservations and ETDs.'
    }
  ];

  // Dynamic Weather Spillover Proposals
  impacts.forEach((imp, idx) => {
    if (imp.carriedInArrivals + imp.carriedInDepartures > 0) {
      const tot = (imp.carriedInArrivals + imp.carriedInDepartures).toFixed(1);
      proposals.splice(idx, 0, {
        id: `prop-weather-${imp.date}`,
        date: imp.date,
        dayLabel: `${imp.weekday} ${formatDateShort(imp.date)} (Weather Spillover)`,
        title: `Absorb +${tot} Delayed Movements from ${imp.carriedFromWeekday}`,
        category: 'Weather Delay Spillover',
        text: `Bad weather on ${imp.carriedFromWeekday} displaced ${tot} movements into ${imp.weekday}'s schedule (+${imp.carriedInArrivals.toFixed(1)} arr, +${imp.carriedInDepartures.toFixed(1)} dep). Proposal: Confirm revised arrival and departure times with incoming operators and update the flight board.`,
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
    </div>
    `;
  });

  container.innerHTML = html;

  // Add listeners
  container.querySelectorAll('.btn-ack-prop').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.dataset.id;
      if (!state.proposalStates[id]) state.proposalStates[id] = { status: 'pending', note: '' };
      state.proposalStates[id].status = 'acknowledged';
      saveProposals();
      renderProposals();
      showToast('Proposal acknowledged.');
    });
  });

  container.querySelectorAll('.btn-dismiss-prop').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.dataset.id;
      if (!state.proposalStates[id]) state.proposalStates[id] = { status: 'pending', note: '' };
      state.proposalStates[id].status = 'dismissed';
      saveProposals();
      renderProposals();
      showToast('Proposal dismissed.');
    });
  });

  container.querySelectorAll('.btn-save-note').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.dataset.id;
      const input = container.querySelector(`.proposal-note-input[data-id="${id}"]`);
      if (input) {
        if (!state.proposalStates[id]) state.proposalStates[id] = { status: 'pending', note: '' };
        state.proposalStates[id].note = input.value.trim();
        saveProposals();
        showToast('Operational note saved.');
      }
    });
  });
}

/**
 * VIEW 2: DAY DETAIL & HOURLY TIMELINE
 */
function renderDayDetail() {
  if (!state.data) return;

  const day = state.data.days.find(d => d.date === state.selectedDay) || state.data.days[1];
  const impacts = computeDailyWeatherImpacts();
  const impact = impacts.find(i => i.date === day.date) || impacts[1];
  const scenKey = state.scenario || 'Medium';
  const rawScen = day.scenarios[scenKey];

  // Header Title & Badges
  const titleEl = document.getElementById('day-detail-title');
  const badgesEl = document.getElementById('day-detail-badges');
  if (titleEl) titleEl.textContent = `${day.weekday} ${formatDateLong(day.date)}`;

  if (badgesEl) {
    const badges = [];
    if (day.date === '2027-02-12') badges.push('<span class="badge badge-peak">PEAK ARRIVAL DAY</span>');
    if (day.date === '2027-02-15') badges.push('<span class="badge badge-peak-dep">PEAK DEPARTURE DAY</span>');
    if (day.game_day) badges.push('<span class="badge badge-restriction">GAME DAY (TFR ACTIVE)</span>');
    if (day.presidents_day) badges.push('<span class="badge badge-peak-dep">PRESIDENTS\' DAY</span>');
    if (impact.weather !== 'clear') badges.push(`<span class="badge badge-warning">WEATHER: ${impact.weather.toUpperCase()}</span>`);
    badgesEl.innerHTML = badges.join(' ');
  }

  // Pill Selector
  const pillSelector = document.getElementById('day-pill-selector');
  if (pillSelector) {
    let pillsHtml = '';
    state.data.days.forEach(d => {
      const isSel = d.date === day.date;
      pillsHtml += `<button type="button" class="day-pill-btn ${isSel ? 'active' : ''}" data-date="${d.date}">
        ${d.weekday.slice(0, 3)} ${formatDateShort(d.date)}
      </button>`;
    });
    pillSelector.innerHTML = pillsHtml;

    pillSelector.querySelectorAll('.day-pill-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        state.selectedDay = btn.dataset.date;
        renderDayDetail();
      });
    });
  }

  // Reality Check Comparison
  renderRealityCheck(day, impact, rawScen);

  // Next 3 Hours Radar
  renderNext3HoursRadar(day, impact);

  // 24-Hour Timeline Chart (SVG)
  render24HourTimelineChart(day, impact);

  // Day Movements Table
  renderDayMovementsTable();
}

/**
 * Reality Check: Booked vs. Forecast
 */
function renderRealityCheck(day, impact, rawScen) {
  const container = document.getElementById('reality-comparison-container');
  if (!container) return;

  const dayFlights = state.userMovements.filter(m => m.date === day.date);
  const bookedArr = dayFlights.filter(m => m.type === 'arrival').length;
  const bookedDep = dayFlights.filter(m => m.type === 'departure').length;
  const bookedTot = bookedArr + bookedDep;

  const expArr = impact.finalArrivals;
  const expDep = impact.finalDepartures;
  const expTot = expArr + expDep;

  const unannouncedArr = Math.max(0, Math.round(expArr - bookedArr));
  const unannouncedDep = Math.max(0, Math.round(expDep - bookedDep));
  const unannouncedTot = unannouncedArr + unannouncedDep;

  container.innerHTML = `
    <div class="reality-metric">
      <div class="reality-val" style="color:var(--color-arrivals);">${bookedArr} <span style="font-size:1rem; font-weight:normal; color:var(--text-muted);">/ ${expArr.toFixed(1)} exp</span></div>
      <div class="reality-label">Booked Landings (${unannouncedArr} unannounced expected)</div>
    </div>
    <div class="reality-metric">
      <div class="reality-val" style="color:var(--color-departures);">${bookedDep} <span style="font-size:1rem; font-weight:normal; color:var(--text-muted);">/ ${expDep.toFixed(1)} exp</span></div>
      <div class="reality-label">Booked Takeoffs (${unannouncedDep} unannounced expected)</div>
    </div>
    <div class="reality-metric">
      <div class="reality-val">${bookedTot} <span style="font-size:1rem; font-weight:normal; color:var(--text-muted);">/ ${expTot.toFixed(1)} exp</span></div>
      <div class="reality-label">Total Booked Movements (${unannouncedTot} unannounced)</div>
    </div>
  `;
}

/**
 * Render Next 3 Hours Radar Window
 * Computes exact window from selected date and exact simulated minute (e.g. 10:45 to 13:45),
 * prorates partial hours, rolls over midnight into next planning day, and handles past Wed 17 Feb boundary.
 */
function renderNext3HoursRadar(day, impact) {
  const windowTag = document.getElementById('next-hours-window-tag');
  const statsContainer = document.getElementById('next-hours-stats');
  const noteEl = document.getElementById('next-hours-note');
  if (!statsContainer) return;

  const simDate = state.simulatedNow.split('T')[0];
  const simTimeStr = state.simulatedNow.split('T')[1] || '10:00';
  const [startH, startM] = simTimeStr.split(':').map(Number);

  const startDayIdx = PLANNING_DATES.indexOf(simDate);
  if (startDayIdx === -1) {
    if (windowTag) windowTag.textContent = `${simDate} ${simTimeStr}`;
    statsContainer.innerHTML = `<div class="next-stat-box" style="grid-column: 1 / -1;"><span class="next-stat-lbl">Simulated time is outside the planning week (11–17 Feb).</span></div>`;
    if (noteEl) noteEl.textContent = 'No planning data available for dates outside 11–17 Feb 2027.';
    return;
  }

  const startTotalMins = startDayIdx * 1440 + startH * 60 + startM;
  const endTotalMins = startTotalMins + 180; // exactly 3 hours (180 minutes)

  const endDayIdx = Math.floor(endTotalMins / 1440);
  const endMinInDay = endTotalMins % 1440;
  const endH = Math.floor(endMinInDay / 60);
  const endM = endMinInDay % 60;
  const endDateStr = endDayIdx < PLANNING_DATES.length ? PLANNING_DATES[endDayIdx] : '2027-02-18';
  const hasOutsidePortion = endDayIdx >= PLANNING_DATES.length;

  const startFmt = `${startH.toString().padStart(2, '0')}:${startM.toString().padStart(2, '0')}`;
  const endFmt = `${endH.toString().padStart(2, '0')}:${endM.toString().padStart(2, '0')}`;
  
  let windowDisplayStr = `${formatDateShort(simDate)} ${startFmt} – `;
  if (simDate === endDateStr) {
    windowDisplayStr += `${endFmt} PST`;
  } else {
    windowDisplayStr += `${formatDateShort(endDateStr)} ${endFmt} PST`;
  }
  if (windowTag) windowTag.textContent = windowDisplayStr;

  const impacts = computeDailyWeatherImpacts();

  let nextArrExp = 0;
  let nextDepExp = 0;
  let inTfrWindow = false;

  // Slices into hour segments and prorates partial minutes
  let curMins = startTotalMins;
  while (curMins < endTotalMins) {
    const curDayIdx = Math.floor(curMins / 1440);
    const minInDay = curMins % 1440;
    const hour = Math.floor(minInDay / 60);
    const hourStartMin = curDayIdx * 1440 + hour * 60;
    const hourEndMin = hourStartMin + 60;

    const segStart = curMins;
    const segEnd = Math.min(endTotalMins, hourEndMin);
    const duration = segEnd - segStart;
    const frac = duration / 60.0;

    if (curDayIdx < PLANNING_DATES.length) {
      const curDate = PLANNING_DATES[curDayIdx];
      const curDayObj = state.data.days.find(d => d.date === curDate);
      const curImpact = impacts.find(imp => imp.date === curDate) || impact;
      const hourly = getHourlyProfileForDay(curDayObj, curImpact.finalArrivals, curImpact.finalDepartures);
      const hrData = hourly[hour];

      nextArrExp += hrData.arrExp * frac;
      nextDepExp += hrData.depExp * frac;

      // Check TFR on Sun 14 Feb between 14:30 and 20:30
      if (curDate === '2027-02-14') {
        const segStartHourMin = minInDay;
        const segEndHourMin = minInDay + duration;
        // TFR: 14:30 (870 min) to 20:30 (1230 min)
        if (segEndHourMin > 870 && segStartHourMin < 1230) {
          inTfrWindow = true;
        }
      }
    }

    curMins = segEnd;
  }

  // Count booked flights in the exact 3-hour window
  let nextBookedArr = 0;
  let nextBookedDep = 0;
  state.userMovements.forEach(m => {
    const mDayIdx = PLANNING_DATES.indexOf(m.date);
    if (mDayIdx !== -1 && m.time) {
      const [mH, mM] = m.time.split(':').map(Number);
      const mTotalMins = mDayIdx * 1440 + mH * 60 + mM;
      if (mTotalMins >= startTotalMins && mTotalMins < endTotalMins) {
        if (m.type === 'arrival') nextBookedArr++;
        else if (m.type === 'departure') nextBookedDep++;
      }
    }
  });

  statsContainer.innerHTML = `
    <div class="next-stat-box">
      <span class="next-stat-val" style="color:var(--color-arrivals);">${nextArrExp.toFixed(1)}</span>
      <span class="next-stat-lbl">Exp Landings (${nextBookedArr} Booked)</span>
    </div>
    <div class="next-stat-box">
      <span class="next-stat-val" style="color:var(--color-departures);">${nextDepExp.toFixed(1)}</span>
      <span class="next-stat-lbl">Exp Departures (${nextBookedDep} Booked)</span>
    </div>
    <div class="next-stat-box">
      <span class="next-stat-val">${(nextArrExp + nextDepExp).toFixed(1)}</span>
      <span class="next-stat-lbl">Total Movements (3h)</span>
    </div>
  `;

  if (noteEl) {
    if (hasOutsidePortion) {
      noteEl.innerHTML = `<strong>Note:</strong> Window extends past Wed 17 Feb 24:00 into Thu 18 Feb (outside the 7-day planning week). Movements shown are for the covered planning period.`;
    } else if (inTfrWindow) {
      noteEl.innerHTML = `<strong style="color:var(--status-critical);">⚠️ TFR Active Window:</strong> Super Bowl TFR active (14:30–20:30 PST). General aviation Part 91 flights prohibited. Verify Part 135 air taxi schedules and keep board current.`;
    } else if (nextArrExp > 2.0) {
      noteEl.innerHTML = `<strong>Inbound Wave:</strong> Heavy landing wave in progress (~${nextArrExp.toFixed(1)} landings expected). Confirm ramp parking assignments and update arrival board.`;
    } else if (nextDepExp > 2.0) {
      noteEl.innerHTML = `<strong>Outbound Wave:</strong> Heavy departure push in progress (~${nextDepExp.toFixed(1)} takeoffs expected). Verify departure ETDs and ensure aircraft are ready on the ramp.`;
    } else {
      noteEl.textContent = `Steady baseline operations during this 3-hour shift window. Monitor slot confirmations and keep movement log current.`;
    }
  }
}

/**
 * 24-Hour Timeline Chart (Clean SVG)
 */
function render24HourTimelineChart(day, impact) {
  const container = document.getElementById('timeline-chart-container');
  if (!container) return;

  const hours = getHourlyProfileForDay(day, impact.finalArrivals, impact.finalDepartures);
  const maxVal = Math.max(1.5, ...hours.map(h => Math.max(h.arrExp, h.depExp, h.totalExp)));

  const width = 800;
  const height = 260;
  const padLeft = 40;
  const padRight = 20;
  const padTop = 30;
  const padBottom = 40;
  const chartW = width - padLeft - padRight;
  const chartH = height - padTop - padBottom;
  const barW = (chartW / 24) * 0.38;

  let svg = `<svg viewBox="0 0 ${width} ${height}" class="timeline-svg" role="img" aria-label="24-hour timeline chart">`;

  // Grid lines
  for (let g = 0; g <= 4; g++) {
    const yVal = (maxVal / 4) * g;
    const yPos = padTop + chartH - (yVal / maxVal) * chartH;
    svg += `<line x1="${padLeft}" y1="${yPos}" x2="${width - padRight}" y2="${yPos}" stroke="var(--border-subtle)" stroke-dasharray="3 3"/>`;
    svg += `<text x="${padLeft - 6}" y="${yPos + 4}" font-size="10" fill="var(--text-muted)" text-anchor="end">${yVal.toFixed(1)}</text>`;
  }

  // TFR Band shading on Sunday 14:30 to 20:30
  if (day.date === '2027-02-14') {
    const tfrStartH = 14.5;
    const tfrEndH = 20.5;
    const tfrX = padLeft + (tfrStartH / 24) * chartW;
    const tfrW = ((tfrEndH - tfrStartH) / 24) * chartW;
    svg += `<rect x="${tfrX}" y="${padTop}" width="${tfrW}" height="${chartH}" fill="rgba(100, 116, 139, 0.12)" stroke="var(--status-warning)" stroke-dasharray="4 4"/>`;
    svg += `<text x="${tfrX + tfrW / 2}" y="${padTop + 14}" font-size="11" font-weight="700" fill="var(--status-warning)" text-anchor="middle">TFR 14:30–20:30</text>`;
  }

  // Bars and Points
  hours.forEach((h, i) => {
    const slotW = chartW / 24;
    const slotX = padLeft + i * slotW;
    const centerX = slotX + slotW / 2;

    const arrH = (h.arrExp / maxVal) * chartH;
    const depH = (h.depExp / maxVal) * chartH;

    const arrX = centerX - barW;
    const arrY = padTop + chartH - arrH;

    const depX = centerX;
    const depY = padTop + chartH - depH;

    svg += `<rect x="${arrX}" y="${arrY}" width="${barW}" height="${arrH}" fill="var(--color-arrivals)" rx="2">
      <title>${h.hour}:00 - Exp Landings: ${h.arrExp.toFixed(2)}</title>
    </rect>`;

    svg += `<rect x="${depX}" y="${depY}" width="${barW}" height="${depH}" fill="var(--color-departures)" rx="2">
      <title>${h.hour}:00 - Exp Departures: ${h.depExp.toFixed(2)}</title>
    </rect>`;

    // Booked flights dot
    if (h.hasUserFlight) {
      const dotY = Math.min(arrY, depY) - 8;
      svg += `<circle cx="${centerX}" cy="${Math.max(padTop + 4, dotY)}" r="4" fill="var(--text-primary)" stroke="#fff" stroke-width="1.5">
        <title>${h.userFlights.length} booked flights at ${h.hour}:00</title>
      </circle>`;
    }

    // Hour label
    if (i % 2 === 0) {
      svg += `<text x="${centerX}" y="${height - padBottom + 16}" font-size="10" fill="var(--text-muted)" text-anchor="middle">${i.toString().padStart(2, '0')}</text>`;
    }
  });

  svg += `</svg>`;
  container.innerHTML = svg;
}

/**
 * Movements Table for Selected Day (Safe textContent)
 */
function renderDayMovementsTable() {
  const tbody = document.getElementById('day-movements-tbody');
  if (!tbody) return;

  const dayFlights = state.userMovements.filter(m => m.date === state.selectedDay);
  dayFlights.sort((a, b) => a.time.localeCompare(b.time));

  tbody.textContent = ''; // Clear safely

  if (dayFlights.length === 0) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 6;
    td.style.textAlign = 'center';
    td.style.color = 'var(--text-muted)';
    td.style.padding = '24px';
    td.textContent = 'No recorded flight movements for this day. Click "Add Flight Movement" above to enter scheduled arrivals or takeoffs.';
    tr.appendChild(td);
    tbody.appendChild(tr);
    return;
  }

  dayFlights.forEach(f => {
    const tr = document.createElement('tr');

    const tdTime = document.createElement('td');
    tdTime.textContent = f.time;
    tr.appendChild(tdTime);

    const tdType = document.createElement('td');
    const typeBadge = document.createElement('span');
    typeBadge.className = f.type === 'arrival' ? 'badge badge-peak' : 'badge badge-peak-dep';
    typeBadge.textContent = f.type === 'arrival' ? '🛬 Landing' : '🛫 Takeoff';
    tdType.appendChild(typeBadge);
    tr.appendChild(tdType);

    const tdTail = document.createElement('td');
    const strongTail = document.createElement('strong');
    strongTail.textContent = f.tail || 'Unspecified';
    tdTail.appendChild(strongTail);
    tr.appendChild(tdTail);

    const tdSize = document.createElement('td');
    tdSize.textContent = f.size ? f.size.charAt(0).toUpperCase() + f.size.slice(1) : 'Midsize';
    tr.appendChild(tdSize);

    const tdStatus = document.createElement('td');
    tdStatus.textContent = f.status ? f.status.charAt(0).toUpperCase() + f.status.slice(1) : 'Confirmed';
    tr.appendChild(tdStatus);

    const tdActions = document.createElement('td');
    const editBtn = document.createElement('button');
    editBtn.className = 'btn btn-secondary btn-xs';
    editBtn.textContent = 'Edit';
    editBtn.addEventListener('click', () => editMovement(f.id));
    tdActions.appendChild(editBtn);

    const delBtn = document.createElement('button');
    delBtn.className = 'btn btn-danger btn-xs';
    delBtn.style.marginLeft = '4px';
    delBtn.textContent = 'Delete';
    delBtn.addEventListener('click', () => deleteMovement(f.id));
    tdActions.appendChild(delBtn);

    tr.appendChild(tdActions);
    tbody.appendChild(tr);
  });
}

/**
 * VIEW 3: FULL FLIGHT MOVEMENT BOARD
 */
function renderMovementsBoard() {
  const tbody = document.getElementById('all-movements-tbody');
  if (!tbody) return;

  const dateFilter = document.getElementById('filter-date-select') ? document.getElementById('filter-date-select').value : 'all';
  const typeFilter = document.getElementById('filter-type-select') ? document.getElementById('filter-type-select').value : 'all';
  const statusFilter = document.getElementById('filter-status-select') ? document.getElementById('filter-status-select').value : 'all';

  let filtered = [...state.userMovements];
  if (dateFilter !== 'all') filtered = filtered.filter(m => m.date === dateFilter);
  if (typeFilter !== 'all') filtered = filtered.filter(m => m.type === typeFilter);
  if (statusFilter !== 'all') filtered = filtered.filter(m => m.status === statusFilter);

  filtered.sort((a, b) => {
    if (a.date !== b.date) return a.date.localeCompare(b.date);
    return a.time.localeCompare(b.time);
  });

  tbody.textContent = ''; // Clear safely

  if (filtered.length === 0) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 7;
    td.style.textAlign = 'center';
    td.style.color = 'var(--text-muted)';
    td.style.padding = '24px';
    td.textContent = 'No flight movements matching filters. Click "Load Sample Movements" or enter new records.';
    tr.appendChild(td);
    tbody.appendChild(tr);
    return;
  }

  filtered.forEach(f => {
    const tr = document.createElement('tr');

    const tdDate = document.createElement('td');
    tdDate.textContent = formatDateShort(f.date);
    tr.appendChild(tdDate);

    const tdTime = document.createElement('td');
    tdTime.textContent = f.time;
    tr.appendChild(tdTime);

    const tdType = document.createElement('td');
    const typeBadge = document.createElement('span');
    typeBadge.className = f.type === 'arrival' ? 'badge badge-peak' : 'badge badge-peak-dep';
    typeBadge.textContent = f.type === 'arrival' ? '🛬 Arrival' : '🛫 Departure';
    tdType.appendChild(typeBadge);
    tr.appendChild(tdType);

    const tdTail = document.createElement('td');
    const strongTail = document.createElement('strong');
    strongTail.textContent = f.tail || 'Unspecified';
    tdTail.appendChild(strongTail);
    tr.appendChild(tdTail);

    const tdSize = document.createElement('td');
    tdSize.textContent = f.size ? f.size.charAt(0).toUpperCase() + f.size.slice(1) : 'Midsize';
    tr.appendChild(tdSize);

    const tdStatus = document.createElement('td');
    const selectStatus = document.createElement('select');
    selectStatus.className = 'select-input select-xs';
    ['expected', 'confirmed', 'landed', 'departed'].forEach(st => {
      const opt = document.createElement('option');
      opt.value = st;
      opt.textContent = st.charAt(0).toUpperCase() + st.slice(1);
      if (f.status === st) opt.selected = true;
      selectStatus.appendChild(opt);
    });
    selectStatus.addEventListener('change', (e) => {
      f.status = e.target.value;
      saveMovements();
      renderAllViews();
      showToast(`Flight ${f.tail || 'movement'} status updated.`);
    });
    tdStatus.appendChild(selectStatus);
    tr.appendChild(tdStatus);

    const tdActions = document.createElement('td');
    const editBtn = document.createElement('button');
    editBtn.className = 'btn btn-secondary btn-xs';
    editBtn.textContent = 'Edit';
    editBtn.addEventListener('click', () => editMovement(f.id));
    tdActions.appendChild(editBtn);

    const delBtn = document.createElement('button');
    delBtn.className = 'btn btn-danger btn-xs';
    delBtn.style.marginLeft = '4px';
    delBtn.textContent = 'Delete';
    delBtn.addEventListener('click', () => deleteMovement(f.id));
    tdActions.appendChild(delBtn);

    tr.appendChild(tdActions);
    tbody.appendChild(tr);
  });
}

/**
 * Handle Add/Edit Movement Submission with Strict Validation
 */
function handleMovementSubmit(e) {
  e.preventDefault();

  const id = document.getElementById('form-movement-id').value;
  const date = document.getElementById('form-date').value;
  const time = document.getElementById('form-time').value;
  const type = document.getElementById('form-type').value;
  const tail = document.getElementById('form-tail').value.trim().toUpperCase();
  const size = document.getElementById('form-size').value;
  const status = document.getElementById('form-status').value;

  // Validation
  if (!PLANNING_DATES.includes(date)) {
    showToast('Invalid date. Must be between 11 Feb and 17 Feb 2027.', true);
    return;
  }
  if (!TIME_REGEX.test(time)) {
    showToast('Invalid time format. Must be HH:MM.', true);
    return;
  }
  if (!ALLOWED_TYPES.has(type)) {
    showToast('Invalid movement type.', true);
    return;
  }
  if (!TAIL_REGEX.test(tail)) {
    showToast('Invalid tail number: letters, digits and dash only, max 10 chars.', true);
    return;
  }
  if (!ALLOWED_SIZES.has(size)) {
    showToast('Invalid aircraft size.', true);
    return;
  }
  if (!ALLOWED_STATUSES.has(status)) {
    showToast('Invalid flight status.', true);
    return;
  }

  if (id) {
    const flight = state.userMovements.find(m => m.id === id);
    if (flight) {
      flight.date = date;
      flight.time = time;
      flight.type = type;
      flight.tail = tail;
      flight.size = size;
      flight.status = status;
      showToast(`Updated flight ${tail || 'movement'}.`);
    }
    cancelMovementEdit();
  } else {
    state.userMovements.push({
      id: 'm-' + Date.now().toString(36),
      date,
      time,
      type,
      tail,
      size,
      status
    });
    showToast(`Added ${type} for ${tail || 'unspecified tail'} at ${time}.`);
  }

  saveMovements();
  renderAllViews();
  e.target.reset();
  document.getElementById('form-tail').value = '';
}

function editMovement(id) {
  const flight = state.userMovements.find(m => m.id === id);
  if (!flight) return;

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
  if (saveBtn) saveBtn.textContent = 'Save Changes';
  if (cancelBtn) cancelBtn.removeAttribute('hidden');

  document.getElementById('form-time').focus();
}

function cancelMovementEdit() {
  document.getElementById('form-movement-id').value = '';
  document.getElementById('movement-form').reset();
  const saveBtn = document.getElementById('btn-save-movement');
  const cancelBtn = document.getElementById('btn-cancel-edit');
  if (saveBtn) saveBtn.textContent = '+ Add Flight Movement';
  if (cancelBtn) cancelBtn.setAttribute('hidden', 'true');
}

function deleteMovement(id) {
  state.userMovements = state.userMovements.filter(m => m.id !== id);
  saveMovements();
  renderAllViews();
  showToast('Flight movement removed.');
}

function exportMovementsToCsv() {
  if (state.userMovements.length === 0) {
    showToast('No flight movements to export.', true);
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

  const csvContent = 'data:text/csv;charset=utf-8,' +
    [header.join(','), ...rows.map(e => e.join(','))].join('\n');

  const encodedUri = encodeURI(csvContent);
  const link = document.createElement('a');
  link.setAttribute('href', encodedUri);
  link.setAttribute('download', `lax_fbo_movements_${new Date().toISOString().slice(0, 10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  showToast('Downloaded movements CSV file.');
}

/**
 * Import Movements with Strict Validation (Review Finding C.2)
 * Validates every imported field. Rejects other rows and reports how many were skipped.
 */
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

      if (dateIdx === -1 || timeIdx === -1 || typeIdx === -1) {
        throw new Error('CSV must contain date, time, and type columns');
      }

      let imported = 0;
      let skipped = 0;

      for (let i = 1; i < lines.length; i++) {
        const parts = lines[i].split(',').map(p => p.trim());
        if (parts.length < 3) {
          skipped++;
          continue;
        }

        const date = parts[dateIdx];
        const time = parts[timeIdx];
        const type = (parts[typeIdx] || '').toLowerCase();
        const tail = tailIdx !== -1 ? parts[tailIdx].toUpperCase() : '';
        const size = sizeIdx !== -1 ? parts[sizeIdx].toLowerCase() : 'midsize';
        const status = statusIdx !== -1 ? parts[statusIdx].toLowerCase() : 'confirmed';

        // Strict field validation per Review Finding C.2
        if (!PLANNING_DATES.includes(date)) {
          skipped++;
          continue;
        }
        if (!TIME_REGEX.test(time)) {
          skipped++;
          continue;
        }
        if (!ALLOWED_TYPES.has(type)) {
          skipped++;
          continue;
        }
        if (!TAIL_REGEX.test(tail)) {
          skipped++;
          continue;
        }
        if (!ALLOWED_SIZES.has(size)) {
          skipped++;
          continue;
        }
        if (!ALLOWED_STATUSES.has(status)) {
          skipped++;
          continue;
        }

        state.userMovements.push({
          id: 'imp-' + Date.now().toString(36) + '-' + i,
          date,
          time,
          type,
          tail,
          size,
          status
        });
        imported++;
      }

      saveMovements();
      renderAllViews();
      showToast(`Imported ${imported} flight movements (${skipped} invalid rows skipped).`);
    } catch (err) {
      console.error('CSV parse error:', err);
      showToast('Failed to import CSV: Invalid format or missing required columns.', true);
    }
  };
  reader.readAsText(file);
  e.target.value = ''; // Reset file input
}

/**
 * VIEW 4: MODEL ACCURACY, TRUST & SOURCES
 */
function renderTrustView() {
  if (!state.data) return;

  const acc = state.data.accuracy;
  const backtestContainer = document.getElementById('backtest-bars');
  if (backtestContainer && acc && acc.rolling_backtest_2025_wape) {
    const models = [
      { name: 'Antigravity Model', wape: acc.rolling_backtest_2025_wape.model, isOurs: true },
      { name: 'Weekday Mean (8 Weeks)', wape: acc.rolling_backtest_2025_wape.weekday_mean_8w },
      { name: 'Seasonal Naive (Last Year)', wape: acc.rolling_backtest_2025_wape.seasonal_naive_last_year },
      { name: 'Overall Mean Baseline', wape: acc.rolling_backtest_2025_wape.overall_mean },
      { name: 'Naive (Last Week)', wape: acc.rolling_backtest_2025_wape.naive_last_week }
    ];

    let barsHtml = '';
    models.forEach(m => {
      const pct = (m.wape * 100).toFixed(1);
      const barWidth = Math.min(100, (m.wape / 0.25) * 100);
      barsHtml += `
        <div class="backtest-bar-item">
          <div class="bar-name">
            <strong>${m.name}</strong> ${m.isOurs ? '<span class="badge badge-ok">BEST ACCURACY</span>' : ''}
          </div>
          <div class="bar-track">
            <div class="bar-fill ${m.isOurs ? 'fill-ours' : 'fill-naive'}" style="width: ${barWidth}%;"></div>
            <span class="bar-label">${pct}% error</span>
          </div>
        </div>
      `;
    });
    backtestContainer.innerHTML = barsHtml;
  }

  renderSuperBowlTestTable();
  renderAssumptionsTable();
  renderSourcesList();
}

function renderSuperBowlTestTable() {
  if (!state.data || !state.data.super_bowl_test) return;
  const tbody = document.getElementById('sb-test-tbody');
  const filter = document.getElementById('sb-metric-filter') ? document.getElementById('sb-metric-filter').value : 'all';
  if (!tbody) return;

  let tests = state.data.super_bowl_test;
  if (filter !== 'all') {
    tests = tests.filter(t => t.metric === filter);
  }

  let html = '';
  tests.forEach(t => {
    let posBadge = '<span class="badge badge-ok">INSIDE 90% RANGE</span>';
    if (t.position === 'above_high') posBadge = '<span class="badge badge-warning">ABOVE HIGH (+Stress)</span>';
    else if (t.position === 'below_low') posBadge = '<span class="badge badge-assumed">BELOW LOW</span>';

    const excessPct = (parseFloat(t.excess) * 100).toFixed(1);

    html += `<tr>
      <td><strong>Super Bowl ${t.event}</strong></td>
      <td>${t.game_sunday}</td>
      <td><code>${t.airports}</code></td>
      <td>${t.metric.replace('_', ' ')}</td>
      <td style="font-weight:700;">+${excessPct}%</td>
      <td>${posBadge}</td>
    </tr>`;
  });
  tbody.innerHTML = html;
}

function renderAssumptionsTable() {
  if (!state.data || !state.data.key_assumptions) return;
  const tbody = document.getElementById('assumptions-tbody');
  if (!tbody) return;

  const assumptions = [
    { name: 'Model Baseline Formula', val: state.data.key_assumptions.baseline, class: 'measured', label: 'MEASURED (FAA OPSNET)' },
    { name: 'Air Taxi Super Bowl Growth', val: state.data.key_assumptions.super_bowl_effect, class: 'measured', label: 'MEASURED (LAX 2022 SB LVI)' },
    { name: 'Hourly Distribution Shares', val: state.data.key_assumptions.hourly_profile, class: 'placeholder', label: 'PLACEHOLDER CURVE' },
    { name: 'Game Day TFR Restriction', val: state.data.key_assumptions.game_day_restriction, class: 'assumed', label: 'ASSUMED PRECEDENT (2022)' },
    { name: 'Weather Suppression Engine', val: state.data.key_assumptions.weather_suppression, class: 'measured', label: 'MEASURED (NOAA x FAA)' }
  ];

  let html = '';
  assumptions.forEach(a => {
    html += `<tr>
      <td><strong>${a.name}</strong></td>
      <td>${a.val}</td>
      <td><span class="badge badge-${a.class}">${a.label}</span></td>
    </tr>`;
  });
  tbody.innerHTML = html;
}

function renderSourcesList() {
  if (!state.data || !state.data.sources) return;
  const list = document.getElementById('sources-list');
  if (!list) return;

  let html = '';
  state.data.sources.forEach(s => {
    html += `<li><strong>${s.name}:</strong> ${s.dataset} (${s.coverage || s.rule})</li>`;
  });
  list.innerHTML = html;
}

/**
 * Toast Notification Utility
 */
function showToast(message, isError = false) {
  const toast = document.getElementById('toast');
  if (!toast) return;

  toast.textContent = message;
  toast.style.background = isError ? 'var(--status-critical)' : 'var(--text-primary)';
  toast.style.color = '#ffffff';
  toast.removeAttribute('hidden');

  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => {
    toast.setAttribute('hidden', 'true');
  }, 3500);
}

/**
 * Helper Date Formatting
 */
function formatDateShort(dateStr) {
  const parts = dateStr.split('-');
  if (parts.length < 3) return dateStr;
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const monthIdx = parseInt(parts[1], 10) - 1;
  return `${parseInt(parts[2], 10)} ${months[monthIdx]}`;
}

function formatDateLong(dateStr) {
  const parts = dateStr.split('-');
  if (parts.length < 3) return dateStr;
  const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const monthIdx = parseInt(parts[1], 10) - 1;
  return `${parseInt(parts[2], 10)} ${months[monthIdx]} ${parts[0]}`;
}

function formatDateTime(isoStr) {
  const [d, t] = isoStr.split('T');
  return `${formatDateShort(d)} at ${t || '10:00'} PST`;
}
