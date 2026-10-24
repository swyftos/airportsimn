const {readFileSync}=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const code=readFileSync('agent_gemini/app.js','utf8');
const data=JSON.parse(readFileSync('agent_gemini/agent_data.json','utf8'));
const nodes={};
const document={addEventListener(){},getElementById(id){return nodes[id] ||= {textContent:'',innerHTML:''}}};
const context=vm.createContext({document,console,localStorage:{setItem(){}}});
vm.runInContext(code,context);
context.input=data;
vm.runInContext('state.data=input',context);
const run=s=>vm.runInContext(s,context);
// An unchanged clear-weather calculation must reproduce the supplied daily forecast.
for(const scenario of ['Low','Medium','High']) {
 context.scenario=scenario;
 const impacts=run('state.scenario=scenario; computeDailyWeatherImpacts()');
 impacts.forEach((d,i)=>{
  assert.equal(d.finalArrivals,data.days[i].scenarios[scenario].expected_arrivals);
  assert.equal(d.finalDepartures,data.days[i].scenarios[scenario].expected_departures);
 });
}
run("state.scenario='Medium'; state.simulatedNow='2027-02-14T20:30'; const impact=computeDailyWeatherImpacts().find(d=>d.date==='2027-02-14'); renderNext3HoursRadar(impact.day,impact)");
assert.match(nodes['next-hours-window-tag'].textContent,/20:30–23:30/);
assert.doesNotMatch(nodes['next-hours-note'].textContent,/overlaps|TFR Active/);
// Weighted partial hours: 20:30–23:30 includes half of hours 20 and 23.
const expected=run('getHourlyProfileForDay(impact.day,impact.finalArrivals,impact.finalDepartures).reduce((n,h)=>n+h.arrExp*([20,23].includes(h.hour)?.5:[21,22].includes(h.hour)?1:0),0)');
assert.ok(nodes['next-hours-stats'].innerHTML.includes(expected.toFixed(1)));
run("state.simulatedNow='2027-02-14T14:00'; renderNext3HoursRadar(impact.day,impact)");
assert.match(nodes['next-hours-note'].textContent,/assumed game-day pause/);
assert.match(nodes['next-hours-note'].textContent,/not an active FAA notice/);
run("state.simulatedNow='2027-02-14T23:30'; renderNext3HoursRadar(impact.day,impact)");
assert.match(nodes['next-hours-window-tag'].textContent,/23:30–24:00/);
run("state.proposalStates={x:{status:'acknowledged',note:'Keep note'}}; invalidatePlanReview()");
assert.equal(run('state.proposalStates.x.status'),'pending');
assert.equal(run('state.proposalStates.x.note'),'Keep note');
console.log('PASS: 3-scenario daily parity; minute-aware windows; assumed restriction boundary; midnight cutoff; review invalidation.');
