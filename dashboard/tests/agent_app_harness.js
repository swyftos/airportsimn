// Loads agent_gemini/app.js without a browser and prints what its planning functions compute, as JSON.
// Used by test_agent_app.py: node agent_app_harness.js <app.js> <agent_data.json>
const fs = require('fs');
const vm = require('vm');
const [, , appPath, dataPath] = process.argv;

const el = () => ({ setAttribute() {}, removeAttribute() {}, querySelector: () => null, querySelectorAll: () => [], style: {} });
const store = {};
const ctx = {
  console, setTimeout, clearTimeout,
  document: { addEventListener() {}, getElementById: () => null, querySelector: () => null, querySelectorAll: () => [],
              documentElement: el(), createElement: el, body: el() },
  localStorage: { getItem: k => store[k] ?? null, setItem: (k, v) => { store[k] = String(v); } },
  FileReader: class { readAsText(file) { this.onload({ target: { result: file.text } }); } },
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(appPath, 'utf8'), ctx);
// Top-level const/let of app.js are visible to later scripts in the same context, functions are globals
const run = code => vm.runInContext(code, ctx);
run(`state.data = ${fs.readFileSync(dataPath, 'utf8')}; renderAllViews = () => {}; updateNavCount = () => {};`);

const out = {};
const impacts = (scenario, weather = {}) => run(`(() => {
  state.scenario = ${JSON.stringify(scenario)};
  state.weatherSettings = Object.fromEntries(state.data.days.map(d => [d.date, 'clear']));
  Object.assign(state.weatherSettings, ${JSON.stringify(weather)});
  return computeDailyWeatherImpacts().map(i => ({ date: i.date, arr: i.finalArrivals, dep: i.finalDepartures,
    lostArr: i.lostArrivals, lostDep: i.lostDepartures, effect: i.effectPct, arrRange: i.arrRange, depRange: i.depRange }));
})()`);
for (const s of ['Low', 'Medium', 'High']) out[`clear_${s}`] = impacts(s);
out.sunday_heavy_rain = impacts('Medium', { '2027-02-14': 'heavy_rain' });
out.last_day_rain = impacts('Medium', { '2027-02-17': 'rain' });
out.every_weather = Object.fromEntries(['rain', 'heavy_rain', 'heavy_fog'].map(w => [w, impacts('Medium', { '2027-02-12': w })]));

// Hour by hour: totals per day and the hours inside the game-day pause
out.hourly = run(`(() => {
  state.scenario = 'Medium';
  state.weatherSettings = Object.fromEntries(state.data.days.map(d => [d.date, 'clear']));
  return computeDailyWeatherImpacts().map(i => { const h = getHourlyProfileForDay(i.day, i.finalArrivals, i.finalDepartures);
    return { date: i.date, arr: h.reduce((a, x) => a + x.arrExp, 0), dep: h.reduce((a, x) => a + x.depExp, 0),
      pause_hours: h.filter(x => x.isTfr).map(x => x.hour), pause_movements: h.filter(x => x.isTfr).reduce((a, x) => a + x.totalExp, 0) }; });
})()`);
out.in_restriction = run(`(() => { const d = date => state.data.days.find(x => x.date === date);
  return { sun_1400_1500: inRestriction(d('2027-02-14'), 14, 15), sun_1300_1400: inRestriction(d('2027-02-14'), 13, 14),
           sun_2000_2100: inRestriction(d('2027-02-14'), 20, 21), sun_2030_2100: inRestriction(d('2027-02-14'), 20.5, 21),
           sat_1500_1600: inRestriction(d('2027-02-13'), 15, 16) }; })()`);
out.peak = run(`(() => ({ weekday_arrivals: peakWindow(state.data.hourly_profile.shares.weekday_arrivals),
  weekday_departures: peakWindow(state.data.hourly_profile.shares.weekday_departures),
  after_pause_departures: shareAfterRestriction('departures'), flat: peakWindow(Array(24).fill(1 / 24)) }))()`);

// The demo: Friday 10:00, four landings and one departure logged
const demo = [['09:15', 'arrival'], ['10:40', 'arrival'], ['11:05', 'arrival'], ['12:20', 'arrival'], ['16:45', 'departure']]
  .map(([time, type], i) => ({ id: `d${i}`, date: '2027-02-12', time, type, tail: `DEMO-0${i + 1}`, size: 'midsize', status: 'confirmed' }));
out.demo = run(`(() => {
  state.scenario = 'Medium';
  state.weatherSettings = Object.fromEntries(state.data.days.map(d => [d.date, 'clear']));
  state.userMovements = ${JSON.stringify(demo)};
  const fri = computeDailyWeatherImpacts().find(i => i.date === '2027-02-12');
  const h = getHourlyProfileForDay(fri.day, fri.finalArrivals, fri.finalDepartures);
  return { booked_arrivals: h.reduce((a, x) => a + x.userArrCount, 0), booked_departures: h.reduce((a, x) => a + x.userDepCount, 0),
           expected_arrivals: fri.finalArrivals, hours_with_flights: h.filter(x => x.hasUserFlight).map(x => x.hour) };
})()`);

// CSV import keeps valid rows and skips bad ones
out.csv = run(`(() => {
  state.userMovements = [];
  const text = ['date,time,type,tail_number,aircraft_size,status',
    '2027-02-12,09:15,arrival,DEMO-01,midsize,confirmed',     // ok
    '2027-02-12,9:15,arrival,DEMO-02,midsize,confirmed',      // bad time
    '2027-03-01,10:00,arrival,DEMO-03,midsize,confirmed',     // outside the week
    '2027-02-13,10:00,landing,DEMO-04,midsize,confirmed',     // bad type
    '2027-02-13,10:00,departure,<script>,midsize,confirmed',  // bad tail
    '2027-02-13,23:59,departure,,large,expected'].join('\\n'); // ok, no tail
  importMovementsFromCsv({ target: { files: [{ text }], value: 'x' } });
  return { imported: state.userMovements.map(m => m.tail || '(none)'), saved: JSON.parse(localStorage.getItem(STORAGE_KEY_MOVEMENTS)).length };
})()`);
out.escape = run(`escapeHtml('<img src=x onerror=alert(1)>')`);
console.log(JSON.stringify(out));
