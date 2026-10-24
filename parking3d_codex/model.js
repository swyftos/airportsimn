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
  return draw < stays.same_day ? 0 : draw < stays.same_day + stays.overnight ? 1 : 3;
}

// The event ledger follows the supplied P50 flow counts and assumed hourly shares.
// Representative carried aircraft then calibrate the picture to the parking model's
// daily demand. The picture is illustrative; the daily model remains the answer.
export function buildIllustration(data, situation, scenario) {
  const rng = random(hash(`${situation}/${scenario}/${data.meta.planning_window[0]}`));
  const snapshots = [];
  const active = [];
  const opening = Math.round(data.aircraft.opening_aircraft);
  let serial = 0;
  for (let i = 0; i < opening; i++) {
    active.push({ id: `opening-${i}`, ...chooseSize(data, rng), due: chooseStay(data, rng) * 24 });
  }
  const meanSu = Object.values(data.aircraft.sizes).reduce((sum, size) => sum + size.su * size.share, 0);
  const sizes = Object.values(data.aircraft.sizes).map(size => size.su).sort((a, b) => a - b);
  const resolution = Math.min(...sizes.slice(1).map((size, index) => size - sizes[index]));
  const tolerance = resolution / 2;
  data.days.forEach((info, dayIndex) => {
    const model = data.parking[situation].days[scenario][info.date];
    const kind = info.day_type === 'weekend' ? 'weekend' : 'weekday';
    const arrivals = distribute(model.arrivals_p50, data.hourly_profile.shares[`${kind}_arrivals`]);
    const departures = distribute(model.departures_p50, data.hourly_profile.shares[`${kind}_departures`]);
    let net = 0;
    const hourly = [];
    for (let hour = 0; hour < 24; hour++) {
      const tick = dayIndex * 24 + hour;
      for (let i = 0; i < departures[hour] && active.length; i++) {
        active.sort((a, b) => a.due - b.due || a.id.localeCompare(b.id));
        active.shift();
      }
      for (let i = 0; i < arrivals[hour]; i++) {
        const stay = chooseStay(data, rng);
        active.push({ id: `flight-${serial++}`, ...chooseSize(data, rng), due: tick + stay * 24 });
      }
      net += arrivals[hour] - departures[hour];
      hourly.push({ active: active.map(a => ({ ...a })), net, arrivals: arrivals[hour], departures: departures[hour] });
    }
    const maxNet = Math.max(...hourly.map(item => item.net));
    hourly.forEach((item, hour) => {
      const illustratedDemand = Math.max(0, model.parking_demand_su_p50 - (maxNet - item.net) * meanSu);
      const fleet = [];
      let used = 0;
      for (const aircraft of [...item.active].sort((a, b) => a.id.localeCompare(b.id))) {
        if (used + aircraft.su <= illustratedDemand + tolerance) { fleet.push(aircraft); used += aircraft.su; }
      }
      // Stable representative IDs make hour-to-hour changes legible. They stand for
      // the model's untracked carry-in/stays, not extra forecast arrivals.
      const carryRng = random(hash(`${situation}/${scenario}/${info.date}/carry`));
      let carry = 0;
      while (used + resolution < illustratedDemand && fleet.length < 80) {
        const drawnSize = chooseSize(data, carryRng);
        const size = used + drawnSize.su <= illustratedDemand + tolerance ? drawnSize : { name: 'light', su: data.aircraft.sizes.light.su };
        if (used + size.su > illustratedDemand + tolerance) break;
        fleet.push({ id: `carry-${dayIndex}-${carry++}`, ...size, due: tickFor(dayIndex, hour) + chooseStay(data, carryRng) * 24 });
        used += size.su;
      }
      snapshots.push({ dayIndex, hour, arrivals: item.arrivals, departures: item.departures, fleet, used, target: illustratedDemand });
    });
  });
  return snapshots;
}

function tickFor(dayIndex, hour) { return dayIndex * 24 + hour; }
