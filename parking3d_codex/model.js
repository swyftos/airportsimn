export const su = value => `${value.toFixed(1)} su`;
export const pct = value => `${Math.round(value * 100)}%`;
export const money = value => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value);

export function dateLabel(date, short = false) {
  const [year, month, day] = date.split('-').map(Number);
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'UTC', weekday: short ? 'short' : 'long', month: short ? undefined : 'short', day: 'numeric'
  }).format(new Date(Date.UTC(year, month - 1, day)));
}

export function getView(data, situation, scenario, prepared) {
  const records = data.parking[situation].days[scenario];
  const days = data.days.map(info => ({
    ...info,
    ...records[info.date],
    ordinary: data.ordinary_week[info.date],
    capacity: prepared ? records[info.date].capacity_prepared_su : records[info.date].capacity_normal_su,
    probability: prepared ? records[info.date].prob_over_prepared_capacity : records[info.date].prob_over_normal_capacity
  }));
  const aboveMedian = days.filter(day => day.parking_demand_su_p50 > day.capacity);
  const first = aboveMedian[0] ?? null;
  const worst = days.reduce((best, day) => day.probability > best.probability ? day : best);
  const peak = days.reduce((best, day) => day.parking_demand_su_p50 > best.parking_demand_su_p50 ? day : best);
  return { days, first, worst, peak, aboveMedian, plan: data.parking[situation].plans[scenario] };
}

function hash(text) {
  let n = 2166136261;
  for (const char of text) n = Math.imul(n ^ char.charCodeAt(0), 16777619);
  return n >>> 0;
}

function random(seed) {
  let state = seed >>> 0;
  return () => {
    state += 0x6D2B79F5;
    let n = state;
    n = Math.imul(n ^ n >>> 15, n | 1);
    n ^= n + Math.imul(n ^ n >>> 7, n | 61);
    return ((n ^ n >>> 14) >>> 0) / 4294967296;
  };
}

function distribute(total, weights) {
  const count = Math.round(total);
  const sum = weights.reduce((a, b) => a + b, 0);
  const quotas = weights.map(weight => count * weight / sum);
  const result = quotas.map(Math.floor);
  let remaining = count - result.reduce((a, b) => a + b, 0);
  const order = quotas.map((value, index) => ({ index, fraction: value % 1 }))
    .sort((a, b) => b.fraction - a.fraction || a.index - b.index);
  for (let i = 0; i < remaining; i++) result[order[i].index]++;
  return result;
}

function chooseSize(data, rng) {
  const draw = rng();
  let threshold = 0;
  for (const [name, size] of Object.entries(data.aircraft.sizes)) {
    threshold += size.share;
    if (draw <= threshold) return { name, su: size.su };
  }
  const [name, size] = Object.entries(data.aircraft.sizes).at(-1);
  return { name, su: size.su };
}

function chooseStay(data, rng) {
  const draw = rng();
  const stays = data.aircraft.stays;
  return draw < stays.same_day ? 0 : draw < stays.same_day + stays.overnight ? 1 : Number(Object.keys(stays).find(key => key.startsWith('multi_day_')).split('_').at(-1));
}

// Calendar and unit conversions are implementation constants; operational values
// below are taken from the supplied model. Carry-over IDs belong to a week-long
// registry, never to a date, so surviving airframes do not reshuffle at midnight.
export const HOURS = 24;
export const clockLabel = hour => `${String(Math.floor(hour)).padStart(2, '0')}:${String(Math.floor((hour % 1) * 60)).padStart(2, '0')}`;
export function restrictionAt(data, situation, date) {
  const window = data.game_day_restriction;
  if (situation !== 'security_restriction' || date !== data.meta.game_day || date !== window.date) return null;
  const hour = value => value.split(':').map(Number).reduce((sum, part, i) => sum + part / (i ? 60 : 1), 0);
  return { ...window, from: hour(window.start), to: hour(window.end) };
}

