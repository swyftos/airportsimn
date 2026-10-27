// Pure model checks. Run with Node; no local server or browser required.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { buildIllustration, HOURS, restrictionAt, getDefaultView, securityPausedAt, getFlowPlan, getImpactGrid, getView } from './model.js';
import { createLayout, buildPlacements, standIntervals } from './layout.js';
const data = JSON.parse(fs.readFileSync(new URL('./parking_data.json', import.meta.url), 'utf8'));
const lightSu = Math.min(...Object.values(data.aircraft.sizes).map(size => size.su));
const largestSu = Math.max(...Object.values(data.aircraft.sizes).map(size => size.su));
let cases = 0, framesChecked = 0, maxPeakError = 0, maxWaitingError = 0, towEvents = 0, remoteTowEvents = 0;
const near = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-6, `${actual} != ${expected}`);

const defaultScenario = data.default_scenario;

for (const situation of Object.keys(data.situations)) for (const scenario of Object.keys(data.scenarios)) {
  const snapshots = buildIllustration(data, situation, scenario);
  assert.deepEqual(snapshots, buildIllustration(data, situation, scenario), 'Reproducible airframes and hourly totals');
  const layout = createLayout(data, snapshots);
  assert.ok(layout.stands.every(stand => [stand.x, stand.z, stand.width, stand.depth].every(Number.isFinite)));
  for (const [area, capacity] of Object.entries({ ramp: data.capacity.ramp_su, packed: data.capacity.ramp_su * data.capacity.tow_packing_gain, remote: data.capacity.overflow_apron_su })) {
    near(layout.areas[area].capacitySu, capacity);
    near(layout.stands.filter(stand => stand.area === area && !stand.flex).reduce((sum, stand) => sum + stand.su, 0), capacity);
    assert.ok(layout.stands.filter(stand => stand.area === area).length >= Math.floor(capacity / lightSu), 'Flex positions can illustrate every all-light fleet within the shared budget');
  }
  const registry = new Map();
  for (const snapshot of snapshots) for (const plane of snapshot.fleet) {
    assert.match(plane.id, /^FBO-\d+$/);
    if (registry.has(plane.id)) assert.deepEqual(plane, registry.get(plane.id), 'Identity and size persist across days');
    registry.set(plane.id, plane);
  }
  for (const [dayIndex, info] of data.days.entries()) {
    const hours = snapshots.slice(dayIndex * HOURS, (dayIndex + 1) * HOURS);
    const model = data.parking[situation].days[scenario][info.date];
    const rampData = data.ramp_aircraft.by_situation[situation][scenario][info.date];

    // Rule B: At each day's busiest hour (max of hour.used) the 3D world, stand map and register show
    // exactly round(at_peak_p50[size]) aircraft of each size.
    // Checked for every situation on the forecast scenario (Medium).
    // If an exact match is impossible on a day (e.g. 24h delay on Game Day where zero departures occurred),
    // list that day honestly rather than skipping assertions.
    if (scenario === defaultScenario) {
      const busiest = hours.reduce((a, f) => f.used > a.used ? f : a);
      const dayKey = `${situation}/${info.date}`;
      const impossibleDays = ['departure_delay_24h/2027-02-14'];
      if (impossibleDays.includes(dayKey)) {
        const actualCount = busiest.fleet.length;
        const medianCount = Math.round(data.ramp_aircraft.by_situation[situation][scenario][info.date].aircraft_at_peak_p50);
        assert.ok(Math.abs(actualCount - medianCount) <= 1, `${dayKey}: on the ramp at peak ${actualCount}, model median ${medianCount}`);
      } else {
        for (const [sizeName] of Object.entries(data.aircraft.sizes)) {
          assert.equal(busiest.fleet.filter(p => p.name === sizeName).length, Math.round(rampData.at_peak_p50[sizeName]),
            `${situation}/${scenario}/${info.date}: busiest hour ${sizeName} count must equal rounded model value`);
        }
      }
    }

    // Game day, Medium, normal: exactly 6 light + 4 midsize + 2 large = 12 aircraft
    if (situation === 'standard' && scenario === 'Medium' && info.date === data.meta.game_day) {
      const gameDayBusiest = hours.reduce((a, f) => f.used > a.used ? f : a);
      assert.equal(gameDayBusiest.fleet.filter(p => p.name === 'light').length, 6, 'Game day light count = 6');
      assert.equal(gameDayBusiest.fleet.filter(p => p.name === 'midsize').length, 4, 'Game day midsize count = 4');
      assert.equal(gameDayBusiest.fleet.filter(p => p.name === 'large').length, 2, 'Game day large count = 2');
      assert.equal(gameDayBusiest.fleet.length, 12, 'Game day total aircraft = 12');
    }

    // P50 anchoring check (within at most one light-jet su beyond rounding) and per-day arrivals/departures totals
    const error = Math.abs(Math.max(...hours.map(hour => hour.used)) - model.parking_demand_su_p50);
    const roundingLoss = Math.abs(Object.entries(rampData.at_peak_p50).reduce((sum, [s, c]) => sum + Math.round(c) * data.aircraft.sizes[s].su, 0) - model.parking_demand_su_p50);
    assert.ok(error <= lightSu + roundingLoss + 1e-6, `${situation}/${scenario}/${info.date}: P50 anchoring`);
    maxPeakError = Math.max(maxPeakError, error);
    near(hours.reduce((sum, hour) => sum + hour.arrivals, 0), Math.round(model.arrivals_p50));
    near(hours.reduce((sum, hour) => sum + hour.departures, 0), Math.round(model.departures_p50));

    const pause = restrictionAt(data, situation, info.date);
    for (const hour of hours) if (pause && hour.hour < pause.to && hour.hour + 1 > pause.from) {
      assert.equal(hour.arrivals + hour.departures, 0, 'No flow movements in the assumed pause');
    }
  }

  // Week opens with data.aircraft.opening_aircraft split by data.aircraft.sizes[*].share
  const openingSnap = snapshots[0];
  const openingTotal = Math.round(data.aircraft.opening_aircraft);
  const openingPlanes = openingSnap.fleet.filter(p => p.source === 'opening');
  assert.equal(openingPlanes.length, openingTotal, 'Week opens with rounded opening_aircraft count');

  const actions = data.parking[situation].plans[scenario].actions;
  const options = [{}, ...actions.map(action => ({ [action.id]: { choice: 'approved', name: 'Verification manager', note: 'Test fixture' } })),
    Object.fromEntries(actions.map(action => [action.id, { choice: 'approved', name: 'Verification manager', note: 'Test fixture' }])),
    Object.fromEntries(actions.map(action => [action.id, { choice: 'rejected', name: 'Verification manager', note: 'Test fixture' }])),
    Object.fromEntries(actions.map(action => [action.id, { choice: 'approved', name: '', note: '' }]))];
  for (const decisions of options) {
    const ledger = buildPlacements(data, situation, scenario, snapshots, layout, decisions);
    let previous = new Map();
    for (const frame of ledger) {
      framesChecked++;
      near(frame.placed.reduce((sum, plane) => sum + plane.su, 0), frame.used);
      assert.equal(new Set(frame.placed.map(plane => plane.id)).size, frame.placed.length);
      assert.equal(new Set(frame.placed.map(plane => plane.standId)).size, frame.placed.length, 'No stand has two aircraft');
      for (const plane of frame.placed) {
        const stand = frame.states.find(s => s.id === plane.standId);
        assert.ok(stand.su >= plane.su && stand.area === plane.area, 'Aircraft fits the reserved stand');
        const span = Number(data.aircraft.sizes[plane.name].example.match(/\(([\d.]+)\s*m/)?.[1]);
        near(span / stand.width, .7);
        near(plane.x, stand.x); near(plane.z, stand.z);
        const bounds = layout.areas[stand.area];
        assert.ok(stand.x - stand.width / 2 >= bounds.x && stand.x + stand.width / 2 <= bounds.x + bounds.width
          && stand.z - stand.depth / 2 >= bounds.z && stand.z + stand.depth / 2 <= bounds.z + bounds.depth, 'Aircraft envelope remains inside its area');
        const last = previous.get(plane.id), tow = frame.movements.find(m => m.type === 'tow' && m.plane.id === plane.id);
        assert.equal(!!tow, !!last && last.standId !== plane.standId, 'Every reposition is illustrated by a tow, and unchanged stands do not tow');
        if (tow) assert.deepEqual(tow.from, last, 'Tow starts from the previous illustrated position');
      }
      const occupied = frame.states.filter(stand => stand.plane);
      occupied.forEach((a, index) => occupied.slice(index + 1).forEach(b => assert.ok(
        Math.abs(a.x - b.x) >= (a.width + b.width) / 2 || Math.abs(a.z - b.z) >= (a.depth + b.depth) / 2,
        `${a.id}/${b.id}: parked aircraft envelopes cannot overlap`)));
      for (const area of ['ramp', 'packed', 'remote']) assert.ok(frame.sums[area] <= frame.capacity[area] + 1e-6, 'No capacity over-allocation');
      const unavoidableWait = Math.max(0, frame.used - frame.capacity.total);
      const waitingError = frame.sums.waiting - unavoidableWait;
      maxWaitingError = Math.max(maxWaitingError, waitingError);
      assert.ok(waitingError >= -1e-6 && waitingError < largestSu + 1e-6,
        `${situation}/${scenario}/${data.days[frame.dayIndex].date}/${frame.hour}: waiting ${frame.sums.waiting} su must match demand above approved space ${unavoidableWait} su within one aircraft`);
      if (frame.used <= frame.capacity.total + 1e-6) assert.equal(frame.sums.waiting, 0,
        `${situation}/${scenario}/${data.days[frame.dayIndex].date}/${frame.hour}: no waiting when demand ${frame.used} su fits approved space ${frame.capacity.total} su`);
      for (const [area, actionId] of [['packed', 'tow_packing'], ['remote', 'overflow_apron']]) {
        const record = decisions[actionId];
        const approved = record?.choice === 'approved' && record.name && record.note && actions.find(a => a.id === actionId)?.dates.includes(data.days[frame.dayIndex].date);
        if (!approved) assert.equal(frame.sums[area], 0, 'Unapproved or out-of-date action cannot supply space');
      }
      towEvents += frame.movements.filter(m => m.type === 'tow').length;
      remoteTowEvents += frame.movements.filter(m => m.type === 'tow' && m.from.area === 'ramp' && m.plane.area === 'remote').length;
      assert.equal(frame.states.filter(s => s.plane).length, frame.placed.length, 'Map and ledger agree');
      previous = new Map(frame.placed.map(plane => [plane.id, plane]));
    }
    for (let dayIndex = 0; dayIndex < data.days.length; dayIndex++) {
      const intervals = standIntervals(ledger, dayIndex, HOURS);
      for (const frame of ledger.slice(dayIndex * HOURS, (dayIndex + 1) * HOURS)) {
        const bars = intervals.filter(bar => bar.from <= frame.hour && bar.to > frame.hour);
        assert.deepEqual(bars.map(bar => `${bar.standId}/${bar.id}`).sort(), frame.placed.map(p => `${p.standId}/${p.id}`).sort(), 'Every timeline bar matches its hourly stand assignment');
      }
    }
  }
  cases++;
}

// Check homogeneous fleets fit shared budget
const situation = Object.keys(data.situations)[0], scenario = data.default_scenario;
const fixtureLayout = createLayout(data, []);
for (const [name, size] of Object.entries(data.aircraft.sizes)) {
  const fleet = Array.from({ length: Math.floor(data.capacity.ramp_su / size.su) }, (_, index) => ({
    id: `FBO-${String(index + 1).padStart(3, '0')}`, name, su: size.su, source: 'carry-over', born: -1, due: Infinity
  }));
  const snapshot = { dayIndex: 0, hour: 0, tick: 0, fleet, used: fleet.length * size.su, arrivals: 0, departures: 0, departing: [] };
  const [frame, next] = buildPlacements(data, situation, scenario, [snapshot, { ...snapshot, hour: 1, tick: 1 }], fixtureLayout, {});
  assert.equal(frame.sums.waiting, 0, `${name}: every fleet that fits the shared budget gets a flex position`);
  assert.equal(next.movements.length, 0, 'Unchanged aircraft keep their positions between frames');
}
assert.ok(towEvents > 0 && remoteTowEvents > 0, 'Approved plans include visible repositioning and ramp-to-overflow tows');
console.log(`PASS: ${cases} scenario/situation combinations; ${framesChecked} approval/hour frames; maximum daily peak error ${maxPeakError.toFixed(2)} su; maximum waiting error ${maxWaitingError.toFixed(2)} su; no under-capacity waiting; per-size peak counts, shared budgets, non-overlap, identity, tows, approvals, pause and timeline checks passed.`);

// V3 situations: preserve all preceding assertions and verify the new data-driven views.
const defaults = getDefaultView(data);
assert.deepEqual(defaults, { scenario: data.default_scenario, situation: data.situation_outlook.base_case });
const html = fs.readFileSync(new URL('./index.html', import.meta.url), 'utf8');
const app = fs.readFileSync(new URL('./app.js', import.meta.url), 'utf8');
assert.ok(app.includes('Object.assign(state, getDefaultView(data))'), 'App starts and returns to the model default');
assert.doesNotMatch(html, /<select[^>]+id=["'](?:situation|scenario)["']/i, 'No scenario or situation selectors');
for (const hook of ['scrub', 'play', 'speed', 'stand-register', 'inspector-content', 'scene', 'whatif-banner', 'whatif-back-btn']) {
  assert.ok(html.includes(`id="${hook}"`), `Retain ${hook}`);
}
let flowRowsChecked = 0, pauseMovementsChecked = 0;
for (const situation of Object.keys(data.situations)) for (const scenario of Object.keys(data.scenarios)) {
  const flow = getFlowPlan(data, situation, scenario);
  assert.equal(flow.rows.length, data.days.length);
  const plan = data.parking[situation].plans[scenario];
  for (const row of flow.rows) {
    const ramp = data.ramp_aircraft.by_situation[situation][scenario][row.date];
    for (const [field, source] of [['arrivals', 'arrivals_p50'], ['departures', 'departures_p50'], ['at_peak', 'at_peak_p50']]) {
      for (const size of Object.keys(data.aircraft.sizes)) assert.equal(row[field][size], Math.round(ramp[source][size]), `${situation}/${scenario}/${row.date}/${field}/${size}`);
      assert.equal(row[field].total, Object.keys(data.aircraft.sizes).reduce((sum, size) => sum + Math.round(ramp[source][size]), 0));
    }
    assert.equal(row.risk_level, data.parking[situation].days[scenario][row.date].risk_level);
    assert.deepEqual(row.activePlanActions, plan.actions.filter(action => action.dates.includes(row.date)));
    for (const lever of row.activeLevers) assert.ok(data.levers.by_scenario[scenario].recommended.includes(lever));
    const offer = data.levers.by_scenario[scenario].recommended.find(lever => lever.id === 'drop_and_go_offer');
    if (offer) assert.equal(row.activeLevers.includes(offer), ['Thursday', 'Friday', 'Saturday', 'Sunday'].includes(row.weekday), 'Offer follows its supplied Thu-Sun range');
    const pause = restrictionAt(data, situation, row.date);
    assert.equal(row.pauseInstruction, pause ? `Land arrivals before ${pause.start}; staff the departure wave after ${pause.end}` : null);
    flowRowsChecked++;
  }
  const grid = getImpactGrid(data, situation, scenario);
  const cells = grid.flatMap(row => row.cells);
  assert.equal(cells.filter(cell => cell.isModelCall).length, 1);
  assert.equal(cells.filter(cell => cell.isActive).length, 1);
  for (const cell of cells) {
    const expected = getView(data, cell.situation, cell.scenario);
    assert.equal(cell.peak_su, expected.peak.parking_demand_su_p50);
    assert.equal(cell.peak_date, expected.peak.date);
    assert.equal(cell.days_over_ramp, expected.days.filter(day => day.parking_demand_su_p50 > data.capacity.ramp_su).length);
    assert.equal(cell.plan_cost_usd, expected.plan.plan_cost_usd);
    assert.deepEqual(cell.unaccommodated, expected.plan.aircraft_not_accommodated_mean);
  }
  if (situation === defaults.situation) {
    const snapshots = buildIllustration(data, situation, scenario);
    const actions = Object.fromEntries(plan.actions.map(action => [action.id, { choice: 'approved', name: 'Verification manager' }]));
    for (const decisions of [{}, actions]) {
      const ledger = buildPlacements(data, situation, scenario, snapshots, createLayout(data, snapshots), decisions);
      for (const frame of ledger) {
        const date = data.days[frame.dayIndex].date, pause = restrictionAt(data, situation, date);
        if (!pause) continue;
        for (const movement of frame.movements) {
          const duration = { arrival: 4, departure: 5, tow: 3 }[movement.type];
          if (!duration) continue;
          const from = frame.hour + movement.minute / 60, to = from + duration / 60;
          assert.ok(to <= pause.from || from >= pause.to, 'No taxi, pushback or tow overlaps the security pause');
          if (movement.type === 'arrival') assert.ok(to <= pause.from, 'Pause-day arrivals finish before restriction');
          pauseMovementsChecked++;
        }
      }
    }
  }
}
for (const item of data.situation_outlook.items.filter(item => item.window)) for (const date of item.dates) {
  const pause = restrictionAt(data, item.situation, date);
  assert.equal(pause.start, item.window[0]); assert.equal(pause.end, item.window[1]);
  assert.equal(securityPausedAt(data, item.situation, date, pause.from - 1 / 60), false);
  assert.equal(securityPausedAt(data, item.situation, date, pause.from), true);
  assert.equal(securityPausedAt(data, item.situation, date, pause.to - 1 / 60), true);
  assert.equal(securityPausedAt(data, item.situation, date, pause.to), false);
}
const shifted = structuredClone(data);
const security = shifted.situation_outlook.items.find(item => item.window);
security.dates = [data.days[0].date]; security.window = ['15:15', '21:15'];
assert.equal(restrictionAt(shifted, security.situation, security.dates[0]).from, 15.25, 'Window and date come from outlook data');
assert.equal(restrictionAt(shifted, security.situation, data.meta.game_day), null);
console.log(`PASS: model default, impact cells, ${flowRowsChecked} exact flow rows, ${pauseMovementsChecked} movement intervals, pause boundaries and offer dates.`);
for (const situation of Object.keys(data.situations)) {
  const snapshots = buildIllustration(data, situation, defaults.scenario);
  data.days.forEach((day, index) => {
    const peak = snapshots.slice(index * HOURS, (index + 1) * HOURS).reduce((a, b) => b.used > a.used ? b : a);
    const medians = data.ramp_aircraft.by_situation[situation][defaults.scenario][day.date].at_peak_p50;
    const mismatch = Object.keys(medians).some(size => peak.fleet.filter(plane => plane.name === size).length !== Math.round(medians[size]));
    if (mismatch) console.log(`Independent-median discrepancy: ${situation}/${day.date}, illustrated ${peak.fleet.length}, rounded size medians ${Object.values(medians).reduce((sum, n) => sum + Math.round(n), 0)} (shown in overlay).`);
  });
}
