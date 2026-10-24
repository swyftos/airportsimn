// Shared geometry and occupancy ledger for every illustration; no Three.js dependency.
export const AREA_LABELS = { ramp: 'Main ramp', packed: 'Tow-in packing', remote: 'Overflow apron', waiting: 'Manager decision' };
export const STATE_LABELS = { free: 'Free', occupied: 'Occupied', packed: 'Packed', overflow: 'Overflow', waiting: 'Waiting' };
const epsilon = 1e-6;

function standSizes(data, capacity) {
  const sizes = Object.entries(data.aircraft.sizes).sort((a, b) => a[1].su - b[1].su);
  const mean = sizes.reduce((sum, [, size]) => sum + size.su * size.share, 0);
  const count = Math.max(1, Math.round(capacity / mean));
  const counts = Object.fromEntries(sizes.map(([key]) => [key, 0]));
  const result = [];
  // Do not strand fractional su: a packing gain may exactly fit a midsize
  // stand even when the most common class is light.
  const memo = new Map();
  const canFill = value => {
    if (Math.abs(value) < epsilon) return true;
    if (value < sizes[0][1].su - epsilon) return false;
    const key = value.toFixed(6);
    if (!memo.has(key)) memo.set(key, sizes.some(([, size]) => size.su <= value + epsilon && canFill(value - size.su)));
    return memo.get(key);
  };
  let remaining = capacity;
  while (remaining + epsilon >= sizes[0][1].su) {
    const possible = sizes.filter(([, size]) => size.su <= remaining + epsilon && canFill(remaining - size.su))
      .sort((a, b) => (count * b[1].share - counts[b[0]]) - (count * a[1].share - counts[a[0]]));
    if (!possible.length) break;
    const [name, size] = possible[0];
    result.push({ name, su: size.su }); counts[name]++; remaining -= size.su;
  }
  return result;
}

