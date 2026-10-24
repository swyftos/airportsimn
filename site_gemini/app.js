/**
 * FBO Super Bowl LXI Operational Readiness Dashboard
 * Plain ES6 JavaScript - Zero Build Step - Offline Capable
 * Strict Human-in-Command Architecture
 */

(function () {
  'use strict';

  // --- Application State ---
  const state = {
    data: null,
    selectedScenario: 'Medium', // 'Low' | 'Medium' | 'High'
    selectedVariant: 'standard', // 'standard' | 'departure_delay_24h' | 'security_restriction' | 'heavy_rain'
    activeTab: 'overview',
    whatIf: {
      rampCapacity: 15,
      demandShockPct: 0,
      towPacking: true,
      apronLease: true
    },
    decisions: {} // Loaded from localStorage
  };

  const STORAGE_KEY_DECISIONS = 'fbo_super_bowl_lxi_decisions';
  const STORAGE_KEY_THEME = 'fbo_super_bowl_lxi_theme';

  // Day of week mapping
  const DAY_NAMES = {
    '2027-02-11': 'Thu 11 Feb',
    '2027-02-12': 'Fri 12 Feb',
    '2027-02-13': 'Sat 13 Feb',
    '2027-02-14': 'Sun 14 Feb (Game)',
    '2027-02-15': 'Mon 15 Feb (Presidents)',
    '2027-02-16': 'Tue 16 Feb',
    '2027-02-17': 'Wed 17 Feb'
  };

  const SHORT_DAY_NAMES = {
    '2027-02-11': 'Thu 11',
    '2027-02-12': 'Fri 12',
    '2027-02-13': 'Sat 13',
    '2027-02-14': 'Sun 14',
    '2027-02-15': 'Mon 15',
    '2027-02-16': 'Tue 16',
    '2027-02-17': 'Wed 17'
  };

  // --- Initialization ---
  async function init() {
    initTheme();
    loadDecisionsFromStorage();
    setupEventListeners();

    try {
      const response = await fetch('fbo_data.json');
      if (!response.ok) {
        throw new Error(`Failed to load data: HTTP ${response.status}`);
      }
      state.data = await response.json();
      renderAll();
    } catch (err) {
      console.error('Initialization error:', err);
      const main = document.querySelector('main');
      if (main) {
        main.innerHTML = `
          <div class="card" style="border-left: 5px solid var(--status-critical); margin-top: 2rem;">
            <h2 style="color: var(--status-critical);">Unable to load operational data</h2>
            <p style="margin-top: 0.5rem; color: var(--text-secondary);">Error loading <code>fbo_data.json</code>: ${err.message}</p>
            <p style="font-size: var(--text-xs); color: var(--text-muted); margin-top: 0.5rem;">Ensure the file is served from a local web server (e.g., <code>python3 -m http.server</code>).</p>
          </div>
        `;
      }
    }
  }

  // --- Theme Management ---
  function initTheme() {
    const savedTheme = localStorage.getItem(STORAGE_KEY_THEME);
    if (savedTheme) {
      document.documentElement.setAttribute('data-theme', savedTheme);
      updateThemeLabel(savedTheme);
    } else {
      const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      updateThemeLabel(prefersDark ? 'dark' : 'light');
    }
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    let next;
    if (!current) {
      const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      next = prefersDark ? 'light' : 'dark';
    } else {
      next = current === 'dark' ? 'light' : 'dark';
    }
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem(STORAGE_KEY_THEME, next);
    updateThemeLabel(next);
    // Re-render charts for theme colors
    if (state.data) {
      renderCharts();
    }
  }

  function updateThemeLabel(theme) {
    const label = document.getElementById('themeLabel');
    if (label) {
      label.textContent = theme === 'dark' ? 'Dark' : 'Light';
    }
  }

  // --- Decisions Storage ---
  function loadDecisionsFromStorage() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY_DECISIONS);
      if (saved) {
        state.decisions = JSON.parse(saved);
      }
    } catch (e) {
      console.warn('Could not read decisions from localStorage:', e);
      state.decisions = {};
    }
  }

  function saveDecisionsToStorage() {
    try {
      localStorage.setItem(STORAGE_KEY_DECISIONS, JSON.stringify(state.decisions));
    } catch (e) {
      console.warn('Could not save decisions to localStorage:', e);
    }
  }

  // --- Event Listeners Setup ---
  function setupEventListeners() {
    // Theme toggle
    const themeBtn = document.getElementById('themeToggleBtn');
    if (themeBtn) {
      themeBtn.addEventListener('click', toggleTheme);
    }

    // Scenario buttons (Low / Medium / High)
    const scenarioBtns = document.querySelectorAll('.segmented-btn[data-scenario]');
    scenarioBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        scenarioBtns.forEach(b => {
          b.classList.remove('active');
          b.setAttribute('aria-checked', 'false');
        });
        btn.classList.add('active');
        btn.setAttribute('aria-checked', 'true');
        state.selectedScenario = btn.getAttribute('data-scenario');
        renderAll();
      });
    });

    // Variant select (Normal, 24h delay, security restriction, heavy rain)
    const variantSelect = document.getElementById('variantSelect');
    if (variantSelect) {
      variantSelect.addEventListener('change', (e) => {
        state.selectedVariant = e.target.value;
        renderAll();
      });
    }

    // Navigation Tabs
    const tabBtns = document.querySelectorAll('.nav-tab-btn[role="tab"]');
    tabBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const targetId = btn.getAttribute('aria-controls');
        tabBtns.forEach(b => {
          b.classList.remove('active');
          b.setAttribute('aria-selected', 'false');
        });
        btn.classList.add('active');
        btn.setAttribute('aria-selected', 'true');

        document.querySelectorAll('.tab-pane').forEach(pane => {
          pane.classList.remove('active');
        });

        const activePane = document.getElementById(targetId);
        if (activePane) {
          activePane.classList.add('active');
        }

        // Trigger chart resize / redraw if needed
        renderCharts();
      });
    });

    // What-If Simulator Controls
    const capSlider = document.getElementById('simCapSlider');
    const shockSlider = document.getElementById('simShockSlider');
    const towToggle = document.getElementById('simTowPackingToggle');
    const apronToggle = document.getElementById('simApronLeaseToggle');

    if (capSlider) {
      capSlider.addEventListener('input', (e) => {
        state.whatIf.rampCapacity = parseFloat(e.target.value);
        document.getElementById('simCapValue').textContent = `${state.whatIf.rampCapacity} su`;
        updateWhatIfResults();
      });
    }

    if (shockSlider) {
      shockSlider.addEventListener('input', (e) => {
        state.whatIf.demandShockPct = parseFloat(e.target.value);
        const sign = state.whatIf.demandShockPct > 0 ? '+' : '';
        document.getElementById('simShockValue').textContent = `${sign}${state.whatIf.demandShockPct}%`;
        updateWhatIfResults();
      });
    }

    if (towToggle) {
      towToggle.addEventListener('change', (e) => {
        state.whatIf.towPacking = e.target.checked;
        updateWhatIfResults();
      });
    }

    if (apronToggle) {
      apronToggle.addEventListener('change', (e) => {
        state.whatIf.apronLease = e.target.checked;
        updateWhatIfResults();
      });
    }

    // Export Decisions Button
    const exportBtn = document.getElementById('exportDecisionsBtn');
    if (exportBtn) {
      exportBtn.addEventListener('click', exportDecisionsJSON);
    }

    // Resize event for charts
    window.addEventListener('resize', debounce(() => {
      renderCharts();
    }, 150));
  }

  // --- Master Render Function ---
  function renderAll() {
    if (!state.data) return;

    renderExecutiveSummary();
    renderKPIs();
    renderDetailedForecastTable();
    renderParkingTable();
    renderPlanActions();
    renderSlotAdvisor();
    renderAccuracyTable();
    renderSuperBowlTestTable();
    renderWeatherTables();
    renderAssumptionsTable();
    renderSources();
    updateWhatIfResults();
    renderCharts();
  }

  // --- Executive Summary Hero Text ---
  function renderExecutiveSummary() {
    const sc = state.selectedScenario;
    const variantKey = state.selectedVariant;
    const variantData = state.data.parking[variantKey];
    const plan = variantData ? variantData.plans[sc] : null;

    if (!plan) return;

    const summary = plan.summary;
    const days = state.data.forecast_daily.filter(d => d.scenario === sc);
    const extraLandings = days.reduce((sum, d) => sum + (d.incremental_arrivals || 0), 0);
    const unaccNoPlan = plan.aircraft_not_accommodated.no_plan.mean;
    const unaccWithPlan = plan.aircraft_not_accommodated.with_plan.mean;
    const netBenefit = plan.net_benefit_usd ? plan.net_benefit_usd.mean : 0;
    const probPayoff = Math.round((plan.prob_plan_pays_off || 0) * 100);

    const variantLabel = variantData.label;

    const el = document.getElementById('execAnswerText');
    if (el) {
      el.innerHTML = `
        During Super Bowl LXI week (Feb 11–17, 2027), under <strong>${sc} demand</strong> and <strong>${variantLabel}</strong>,
        LAX private aviation traffic generates <strong>+${extraLandings.toFixed(1)} additional landings</strong> above ordinary baseline.
        Parking occupancy peaks on <strong>Sun 14 Feb (Game Day) at ${summary.peak_parking_demand_su_p50.toFixed(1)} su</strong> (P50) and 
        <strong>${summary.peak_parking_demand_su_p90.toFixed(1)} su</strong> (P90), exceeding the standard <strong>15.0 su ramp capacity</strong>.
        Without operational intervention, an average of <strong>${unaccNoPlan.toFixed(1)} aircraft</strong> cannot be accommodated.
        With the recommended parking plan ($${plan.parking_cost_usd.toLocaleString()} apron lease + tow-in packing),
        ramp capacity is expanded to <strong>${summary.max_prepared_capacity_su.toFixed(1)} su</strong>, driving unaccommodated aircraft down to 
        <strong>${unaccWithPlan.toFixed(1)}</strong> with a <strong>${probPayoff}% probability of net positive ROI</strong> 
        (estimated net benefit: +$${Math.round(netBenefit).toLocaleString()}).
      `;
    }
  }

  // --- KPI Cards ---
  function renderKPIs() {
    const sc = state.selectedScenario;
    const variantKey = state.selectedVariant;
    const variantData = state.data.parking[variantKey];
    const plan = variantData ? variantData.plans[sc] : null;

    if (!plan) return;

    const days = state.data.forecast_daily.filter(d => d.scenario === sc);
    const extraLandings = days.reduce((sum, d) => sum + (d.incremental_arrivals || 0), 0);
    const totalLandings = days.reduce((sum, d) => sum + (d.expected_arrivals || 0), 0);

    // KPI 1: Extra Landings
    const kpiExtra = document.getElementById('kpiExtraLandings');
    const kpiExtraSub = document.getElementById('kpiExtraLandingsSub');
    if (kpiExtra) kpiExtra.textContent = `+${extraLandings.toFixed(1)}`;
    if (kpiExtraSub) kpiExtraSub.textContent = `Total: ${totalLandings.toFixed(1)} arrivals (${sc} SB effect)`;

    // KPI 2: Peak Parking vs Capacity
    const peakP50 = plan.summary.peak_parking_demand_su_p50;
    const peakP90 = plan.summary.peak_parking_demand_su_p90;
    const kpiPeak = document.getElementById('kpiPeakParking');
    const kpiPeakSub = document.getElementById('kpiPeakParkingSub');
    const kpiPeakBadge = document.getElementById('kpiPeakParkingBadge');

    if (kpiPeak) kpiPeak.textContent = `${peakP50.toFixed(1)}`;
    if (kpiPeakSub) kpiPeakSub.textContent = `P90: ${peakP90.toFixed(1)} su vs 15.0 su ramp (Sun Feb 14)`;
    if (kpiPeakBadge) {
      if (peakP50 > 15) {
        kpiPeakBadge.className = 'kpi-indicator critical';
        kpiPeakBadge.textContent = 'Ramp Exceeded';
      } else if (peakP90 > 15) {
        kpiPeakBadge.className = 'kpi-indicator warning';
        kpiPeakBadge.textContent = 'High P90 Risk';
      } else {
        kpiPeakBadge.className = 'kpi-indicator ok';
        kpiPeakBadge.textContent = 'Capacity Adequate';
      }
    }

    // KPI 3: Unaccommodated Aircraft
    const unaccNoPlan = plan.aircraft_not_accommodated.no_plan.mean;
    const unaccWithPlan = plan.aircraft_not_accommodated.with_plan.mean;
    const kpiUnacc = document.getElementById('kpiUnaccommodated');
    const kpiUnaccSub = document.getElementById('kpiUnaccommodatedSub');
    if (kpiUnacc) kpiUnacc.textContent = `${unaccNoPlan.toFixed(1)} → ${unaccWithPlan.toFixed(1)}`;
    if (kpiUnaccSub) {
      const pctDrop = unaccNoPlan > 0 ? Math.round((1 - unaccWithPlan / unaccNoPlan) * 100) : 0;
      kpiUnaccSub.textContent = `${pctDrop}% reduction with prepared plan`;
    }

    // KPI 4: Plan Cost & Payoff
    const cost = plan.parking_cost_usd;
    const net = plan.net_benefit_usd ? plan.net_benefit_usd.mean : 0;
    const prob = Math.round((plan.prob_plan_pays_off || 0) * 100);
    const kpiCost = document.getElementById('kpiPlanCost');
    const kpiBenefitSub = document.getElementById('kpiPlanBenefitSub');
    const kpiPayoffBadge = document.getElementById('kpiPayoffBadge');

    if (kpiCost) kpiCost.textContent = `$${cost.toLocaleString()}`;
    if (kpiBenefitSub) kpiBenefitSub.textContent = `Net benefit: +$${Math.round(net).toLocaleString()} (mean)`;
    if (kpiPayoffBadge) {
      kpiPayoffBadge.textContent = `${prob}% Payoff Chance`;
      kpiPayoffBadge.className = prob >= 50 ? 'kpi-indicator ok' : 'kpi-indicator warning';
    }
  }

  // --- Detailed Flight Forecast Table ---
  function renderDetailedForecastTable() {
    const sc = state.selectedScenario;
    const days = state.data.forecast_daily.filter(d => d.scenario === sc);
    const tbody = document.getElementById('detailedForecastTableBody');
    const mTableBody = document.getElementById('movementsTableBody');

    if (tbody) {
      tbody.innerHTML = days.map(d => {
        const sizes = d.by_aircraft_size || {};
        const isGameDay = d.date === '2027-02-14';
        const isPresDay = d.date === '2027-02-15';
        const rowClass = isGameDay ? 'highlight-row' : '';
        const dayLabel = DAY_NAMES[d.date] || d.date;

        return `
          <tr class="${rowClass}">
            <td><strong>${dayLabel}</strong> ${isGameDay ? '🏈' : ''} ${isPresDay ? '🏛️' : ''}</td>
            <td class="num">${d.expected_arrivals.toFixed(1)}</td>
            <td class="num" style="color:var(--status-ok);">+${d.incremental_arrivals.toFixed(2)}</td>
            <td class="num">${d.expected_departures.toFixed(1)}</td>
            <td class="num" style="color:var(--status-ok);">+${d.incremental_departures.toFixed(2)}</td>
            <td class="num">${sizes.light_jet ? sizes.light_jet.arrivals.toFixed(1) : '-'}</td>
            <td class="num">${sizes.midsize_jet ? sizes.midsize_jet.arrivals.toFixed(1) : '-'}</td>
            <td class="num">${sizes.large_jet ? sizes.large_jet.arrivals.toFixed(1) : '-'}</td>
          </tr>
        `;
      }).join('');
    }

    if (mTableBody) {
      mTableBody.innerHTML = days.map(d => {
        const isGameDay = d.date === '2027-02-14';
        const isPresDay = d.date === '2027-02-15';
        const rowClass = isGameDay ? 'highlight-row' : '';
        const arrBand = d.arrivals_range90 ? `[${d.arrivals_range90[0]}, ${d.arrivals_range90[1]}]` : '-';
        const depBand = d.departures_range90 ? `[${d.departures_range90[0]}, ${d.departures_range90[1]}]` : '-';
        const dayLabel = DAY_NAMES[d.date] || d.date;

        return `
          <tr class="${rowClass}">
            <td><strong>${d.date}</strong></td>
            <td>${dayLabel}</td>
            <td class="num">${d.baseline_arrivals.toFixed(1)}</td>
            <td class="num" style="font-weight:700; color:var(--chart-arrival);">${d.expected_arrivals.toFixed(1)}</td>
            <td class="num">${arrBand}</td>
            <td class="num">${d.baseline_departures.toFixed(1)}</td>
            <td class="num" style="font-weight:700; color:var(--chart-departure);">${d.expected_departures.toFixed(1)}</td>
            <td class="num">${depBand}</td>
          </tr>
        `;
      }).join('');
    }
  }

  // --- Parking Table ---
  function renderParkingTable() {
    const sc = state.selectedScenario;
    const variantKey = state.selectedVariant;
    const variantData = state.data.parking[variantKey];
    if (!variantData) return;

    const days = variantData.days.filter(d => d.scenario === sc);
    const tbody = document.getElementById('parkingTableBody');
    if (!tbody) return;

    tbody.innerHTML = days.map(d => {
      const isGameDay = d.date === '2027-02-14';
      const isCritical = d.parking_demand_su_p50 > d.capacity_normal_su;
      const rowClass = isCritical ? 'critical-row' : (isGameDay ? 'highlight-row' : '');
      const dayLabel = DAY_NAMES[d.date] || d.date;

      const probNormal = (d.prob_over_normal_capacity * 100).toFixed(1);
      const probPrep = (d.prob_over_prepared_capacity * 100).toFixed(1);
      const utilNormal = (d.utilization_normal_p50 * 100).toFixed(1);

      let riskBadge = `<span class="kpi-indicator ok">Low</span>`;
      if (d.risk_level === 'High') {
        riskBadge = `<span class="kpi-indicator critical">High</span>`;
      } else if (d.risk_level === 'Medium') {
        riskBadge = `<span class="kpi-indicator warning">Medium</span>`;
      }

      return `
        <tr class="${rowClass}">
          <td><strong>${dayLabel}</strong> ${isGameDay ? '🏈' : ''}</td>
          <td class="num">${d.arrivals_p50.toFixed(1)}</td>
          <td class="num">${d.departures_p50.toFixed(1)}</td>
          <td class="num">${d.parking_demand_su_p10.toFixed(1)}</td>
          <td class="num" style="font-weight:700; color:${isCritical ? 'var(--status-critical)' : 'var(--text-primary)'};">${d.parking_demand_su_p50.toFixed(1)}</td>
          <td class="num">${d.parking_demand_su_p90.toFixed(1)}</td>
          <td class="num">${utilNormal}%</td>
          <td class="num" style="color:${d.prob_over_normal_capacity > 0.5 ? 'var(--status-critical)' : 'inherit'};">${probNormal}%</td>
          <td class="num" style="color:var(--status-ok);">${probPrep}%</td>
          <td>${riskBadge}</td>
        </tr>
      `;
    }).join('');

    const pill = document.getElementById('parkingStatusPill');
    if (pill) {
      const maxP50 = Math.max(...days.map(d => d.parking_demand_su_p50));
      if (maxP50 > 15) {
        pill.className = 'kpi-indicator critical';
        pill.textContent = `Peak Overflow: ${maxP50.toFixed(1)} su vs 15.0 su Normal`;
      } else {
        pill.className = 'kpi-indicator ok';
        pill.textContent = `Peak Within Normal Ramp: ${maxP50.toFixed(1)} su`;
      }
    }
  }

  // --- Plan Actions & Human Approval Workflow ---
  function renderPlanActions() {
    const sc = state.selectedScenario;
    const variantKey = state.selectedVariant;
    const variantData = state.data.parking[variantKey];
    const plan = variantData ? variantData.plans[sc] : null;

    if (!plan) return;

    // Plan Economics
    const ecoCost = document.getElementById('planEcoCost');
    const ecoUnacc = document.getElementById('planEcoUnacc');
    const ecoNet = document.getElementById('planEcoNet');
    const ecoProb = document.getElementById('planEcoProb');

    if (ecoCost) ecoCost.textContent = `$${plan.parking_cost_usd.toLocaleString()}`;
    if (ecoUnacc) {
      ecoUnacc.textContent = `${plan.aircraft_not_accommodated.no_plan.mean.toFixed(1)} → ${plan.aircraft_not_accommodated.with_plan.mean.toFixed(1)}`;
    }
    if (ecoNet && plan.net_benefit_usd) {
      const netVal = plan.net_benefit_usd.mean;
      ecoNet.textContent = `${netVal >= 0 ? '+' : ''}$${Math.round(netVal).toLocaleString()}`;
      ecoNet.style.color = netVal >= 0 ? 'var(--status-ok)' : 'var(--status-critical)';
    }
    if (ecoProb) {
      ecoProb.textContent = `${Math.round(plan.prob_plan_pays_off * 100)}%`;
    }

    const container = document.getElementById('planActionsContainer');
    if (!container) return;

    if (!plan.actions || plan.actions.length === 0) {
      container.innerHTML = `
        <div class="card" style="text-align: center; color: var(--text-muted); padding: var(--space-4);">
          No explicit parking actions required for this scenario/variant.
        </div>
      `;
      return;
    }

    let approvedCount = 0;

    container.innerHTML = plan.actions.map(act => {
      const key = `${sc}_${variantKey}_${act.id}`;
      const decision = state.decisions[key] || {
        status: 'pending',
        approverName: act.approver || 'FBO Manager',
        approverRole: act.approver || 'Operations Director',
        note: '',
        timestamp: null
      };

      if (decision.status === 'approved') approvedCount++;

      let statusBadgeClass = 'status-pending';
      let statusText = 'Pending Approval';
      let cardBorderClass = '';

      if (decision.status === 'approved') {
        statusBadgeClass = 'status-approved';
        statusText = 'Authorized / Approved';
        cardBorderClass = 'approved';
      } else if (decision.status === 'rejected') {
        statusBadgeClass = 'status-rejected';
        statusText = 'Rejected';
        cardBorderClass = 'rejected';
      } else if (decision.status === 'changes_requested') {
        statusBadgeClass = 'status-changes';
        statusText = 'Changes Requested';
        cardBorderClass = 'changes-requested';
      }

      const datesFormatted = act.dates.map(d => SHORT_DAY_NAMES[d] || d).join(', ');

      return `
        <div class="plan-action-card ${cardBorderClass}" data-action-key="${key}">
          <div class="action-card-header">
            <div class="action-title-group">
              <span class="action-meta">
                <span class="badge-tag badge-assumed">${act.category.toUpperCase()}</span>
                <span>ID: ${act.id}</span>
                <span>• Designated Approver: <strong>${act.approver}</strong></span>
              </span>
              <h4 class="action-title">${act.action}</h4>
            </div>
            <span class="action-badge-status ${statusBadgeClass}">${statusText}</span>
          </div>

          <div class="action-details-grid">
            <div class="action-detail-item">
              <span class="action-detail-label">Active Dates</span>
              <span class="action-detail-val">${datesFormatted}</span>
            </div>
            <div class="action-detail-item">
              <span class="action-detail-label">Financial Commitment</span>
              <span class="action-detail-val">$${act.cost_usd.toLocaleString()}</span>
            </div>
            <div class="action-detail-item">
              <span class="action-detail-label">Operational Rationale</span>
              <span class="action-detail-val">${act.rationale}</span>
            </div>
            <div class="action-detail-item">
              <span class="action-detail-label">Audit Timestamp</span>
              <span class="action-detail-val">${decision.timestamp ? new Date(decision.timestamp).toLocaleString() : 'Not Yet Signed'}</span>
            </div>
          </div>

          <!-- Human Decision Workflow Form -->
          <div class="approval-form">
            <div class="form-row">
              <div class="form-group">
                <label class="form-label" for="approver_${key}">Approver Name &amp; Title:</label>
                <input type="text" id="approver_${key}" class="form-input" value="${escapeHtml(decision.approverName)}" placeholder="e.g. John Doe, Line Service Manager">
              </div>
              <div class="form-group" style="flex: 2;">
                <label class="form-label" for="note_${key}">Operational Decision Note / Constraints:</label>
                <input type="text" id="note_${key}" class="form-input" value="${escapeHtml(decision.note)}" placeholder="Enter rationale or specific ramp instructions...">
              </div>
            </div>

            <div class="approval-btn-group">
              <button type="button" class="btn btn-approve" data-btn-action="approve" data-key="${key}">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                <span>Approve Action</span>
              </button>
              <button type="button" class="btn btn-changes" data-btn-action="changes" data-key="${key}">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
                <span>Request Changes</span>
              </button>
              <button type="button" class="btn btn-reject" data-btn-action="reject" data-key="${key}">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
                <span>Reject</span>
              </button>
              <button type="button" class="btn btn-secondary" data-btn-action="reset" data-key="${key}">
                <span>Reset Status</span>
              </button>
            </div>
          </div>
        </div>
      `;
    }).join('');

    // Summary Badge in header
    const sumBadge = document.getElementById('approvalSummaryBadge');
    if (sumBadge) {
      const total = plan.actions.length;
      if (approvedCount === total) {
        sumBadge.className = 'badge-tag badge-measured';
        sumBadge.textContent = `All ${total} Actions Approved`;
      } else {
        sumBadge.className = 'badge-tag badge-assumed';
        sumBadge.textContent = `${approvedCount} of ${total} Actions Approved`;
      }
    }

    // Attach event listeners to decision buttons
    container.querySelectorAll('button[data-btn-action]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const actionType = btn.getAttribute('data-btn-action');
        const key = btn.getAttribute('data-key');
        handleDecisionChange(key, actionType);
      });
    });
  }

  function handleDecisionChange(key, actionType) {
    const approverInput = document.getElementById(`approver_${key}`);
    const noteInput = document.getElementById(`note_${key}`);

    const approverName = approverInput ? approverInput.value.trim() : 'Operations Manager';
    const note = noteInput ? noteInput.value.trim() : '';

    let newStatus = 'pending';
    if (actionType === 'approve') newStatus = 'approved';
    else if (actionType === 'reject') newStatus = 'rejected';
    else if (actionType === 'changes') newStatus = 'changes_requested';

    state.decisions[key] = {
      status: newStatus,
      approverName: approverName,
      note: note,
      timestamp: newStatus === 'pending' ? null : new Date().toISOString()
    };

    saveDecisionsToStorage();
    renderPlanActions();
  }

  function exportDecisionsJSON() {
    const exportData = {
      exportTimestamp: new Date().toISOString(),
      scenario: state.selectedScenario,
      variant: state.selectedVariant,
      governanceRule: "The system never accepts or refuses an aircraft. All actions approved by named manager.",
      decisions: state.decisions
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `fbo_super_bowl_decisions_${state.selectedScenario.toLowerCase()}_${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // --- Slot Advisor & Pricing Incentives ---
  function renderSlotAdvisor() {
    const sc = state.selectedScenario;
    const advisor = state.data.slot_advisor;
    if (!advisor) return;

    // Finding text
    const rec = advisor.recommendations[sc];
    const findingEl = document.getElementById('earlyArrivalFindingText');
    if (findingEl && rec) {
      findingEl.textContent = rec.early_arrival_finding || 'Analysis of price incentives shows cheap early arrival lengthens dwell time without freeing parking.';
    }

    // Rows for Drop and Go
    const tbody = document.getElementById('slotAdvisorTableBody');
    if (!tbody || !advisor.rows) return;

    const rows = advisor.rows.filter(r => r.scenario === sc && r.lever === 'drop_and_go');

    tbody.innerHTML = rows.map(r => {
      const takeUpPct = Math.round(r.take_up * 100);
      const isBase = takeUpPct === 0;
      const rowClass = isBase ? 'highlight-row' : '';

      return `
        <tr class="${rowClass}">
          <td><strong>${takeUpPct}% Take-Up</strong> ${isBase ? '(No Action)' : ''}</td>
          <td class="num">${r.peak_su_p50.toFixed(2)}</td>
          <td class="num">${r.peak_su_p90.toFixed(2)}</td>
          <td class="num">${r.game_day_su_p50.toFixed(2)}</td>
          <td class="num" style="color:${r.unaccommodated_mean > 2 ? 'var(--status-critical)' : 'inherit'};">${r.unaccommodated_mean.toFixed(2)}</td>
          <td class="num">$${r.incentive_cost_usd.toLocaleString()}</td>
          <td class="num" style="font-weight:700; color:${r.net_vs_no_action_usd > 0 ? 'var(--status-ok)' : 'inherit'};">
            ${r.net_vs_no_action_usd >= 0 ? '+' : ''}$${r.net_vs_no_action_usd.toLocaleString()}
          </td>
        </tr>
      `;
    }).join('');
  }

  // --- What-If Simulator Live Calculation ---
  function updateWhatIfResults() {
    if (!state.data) return;

    const sc = state.selectedScenario;
    const variantKey = state.selectedVariant;
    const variantData = state.data.parking[variantKey];
    const plan = variantData ? variantData.plans[sc] : null;

    if (!plan) return;

    const basePeak = plan.summary.peak_parking_demand_su_p50;
    const shockMultiplier = 1 + (state.whatIf.demandShockPct / 100);
    const simPeakDemand = basePeak * shockMultiplier;

    let simCapacity = state.whatIf.rampCapacity;
    if (state.whatIf.towPacking) simCapacity += 1.5;
    if (state.whatIf.apronLease) simCapacity += 5.0;

    const utilPct = (simPeakDemand / simCapacity) * 100;
    const overflow = Math.max(0, simPeakDemand - simCapacity);
    const estimatedUnaccommodated = overflow > 0 ? (overflow * 0.85).toFixed(1) : '0.0';

    const peakEl = document.getElementById('simResultPeakDemand');
    const capEl = document.getElementById('simResultNetCapacity');
    const utilEl = document.getElementById('simResultUtil');
    const unaccEl = document.getElementById('simResultUnaccommodated');
    const pillEl = document.getElementById('simResultStatusPill');

    if (peakEl) peakEl.textContent = `${simPeakDemand.toFixed(1)} su`;
    if (capEl) capEl.textContent = `${simCapacity.toFixed(1)} su`;
    if (utilEl) utilEl.textContent = `${utilPct.toFixed(1)}%`;
    if (unaccEl) unaccEl.textContent = estimatedUnaccommodated;

    if (pillEl) {
      if (utilPct > 100) {
        pillEl.className = 'kpi-indicator critical';
        pillEl.textContent = 'Ramp Overloaded';
      } else if (utilPct > 85) {
        pillEl.className = 'kpi-indicator warning';
        pillEl.textContent = 'High Density Buffer';
      } else {
        pillEl.className = 'kpi-indicator ok';
        pillEl.textContent = 'Ramp Buffer Safe';
      }
    }
  }

  // --- Model Trust & Verification Tables ---
  function renderAccuracyTable() {
    const acc = state.data.accuracy;
    const tbody = document.getElementById('accuracyTableBody');
    if (!tbody || !acc || !acc.backtest) return;

    tbody.innerHTML = acc.backtest.map(b => {
      const isModel = b.model === 'model';
      const rowClass = isModel ? 'highlight-row' : '';
      const wapePct = (b.wape * 100).toFixed(2);
      const covPct = b.coverage_90 !== '' ? `${(b.coverage_90 * 100).toFixed(1)}%` : '-';

      return `
        <tr class="${rowClass}">
          <td><strong>${formatModelName(b.model)}</strong></td>
          <td>${b.window === 'all_2025_origins' ? 'All 2025 origins (rolling)' : "Presidents' Day 2025"}</td>
          <td class="num">${b.n}</td>
          <td class="num">${b.mae.toFixed(2)}</td>
          <td class="num" style="font-weight:${isModel ? '700' : 'normal'}; color:${isModel ? 'var(--status-ok)' : 'inherit'};">${wapePct}%</td>
          <td class="num">${b.bias > 0 ? '+' : ''}${b.bias.toFixed(3)}</td>
          <td class="num">${covPct}</td>
        </tr>
      `;
    }).join('');
  }

  function formatModelName(m) {
    if (m === 'model') return 'FBO Production Forecast Model';
    if (m === 'naive_last_week') return 'Baseline: Naive Last Week';
    if (m === 'seasonal_naive_last_year') return 'Baseline: Seasonal Naive Last Year';
    if (m === 'rolling_4w_mean') return 'Baseline: Rolling 4-Week Mean';
    if (m === 'historical_growth_mean') return 'Baseline: Historical Growth Mean';
    return m;
  }

  function renderSuperBowlTestTable() {
    const tests = state.data.super_bowl_test;
    const tbody = document.getElementById('superBowlTestTableBody');
    if (!tbody || !tests) return;

    // Show sample of prominent events
    tbody.innerHTML = tests.slice(0, 10).map(t => {
      const excessPct = (t.excess * 100).toFixed(1);
      const isPos = t.excess >= 0;

      let posBadge = `<span class="badge-tag badge-assumed">${t.position}</span>`;
      if (t.position === 'within_low_high') {
        posBadge = `<span class="badge-tag badge-measured" style="color:var(--status-ok);">Within Model Range</span>`;
      } else if (t.position === 'above_high') {
        posBadge = `<span class="badge-tag badge-estimated" style="color:var(--status-warning);">Above High</span>`;
      }

      return `
        <tr>
          <td><strong>SB ${t.event}</strong></td>
          <td>${t.airports}</td>
          <td>${t.game_sunday}</td>
          <td class="num">${t.ratio_game.toFixed(2)}</td>
          <td class="num">${t.control_mean.toFixed(2)}</td>
          <td class="num" style="font-weight:700; color:${isPos ? 'var(--status-ok)' : 'inherit'};">${isPos ? '+' : ''}${excessPct}%</td>
          <td>${posBadge}</td>
          <td><span style="font-size:0.7rem; color:var(--text-muted);">FAA ATADS</span></td>
        </tr>
      `;
    }).join('');
  }

  function renderWeatherTables() {
    const weather = state.data.weather;
    if (!weather) return;

    const tbodyEffects = document.getElementById('weatherEffectsTableBody');
    if (tbodyEffects && weather.effects) {
      tbodyEffects.innerHTML = weather.effects.map(w => {
        const catLabel = w.category === 'part91_general_aviation' ? 'Part 91 GA' : 'Part 135 Air Taxi';
        const effPct = (w.effect * 100).toFixed(1);
        const ciStr = `[${(w.ci_low * 100).toFixed(1)}%, ${(w.ci_high * 100).toFixed(1)}%]`;
        const isNeg = w.effect < 0;

        return `
          <tr>
            <td><strong>${catLabel}</strong></td>
            <td>${formatWeatherType(w.weather_type)}</td>
            <td class="num">${w.n_days}</td>
            <td class="num" style="font-weight:600; color:${isNeg ? 'var(--status-critical)' : 'var(--status-ok)'};">${w.effect > 0 ? '+' : ''}${effPct}%</td>
            <td class="num" style="color:var(--text-muted); font-size:0.7rem;">${ciStr}</td>
          </tr>
        `;
      }).join('');
    }

    const tbodyFeb = document.getElementById('weatherFebTableBody');
    if (tbodyFeb && weather.february) {
      tbodyFeb.innerHTML = weather.february.filter(f => f.metric === 'february_day_share').map(f => {
        const sharePct = (f.value * 100).toFixed(1);
        return `
          <tr>
            <td><strong>${formatWeatherType(f.weather_type)}</strong></td>
            <td>All February</td>
            <td class="num">${sharePct}% of days</td>
            <td class="num">${f.weather_type === 'rain' ? '0.75 d' : (f.weather_type === 'heavy_fog' ? '0.50 d' : '-')}</td>
            <td class="num">${f.weather_type === 'rain' ? '3 d' : (f.weather_type === 'heavy_fog' ? '2 d' : '-')}</td>
          </tr>
        `;
      }).join('');
    }
  }

  function formatWeatherType(wt) {
    if (wt === 'rain') return 'Rain';
    if (wt === 'heavy_rain') return 'Heavy Rain (Adverse)';
    if (wt === 'fog') return 'Fog';
    if (wt === 'heavy_fog') return 'Heavy Fog';
    if (wt === 'dry_clear') return 'Dry / Clear';
    if (wt === 'day_after_rain') return 'Day After Rain (Rebound)';
    return wt;
  }

  function renderAssumptionsTable() {
    const assumptions = state.data.key_assumptions;
    const tbody = document.getElementById('assumptionsTableBody');
    if (!tbody || !assumptions) return;

    tbody.innerHTML = assumptions.map(a => {
      let badgeClass = 'badge-assumed';
      if (a.class === 'measured') badgeClass = 'badge-measured';
      else if (a.class === 'estimated') badgeClass = 'badge-estimated';

      let valDisplay = a.value;
      if (Array.isArray(a.value)) {
        valDisplay = a.value.map(v => typeof v === 'number' ? (v * 100).toFixed(0) + '%' : v).join(' / ');
      } else if (typeof a.value === 'number') {
        valDisplay = a.value.toLocaleString();
      }

      return `
        <tr>
          <td><strong>${a.name}</strong></td>
          <td><span class="badge-tag ${badgeClass}">${a.class}</span></td>
          <td class="num" style="font-weight:700;">${valDisplay}</td>
          <td>${a.unit || '-'}</td>
          <td style="color:var(--text-secondary);">${a.note || '-'}</td>
        </tr>
      `;
    }).join('');
  }

  function renderSources() {
    const sources = state.data.sources;
    const container = document.getElementById('sourcesContainer');
    if (!container || !sources) return;

    container.innerHTML = sources.map(s => `
      <div style="font-size: var(--text-xs); display:flex; align-items:center; gap:var(--space-2);">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
          <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
        </svg>
        <a href="${s.url}" target="_blank" rel="noopener noreferrer" class="footer-link" style="font-weight:600;">${s.name}</a>
      </div>
    `).join('');
  }

  // ==========================================================================
  // Interactive Hand-Rolled Responsive SVG Charts
  // Clean, zero external dependencies, sharp rendering, robust tooltips
  // ==========================================================================

  function renderCharts() {
    if (!state.data) return;
    renderMovementsChart();
    renderSizeMixChart();
    renderParkingChart();
    renderHistoryChart();
  }

  // --- Chart 1: 7-Day Movements (Arrivals & Departures with 90% ranges) ---
  function renderMovementsChart() {
    const container = document.getElementById('chartMovementsContainer');
    const tooltip = document.getElementById('movementsTooltip');
    if (!container) return;

    const sc = state.selectedScenario;
    const days = state.data.forecast_daily.filter(d => d.scenario === sc);
    if (!days || days.length === 0) return;

    const W = container.clientWidth || 800;
    const H = 300;
    const padL = 45;
    const padR = 25;
    const padT = 30;
    const padB = 45;
    const innerW = W - padL - padR;
    const innerH = H - padT - padB;

    // Find min and max for scaling
    let maxVal = 0;
    days.forEach(d => {
      if (d.arrivals_range90) maxVal = Math.max(maxVal, d.arrivals_range90[1]);
      if (d.departures_range90) maxVal = Math.max(maxVal, d.departures_range90[1]);
      maxVal = Math.max(maxVal, d.expected_arrivals, d.expected_departures);
    });
    maxVal = Math.ceil(maxVal + 1);

    const getX = (idx) => padL + (idx / (days.length - 1)) * innerW;
    const getY = (val) => padT + innerH - (val / maxVal) * innerH;

    // SVG Defs & styles
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark' ||
      (!document.documentElement.getAttribute('data-theme') && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);

    const gridColor = isDark ? '#243048' : '#e2e8f0';
    const textColor = isDark ? '#94a3b8' : '#64748b';
    const arrColor = isDark ? '#38bdf8' : '#0284c7';
    const arrBand = isDark ? 'rgba(56, 189, 248, 0.22)' : 'rgba(2, 132, 199, 0.16)';
    const depColor = isDark ? '#fb923c' : '#ea580c';
    const depBand = isDark ? 'rgba(251, 146, 60, 0.22)' : 'rgba(234, 88, 12, 0.16)';
    const baseColor = isDark ? '#64748b' : '#94a3b8';

    // Build Bands and Lines
    let arrBandPath = '';
    let depBandPath = '';
    let arrLine = '';
    let depLine = '';
    let baseArrLine = '';
    let baseDepLine = '';

    // Upper and lower band paths
    days.forEach((d, i) => {
      const x = getX(i);
      const arrHighY = getY(d.arrivals_range90 ? d.arrivals_range90[1] : d.expected_arrivals);
      if (i === 0) arrBandPath += `M ${x} ${arrHighY} `;
      else arrBandPath += `L ${x} ${arrHighY} `;
    });
    for (let i = days.length - 1; i >= 0; i--) {
      const x = getX(i);
      const arrLowY = getY(days[i].arrivals_range90 ? days[i].arrivals_range90[0] : days[i].expected_arrivals);
      arrBandPath += `L ${x} ${arrLowY} `;
    }
    arrBandPath += 'Z';

    days.forEach((d, i) => {
      const x = getX(i);
      const depHighY = getY(d.departures_range90 ? d.departures_range90[1] : d.expected_departures);
      if (i === 0) depBandPath += `M ${x} ${depHighY} `;
      else depBandPath += `L ${x} ${depHighY} `;
    });
    for (let i = days.length - 1; i >= 0; i--) {
      const x = getX(i);
      const depLowY = getY(days[i].departures_range90 ? days[i].departures_range90[0] : days[i].expected_departures);
      depBandPath += `L ${x} ${depLowY} `;
    }
    depBandPath += 'Z';

    // Lines
    days.forEach((d, i) => {
      const x = getX(i);
      const yArr = getY(d.expected_arrivals);
      const yDep = getY(d.expected_departures);
      const yBaseArr = getY(d.baseline_arrivals);
      const yBaseDep = getY(d.baseline_departures);

      if (i === 0) {
        arrLine += `M ${x} ${yArr} `;
        depLine += `M ${x} ${yDep} `;
        baseArrLine += `M ${x} ${yBaseArr} `;
        baseDepLine += `M ${x} ${yBaseDep} `;
      } else {
        arrLine += `L ${x} ${yArr} `;
        depLine += `L ${x} ${yDep} `;
        baseArrLine += `L ${x} ${yBaseArr} `;
        baseDepLine += `L ${x} ${yBaseDep} `;
      }
    });

    // Grid ticks (Y-axis)
    const yTicks = [0, Math.round(maxVal / 2), maxVal];
    let gridMarkup = '';
    yTicks.forEach(tick => {
      const y = getY(tick);
      gridMarkup += `
        <line x1="${padL}" y1="${y}" x2="${W - padR}" y2="${y}" stroke="${gridColor}" stroke-width="1" />
        <text x="${padL - 8}" y="${y + 4}" fill="${textColor}" font-size="10" text-anchor="end">${tick}</text>
      `;
    });

    // Special Date Markers (Sun 14 Game Day, Mon 15 Presidents' Day)
    let markersMarkup = '';
    days.forEach((d, i) => {
      const x = getX(i);
      const isGame = d.date === '2027-02-14';
      const isPres = d.date === '2027-02-15';

      if (isGame || isPres) {
        markersMarkup += `
          <line x1="${x}" y1="${padT}" x2="${x}" y2="${H - padB}" stroke="${isGame ? '#f59e0b' : '#38bdf8'}" stroke-width="1.5" stroke-dasharray="3,3" opacity="0.8"/>
          <text x="${x}" y="${padT - 10}" fill="${isGame ? '#f59e0b' : textColor}" font-size="10" font-weight="700" text-anchor="middle">
            ${isGame ? '🏈 Super Bowl' : 'Presidents Day'}
          </text>
        `;
      }

      // X labels
      markersMarkup += `
        <text x="${x}" y="${H - padB + 16}" fill="${textColor}" font-size="11" font-weight="${isGame ? '700' : '500'}" text-anchor="middle">
          ${SHORT_DAY_NAMES[d.date] || d.date}
        </text>
      `;
    });

    // Interactive Data Points
    let pointsMarkup = '';
    days.forEach((d, i) => {
      const x = getX(i);
      const yArr = getY(d.expected_arrivals);
      const yDep = getY(d.expected_departures);

      pointsMarkup += `
        <circle cx="${x}" cy="${yArr}" r="4.5" fill="${arrColor}" stroke="#fff" stroke-width="1.5" class="chart-point" data-type="arr" data-index="${i}"/>
        <circle cx="${x}" cy="${yDep}" r="4.5" fill="${depColor}" stroke="#fff" stroke-width="1.5" class="chart-point" data-type="dep" data-index="${i}"/>
      `;
    });

    container.innerHTML = `
      <svg width="100%" height="${H}" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
        ${gridMarkup}
        ${markersMarkup}
        <!-- 90% Confidence Bands -->
        <path d="${arrBandPath}" fill="${arrBand}" />
        <path d="${depBandPath}" fill="${depBand}" />
        <!-- Baseline lines -->
        <path d="${baseArrLine}" fill="none" stroke="${baseColor}" stroke-width="1.5" stroke-dasharray="4,4" opacity="0.6"/>
        <path d="${baseDepLine}" fill="none" stroke="${baseColor}" stroke-width="1.5" stroke-dasharray="4,4" opacity="0.6"/>
        <!-- Forecast Lines -->
        <path d="${arrLine}" fill="none" stroke="${arrColor}" stroke-width="2.5" />
        <path d="${depLine}" fill="none" stroke="${depColor}" stroke-width="2.5" />
        ${pointsMarkup}
        <!-- Y-axis Label -->
        <text x="14" y="${H / 2}" fill="${textColor}" font-size="10" text-anchor="middle" transform="rotate(-90 14 ${H/2})">Movements (aircraft)</text>
      </svg>
    `;

    // Tooltip listeners
    if (tooltip) {
      container.querySelectorAll('.chart-point').forEach(pt => {
        pt.addEventListener('mouseenter', (e) => {
          const idx = parseInt(pt.getAttribute('data-index'), 10);
          const d = days[idx];
          if (!d) return;

          const rect = container.getBoundingClientRect();
          const cx = parseFloat(pt.getAttribute('cx'));
          const cy = parseFloat(pt.getAttribute('cy'));

          tooltip.innerHTML = `
            <div class="tooltip-title">
              <span>${DAY_NAMES[d.date] || d.date}</span>
              <span class="badge-tag badge-estimated">${d.scenario}</span>
            </div>
            <div class="tooltip-row">
              <span class="tooltip-label" style="color:${arrColor}; font-weight:600;">● Expected Arrivals:</span>
              <span class="tooltip-val">${d.expected_arrivals.toFixed(1)}</span>
            </div>
            <div class="tooltip-row">
              <span class="tooltip-label">Arr 90% Range:</span>
              <span class="tooltip-val">[${d.arrivals_range90[0]}, ${d.arrivals_range90[1]}]</span>
            </div>
            <div class="tooltip-row">
              <span class="tooltip-label" style="color:var(--text-muted);">Baseline Arrivals:</span>
              <span class="tooltip-val">${d.baseline_arrivals.toFixed(1)} (+${d.incremental_arrivals.toFixed(1)})</span>
            </div>
            <div class="tooltip-row" style="margin-top:6px; border-top:1px dashed var(--border-light); padding-top:4px;">
              <span class="tooltip-label" style="color:${depColor}; font-weight:600;">● Expected Departures:</span>
              <span class="tooltip-val">${d.expected_departures.toFixed(1)}</span>
            </div>
            <div class="tooltip-row">
              <span class="tooltip-label">Dep 90% Range:</span>
              <span class="tooltip-val">[${d.departures_range90[0]}, ${d.departures_range90[1]}]</span>
            </div>
            <div class="tooltip-row">
              <span class="tooltip-label" style="color:var(--text-muted);">Baseline Departures:</span>
              <span class="tooltip-val">${d.baseline_departures.toFixed(1)} (+${d.incremental_departures.toFixed(1)})</span>
            </div>
          `;

          tooltip.style.display = 'block';
          tooltip.style.left = `${Math.min(cx + 12, rect.width - 200)}px`;
          tooltip.style.top = `${Math.max(10, cy - 80)}px`;
        });

        pt.addEventListener('mouseleave', () => {
          tooltip.style.display = 'none';
        });
      });
    }
  }

  // --- Chart 2: Aircraft Size Mix (Predict Tab) ---
  function renderSizeMixChart() {
    const container = document.getElementById('chartSizeMixContainer');
    const tooltip = document.getElementById('sizeMixTooltip');
    if (!container) return;

    const sc = state.selectedScenario;
    const days = state.data.forecast_daily.filter(d => d.scenario === sc);
    if (!days || days.length === 0) return;

    const W = container.clientWidth || 500;
    const H = 260;
    const padL = 40;
    const padR = 15;
    const padT = 20;
    const padB = 40;
    const innerW = W - padL - padR;
    const innerH = H - padT - padB;

    let maxArr = 0;
    days.forEach(d => {
      maxArr = Math.max(maxArr, d.expected_arrivals);
    });
    maxArr = Math.ceil(maxArr + 1);

    const isDark = document.documentElement.getAttribute('data-theme') === 'dark' ||
      (!document.documentElement.getAttribute('data-theme') && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);

    const textColor = isDark ? '#94a3b8' : '#64748b';
    const gridColor = isDark ? '#243048' : '#e2e8f0';

    const colWidth = Math.min(36, (innerW / days.length) * 0.7);

    let barsMarkup = '';
    days.forEach((d, i) => {
      const centerX = padL + (i + 0.5) * (innerW / days.length);
      const x = centerX - colWidth / 2;
      const sizes = d.by_aircraft_size || {};

      const lightH = sizes.light_jet ? (sizes.light_jet.arrivals / maxArr) * innerH : 0;
      const midH = sizes.midsize_jet ? (sizes.midsize_jet.arrivals / maxArr) * innerH : 0;
      const largeH = sizes.large_jet ? (sizes.large_jet.arrivals / maxArr) * innerH : 0;

      const yLight = padT + innerH - lightH;
      const yMid = yLight - midH;
      const yLarge = yMid - largeH;

      barsMarkup += `
        <g class="size-bar-group" data-index="${i}">
          <rect x="${x}" y="${yLight}" width="${colWidth}" height="${lightH}" fill="#38bdf8" rx="1"/>
          <rect x="${x}" y="${yMid}" width="${colWidth}" height="${midH}" fill="#818cf8" rx="1"/>
          <rect x="${x}" y="${yLarge}" width="${colWidth}" height="${largeH}" fill="#f43f5e" rx="1"/>
        </g>
        <text x="${centerX}" y="${H - padB + 16}" fill="${textColor}" font-size="10" text-anchor="middle">
          ${SHORT_DAY_NAMES[d.date] || d.date}
        </text>
      `;
    });

    const yTicks = [0, Math.round(maxArr / 2), maxArr];
    let gridMarkup = '';
    yTicks.forEach(t => {
      const y = padT + innerH - (t / maxArr) * innerH;
      gridMarkup += `
        <line x1="${padL}" y1="${y}" x2="${W - padR}" y2="${y}" stroke="${gridColor}" stroke-width="1"/>
        <text x="${padL - 6}" y="${y + 4}" fill="${textColor}" font-size="10" text-anchor="end">${t}</text>
      `;
    });

    container.innerHTML = `
      <svg width="100%" height="${H}" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
        ${gridMarkup}
        ${barsMarkup}
        <text x="12" y="${H / 2}" fill="${textColor}" font-size="10" text-anchor="middle" transform="rotate(-90 12 ${H/2})">Arrivals</text>
      </svg>
    `;

    // Tooltip
    if (tooltip) {
      container.querySelectorAll('.size-bar-group').forEach(grp => {
        grp.addEventListener('mouseenter', (e) => {
          const idx = parseInt(grp.getAttribute('data-index'), 10);
          const d = days[idx];
          if (!d) return;

          const rect = container.getBoundingClientRect();
          const sizes = d.by_aircraft_size || {};
          const light = sizes.light_jet ? sizes.light_jet.arrivals.toFixed(1) : '-';
          const mid = sizes.midsize_jet ? sizes.midsize_jet.arrivals.toFixed(1) : '-';
          const large = sizes.large_jet ? sizes.large_jet.arrivals.toFixed(1) : '-';

          tooltip.innerHTML = `
            <div class="tooltip-title">${DAY_NAMES[d.date] || d.date}</div>
            <div class="tooltip-row">
              <span class="tooltip-label" style="color:#38bdf8;">Light Jet (1.0 su):</span>
              <span class="tooltip-val">${light}</span>
            </div>
            <div class="tooltip-row">
              <span class="tooltip-label" style="color:#818cf8;">Midsize Jet (1.5 su):</span>
              <span class="tooltip-val">${mid}</span>
            </div>
            <div class="tooltip-row">
              <span class="tooltip-label" style="color:#f43f5e;">Large Jet (2.5 su):</span>
              <span class="tooltip-val">${large}</span>
            </div>
            <div class="tooltip-row" style="margin-top:4px; border-top:1px solid var(--border-light); padding-top:4px;">
              <span class="tooltip-label" style="font-weight:700;">Total Arrivals:</span>
              <span class="tooltip-val">${d.expected_arrivals.toFixed(1)}</span>
            </div>
          `;

          tooltip.style.display = 'block';
          const mouseX = e.clientX - rect.left;
          tooltip.style.left = `${Math.min(mouseX + 10, rect.width - 180)}px`;
          tooltip.style.top = `20px`;
        });

        grp.addEventListener('mouseleave', () => {
          tooltip.style.display = 'none';
        });
      });
    }
  }

  // --- Chart 3: Ramp Parking Occupancy vs Capacity (Predict Tab) ---
  function renderParkingChart() {
    const container = document.getElementById('chartParkingContainer');
    const tooltip = document.getElementById('parkingTooltip');
    if (!container) return;

    const sc = state.selectedScenario;
    const variantKey = state.selectedVariant;
    const variantData = state.data.parking[variantKey];
    if (!variantData) return;

    const days = variantData.days.filter(d => d.scenario === sc);
    if (!days || days.length === 0) return;

    const W = container.clientWidth || 800;
    const H = 320;
    const padL = 45;
    const padR = 25;
    const padT = 30;
    const padB = 45;
    const innerW = W - padL - padR;
    const innerH = H - padT - padB;

    let maxVal = 24;
    days.forEach(d => {
      maxVal = Math.max(maxVal, d.parking_demand_su_p90, d.capacity_prepared_su || 0);
    });
    maxVal = Math.ceil(maxVal + 2);

    const getX = (idx) => padL + (idx / (days.length - 1)) * innerW;
    const getY = (val) => padT + innerH - (val / maxVal) * innerH;

    const isDark = document.documentElement.getAttribute('data-theme') === 'dark' ||
      (!document.documentElement.getAttribute('data-theme') && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);

    const gridColor = isDark ? '#243048' : '#e2e8f0';
    const textColor = isDark ? '#94a3b8' : '#64748b';
    const p50Color = isDark ? '#818cf8' : '#6366f1';
    const bandColor = isDark ? 'rgba(129, 140, 248, 0.22)' : 'rgba(99, 102, 241, 0.18)';
    const normalCapColor = isDark ? '#f87171' : '#dc2626';
    const prepCapColor = isDark ? '#4ade80' : '#16a34a';

    // Normal Capacity (15 su) line
    const normalCap = days[0].capacity_normal_su || 15.0;
    const normalCapY = getY(normalCap);

    // Prepared Capacity line
    const prepCap = days[0].capacity_prepared_su || 21.5;
    const prepCapY = getY(prepCap);

    // Build P10-P90 band
    let bandPath = '';
    days.forEach((d, i) => {
      const x = getX(i);
      const highY = getY(d.parking_demand_su_p90);
      if (i === 0) bandPath += `M ${x} ${highY} `;
      else bandPath += `L ${x} ${highY} `;
    });
    for (let i = days.length - 1; i >= 0; i--) {
      const x = getX(i);
      const lowY = getY(days[i].parking_demand_su_p10);
      bandPath += `L ${x} ${lowY} `;
    }
    bandPath += 'Z';

    // Build P50 line
    let p50Line = '';
    days.forEach((d, i) => {
      const x = getX(i);
      const y = getY(d.parking_demand_su_p50);
      if (i === 0) p50Line += `M ${x} ${y} `;
      else p50Line += `L ${x} ${y} `;
    });

    // Build Critical Overflow Area (fill between P50 and Normal Cap when P50 > 15)
    let overflowPath = '';
    let hasOverflow = false;
    days.forEach((d, i) => {
      if (d.parking_demand_su_p50 > normalCap) {
        hasOverflow = true;
      }
    });

    // Grid ticks
    const yTicks = [0, 5, 10, 15, 20, maxVal];
    let gridMarkup = '';
    yTicks.forEach(tick => {
      if (tick <= maxVal) {
        const y = getY(tick);
        gridMarkup += `
          <line x1="${padL}" y1="${y}" x2="${W - padR}" y2="${y}" stroke="${gridColor}" stroke-width="1" />
          <text x="${padL - 8}" y="${y + 4}" fill="${textColor}" font-size="10" text-anchor="end">${tick}</text>
        `;
      }
    });

    // Date Ticks & Game Day
    let dateTicksMarkup = '';
    days.forEach((d, i) => {
      const x = getX(i);
      const isGame = d.date === '2027-02-14';

      if (isGame) {
        dateTicksMarkup += `
          <line x1="${x}" y1="${padT}" x2="${x}" y2="${H - padB}" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="3,3" opacity="0.8"/>
          <text x="${x}" y="${padT - 10}" fill="#f59e0b" font-size="10" font-weight="700" text-anchor="middle">🏈 Game Day</text>
        `;
      }

      dateTicksMarkup += `
        <text x="${x}" y="${H - padB + 16}" fill="${textColor}" font-size="11" font-weight="${isGame ? '700' : '500'}" text-anchor="middle">
          ${SHORT_DAY_NAMES[d.date] || d.date}
        </text>
      `;
    });

    // Interactive points
    let pointsMarkup = '';
    days.forEach((d, i) => {
      const x = getX(i);
      const y = getY(d.parking_demand_su_p50);
      const isOver = d.parking_demand_su_p50 > normalCap;

      pointsMarkup += `
        <circle cx="${x}" cy="${y}" r="5" fill="${isOver ? normalCapColor : p50Color}" stroke="#fff" stroke-width="1.5" class="parking-point" data-index="${i}"/>
      `;
    });

    container.innerHTML = `
      <svg width="100%" height="${H}" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
        ${gridMarkup}
        ${dateTicksMarkup}
        <!-- P10-P90 Band -->
        <path d="${bandPath}" fill="${bandColor}" />
        <!-- P50 Line -->
        <path d="${p50Line}" fill="none" stroke="${p50Color}" stroke-width="2.5" />
        <!-- Normal Capacity Line -->
        <line x1="${padL}" y1="${normalCapY}" x2="${W - padR}" y2="${normalCapY}" stroke="${normalCapColor}" stroke-width="2" />
        <text x="${W - padR}" y="${normalCapY - 6}" fill="${normalCapColor}" font-size="10" font-weight="700" text-anchor="end">Normal Capacity (15.0 su)</text>
        <!-- Prepared Capacity Line -->
        <line x1="${padL}" y1="${prepCapY}" x2="${W - padR}" y2="${prepCapY}" stroke="${prepCapColor}" stroke-width="2" stroke-dasharray="5,4" />
        <text x="${W - padR}" y="${prepCapY - 6}" fill="${prepCapColor}" font-size="10" font-weight="700" text-anchor="end">Prepared Capacity (${prepCap.toFixed(1)} su)</text>
        ${pointsMarkup}
        <!-- Y-axis Label -->
        <text x="14" y="${H / 2}" fill="${textColor}" font-size="10" text-anchor="middle" transform="rotate(-90 14 ${H/2})">Occupancy (su)</text>
      </svg>
    `;

    // Tooltip
    if (tooltip) {
      container.querySelectorAll('.parking-point').forEach(pt => {
        pt.addEventListener('mouseenter', (e) => {
          const idx = parseInt(pt.getAttribute('data-index'), 10);
          const d = days[idx];
          if (!d) return;

          const rect = container.getBoundingClientRect();
          const cx = parseFloat(pt.getAttribute('cx'));
          const cy = parseFloat(pt.getAttribute('cy'));

          const isOverNormal = d.parking_demand_su_p50 > normalCap;
          const probOverNormal = (d.prob_over_normal_capacity * 100).toFixed(1);
          const probOverPrep = (d.prob_over_prepared_capacity * 100).toFixed(1);

          tooltip.innerHTML = `
            <div class="tooltip-title">
              <span>${DAY_NAMES[d.date] || d.date}</span>
              <span class="badge-tag ${isOverNormal ? 'badge-estimated' : 'badge-measured'}">${d.risk_level} Risk</span>
            </div>
            <div class="tooltip-row">
              <span class="tooltip-label" style="color:${p50Color}; font-weight:700;">● Parking P50:</span>
              <span class="tooltip-val">${d.parking_demand_su_p50.toFixed(1)} su</span>
            </div>
            <div class="tooltip-row">
              <span class="tooltip-label">90% Range (P10–P90):</span>
              <span class="tooltip-val">[${d.parking_demand_su_p10.toFixed(1)}, ${d.parking_demand_su_p90.toFixed(1)}]</span>
            </div>
            <div class="tooltip-row">
              <span class="tooltip-label">Normal Utilization:</span>
              <span class="tooltip-val">${(d.utilization_normal_p50 * 100).toFixed(1)}%</span>
            </div>
            <div class="tooltip-row" style="margin-top:4px; border-top:1px dashed var(--border-light); padding-top:4px;">
              <span class="tooltip-label" style="color:${normalCapColor};">Prob &gt; 15 su:</span>
              <span class="tooltip-val">${probOverNormal}%</span>
            </div>
            <div class="tooltip-row">
              <span class="tooltip-label" style="color:${prepCapColor};">Prob &gt; Prepared:</span>
              <span class="tooltip-val">${probOverPrep}%</span>
            </div>
          `;

          tooltip.style.display = 'block';
          tooltip.style.left = `${Math.min(cx + 12, rect.width - 200)}px`;
          tooltip.style.top = `${Math.max(10, cy - 80)}px`;
        });

        pt.addEventListener('mouseleave', () => {
          tooltip.style.display = 'none';
        });
      });
    }
  }

  // --- Chart 4: Historical FAA Daily Traffic Time Series (Trust Tab) ---
  function renderHistoryChart() {
    const container = document.getElementById('chartHistoryContainer');
    const tooltip = document.getElementById('historyTooltip');
    if (!container) return;

    const history = state.data.history_daily_faa;
    if (!history || history.length === 0) return;

    const W = container.clientWidth || 800;
    const H = 220;
    const padL = 40;
    const padR = 20;
    const padT = 20;
    const padB = 35;
    const innerW = W - padL - padR;
    const innerH = H - padT - padB;

    let maxVal = 140;
    history.forEach(h => {
      maxVal = Math.max(maxVal, h.part135_air_taxi, h.part91_general_aviation);
    });

    const getX = (idx) => padL + (idx / (history.length - 1)) * innerW;
    const getY = (val) => padT + innerH - (val / maxVal) * innerH;

    const isDark = document.documentElement.getAttribute('data-theme') === 'dark' ||
      (!document.documentElement.getAttribute('data-theme') && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);

    const textColor = isDark ? '#94a3b8' : '#64748b';
    const gridColor = isDark ? '#243048' : '#e2e8f0';
    const taxiColor = isDark ? '#38bdf8' : '#0284c7';
    const gaColor = isDark ? '#fb923c' : '#ea580c';

    // Sample points every 3 days for fast rendering
    const step = 3;
    let taxiPath = '';
    let gaPath = '';

    for (let i = 0; i < history.length; i += step) {
      const h = history[i];
      const x = getX(i);
      const yTaxi = getY(h.part135_air_taxi);
      const yGA = getY(h.part91_general_aviation);

      if (i === 0) {
        taxiPath += `M ${x} ${yTaxi} `;
        gaPath += `M ${x} ${yGA} `;
      } else {
        taxiPath += `L ${x} ${yTaxi} `;
        gaPath += `L ${x} ${yGA} `;
      }
    }

    const yTicks = [0, 50, 100, maxVal];
    let gridMarkup = '';
    yTicks.forEach(t => {
      const y = getY(t);
      gridMarkup += `
        <line x1="${padL}" y1="${y}" x2="${W - padR}" y2="${y}" stroke="${gridColor}" stroke-width="1"/>
        <text x="${padL - 6}" y="${y + 4}" fill="${textColor}" font-size="10" text-anchor="end">${t}</text>
      `;
    });

    // Year markers (2023, 2024, 2025)
    let yearMarkers = `
      <text x="${getX(0)}" y="${H - padB + 16}" fill="${textColor}" font-size="10">2023</text>
      <text x="${getX(365)}" y="${H - padB + 16}" fill="${textColor}" font-size="10">2024</text>
      <text x="${getX(730)}" y="${H - padB + 16}" fill="${textColor}" font-size="10">2025</text>
      <text x="${getX(1095)}" y="${H - padB + 16}" fill="${textColor}" font-size="10" text-anchor="end">Dec 2025</text>
    `;

    container.innerHTML = `
      <svg width="100%" height="${H}" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
        ${gridMarkup}
        ${yearMarkers}
        <path d="${taxiPath}" fill="none" stroke="${taxiColor}" stroke-width="1.2" opacity="0.85" />
        <path d="${gaPath}" fill="none" stroke="${gaColor}" stroke-width="1.2" opacity="0.85" />
        <text x="12" y="${H / 2}" fill="${textColor}" font-size="10" text-anchor="middle" transform="rotate(-90 12 ${H/2})">Daily Movements</text>
      </svg>
    `;
  }

  // --- Helper Functions ---
  function debounce(func, wait) {
    let timeout;
    return function (...args) {
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(this, args), wait);
    };
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Kickoff on DOM loaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
