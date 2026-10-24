/**
 * app.js
 * Main application controller for the LAX FBO 3D Parking Simulator.
 * Integrates:
 * - 2D Executive Answer (KPIs, SVG forecast chart, accessible data table, plan approvals)
 * - Explorable 3D Ramp (Three.js free orbit camera, day/night lighting, stands, overflow, manager holding)
 * - Week Timeline Strip coloured by model's over-capacity probability (click jumps simulation)
 * - Governance & Transparency (Human in command, formulas, source citations)
 */

import { SimulationEngine } from './sim-engine.js';
import { Ramp3DScene } from './ramp3d.js';

class FBOApp {
  constructor() {
    this.data = null;
    this.simEngine = null;
    this.ramp3d = null;

    // Simulation Clock State
    this.simSeconds = 0; // Starts at Thu 11 Feb 00:00
    this.totalSeconds = 7 * 86400; // 604,800 s
    this.isPlaying = false;
    this.playbackSpeed = 120; // Simulated seconds per wall second (default 2 min/sec)
    this.lastWallTime = null;

    // Plan approvals state (persisted in localStorage)
    this.planApprovals = {
      towPacking: true,
      overflowApron: true,
      notes: {
        towPacking: '',
        overflowApron: ''
      }
    };

    this.selectedAircraft = null;
  }

  async init() {
    try {
      // 1. Fetch parking_data.json
      const response = await fetch('./parking_data.json');
      if (!response.ok) {
        throw new Error(`Failed to load parking_data.json: ${response.statusText}`);
      }
      this.data = await response.json();

      // 2. Load stored approvals from localStorage if present
      this.loadStoredApprovals();

      // 3. Initialize Simulation Engine
      this.simEngine = new SimulationEngine(this.data);
      this.simEngine.setPlanState(this.planApprovals.towPacking, this.planApprovals.overflowApron);

      // Start at Thursday 08:30 for great initial daylight scene
      this.simSeconds = 8.5 * 3600;

      // 4. Initialize 3D Ramp Scene
      const canvasContainer = document.getElementById('ramp-canvas-container');
      if (canvasContainer) {
        this.ramp3d = new Ramp3DScene(canvasContainer, this.onAircraftSelected.bind(this));
      }

      // 5. Setup UI & Event Listeners
      this.setupControls();

      // 6. Initial Render of all views
      this.renderAll();

      // 7. Start simulation animation loop
      requestAnimationFrame(this.simLoop.bind(this));

    } catch (err) {
      console.error('Initialization error:', err);
      const errBox = document.getElementById('init-error');
      if (errBox) {
        errBox.style.display = 'block';
        errBox.textContent = `Error loading simulation: ${err.message}`;
      }
    }
  }

  loadStoredApprovals() {
    try {
      const stored = localStorage.getItem('lax_fbo_sb61_plan_approvals');
      if (stored) {
        const parsed = JSON.parse(stored);
        this.planApprovals = { ...this.planApprovals, ...parsed };
      }
    } catch (e) {
      console.warn('LocalStorage unavailable or corrupt:', e);
    }
  }

  saveStoredApprovals() {
    try {
      localStorage.setItem('lax_fbo_sb61_plan_approvals', JSON.stringify(this.planApprovals));
    } catch (e) {
      console.warn('Could not save to localStorage:', e);
    }
  }