export function buildIllustration(data, situation, scenario) {
  const rng = random(hash(`${situation}/${scenario}/${data.meta.planning_window[0]}`));
  const meanSu = Object.values(data.aircraft.sizes).reduce((sum, size) => sum + size.su * size.share, 0);
  const sizes = Object.entries(data.aircraft.sizes).sort((a, b) => a[1].su - b[1].su);
  const smallest = sizes[0][1].su;
  const resolution = Math.min(smallest, ...sizes.slice(1).map((entry, index) => entry[1].su - sizes[index][1].su));
  const tolerance = resolution / 2;
  let serial = 0;
  const make = (size, source, born, due) => ({ id: `FBO-${String(++serial).padStart(3, '0')}`, ...size, source, born, due });
  const active = Array.from({ length: Math.round(data.aircraft.opening_aircraft) }, () =>
    make(chooseSize(data, rng), 'opening', -1, chooseStay(data, rng) * HOURS));
  const snapshots = [];
  const carryPool = [];
  let previous = [];
  data.days.forEach((info, dayIndex) => {
    const model = data.parking[situation].days[scenario][info.date];
    const kind = info.day_type === 'weekend' ? 'weekend' : 'weekday';
    const pause = restrictionAt(data, situation, info.date);
    // Conserve daily totals while moving placeholder events out of the pause.
    // Whole intersecting hourly bins are held: no invented minute precision.
    const weights = direction => data.hourly_profile.shares[`${kind}_${direction}`].map((value, hour) =>
      pause && hour < pause.to && hour + 1 > pause.from ? 0 : value);
    const arrivals = distribute(model.arrivals_p50, weights('arrivals'));
    const departures = distribute(model.departures_p50, weights('departures'));
    let net = 0;
    const hourly = [];
    for (let hour = 0; hour < HOURS; hour++) {
      const tick = dayIndex * HOURS + hour;
      const departing = [];
      for (let i = 0; i < departures[hour] && active.length; i++) {
        active.sort((a, b) => a.due - b.due || a.id.localeCompare(b.id));
        departing.push(active.shift().id);
      }
      for (let i = 0; i < arrivals[hour]; i++) {
        active.push(make(chooseSize(data, rng), 'arrival', tick, tick + chooseStay(data, rng) * HOURS));
      }
      net += arrivals[hour] - departures[hour];
      hourly.push({ active: [...active], net, arrivals: arrivals[hour], departures: departures[hour], departing });
    }
    const maxNet = Math.max(...hourly.map(item => item.net));
    hourly.forEach((item, hour) => {
      const tick = dayIndex * HOURS + hour;
      const target = Math.max(0, model.parking_demand_su_p50 - (maxNet - item.net) * meanSu);
      const fleet = [];
      let used = 0;
      const available = new Map([...item.active, ...carryPool].map(plane => [plane.id, plane]));
      const newArrivals = item.active.filter(plane => plane.born === tick);
      // Preserve identities, prioritising real illustrated arrivals and ongoing
      // flow-led airframes before representative carry-over corrections.
      const candidates = [...newArrivals, ...previous.filter(p => p.source !== 'carry-over'),
        ...previous.filter(p => p.source === 'carry-over'), ...item.active, ...carryPool];
      const seen = new Set();
      for (const plane of candidates) {
        if (seen.has(plane.id) || !available.has(plane.id)) continue;
        seen.add(plane.id);
        if (used + plane.su <= target + tolerance) { fleet.push(plane); used += plane.su; }
      }
      while (used + smallest <= target + tolerance) {
        const draw = chooseSize(data, rng);
        const fitting = draw.su <= target - used + tolerance ? draw : { name: sizes[0][0], su: smallest };
        const carry = make(fitting, 'carry-over', -1, Infinity);
        carryPool.push(carry); fleet.push(carry); used += carry.su;
      }
      snapshots.push({ dayIndex, hour, tick, arrivals: item.arrivals, departures: item.departures,
        departing: item.departing, fleet, used, target });
      previous = fleet;
    });
  });
  return snapshots;
}
