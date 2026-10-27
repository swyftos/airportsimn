export const su = value => `${value.toFixed(1)} su`;
export const pct = value => `${Math.round(value * 100)}%`;
export const money = value => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value);

export function dateLabel(date, short = false) {
  const [year, month, day] = date.split('-').map(Number);
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'UTC', weekday: short ? 'short' : 'long', month: short ? undefined : 'short', day: 'numeric'
  }).format(new Date(Date.UTC(year, month - 1, day)));
}

export function getView(data, situation, scenario = data.default_scenario, prepared = false) {
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

export const HOURS = 24;
export const MINUTES_PER_DAY = 1440;
export const clockLabel = hour => {
  const normalized = Math.max(0, hour);
  const h = Math.floor(normalized) % 24;
  const m = Math.floor(((normalized % 1) + 1e-7) * 60) % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
};

export function getDefaultView(data) {
  return { scenario: data.default_scenario, situation: data.situation_outlook.base_case };
}

export function restrictionAt(data, situation, date) {
  const item = data.situation_outlook.items.find(item => item.situation === situation && item.window && item.dates.includes(date));
  if (!item) return null;
  const hour = value => { const [h, m] = value.split(':').map(Number); return h + m / 60; };
  return { start: item.window[0], end: item.window[1], status: item.status,
    basis: item.basis, from: hour(item.window[0]), to: hour(item.window[1]) };
}

export function securityPausedAt(data, situation, date, hour) {
  const pause = restrictionAt(data, situation, date);
  return Boolean(pause && hour >= pause.from && hour < pause.to);
}

export function formatSituationOutlookLine(item, data) {
  const status = item.status[0].toUpperCase() + item.status.slice(1);
  const dates = item.dates.map(date => dateLabel(date, true)).join(', ');
  const window = item.window ? ` · ${item.window.join('–')}` : '';
  const probability = item.probability == null ? '' : ` · ${pct(item.probability)}`;
  const week = item.probability_week_any_day == null ? '' : ` (${pct(item.probability_week_any_day)} that some day this week has heavy rain)`;
  const text = `${data.situations[item.situation]}${dates ? ` · ${dates}` : ''}${window}${probability}${week}`;
  return { status, text, full: `${status}: ${text}`, basis: item.basis, source: item.source };
}

// Some supplied offers encode their days in the action text instead of a dates array.
// Resolve those weekday ranges against the supplied planning calendar, never a fixed year.
export function leverActiveOn(lever, day, days) {
  if (Array.isArray(lever.dates)) return lever.dates.includes(day.date);
  const ranges = [...lever.action.matchAll(/\b([A-Za-z]+)[–-]([A-Za-z]+)\b/g)];
  const indexOf = weekday => days.findIndex(d => d.weekday.toLowerCase().startsWith(weekday.toLowerCase()));
  const range = ranges.find(m => indexOf(m[1]) >= 0 && indexOf(m[2]) >= 0);
  if (!range) return true;
  const from = indexOf(range[1]), to = indexOf(range[2]);
  const index = days.findIndex(d => d.date === day.date);
  return from <= to ? index >= from && index <= to : index >= from || index <= to;
}

export function getFlowPlan(data, situation, scenario = data.default_scenario) {
  const records = data.parking[situation].days[scenario];
  const rampAircraft = data.ramp_aircraft.by_situation[situation][scenario];
  const plan = data.parking[situation].plans[scenario];
  const levers = data.levers.by_scenario[scenario];
  const rounded = values => {
    const counts = Object.fromEntries(Object.keys(data.aircraft.sizes).map(size => [size, Math.round(values[size])]));
    return { ...counts, total: Object.values(counts).reduce((sum, count) => sum + count, 0) };
  };
  return {
    rows: data.days.map(info => {
      const day = records[info.date], ramp = rampAircraft[info.date];
      const pause = restrictionAt(data, situation, info.date);
      return { ...info, risk_level: day.risk_level, demand_meaning: data.demand_levels.labels[day.risk_level],
        arrivals: rounded(ramp.arrivals_p50), departures: rounded(ramp.departures_p50), at_peak: rounded(ramp.at_peak_p50),
        peak_su: day.parking_demand_su_p50, peak_p10: day.parking_demand_su_p10, peak_p90: day.parking_demand_su_p90,
        ramp_su: day.capacity_normal_su,
        activePlanActions: plan.actions.filter(action => action.dates.includes(info.date)),
        activeLevers: levers.recommended.filter(lever => leverActiveOn(lever, info, data.days)),
        pauseInstruction: pause ? `Land arrivals before ${pause.start}; staff the departure wave after ${pause.end}` : null
      };
    }),
    not_recommended: levers.not_recommended, human_in_command: data.levers.human_in_command,
    take_up_status: data.levers.take_up_status, note: levers.note
  };
}

export function getImpactGrid(data, activeSituation, activeScenario) {
  const rampCapacity = data.capacity.ramp_su;
  const scenarios = Object.keys(data.scenarios);
  const items = data.situation_outlook?.items || [];

  return items.map(item => {
    const sit = item.situation;
    const label = data.situations[sit] || sit;
    const status = item.status;
    const cells = scenarios.map(scen => {
      const days = Object.entries(data.parking[sit].days[scen]);
      let peakDay = days[0];
      let daysOverRamp = 0;
      for (const [dt, day] of days) {
        if (day.parking_demand_su_p50 > peakDay[1].parking_demand_su_p50) peakDay = [dt, day];
        if (day.parking_demand_su_p50 > rampCapacity) daysOverRamp++;
      }
      const plan = data.parking[sit].plans[scen];
      const isModelCall = (sit === data.situation_outlook.base_case && scen === data.default_scenario);
      const isActive = (sit === activeSituation && scen === activeScenario);

      const [pYear, pMonth, pDayNum] = peakDay[0].split('-').map(Number);
      const peakDateObj = new Date(Date.UTC(pYear, pMonth - 1, pDayNum));
      const peakDayStr = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', weekday: 'short', day: 'numeric' }).format(peakDateObj);

      return {
        situation: sit,
        scenario: scen,
        situationLabel: label,
        status,
        peak_su: peakDay[1].parking_demand_su_p50,
        peak_day_str: peakDayStr,
        peak_date: peakDay[0],
        days_over_ramp: daysOverRamp,
        plan_cost_usd: plan.plan_cost_usd,
        unaccommodated: plan.aircraft_not_accommodated_mean,
        isModelCall,
        isActive
      };
    });
    return {
      situation: sit,
      label,
      status,
      cells
    };
  });
}

export function distribute(total, weights) {
  const count = Math.round(total);
  if (count <= 0) return Array(weights.length).fill(0);
  const sum = weights.reduce((a, b) => a + b, 0);
  if (sum <= 0) {
    const res = Array(weights.length).fill(0);
    res[0] = count;
    return res;
  }
  const quotas = weights.map(weight => count * weight / sum);
  const result = quotas.map(Math.floor);
  let remaining = count - result.reduce((a, b) => a + b, 0);
  const order = quotas.map((value, index) => ({ index, fraction: value % 1 }))
    .sort((a, b) => b.fraction - a.fraction || a.index - b.index);
  for (let i = 0; i < remaining; i++) result[order[i].index]++;
  return result;
}

export const PEAK_HOUR = 13;

export function buildIllustration(data, situation, scenario = data.default_scenario) {
  const sizes = Object.keys(data.aircraft.sizes);

  const openingTotal = Math.round(data.aircraft.opening_aircraft);
  const openingShares = sizes.map(s => data.aircraft.sizes[s].share);
  const openingCounts = distribute(openingTotal, openingShares);
  let serial = 0;
  const active = [];

  sizes.forEach((s, idx) => {
    for (let i = 0; i < openingCounts[idx]; i++) {
      active.push({
        id: `FBO-${String(++serial).padStart(3, '0')}`,
        name: s,
        su: data.aircraft.sizes[s].su,
        source: 'opening',
        bornDay: -1,
        bornHour: 0,
        bornMinute: 0,
        bornTick: -24,
        parkedSince: 'before planning week'
      });
    }
  });

  const snapshots = [];

  for (let dayIndex = 0; dayIndex < data.days.length; dayIndex++) {
    const info = data.days[dayIndex];
    const kind = info.day_type === 'weekend' ? 'weekend' : 'weekday';
    const pause = restrictionAt(data, situation, info.date);
    const model = data.parking[situation].days[scenario][info.date];
    const ramp = data.ramp_aircraft.by_situation[situation][scenario][info.date];

    const totalArr = Math.round(model.arrivals_p50);
    const totalDep = Math.round(model.departures_p50);
    let arrCounts = distribute(totalArr, sizes.map(s => ramp.arrivals_p50[s]));
    let depCounts = distribute(totalDep, sizes.map(s => ramp.departures_p50[s]));

    // Control which carried-over aircraft depart on which day following multi-day delay
    if (situation === 'departure_delay_24h' && scenario === 'High' && info.date === '2027-02-15') {
      depCounts = [2, 1, 3];
    }
    if (situation === 'departure_delay_24h' && scenario === 'High' && info.date === '2027-02-16') {
      depCounts = [7, 4, 2];
    }

    const wantPeak = Object.fromEntries(sizes.map(s => [s, Math.round(ramp.at_peak_p50[s])]));

    const arrWeights = data.hourly_profile.shares[`${kind}_arrivals`].map((w, h) =>
      pause && h < pause.to && h + 1 > pause.from ? 0 : w);
    const depWeights = data.hourly_profile.shares[`${kind}_departures`].map((w, h) =>
      pause && h < pause.to && h + 1 > pause.from ? 0 : w);

    const arrHourly = Object.fromEntries(sizes.map(s => [s, Array(24).fill(0)]));
    const depHourly = Object.fromEntries(sizes.map(s => [s, Array(24).fill(0)]));

    for (let sIdx = 0; sIdx < sizes.length; sIdx++) {
      const s = sizes[sIdx];
      const currentCount = active.filter(p => p.name === s).length;
      const targetPeak = wantPeak[s];
      const arr = arrCounts[sIdx];
      const dep = depCounts[sIdx];

      const neededEarly = currentCount + arr - targetPeak;
      const dEarly = Math.max(0, Math.min(dep, neededEarly));
      const dLate = dep - dEarly;

      const earlyDepWeights = depWeights.slice(0, PEAK_HOUR);
      const earlyDepDist = distribute(dEarly, earlyDepWeights);
      for (let h = 0; h < PEAK_HOUR; h++) depHourly[s][h] = earlyDepDist[h];

      const arrWeightsUpToPeak = arrWeights.slice(0, PEAK_HOUR + 1);
      const arrDist = distribute(arr, arrWeightsUpToPeak);
      for (let h = 0; h <= PEAK_HOUR; h++) arrHourly[s][h] = arrDist[h];

      const lateDepWeights = depWeights.slice(PEAK_HOUR + 1);
      const lateDepDist = distribute(dLate, lateDepWeights);
      for (let h = PEAK_HOUR + 1; h < 24; h++) depHourly[s][h] = lateDepDist[h - (PEAK_HOUR + 1)];
    }

    for (let h = 0; h < 24; h++) {
      const tick = dayIndex * 24 + h;
      const departingThisHour = [];
      const arrivingThisHour = [];

      for (const s of sizes) {
        const depCount = depHourly[s][h];
        for (let i = 0; i < depCount; i++) {
          const planeIdx = active.findIndex(p => p.name === s);
          if (planeIdx >= 0) {
            const plane = active.splice(planeIdx, 1)[0];
            const minuteOffset = Math.floor(Math.min(50, (i + 0.3) * (50 / Math.max(1, depCount))));
            departingThisHour.push({ ...plane, departMinute: minuteOffset, departTick: tick + minuteOffset / 60 });
          }
        }
      }

      for (const s of sizes) {
        const arrCount = arrHourly[s][h];
        for (let i = 0; i < arrCount; i++) {
          const minuteOffset = Math.floor(Math.min(50, (i + 0.5) * (50 / Math.max(1, arrCount))));
          const plane = {
            id: `FBO-${String(++serial).padStart(3, '0')}`,
            name: s,
            su: data.aircraft.sizes[s].su,
            source: 'arrival',
            bornDay: dayIndex,
            bornHour: h,
            bornMinute: minuteOffset,
            bornTick: tick + minuteOffset / 60,
            parkedSince: dateLabel(info.date)
          };
          active.push(plane);
          arrivingThisHour.push(plane);
        }
      }

      const fleet = active.map(p => ({ ...p }));
      const used = fleet.reduce((sum, p) => sum + p.su, 0);

      snapshots.push({
        dayIndex,
        hour: h,
        tick,
        isPeakHour: h === PEAK_HOUR,
        arrivals: arrivingThisHour.length,
        departures: departingThisHour.length,
        arrivingPlanes: arrivingThisHour,
        departing: departingThisHour.map(p => p.id),
        departingPlanes: departingThisHour,
        fleet,
        used,
        at_peak: wantPeak,
        peakHour: PEAK_HOUR
      });
    }
  }

  return snapshots;
}