  setupControls() {
    // Scenario selector (Low / Medium / High)
    const scenarioSelect = document.getElementById('scenario-select');
    if (scenarioSelect) {
      scenarioSelect.value = this.simEngine.scenarioKey;
      scenarioSelect.addEventListener('change', (e) => {
        this.simEngine.setScenario(e.target.value);
        this.renderAll();
      });
    }

    // Situation variant selector (standard / departure_delay_24h / security_restriction / heavy_rain)
    const situationSelect = document.getElementById('situation-select');
    if (situationSelect) {
      Object.entries(this.data.situations || {}).forEach(([key, label]) => {
        const opt = situationSelect.querySelector(`option[value="${key}"]`);
        if (opt) opt.textContent = label;
      });
      situationSelect.value = this.simEngine.situationKey;
      situationSelect.addEventListener('change', (e) => {
        this.simEngine.setSituation(e.target.value);
        this.renderAll();
      });
    }

    // Plan action toggles
    const towToggle = document.getElementById('toggle-tow-packing');
    if (towToggle) {
      towToggle.checked = this.planApprovals.towPacking;
      towToggle.addEventListener('change', (e) => {
        this.planApprovals.towPacking = e.target.checked;
        this.simEngine.setPlanState(this.planApprovals.towPacking, this.planApprovals.overflowApron);
        this.saveStoredApprovals();
        this.renderAll();
      });
    }

    const overflowToggle = document.getElementById('toggle-overflow-lease');
    if (overflowToggle) {
      overflowToggle.checked = this.planApprovals.overflowApron;
      overflowToggle.addEventListener('change', (e) => {
        this.planApprovals.overflowApron = e.target.checked;
        this.simEngine.setPlanState(this.planApprovals.towPacking, this.planApprovals.overflowApron);
        this.saveStoredApprovals();
        this.renderAll();
      });
    }

    // Plan manager notes inputs
    const towNotes = document.getElementById('notes-tow-packing');
    if (towNotes) {
      towNotes.value = this.planApprovals.notes.towPacking || '';
      towNotes.addEventListener('input', (e) => {
        this.planApprovals.notes.towPacking = e.target.value;
        this.saveStoredApprovals();
      });
    }

    const overflowNotes = document.getElementById('notes-overflow-lease');
    if (overflowNotes) {
      overflowNotes.value = this.planApprovals.notes.overflowApron || '';
      overflowNotes.addEventListener('input', (e) => {
        this.planApprovals.notes.overflowApron = e.target.value;
        this.saveStoredApprovals();
      });
    }

    // Playback buttons
    const playPauseBtn = document.getElementById('btn-play-pause');
    if (playPauseBtn) {
      playPauseBtn.addEventListener('click', () => {
        this.isPlaying = !this.isPlaying;
        playPauseBtn.textContent = this.isPlaying ? '⏸ Pause' : '▶ Play';
        playPauseBtn.setAttribute('aria-label', this.isPlaying ? 'Pause simulation' : 'Play simulation');
      });
    }

    // Playback speed selectors
    document.querySelectorAll('.speed-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.speed-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.playbackSpeed = parseFloat(btn.dataset.speed || 120);
      });
    });

    // Time scrubber slider
    const scrubber = document.getElementById('time-scrubber');
    if (scrubber) {
      scrubber.value = this.simSeconds;
      scrubber.addEventListener('input', (e) => {
        this.simSeconds = parseFloat(e.target.value);
        this.updateSimulationViews();
      });
    }

    // Jump Buttons
    const btnGameKickoff = document.getElementById('btn-jump-kickoff');
    if (btnGameKickoff) {
      btnGameKickoff.addEventListener('click', () => {
        // Sun 14 Feb 15:30 = Day 3 (Sunday) + 15.5 hours = 3 * 86400 + 15.5 * 3600 = 315000 s
        this.simSeconds = 3 * 86400 + 15.5 * 3600;
        this.updateSimulationViews();
      });
    }

    const btnStepPrev = document.getElementById('btn-step-prev');
    if (btnStepPrev) {
      btnStepPrev.addEventListener('click', () => {
        this.simSeconds = Math.max(0, this.simSeconds - 3600);
        this.updateSimulationViews();
      });
    }

    const btnStepNext = document.getElementById('btn-step-next');
    if (btnStepNext) {
      btnStepNext.addEventListener('click', () => {
        this.simSeconds = Math.min(this.totalSeconds, this.simSeconds + 3600);
        this.updateSimulationViews();
      });
    }

    // Camera preset buttons
    document.querySelectorAll('.camera-preset-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.camera-preset-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const preset = btn.dataset.preset;
        if (this.ramp3d && preset) {
          this.ramp3d.setCameraPreset(preset);
        }
      });
    });

    // Theme toggle
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
      themeToggle.addEventListener('click', () => {
        document.body.classList.toggle('dark');
        const isDark = document.body.classList.contains('dark');
        themeToggle.textContent = isDark ? '☀️ Light' : '🌙 Dark';
      });
    }
  }

  // Simulation loop running on requestAnimationFrame
  simLoop(wallTimestamp) {
    if (this.lastWallTime === null) {
      this.lastWallTime = wallTimestamp;
    }

    const wallDeltaSec = (wallTimestamp - this.lastWallTime) / 1000;
    this.lastWallTime = wallTimestamp;

    if (this.isPlaying) {
      this.simSeconds += wallDeltaSec * this.playbackSpeed;
      if (this.simSeconds > this.totalSeconds) {
        this.simSeconds = 0; // Loop week
      }
      this.updateSimulationViews();
    }

    requestAnimationFrame(this.simLoop.bind(this));
  }

  // Render everything (called on scenario/situation/plan change)
  renderAll() {
    this.render2DAnswerKPIs();
    this.renderSVGChart();
    this.renderDataTable();
    this.renderPlanDetails();
    this.renderWeekTimelineStrip();
    this.updateSimulationViews();
  }

  // Update views that react directly to the simulation clock (3D, clock badge, timeline playhead, live gauges)
  updateSimulationViews() {
    if (!this.simEngine) return;

    const simState = this.simEngine.getStateAtTime(this.simSeconds);

    // 1. Update 3D Scene
    if (this.ramp3d) {
      this.ramp3d.updateSimulationState(simState);
    }

    // 2. Update Live Clock Display
    const clockEl = document.getElementById('sim-clock-display');
    if (clockEl) {
      const dayName = simState.weekday;
      const gameBadge = simState.isGameDay ? ' <span class="badge-game">🏆 Super Bowl LXI</span>' : (simState.isPresidentsDay ? ' <span class="badge-holiday">Presidents\' Day</span>' : '');
      const hour = simState.hourFloat;
      let lightingIcon = '☀️ Day';
      if (hour < 6.5 || hour > 18.5) lightingIcon = '🌙 Night (Floodlights ON)';
      else if (hour < 7.5 || hour > 17.5) lightingIcon = '🌅 Golden Hour';

      clockEl.innerHTML = `<strong>${dayName} ${simState.dateStr}</strong> &bull; <strong>${simState.timeStr}</strong> &bull; <span class="lighting-tag">${lightingIcon}</span>${gameBadge}`;
    }

    // 3. Update Time Scrubber Slider
    const scrubber = document.getElementById('time-scrubber');
    if (scrubber && Math.abs(parseFloat(scrubber.value) - this.simSeconds) > 30) {
      scrubber.value = this.simSeconds;
    }

    // 4. Update Live Gauges in 3D Header
    const rampSuEl = document.getElementById('gauge-main-ramp-su');
    if (rampSuEl) {
      const cap = simState.mainRampCap;
      const used = simState.mainRampUsedSu;
      const pct = Math.round((used / cap) * 100);
      rampSuEl.innerHTML = `<strong>${used.toFixed(1)}</strong> / ${cap.toFixed(1)} su <span class="util-tag ${pct > 100 ? 'critical' : (pct >= 85 ? 'warning' : 'ok')}">(${pct}%)</span>`;
    }

    const overflowSuEl = document.getElementById('gauge-overflow-su');
    if (overflowSuEl) {
      const leased = simState.overflowLeasedCap;
      const used = simState.overflowUsedSu;
      if (leased > 0) {
        overflowSuEl.innerHTML = `<strong>${used.toFixed(1)}</strong> / ${leased.toFixed(1)} su`;
      } else {
        overflowSuEl.innerHTML = `<span class="text-muted">Unleased (0 su)</span>`;
      }
    }

    const decisionSuEl = document.getElementById('gauge-decision-area-su');
    if (decisionSuEl) {
      const count = simState.managerDecisionCount;
      const su = simState.managerDecisionSu;
      if (count > 0) {
        decisionSuEl.innerHTML = `<strong class="critical-text">${count} jet(s) (${su.toFixed(1)} su)</strong> <span class="badge-decision">Awaiting Manager</span>`;
      } else {
        decisionSuEl.innerHTML = `<span class="ok-text">0 waiting (Normal flow)</span>`;
      }
    }

    // 5. Update Timeline Strip playhead indicator
    const playhead = document.getElementById('timeline-playhead');
    if (playhead) {
      const pct = (this.simSeconds / this.totalSeconds) * 100;
      playhead.style.left = `${pct}%`;
    }

    // Update active day card in timeline strip
    document.querySelectorAll('.timeline-day-card').forEach((card, idx) => {
      if (idx === simState.dayIndex) {
        card.classList.add('active-sim-day');
      } else {
        card.classList.remove('active-sim-day');
      }
    });

    // 6. Update Inspector Drawer if an aircraft is selected
    if (this.selectedAircraft) {
      // Find updated state
      const currentFlight = simState.activeAircraft.find(a => a.id === this.selectedAircraft.id);
      this.updateAircraftInspector(currentFlight || this.selectedAircraft);
    }
  }

  // ==========================================
  // SECTION 1: THE 2D ANSWER (FIRST & VISIBLE)
  // ==========================================

  render2DAnswerKPIs() {
    const week = this.simEngine.getWeekSummary();
    const plan = this.simEngine.getCurrentPlan();
    const normalCap = this.data.capacity.ramp_su;
    document.querySelectorAll('.js-ramp-su').forEach(e => { e.textContent = normalCap.toFixed(1); });
    document.querySelectorAll('.js-ramp-derivation').forEach(e => { e.textContent = this.data.capacity.derivation; });
    const cap = this.data.capacity, ac = this.data.aircraft, pct = x => `${Math.round(x * 100)}%`;
    const fill = (sel, text) => document.querySelectorAll(sel).forEach(e => { e.textContent = text; });
    fill('.js-tow-gain', `+${pct(cap.tow_packing_gain)} (+${(normalCap * cap.tow_packing_gain).toFixed(1)} su)`);
    fill('.js-packed-su', (normalCap * (1 + cap.tow_packing_gain)).toFixed(1));
    fill('.js-size-mix', Object.entries(ac.sizes).map(([k, v]) => `${k} ${v.su} su, ${pct(v.share)}, e.g. ${v.example.split(' (')[0]}`).join(' • ') + '.');
    fill('.js-stay-mix', `Average dwell: ${ac.stays.average_days} days (same-day ${pct(ac.stays.same_day)}, overnight ${pct(ac.stays.overnight)}, multi-day ${pct(ac.stays.multi_day_3)}).`);

    // Find first day over capacity (prob > 50%)
    const overDays = week.filter(d => d.probOverNormal >= 0.5);
    const firstDay = overDays.length > 0 ? overDays[0] : null;

    // Find peak demand day (max P50)
    let peakDay = week[0];
    week.forEach(d => {
      if (d.p50 > peakDay.p50) peakDay = d;
    });

    // KPI 1: When demand exceeds ramp
    const kpi1 = document.getElementById('kpi-overflow-timing');
    if (kpi1) {
      if (firstDay) {
        kpi1.innerHTML = `
          <div class="kpi-label">First Over-Capacity Day</div>
          <div class="kpi-value critical">${firstDay.weekday} ${firstDay.date.slice(5)}</div>
          <div class="kpi-sub">${(firstDay.probOverNormal * 100).toFixed(1)}% chance over ${normalCap.toFixed(1)} su ramp</div>
          <div class="kpi-formula">Formula: Model simulated weeks where demand &gt; ${normalCap} su / 10,000 runs</div>
        `;
      } else {
        kpi1.innerHTML = `
          <div class="kpi-label">First Over-Capacity Day</div>
          <div class="kpi-value ok">None (&lt;50%)</div>
          <div class="kpi-sub">Ramp sufficient under Low scenario</div>
        `;
      }
    }

    // KPI 2: Peak Day P50/P90 vs Capacity
    const kpi2 = document.getElementById('kpi-peak-demand');
    if (kpi2) {
      const overloadP50 = (peakDay.p50 - normalCap).toFixed(1);
      const overloadP90 = (peakDay.p90 - normalCap).toFixed(1);
      kpi2.innerHTML = `
        <div class="kpi-label">Peak Demand (${peakDay.date === this.data.meta.game_day ? 'Game Day ' : ''}${peakDay.weekday} ${peakDay.date.slice(5)})</div>
        <div class="kpi-value">${peakDay.p50.toFixed(1)} su <span class="kpi-range">[P10 ${peakDay.p10.toFixed(1)} - P90 ${peakDay.p90.toFixed(1)}]</span></div>
        <div class="kpi-sub critical-text">+${overloadP50} su over normal capacity (+${overloadP90} su at P90)</div>
        <div class="kpi-formula">Peak Overload = P50 (${peakDay.p50.toFixed(1)}) - Normal Cap (${normalCap.toFixed(1)}) = +${overloadP50} su</div>
      `;
    }

    // KPI 3: AI Preparation Plan ROI & Cost
    const kpi3 = document.getElementById('kpi-plan-impact');
    if (kpi3) {
      if (plan) {
        const costStr = plan.plan_cost_usd === 0 ? '$0 (Tow-packing only)' : `$${plan.plan_cost_usd.toLocaleString()}`;
        const payoffPct = (plan.prob_plan_pays_off * 100).toFixed(1);
        const unaccNo = plan.aircraft_not_accommodated_mean.no_plan;
        const unaccWith = plan.aircraft_not_accommodated_mean.with_plan;
        kpi3.innerHTML = `
          <div class="kpi-label">AI Preparation Plan (Tow-Packing + Lease)</div>
          <div class="kpi-value ok-text">${costStr}</div>
          <div class="kpi-sub">${payoffPct}% chance pays off &bull; Unaccommodated: ${unaccNo} &rarr; <strong>${unaccWith}</strong> jets</div>
          <div class="kpi-formula">Unaccommodated reduction: ${((1 - unaccWith / unaccNo) * 100).toFixed(0)}% drop with plan</div>
        `;
      }
    }

    // KPI 4: Comparison with Ordinary Week
    const kpi4 = document.getElementById('kpi-ordinary-compare');
    if (kpi4) {
      const ordPeak = week.reduce((max, d) => d.ordP50 > max ? d.ordP50 : max, 0);
      const ordMaxProb = Math.max(...Object.values(this.data.ordinary_week).map(o => o.prob_over_normal_capacity));
      const surgeDelta = (peakDay.p50 - ordPeak).toFixed(1);
      const surgePct = ((surgeDelta / ordPeak) * 100).toFixed(1);
      kpi4.innerHTML = `
        <div class="kpi-label">Ordinary Week Peak (same dates, no Super Bowl)</div>
        <div class="kpi-value">${ordPeak.toFixed(1)} su <span class="kpi-range">(max chance over the ramp: ${(ordMaxProb * 100).toFixed(1)}%)</span></div>
        <div class="kpi-sub">Super Bowl surge: <strong>+${surgeDelta} su (+${surgePct}%)</strong> above baseline</div>
        <div class="kpi-formula">Surge = Super Bowl P50 (${peakDay.p50.toFixed(1)}) - Baseline (${ordPeak.toFixed(1)})</div>
      `;
    }
  }

  // Render SVG Forecast Chart (P10-P90 band, P50 line, capacity lines, ordinary baseline)
  renderSVGChart() {
    const container = document.getElementById('chart-container');
    if (!container) return;

    const week = this.simEngine.getWeekSummary();
    const width = 840;
    const height = 300;
    const padding = { top: 30, right: 130, bottom: 45, left: 55 };

    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;

    // Y scale: 0 to max P90 with margin (at least 25 su, or up to 42 for delay scenarios)
    const maxVal = Math.max(26, ...week.map(d => Math.max(d.p90, d.capacityPrepared) + 3));
    const yScale = (val) => padding.top + chartH - (val / maxVal) * chartH;
    const xScale = (idx) => padding.left + (idx / 6) * chartW;

    // Build P10-P90 band path
    let bandPath = `M ${xScale(0)} ${yScale(week[0].p90)}`;
    for (let i = 1; i < 7; i++) {
      bandPath += ` L ${xScale(i)} ${yScale(week[i].p90)}`;
    }
    for (let i = 6; i >= 0; i--) {
      bandPath += ` L ${xScale(i)} ${yScale(week[i].p10)}`;
    }
    bandPath += ' Z';

    // Build P50 line
    let p50Line = `M ${xScale(0)} ${yScale(week[0].p50)}`;
    for (let i = 1; i < 7; i++) {
      p50Line += ` L ${xScale(i)} ${yScale(week[i].p50)}`;
    }

    // Build Ordinary baseline line
    let ordLine = `M ${xScale(0)} ${yScale(week[0].ordP50)}`;
    for (let i = 1; i < 7; i++) {
      ordLine += ` L ${xScale(i)} ${yScale(week[i].ordP50)}`;
    }

    const normalCap = this.data.capacity.ramp_su;
    const preparedCap = Math.max(...week.map(d => d.capacityPrepared));
    const normalCapY = yScale(normalCap);
    const gameIdx = Math.max(0, this.data.days.findIndex(d => d.date === this.data.meta.game_day));
    const preparedCapY = yScale(preparedCap);

    // SVG Generation
    let svg = `
      <svg viewBox="0 0 ${width} ${height}" class="forecast-svg" aria-label="Ramp demand forecast chart showing P10 to P90 band against normal and prepared capacity">
        <defs>
          <linearGradient id="bandGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#3b82f6" stop-opacity="0.28" />
            <stop offset="100%" stop-color="#3b82f6" stop-opacity="0.08" />
          </linearGradient>
        </defs>

        <!-- Y Axis Gridlines -->
        ${[0, 5, 10, 15, 20, 25, 30].filter(v => v <= maxVal).map(v => `
          <line x1="${padding.left}" y1="${yScale(v)}" x2="${padding.left + chartW}" y2="${yScale(v)}" stroke="#e2e8f0" stroke-dasharray="3 3" />
          <text x="${padding.left - 10}" y="${yScale(v) + 4}" text-anchor="end" class="chart-axis-label">${v} su</text>
        `).join('')}

        <!-- P10 - P90 Uncertainty Range Band -->
        <path d="${bandPath}" fill="url(#bandGrad)" />

        <!-- Ordinary Week Baseline (Dashed Slate) -->
        <path d="${ordLine}" fill="none" stroke="#64748b" stroke-width="2" stroke-dasharray="4 4" />

        <!-- Capacity Line: Normal Ramp (from data) -->
        <line x1="${padding.left}" y1="${normalCapY}" x2="${padding.left + chartW}" y2="${normalCapY}" stroke="#ef4444" stroke-width="2.5" />
        <text x="${padding.left + chartW + 8}" y="${normalCapY + 4}" fill="#ef4444" font-weight="bold" font-size="12">${normalCap} su (Normal Ramp)</text>

        <!-- Capacity Line: Prepared Capacity with Plan (from data) -->
        <line x1="${padding.left}" y1="${preparedCapY}" x2="${padding.left + chartW}" y2="${preparedCapY}" stroke="#10b981" stroke-width="2.5" stroke-dasharray="5 3" />
        <text x="${padding.left + chartW + 8}" y="${preparedCapY + 4}" fill="#10b981" font-weight="bold" font-size="12">${preparedCap.toFixed(1)} su (Prepared)</text>

        <!-- P50 Forecast Line (Solid Bold Royal Blue) -->
        <path d="${p50Line}" fill="none" stroke="#2563eb" stroke-width="3" />

        <!-- Super Bowl game-day marker (date from data.meta.game_day) -->
        <line x1="${xScale(gameIdx)}" y1="${padding.top}" x2="${xScale(gameIdx)}" y2="${padding.top + chartH}" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="4 2" />
        <rect x="${xScale(gameIdx) - 38}" y="${padding.top - 20}" width="76" height="18" rx="4" fill="#fef3c7" stroke="#f59e0b" />
        <text x="${xScale(gameIdx)}" y="${padding.top - 7}" text-anchor="middle" font-size="10" font-weight="bold" fill="#b45309">🏆 GAME DAY</text>

        <!-- Data Points & X Axis Labels -->
        ${week.map((d, i) => {
          const x = xScale(i);
          const y = yScale(d.p50);
          const isOver = d.p50 > this.data.capacity.ramp_su;
          return `
            <g class="chart-point-group" tabindex="0" role="button" aria-label="${d.weekday} ${d.date}: P50 demand ${d.p50} space units, ${(d.probOverNormal * 100).toFixed(0)}% chance over capacity">
              <!-- Point circle -->
              <circle cx="${x}" cy="${y}" r="5" fill="${isOver ? '#ef4444' : '#2563eb'}" stroke="#ffffff" stroke-width="2" />
              <!-- P50 Value label -->
              <text x="${x}" y="${y - 9}" text-anchor="middle" font-size="11" font-weight="bold" fill="${isOver ? '#b91c1c' : '#1e3a8a'}">${d.p50.toFixed(1)}</text>
              <!-- X Axis Day Label -->
              <text x="${x}" y="${padding.top + chartH + 18}" text-anchor="middle" font-size="12" font-weight="${d.isGameDay ? 'bold' : 'normal'}" fill="#334155">${d.weekday.slice(0, 3)} ${d.date.slice(8)}</text>
              <text x="${x}" y="${padding.top + chartH + 32}" text-anchor="middle" font-size="10" fill="${d.probOverNormal > 0.5 ? '#dc2626' : '#64748b'}">${(d.probOverNormal * 100).toFixed(0)}% over</text>
            </g>
          `;
        }).join('')}
      </svg>
    `;

    container.innerHTML = svg;
  }

  // Render Accessible 7-Day Data Table with explicit formulas
  renderDataTable() {
    const tbody = document.getElementById('data-table-body');
    if (!tbody) return;

    const week = this.simEngine.getWeekSummary();
    const normalCap = this.data.capacity.ramp_su;

    tbody.innerHTML = week.map(d => {
      const utilPct = ((d.p50 / normalCap) * 100).toFixed(1);
      const probPct = (d.probOverNormal * 100).toFixed(1);
      const riskClass = d.riskLevel === 'High' ? 'badge-risk-high' : (d.riskLevel === 'Medium' ? 'badge-risk-med' : 'badge-risk-low');
      const eventBadge = d.isGameDay ? '<span class="badge-game">Super Bowl LXI</span>' : (d.isPresidentsDay ? '<span class="badge-holiday">Presidents\' Day</span>' : '');

      return `
        <tr>
          <td><strong>${d.weekday}</strong><br><span class="text-muted">${d.date}</span> ${eventBadge}</td>
          <td class="num">${d.arrivalsP50.toFixed(1)}</td>
          <td class="num">${d.departuresP50.toFixed(1)}</td>
          <td class="num text-muted">${d.p10.toFixed(1)}</td>
          <td class="num"><strong>${d.p50.toFixed(1)}</strong></td>
          <td class="num text-muted">${d.p90.toFixed(1)}</td>
          <td class="num">${normalCap.toFixed(1)} su</td>
          <td class="num"><strong>${probPct}%</strong></td>
          <td><span class="badge-risk ${riskClass}">${d.riskLevel}</span></td>
          <td class="formula-cell">
            <code>Util: ${d.p50.toFixed(1)} / ${normalCap.toFixed(1)} = ${utilPct}%</code>
            ${d.p50 > normalCap ? `<br><span class="critical-text">+${(d.p50 - normalCap).toFixed(1)} su over cap</span>` : ''}
          </td>
        </tr>
      `;
    }).join('');
  }

  // Render AI Preparation Plan details & approval card
  renderPlanDetails() {
    const plan = this.simEngine.getCurrentPlan();
    if (!plan) return;

    const planCostEl = document.getElementById('plan-cost-display');
    if (planCostEl) {
      planCostEl.textContent = plan.plan_cost_usd === 0 ? '$0 (No cash lease required)' : `$${plan.plan_cost_usd.toLocaleString()} USD`;
    }

    const payoffEl = document.getElementById('plan-payoff-display');
    if (payoffEl) {
      payoffEl.textContent = `${(plan.prob_plan_pays_off * 100).toFixed(1)}% chance plan pays off`;
    }

    // Action cards follow the selected plan (the lease size and cost change with the situation and scenario)
    for (const id of ['tow_packing', 'overflow_apron']) {
      const a = plan.actions.find(x => x.id === id);
      const set = (attr, html) => document.querySelectorAll(`[${attr}="${id}"]`).forEach(e => { e.innerHTML = html; });
      if (!a) {
        set('data-action-meta', 'Not in the model plan for this scenario and situation.');
        set('data-action-desc', '');
        continue;
      }
      set('data-action-title', escapeHtml(a.action));
      set('data-action-meta', `Cost: <strong>$${a.cost_usd.toLocaleString()}</strong> &bull; ${a.dates.length} day(s)`);
      set('data-action-desc', `${escapeHtml(a.rationale)}. Approver: <strong>${escapeHtml(a.approver)}</strong>`);
    }

    const unaccEl = document.getElementById('plan-unaccommodated-display');
    if (unaccEl) {
      unaccEl.textContent = `${plan.aircraft_not_accommodated_mean.no_plan} jets without plan → ${plan.aircraft_not_accommodated_mean.with_plan} with plan`;
    }
  }

  // ==========================================
  // SECTION 2: WEEK TIMELINE STRIP UNDER SCENE
  // ==========================================

  renderWeekTimelineStrip() {
    const container = document.getElementById('week-timeline-strip');
    if (!container) return;

    const week = this.simEngine.getWeekSummary();

    container.innerHTML = week.map((d, idx) => {
      const probPct = (d.probOverNormal * 100).toFixed(1);
      // Color-coding based on model's chance of exceeding the ramp
      let riskTier = 'tier-low'; // Green
      if (d.probOverNormal >= 0.7) {
        riskTier = 'tier-high'; // Red
      } else if (d.probOverNormal >= 0.3) {
        riskTier = 'tier-med';  // Amber
      }

      const eventTag = d.isGameDay ? '🏆 GAME' : (d.isPresidentsDay ? 'HOLIDAY' : '');

      return `
        <button class="timeline-day-card ${riskTier}" data-day-index="${idx}" aria-label="Jump to ${d.weekday} ${d.date}, ${probPct}% chance of exceeding ramp">
          <div class="day-card-header">
            <span class="day-name">${d.weekday.slice(0, 3)}</span>
            <span class="day-num">${d.date.slice(8)}</span>
            ${eventTag ? `<span class="day-event-tag">${eventTag}</span>` : ''}
          </div>
          <div class="day-prob-badge">${probPct}% over</div>
          <div class="day-demand-bar-wrap">
            <div class="day-demand-fill" style="width: ${Math.min(100, (d.p50 / (this.data.capacity.ramp_su * 1.5)) * 100)}%;"></div>
          </div>
          <div class="day-card-stats">
            <span>P50: ${d.p50.toFixed(1)} su</span>
            <span>Cap: ${this.data.capacity.ramp_su} su</span>
          </div>
        </button>
      `;
    }).join('');

    // Attach click listeners to jump simulation time
    container.querySelectorAll('.timeline-day-card').forEach(btn => {
      btn.addEventListener('click', () => {
        const dayIdx = parseInt(btn.dataset.dayIndex, 10);
        // Jump simulation to 09:00 on clicked day
        this.simSeconds = dayIdx * 86400 + 9 * 3600;
        this.updateSimulationViews();
      });
    });
  }

  // ==========================================
  // AIRCRAFT INSPECTION DRAWER
  // ==========================================

  onAircraftSelected(flight) {
    this.selectedAircraft = flight;
    this.updateAircraftInspector(flight);
  }

  updateAircraftInspector(flight) {
    const card = document.getElementById('aircraft-inspector-card');
    if (!card) return;

    if (!flight) {
      card.style.display = 'none';
      return;
    }

    card.style.display = 'block';

    const locationLabels = {
      main_ramp: `Parked on Main Ramp (${this.data.capacity.ramp_su} su capacity)`,
      overflow_apron: 'Parked on Remote Overflow Apron (Leased)',
      manager_decision_area: '⚠️ Holding Area: Awaiting Manager Decision'
    };

    const isHolding = flight.location === 'manager_decision_area';

    card.innerHTML = `
      <div class="inspector-header">
        <div>
          <span class="inspector-tail">${flight.tail}</span>
          <span class="inspector-badge ${isHolding ? 'critical' : 'ok'}">${flight.su} su &bull; ${flight.type.toUpperCase()}</span>
        </div>
        <button id="btn-close-inspector" class="btn-close-card" aria-label="Close inspector">&times;</button>
      </div>

      <div class="inspector-body">
        <div class="inspector-row">
          <span class="text-muted">Aircraft Model:</span>
          <strong>${flight.modelName}</strong>
        </div>
        <div class="inspector-row">
          <span class="text-muted">Stand Location:</span>
          <strong>${flight.standId || 'En route'} (${locationLabels[flight.location] || flight.location})</strong>
        </div>
        <div class="inspector-row">
          <span class="text-muted">Stay Duration:</span>
          <span>${flight.isCarry ? 'Carried over: stands for the model\'s daily ramp stock, not a forecast arrival' : `${flight.dwellHours} hrs (${flight.stayType})`}</span>
        </div>
        <div class="inspector-row">
          <span class="text-muted">Arrival & Departure:</span>
          <span>Arr: ${(flight.arrivalTime / 3600).toFixed(1)}h &bull; Dep: ${(flight.departureTime / 3600).toFixed(1)}h</span>
        </div>

        ${isHolding ? `
          <div class="inspector-alert">
            <strong>Rule: Overflow aircraft wait for manager decision and are NEVER refused.</strong><br>
            Main ramp is at capacity. This aircraft is waiting for manager assignment or overflow apron lease approval.
          </div>
        ` : `
          <div class="inspector-note text-muted">
            Generated illustration seeded reproducibly from daily totals and hourly profile.
          </div>
        `}
      </div>
    `;

    document.getElementById('btn-close-inspector')?.addEventListener('click', () => {
      this.selectedAircraft = null;
      if (this.ramp3d) {
        this.ramp3d.selectedFlightId = null;
      }
      card.style.display = 'none';
    });
  }
}

// Bootstrap on DOM loaded
window.addEventListener('DOMContentLoaded', () => {
  const app = new FBOApp();
  app.init();
});

function escapeHtml(v) {
  return String(v).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