export function createLayout(data, snapshots) {
  // The example span is the only dimensional aircraft value in the source.
  const light = Object.values(data.aircraft.sizes).reduce((a, b) => a.su < b.su ? a : b);
  const lightSpan = Number(light.example.match(/\(([\d.]+)\s*m/)?.[1]);
  const unit = lightSpan / .7; // illustrative clearance, not an operational measurement
  const largest = Object.values(data.aircraft.sizes).reduce((a, b) => a.su > b.su ? a : b);
  const spanFor = name => Number(data.aircraft.sizes[name].example.match(/\(([\d.]+)\s*m/)?.[1]);
  const bayFor = name => spanFor(name) / .7;
  const budgets = { ramp: data.capacity.ramp_su, packed: data.capacity.ramp_su * data.capacity.tow_packing_gain, remote: data.capacity.overflow_apron_su };
  const flexPositions = capacity => {
    const nominal = standSizes(data, capacity);
    // The assumed mix gives the nominal layout; additional marshaller positions
    // allow a lighter fleet. Positions share one area budget, not additive su.
    while (nominal.length < Math.floor((capacity + epsilon) / light.su)) nominal.push({ name: Object.keys(data.aircraft.sizes).find(name => data.aircraft.sizes[name] === light), su: light.su, flex: true });
    return nominal;
  };
  const groups = {
    ramp: flexPositions(budgets.ramp),
    packed: flexPositions(budgets.packed),
    remote: flexPositions(budgets.remote),
    // Waiting positions are unconstrained holding illustrations, not capacity.
    waiting: Array.from({ length: Math.ceil(Math.max(...Object.values(data.parking).flatMap(situation => Object.values(situation.days).flatMap(days => Object.values(days).map(day => day.parking_demand_su_p50)))) / light.su) }, () => {
      const [name, size] = Object.entries(data.aircraft.sizes).reduce((a, b) => a[1].su > b[1].su ? a : b);
      return { name, su: size.su };
    })
  };
  const stands = [], areas = {};
  const prefixes = { ramp: 'R', packed: 'P', remote: 'O', waiting: 'W' };
  for (const [area, sizes] of Object.entries(groups)) {
    const columns = Math.ceil(Math.sqrt(sizes.length));
    let z = 0, maxWidth = 0;
    for (let row = 0; row < Math.ceil(sizes.length / columns); row++) {
      const entries = sizes.slice(row * columns, (row + 1) * columns);
      // Centers have room for any class; the current aircraft determines its
      // painted envelope. Flex geometry never invents more approved capacity.
      const cell = Math.max(...Object.keys(data.aircraft.sizes).map(bayFor)) * 1.08;
      const rowDepth = cell;
      let x = 0;
      entries.forEach((size, column) => {
        const width = bayFor(size.name), depth = width;
        stands.push({ ...size, area, id: `${prefixes[area]}-${String(row * columns + column + 1).padStart(2, '0')}`,
          x: x + cell / 2, z: z + rowDepth / 2, width, depth, maxSu: largest.su });
        x += cell;
      });
      maxWidth = Math.max(maxWidth, x); z += rowDepth + unit * .35;
    }
    areas[area] = { x: 0, z: 0, width: maxWidth + unit * .5, depth: z + unit * .3, capacitySu: budgets[area] ?? Infinity };
  }
  const gap = unit * 1.7;
  areas.packed.x = areas.ramp.width + unit * .3;
  areas.remote.x = areas.packed.x + areas.packed.width + gap;
  areas.waiting.z = Math.max(areas.ramp.depth, areas.packed.depth) + gap;
  for (const stand of stands) {
    stand.x += areas[stand.area].x + unit * .25;
    stand.z += areas[stand.area].z + unit * .25;
  }
  const width = areas.remote.x + areas.remote.width;
  const depth = Math.max(areas.remote.depth, areas.waiting.z + areas.waiting.depth);
  const laneZ = -unit * .65;
  return { stands, areas, unit, width, depth, laneZ, bayWidths: Object.fromEntries(Object.keys(data.aircraft.sizes).map(name => [name, bayFor(name)])),
    entry: { x: -unit * 2, z: laneZ }, exit: { x: width + unit * 1.5, z: laneZ },
    staging: { x: areas.packed.x, z: laneZ } };
}

export function approvedCapacity(data, situation, scenario, date, decisions) {
  const plan = data.parking[situation].plans[scenario];
  const approved = id => plan.actions.some(action => action.id === id && action.dates.includes(date)
    && decisions[id]?.choice === 'approved' && decisions[id]?.name?.trim() && decisions[id]?.note?.trim());
  const packed = approved('tow_packing') ? data.capacity.ramp_su * data.capacity.tow_packing_gain : 0;
  const record = data.parking[situation].days[scenario][date];
  const proposedPacked = data.capacity.ramp_su * (1 + data.capacity.tow_packing_gain);
  const remote = approved('overflow_apron') ? Math.min(data.capacity.overflow_apron_su, Math.max(0, record.capacity_prepared_su - proposedPacked)) : 0;
  return { ramp: data.capacity.ramp_su, packed, remote, total: data.capacity.ramp_su + packed + remote };
}

// Separate area budgets can strand fractions (for example a light jet in the
// packing position while a midsize waits). Search class counts, not identities,
// only when a whole light-aircraft footprint is being wasted. Among equally
// full arrangements, preserve the most existing area assignments.
function repackedCounts(data, placed, capacity) {
  const classes = Object.entries(data.aircraft.sizes).sort((a, b) => b[1].su - a[1].su);
  const areaNames = ['ramp', 'packed', 'remote', 'waiting'];
  const current = Object.fromEntries(areaNames.map(area => [area, classes.map(([name]) => placed.filter(p => p.area === area && p.name === name).length)]));
  const counts = classes.map((_, index) => areaNames.reduce((sum, area) => sum + current[area][index], 0));
  const load = numbers => numbers.reduce((sum, count, index) => sum + count * classes[index][1].su, 0);
  const areas = areaNames.filter(area => area !== 'waiting' && capacity[area] > 0).sort((a, b) => capacity[a] - capacity[b]);
  const zeros = () => classes.map(() => 0);
  let best = { used: -1, retained: -1, ramp: -1, allocation: null };
  function patterns(available, budget, fillLast, callback, index = 0, selected = []) {
    const maximum = Math.min(available[index], Math.floor((budget + epsilon) / classes[index][1].su));
    for (let count = maximum; count >= (fillLast && index === classes.length - 1 ? maximum : 0); count--) {
      const next = [...selected, count];
      if (index === classes.length - 1) callback(next);
      else patterns(available, budget - count * classes[index][1].su, fillLast, callback, index + 1, next);
    }
  }
  function search(index, available, allocation, used) {
    const possible = used + Math.min(load(available), areas.slice(index).reduce((sum, area) => sum + capacity[area], 0));
    if (possible + epsilon < best.used) return;
    if (index === areas.length) {
      const candidate = { ...allocation, waiting: available };
      const retained = areaNames.reduce((sum, area) => sum + classes.reduce((n, _, i) => n + Math.min(current[area][i], candidate[area]?.[i] || 0), 0), 0);
      const ramp = load(candidate.ramp || zeros());
      if (used > best.used + epsilon || Math.abs(used - best.used) < epsilon && (retained > best.retained || retained === best.retained && ramp > best.ramp)) {
        best = { used, retained, ramp, allocation: candidate };
      }
      return;
    }
    const area = areas[index];
    patterns(available, capacity[area], index === areas.length - 1, chosen => search(index + 1,
      available.map((count, i) => count - chosen[i]), { ...allocation, [area]: chosen }, used + load(chosen)));
  }
  search(0, counts, {}, 0);
  return Object.fromEntries(areaNames.map(area => [area, Object.fromEntries(classes.map(([name], index) => [name, best.allocation[area]?.[index] || 0]))]));
}

export function buildPlacements(data, situation, scenario, snapshots, layout, decisions) {
  let previous = new Map();
  return snapshots.map(snapshot => {
    const capacity = approvedCapacity(data, situation, scenario, data.days[snapshot.dayIndex].date, decisions);
    const remaining = { ...capacity, waiting: Infinity };
    const occupied = new Set(), placed = [], sums = { ramp: 0, packed: 0, remote: 0, waiting: 0 };
    const take = (plane, stand) => {
      remaining[stand.area] -= plane.su; sums[stand.area] += plane.su; occupied.add(stand.id);
      placed.push({ ...plane, standId: stand.id, area: stand.area, x: stand.x, z: stand.z,
        status: stand.area === 'ramp' ? 'occupied' : stand.area === 'remote' ? 'overflow' : stand.area });
    };
    const pending = [];
    // Retain a stand for as long as its airframe remains in the picture and the
    // approved capacity is valid. Scrubbing reconstructs this same ledger.
    // Waiting aircraft are not retained: each hour they are offered any stand that has freed up.
    for (const plane of snapshot.fleet) {
      const last = previous.get(plane.id);
      const stand = last && last.area !== 'waiting' && layout.stands.find(s => s.id === last.standId);
      if (stand && !occupied.has(stand.id) && remaining[stand.area] + epsilon >= plane.su) take(plane, stand);
      else pending.push(plane);
    }
    for (const plane of pending.sort((a, b) => b.su - a.su || a.id.localeCompare(b.id))) {
      const mainFits = layout.stands.some(s => s.area === 'ramp' && !occupied.has(s.id) && remaining.ramp + epsilon >= plane.su);
      // An arriving aircraft can illustrate the approved plan's mechanism:
      // tow an ongoing stay to the leased apron, then reserve the released bay.
      // This is a proposed route in the illustration, never an executed dispatch.
      if (!mainFits && plane.source === 'arrival' && plane.born === snapshot.tick && capacity.remote > 0) {
        const candidate = placed.find(p => p.area === 'ramp' && (p.source === 'carry-over' || p.due > snapshot.tick)
          && remaining.ramp + p.su + epsilon >= plane.su
          && layout.stands.some(s => s.area === 'remote' && !occupied.has(s.id) && remaining.remote + epsilon >= p.su));
        if (candidate) {
          const destination = layout.stands.find(s => s.area === 'remote' && !occupied.has(s.id));
          occupied.delete(candidate.standId); sums.ramp -= candidate.su; remaining.ramp += candidate.su;
          placed.splice(placed.indexOf(candidate), 1); take(candidate, destination);
        }
      }
      // A flex position can take any class. Its footprint changes with the
      // airframe, while the su debit always comes from the shared area budget.
      const stand = ['ramp', 'packed', 'remote', 'waiting'].flatMap(area => layout.stands
        .filter(s => s.area === area && !occupied.has(s.id) && remaining[area] + epsilon >= plane.su)
        .sort((a, b) => Math.abs(a.su - plane.su) - Math.abs(b.su - plane.su)))[0];
      if (!stand) throw new Error('Illustration has no decision-area position.');
      take(plane, stand);
    }
    const unused = capacity.total - sums.ramp - sums.packed - sums.remote;
    const smallest = Math.min(...Object.values(data.aircraft.sizes).map(size => size.su));
    if (sums.waiting > 0 && unused + epsilon >= smallest) {
      const desired = repackedCounts(data, placed, capacity);
      const candidates = [...placed], movers = [];
      placed.length = 0; occupied.clear();
      Object.assign(remaining, capacity, { waiting: Infinity });
      for (const area of Object.keys(sums)) sums[area] = 0;
      // Keep each usable stand, including stable waiting positions when the
      // exact search confirms they still cannot fit. Only actual changes tow.
      for (const plane of candidates) {
        if (desired[plane.area][plane.name] > 0) {
          desired[plane.area][plane.name]--;
          take(plane, layout.stands.find(s => s.id === plane.standId));
        } else movers.push(plane);
      }
      for (const plane of movers) {
        const area = ['ramp', 'packed', 'remote', 'waiting'].find(name => desired[name][plane.name] > 0);
        desired[area][plane.name]--;
        take(plane, layout.stands.find(s => s.area === area && !occupied.has(s.id)));
      }
    }
    const states = layout.stands.map(stand => {
      const plane = placed.find(p => p.standId === stand.id);
      return { ...stand, ...(plane ? { name: plane.name, su: plane.su, width: layout.bayWidths[plane.name], depth: layout.bayWidths[plane.name] } : {}), plane: plane || null, status: plane?.status || 'free',
        enabled: stand.area === 'ramp' || stand.area === 'waiting' || capacity[stand.area] > 0 };
    });
    const current = new Map(placed.map(plane => [plane.id, plane]));
    const movements = [];
    for (const plane of placed) {
      const last = previous.get(plane.id);
      if (!last) movements.push({ plane, type: plane.source === 'arrival' && plane.born === snapshot.tick ? 'arrival' : 'carry-in' });
      else if (last.standId !== plane.standId) movements.push({ plane, from: last, type: 'tow' });
    }
    for (const [id, plane] of previous) if (!current.has(id)) movements.push({ plane, type: snapshot.departing.includes(id) ? 'departure' : 'carry-out' });
    previous = current;
    return { ...snapshot, placed, states, movements, capacity, sums };
  });
}

export function standIntervals(placements, dayIndex, hours) {
  const intervals = [];
  for (const frame of placements.slice(dayIndex * hours, (dayIndex + 1) * hours)) {
    for (const plane of frame.placed) {
      const last = intervals.findLast(item => item.standId === plane.standId);
      if (last?.id === plane.id && last.to === frame.hour) last.to++;
      else intervals.push({ id: plane.id, standId: plane.standId, area: plane.area, from: frame.hour, to: frame.hour + 1 });
    }
  }
  return intervals;
}
