// Pure model checks. Run with Node; no local server or browser required.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { buildIllustration, HOURS, restrictionAt } from './model.js';
import { createLayout, buildPlacements, standIntervals } from './layout.js';
const data = JSON.parse(fs.readFileSync(new URL('./parking_data.json', import.meta.url), 'utf8'));
const lightSu = Math.min(...Object.values(data.aircraft.sizes).map(size => size.su));
const largestSu = Math.max(...Object.values(data.aircraft.sizes).map(size => size.su));
let cases = 0, framesChecked = 0, maxPeakError = 0, maxWaitingError = 0, towEvents = 0, remoteTowEvents = 0;
const near = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-6, `${actual} != ${expected}`);
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
    const error = Math.abs(Math.max(...hours.map(hour => hour.used)) - model.parking_demand_su_p50);
    assert.ok(error <= lightSu, `${situation}/${scenario}/${info.date}: P50 anchoring`);
    maxPeakError = Math.max(maxPeakError, error);
    near(hours.reduce((sum, hour) => sum + hour.arrivals, 0), Math.round(model.arrivals_p50));
    near(hours.reduce((sum, hour) => sum + hour.departures, 0), Math.round(model.departures_p50));
    const pause = restrictionAt(data, situation, info.date);
    for (const hour of hours) if (pause && hour.hour < pause.to && hour.hour + 1 > pause.from) {
      assert.equal(hour.arrivals + hour.departures, 0, 'No flow movements in the assumed pause');
    }
  }
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
// A changing assumed mix must not turn the estimate into a fixed stand-class
// limit: each homogeneous fleet that fits the ramp's su budget also fits the map.
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
console.log(`PASS: ${cases} scenario/situation combinations; ${framesChecked} approval/hour frames; maximum daily peak error ${maxPeakError.toFixed(2)} su; maximum waiting error ${maxWaitingError.toFixed(2)} su; no under-capacity waiting; shared budgets, non-overlap, identity, tows, approvals, pause and timeline checks passed.`);
