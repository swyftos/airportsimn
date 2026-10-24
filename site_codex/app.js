const $ = (selector) => document.querySelector(selector);
const DAYS = ['2027-02-11','2027-02-12','2027-02-13','2027-02-14','2027-02-15','2027-02-16','2027-02-17'];
const state = { scenario:'Medium', variant:'standard', day:'2027-02-14', extraCapacity:0 };
let data;
const fmt = (n, digits=1) => Number(n).toFixed(digits);
const whole = (n) => new Intl.NumberFormat('en-US',{maximumFractionDigits:0}).format(n);
const money = (n) => new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(n);
const pct = (n, digits=0) => `${fmt(n*100,digits)}%`;
const dateLabel = (date, long=false) => new Date(`${date}T12:00:00Z`).toLocaleDateString('en-US',{timeZone:'UTC',weekday:long?'long':'short',month:long?'long':'short',day:'numeric'});
const esc = (s) => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const tag = (name) => `<span class="badge ${name}">${name.toUpperCase()}</span>`;
const parkingDays = () => data.parking[state.variant].days.filter(d=>d.scenario===state.scenario);
const forecasts = () => data.forecast_daily.filter(d=>d.scenario===state.scenario);
const plan = () => data.parking[state.variant].plans[state.scenario];
const dayRow = () => parkingDays().find(d=>d.date===state.day);
const forecastRow = () => forecasts().find(d=>d.date===state.day);
const ordinaryRow = () => data.ordinary_week_parking.find(d=>d.date===state.day);
const table = (headers, rows) => `<thead><tr>${headers.map(h=>`<th scope="col">${h}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map(cell=>`<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody>`;

function initTheme(){
  const saved = localStorage.getItem('ramp27-theme');
  if(saved) document.documentElement.dataset.theme=saved;
  $('#theme-toggle').addEventListener('click',()=>{
    const current=document.documentElement.dataset.theme || (matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');
    const next=current==='dark'?'light':'dark';
    document.documentElement.dataset.theme=next;
    localStorage.setItem('ramp27-theme',next);
    $('#theme-toggle').setAttribute('aria-label',`Switch to ${next==='dark'?'light':'dark'} theme`);
  });
}

function initControls(){
  $('#day-select').innerHTML=DAYS.map(d=>`<option value="${d}">${dateLabel(d)}${d===data.meta.game_day?' · Game day':d===data.meta.presidents_day?' · Presidents’ Day':''}</option>`).join('');
  document.querySelectorAll('[data-scenario]').forEach(btn=>btn.addEventListener('click',()=>{state.scenario=btn.dataset.scenario;render();}));
  $('#variant').addEventListener('change',e=>{state.variant=e.target.value;render();});
  $('#day-select').addEventListener('change',e=>{state.day=e.target.value;render();});
  $('#capacity-slider').addEventListener('input',e=>{state.extraCapacity=Number(e.target.value);renderWhatIf();});
  $('#export-decisions').addEventListener('click',exportDecisions);
  $('#data-section').innerHTML=Object.keys(data).map(k=>`<option value="${esc(k)}">${esc(k.replaceAll('_',' '))}</option>`).join('');
  $('#data-section').addEventListener('change',renderRawData);
  renderRawData();
}

function render(){
  document.querySelectorAll('[data-scenario]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.scenario===state.scenario)));
  $('#variant').value=state.variant;
  $('#day-select').value=state.day;
  renderOverview();renderMovement();renderParking();renderDay();renderPlan();renderAdvice();
}

function renderOverview(){
  const p=plan(), s=p.summary, extra=forecasts().reduce((sum,d)=>sum+d.incremental_arrivals,0);
  const peak=parkingDays().find(d=>d.date===s.peak_day);
  const over=s.peak_parking_demand_su_p50>s.normal_capacity_su;
  $('#brief-risk').textContent=`${s.overall_risk.toUpperCase()} RAMP RISK`;
  $('#brief-risk').className=`risk-pill ${s.overall_risk.toLowerCase()}`;
  $('#brief-headline').textContent=over?`Prepare ${fmt(s.max_prepared_capacity_su-s.normal_capacity_su)} extra su for a ${fmt(s.peak_parking_demand_su_p50)} su peak.`:`Keep overflow ready: the P90 reaches ${fmt(s.peak_parking_demand_su_p90)} su.`;
  $('#brief-detail').textContent=`${state.scenario} case · ${data.parking[state.variant].label}. Peak ${dateLabel(s.peak_day)}: ${pct(peak.prob_over_normal_capacity)} chance of exceeding the normal ${fmt(s.normal_capacity_su)} su ramp. The proposed plan needs human approval.`;
  const kpis=[
    {label:'Extra landings',value:`+${fmt(extra)}`,note:`Above ordinary week · ${state.scenario} case · 90% daily ranges below`},
    {label:'Peak parking · P50',value:`${fmt(s.peak_parking_demand_su_p50)} su`,note:`${dateLabel(s.peak_day)} · P10–P90 ${fmt(peak.parking_demand_su_p10)}–${fmt(peak.parking_demand_su_p90)} su · normal ${fmt(s.normal_capacity_su)} su`,class:over?'critical':'warning'},
    {label:'Aircraft without space',value:`${fmt(p.aircraft_not_accommodated.no_plan.mean)} → ${fmt(p.aircraft_not_accommodated.with_plan.mean)}`,note:`Mean no plan → proposed plan · P10–P90 ${fmt(p.aircraft_not_accommodated.no_plan.p10)}–${fmt(p.aircraft_not_accommodated.no_plan.p90)} vs ${fmt(p.aircraft_not_accommodated.with_plan.p10)}–${fmt(p.aircraft_not_accommodated.with_plan.p90)}`},
    {label:'Proposed plan cost',value:money(p.parking_cost_usd),note:`${pct(p.prob_plan_pays_off)} chance plan pays off · approval pending`}
  ];
  $('#kpis').innerHTML=kpis.map(k=>`<div class="kpi ${k.class||''}"><span class="kpi-label">${k.label}</span><strong class="kpi-value">${k.value}</strong><p class="kpi-note">${k.note}</p></div>`).join('');
}

function chartEvents(container){
  container.querySelectorAll('[data-chart-day]').forEach(el=>{
    el.addEventListener('click',()=>{state.day=el.dataset.chartDay;render();});
    el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();state.day=el.dataset.chartDay;render();}});
  });
}

function renderMovement(){
  const rows=forecasts(), W=760,H=285,L=42,R=16,T=20,B=46,plotH=H-T-B,plotW=W-L-R,step=plotW/7;
  const max=Math.ceil(Math.max(...rows.flatMap(d=>[d.arrivals_range90[1],d.departures_range90[1],d.baseline_arrivals,d.baseline_departures]))/2)*2;
  const y=v=>T+plotH-(v/max)*plotH;
  let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Daily landings and departures chart, ordinary versus Super Bowl week, with 90 percent ranges"><text x="4" y="12" class="axis-label">AIRCRAFT / DAY</text>`;
  for(let t=0;t<=max;t+=2) svg+=`<line class="grid" x1="${L}" x2="${W-R}" y1="${y(t)}" y2="${y(t)}"/><text x="${L-9}" y="${y(t)+4}" text-anchor="end">${t}</text>`;
  rows.forEach((d,i)=>{
    const x=L+i*step,mid=x+step/2;
    if(d.date===data.meta.game_day)svg+=`<rect class="day-shade" x="${x+2}" y="${T}" width="${step-4}" height="${plotH}"/>`;
    if(d.date===data.meta.presidents_day)svg+=`<rect class="holiday-shade" x="${x+2}" y="${T}" width="${step-4}" height="${plotH}"/>`;
    if(d.date===state.day)svg+=`<rect class="active-day" x="${x+2}" y="${T}" width="${step-4}" height="${plotH}" rx="5"/>`;
    [['arrivals',mid-20,'arrival'],['departures',mid+5,'departure']].forEach(([type,bx,cls])=>{
      const range=d[`${type}_range90`],base=d[`baseline_${type}`],value=d[`expected_${type}`],bw=15;
      svg+=`<rect class="range-${cls}" x="${bx}" y="${y(range[1])}" width="${bw}" height="${Math.max(1,y(range[0])-y(range[1]))}" rx="3"/>`;
      svg+=`<rect class="${cls}" x="${bx+3}" y="${y(value)}" width="${bw-6}" height="${T+plotH-y(value)}" rx="2"/>`;
      svg+=`<line class="baseline" x1="${bx-3}" x2="${bx+bw+3}" y1="${y(base)}" y2="${y(base)}"/>`;
    });
    svg+=`<text x="${mid}" y="${H-22}" text-anchor="middle">${dateLabel(d.date)}</text><text x="${mid}" y="${H-7}" text-anchor="middle" class="axis-label">${d.date===data.meta.game_day?'GAME':d.date===data.meta.presidents_day?'HOLIDAY':''}</text>`;
    svg+=`<g data-chart-day="${d.date}" role="button" tabindex="0" aria-label="Focus ${dateLabel(d.date,true)}"><title>${dateLabel(d.date)}: landings ${fmt(d.expected_arrivals)} (${fmt(d.arrivals_range90[0])}–${fmt(d.arrivals_range90[1])}); departures ${fmt(d.expected_departures)} (${fmt(d.departures_range90[0])}–${fmt(d.departures_range90[1])})</title><rect class="hit" x="${x+2}" y="${T}" width="${step-4}" height="${plotH}"/></g>`;
  });
  svg+='</svg>';
  $('#movement-chart').innerHTML=svg;chartEvents($('#movement-chart'));
  const f=forecastRow();
  $('#movement-detail').textContent=`${dateLabel(state.day,true)}: ${fmt(f.expected_arrivals)} landings (90% ${fmt(f.arrivals_range90[0])}–${fmt(f.arrivals_range90[1])}) and ${fmt(f.expected_departures)} departures (90% ${fmt(f.departures_range90[0])}–${fmt(f.departures_range90[1])}). Ordinary week: ${fmt(f.baseline_arrivals)} / ${fmt(f.baseline_departures)}. Situation variants affect the parking simulation; these movement ranges are the base case.`;
  $('#movement-table').innerHTML=table(['Day','Ordinary landings','Game landings','90% range','Ordinary departures','Game departures','90% range'],rows.map(d=>[dateLabel(d.date),fmt(d.baseline_arrivals),fmt(d.expected_arrivals),`${fmt(d.arrivals_range90[0])}–${fmt(d.arrivals_range90[1])}`,fmt(d.baseline_departures),fmt(d.expected_departures),`${fmt(d.departures_range90[0])}–${fmt(d.departures_range90[1])}`]));
}

function renderParking(){
  const rows=parkingDays(),ord=data.ordinary_week_parking,W=760,H=310,L=42,R=52,T=20,B=45,plotH=H-T-B,plotW=W-L-R,step=plotW/7;
  const max=Math.ceil(Math.max(...rows.flatMap(d=>[d.parking_demand_su_p90,d.capacity_prepared_su]))/5)*5;
  const y=v=>T+plotH-v/max*plotH, xs=rows.map((_,i)=>L+step*(i+.5));
  let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Parking occupancy P10 to P90 band and P50, compared with ordinary week and capacity"><text x="3" y="12" class="axis-label">SPACE UNITS (su)</text>`;
  for(let t=0;t<=max;t+=5)svg+=`<line class="grid" x1="${L}" x2="${W-R}" y1="${y(t)}" y2="${y(t)}"/><text x="${L-9}" y="${y(t)+4}" text-anchor="end">${t}</text>`;
  rows.forEach((d,i)=>{
    const x=L+i*step;
    if(d.date===data.meta.game_day)svg+=`<rect class="day-shade" x="${x+2}" y="${T}" width="${step-4}" height="${plotH}"/>`;
    if(d.date===data.meta.presidents_day)svg+=`<rect class="holiday-shade" x="${x+2}" y="${T}" width="${step-4}" height="${plotH}"/>`;
    if(d.date===state.day)svg+=`<rect class="active-day" x="${x+2}" y="${T}" width="${step-4}" height="${plotH}" rx="5"/>`;
    if(d.parking_demand_su_p50>d.capacity_normal_su)svg+=`<rect class="overfill" x="${x+step*.26}" y="${y(d.parking_demand_su_p50)}" width="${step*.48}" height="${y(d.capacity_normal_su)-y(d.parking_demand_su_p50)}"/>`;
  });
  const points=key=>rows.map((d,i)=>`${xs[i]},${y(d[key])}`).join(' ');
  const lower=rows.map((d,i)=>`${xs[i]},${y(d.parking_demand_su_p10)}`).reverse().join(' ');
  svg+=`<polygon class="parking-band" points="${points('parking_demand_su_p90')} ${lower}"/>`;
  svg+=`<line class="normal-line" x1="${L}" x2="${W-R}" y1="${y(rows[0].capacity_normal_su)}" y2="${y(rows[0].capacity_normal_su)}"/>`;
  svg+=`<polyline class="prepared-line" fill="none" points="${points('capacity_prepared_su')}"/>`;
  svg+=`<polyline class="ordinary-line" points="${ord.map((d,i)=>`${xs[i]},${y(d.parking_demand_su_p50)}`).join(' ')}"/>`;
  svg+=`<polyline class="parking-line" points="${points('parking_demand_su_p50')}"/>`;
  svg+=`<text x="${W-R+4}" y="${y(rows[0].capacity_normal_su)-4}">Normal</text><text x="${W-R+4}" y="${y(rows[6].capacity_prepared_su)-4}">Ready</text>`;
  rows.forEach((d,i)=>{
    svg+=`<circle cx="${xs[i]}" cy="${y(d.parking_demand_su_p50)}" r="4" fill="var(--ink)"/>`;
    svg+=`<text x="${xs[i]}" y="${H-20}" text-anchor="middle">${dateLabel(d.date)}</text><text x="${xs[i]}" y="${H-5}" text-anchor="middle" class="axis-label">${d.date===data.meta.game_day?'GAME':d.date===data.meta.presidents_day?'HOLIDAY':''}</text>`;
    svg+=`<g data-chart-day="${d.date}" role="button" tabindex="0" aria-label="Focus parking on ${dateLabel(d.date,true)}"><title>${dateLabel(d.date)}: P50 ${fmt(d.parking_demand_su_p50)} su; P10–P90 ${fmt(d.parking_demand_su_p10)}–${fmt(d.parking_demand_su_p90)} su; ${pct(d.prob_over_normal_capacity)} chance above normal capacity</title><rect class="hit" x="${L+i*step+2}" y="${T}" width="${step-4}" height="${plotH}"/></g>`;
  });
  svg+='</svg>';$('#parking-chart').innerHTML=svg;chartEvents($('#parking-chart'));
  const d=dayRow(),o=ordinaryRow();
  $('#parking-detail').textContent=`${dateLabel(state.day,true)}: game-week P50 ${fmt(d.parking_demand_su_p50)} su (P10–P90 ${fmt(d.parking_demand_su_p10)}–${fmt(d.parking_demand_su_p90)}); ordinary week P50 ${fmt(o.parking_demand_su_p50)} su. Chance over normal capacity ${pct(d.prob_over_normal_capacity)}; after proposed preparation ${pct(d.prob_over_prepared_capacity)}.`;
  $('#parking-table').innerHTML=table(['Day','Ordinary P50 su','Game P10 su','Game P50 su','Game P90 su','Normal su','Prepared su','P(over normal)','P(over prepared)'],rows.map((d,i)=>[dateLabel(d.date),fmt(ord[i].parking_demand_su_p50),fmt(d.parking_demand_su_p10),fmt(d.parking_demand_su_p50),fmt(d.parking_demand_su_p90),fmt(d.capacity_normal_su),fmt(d.capacity_prepared_su),pct(d.prob_over_normal_capacity),pct(d.prob_over_prepared_capacity)]));
}

function renderDay(){
  const d=dayRow(),f=forecastRow();
  $('#selected-day-heading').textContent=`${dateLabel(state.day,true)}${state.day===data.meta.game_day?' · Game day':state.day===data.meta.presidents_day?' · Presidents’ Day':''}`;
  const metrics=[['Landings, situation median',`${fmt(d.arrivals_p50)} aircraft`],['Departures, situation median',`${fmt(d.departures_p50)} aircraft`],['Parking P10 / P50 / P90',`${fmt(d.parking_demand_su_p10)} / ${fmt(d.parking_demand_su_p50)} / ${fmt(d.parking_demand_su_p90)} su`],['Normal / prepared capacity',`${fmt(d.capacity_normal_su)} / ${fmt(d.capacity_prepared_su)} su`],['Chance above normal',pct(d.prob_over_normal_capacity)]];
  $('#daily-detail').innerHTML=metrics.map(([label,value])=>`<div class="daily-metric"><span>${label}</span><strong class="${label==='Chance above normal'&&d.prob_over_normal_capacity>.5?'critical':''}">${value}</strong></div>`).join('');
  const names=[['light_jet','Light jet'],['midsize_jet','Midsize jet'],['large_jet','Large jet']];
  $('#size-detail').innerHTML=names.map(([key,name])=>`<div class="size-item"><div class="size-name">${name}</div><div class="size-values"><span><b>${fmt(f.by_aircraft_size[key].arrivals)}</b> landings</span><span><b>${fmt(f.by_aircraft_size[key].departures)}</b> departures</span></div></div>`).join('');
  renderWhatIf();
}

function renderWhatIf(){
  const d=dayRow(),capacity=d.capacity_normal_su+state.extraCapacity;
  $('#capacity-value').textContent=`+${fmt(state.extraCapacity)} su`;
  const range=capacity<d.parking_demand_su_p10?'Even P10 exceeds this capacity.':capacity<d.parking_demand_su_p50?'Capacity sits between P10 and P50.':capacity<d.parking_demand_su_p90?'Capacity sits between P50 and P90.':'Capacity meets or exceeds P90.';
  $('#what-if-result').textContent=`${fmt(capacity)} su total on ${dateLabel(state.day)}. ${range}`;
}

const decisionKey=(action)=>`${action.category==='pricing'?'pricing':state.variant}|${state.scenario}|${action.id}`;
function getDecisions(){try{return JSON.parse(localStorage.getItem('ramp27-decisions')||'{}')}catch{return {}}}
function saveDecision(key,record){const all=getDecisions();all[key]=record;localStorage.setItem('ramp27-decisions',JSON.stringify(all));}
function renderPlan(){
  const p=plan(),s=p.summary,u=p.aircraft_not_accommodated;
  $('#plan-summary').innerHTML=[['Normal ramp',`${fmt(s.normal_capacity_su)} su`,'Estimated available space'],['Proposed prepared',`${fmt(s.max_prepared_capacity_su)} su`,'Subject to approval'],['No plan → plan',`${fmt(u.no_plan.mean)} → ${fmt(u.with_plan.mean)}`,'Mean aircraft without space'],['Plan payoff chance',pct(p.prob_plan_pays_off),'Modelled, not guaranteed']].map(([label,value,note])=>`<div class="plan-stat"><span>${label}</span><strong>${value}</strong><small>${note}</small></div>`).join('');
  const records=getDecisions();
  const actions=[...p.actions,...data.slot_advisor.recommendations[state.scenario].actions];
  $('#plan-actions').innerHTML=actions.map((a,i)=>{
    const key=decisionKey(a),r=records[key];
    const pricing=a.category==='pricing';
    const dates=pricing?'Optional offer · Thu–Sun':`${dateLabel(a.dates[0])}–${dateLabel(a.dates.at(-1))}`;
    const cost=pricing?'Cost varies with take-up':money(a.cost_usd);
    return `<article class="action-card"><div class="action-top"><span class="action-no">PROPOSAL ${String(i+1).padStart(2,'0')} / ${pricing?'PRICE OFFER':'PARKING'}</span>${tag('estimated')}</div><h3>${esc(a.action)}</h3><div class="action-meta"><span>${esc(dates)}</span><span>${esc(cost)}</span><span>${esc(a.approver)} review</span></div><p>${esc(a.rationale)}</p>${pricing?'<p>This offer is separate from the parking-plan cost and effect above. Take-up is unknown.</p>':''}<div class="decision-form" data-action="${esc(a.id)}"><label for="name-${i}">Approver name · ${esc(a.approver)}</label><input id="name-${i}" name="name" autocomplete="name" required placeholder="Enter name" value="${esc(r?.name||'')}"><label for="note-${i}">Decision note</label><textarea id="note-${i}" name="note" required placeholder="Reason or change requested">${esc(r?.note||'')}</textarea><div class="decision-buttons"><button type="button" data-decision="approve">Approve proposal</button><button type="button" data-decision="request_changes">Request changes</button><button type="button" data-decision="reject">Reject proposal</button></div><p class="decision-state" role="status">${r?`<strong>${esc(r.status.replace('_',' '))}</strong> by ${esc(r.name)} · ${esc(new Date(r.timestamp).toLocaleString())}`:'Awaiting human decision'}</p></div></article>`;
  }).join('');
  $('#plan-actions').querySelectorAll('[data-decision]').forEach(btn=>btn.addEventListener('click',()=>{
    const form=btn.closest('.decision-form'),name=form.querySelector('[name=name]'),note=form.querySelector('[name=note]');
    if(!name.reportValidity()||!note.reportValidity())return;
    if(!name.value.trim()){name.setCustomValidity('Enter the approver name.');name.reportValidity();name.setCustomValidity('');return;}
    if(!note.value.trim()){note.setCustomValidity('Add a decision note.');note.reportValidity();note.setCustomValidity('');return;}
    const action=actions.find(a=>a.id===form.dataset.action);
    saveDecision(decisionKey(action),{scenario:state.scenario,variant:action.category==='pricing'?'all situations':state.variant,actionId:action.id,action:action.action,role:action.approver,name:name.value.trim(),note:note.value.trim(),status:btn.dataset.decision,timestamp:new Date().toISOString()});
    renderPlan();
  }));
}

function exportDecisions(){
  const payload={exportedAt:new Date().toISOString(),scope:'Parking proposal decisions only; this export does not activate actions.',decisions:Object.values(getDecisions())};
  const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download='ramp27-decisions.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

function renderAdvice(){
  const rec=data.slot_advisor.recommendations[state.scenario];
  const offer=rec.actions.find(a=>a.id==='drop_and_go_offer');
  $('#slot-advice').innerHTML=`${offer?`${esc(offer.action)}. ${tag('estimated')} This is a separate offer requiring ${esc(offer.approver)} approval; it is not part of the parking-plan cost above.`:'No price offer is recommended for this case.'}<br><br><strong>Why not discount early arrival?</strong> ${esc(rec.early_arrival_finding)}`;
  const rows=data.slot_advisor.rows.filter(r=>r.scenario===state.scenario && r.take_up>0);
  $('#slot-table').innerHTML=`<strong>Estimated effect if travellers take up an offer</strong><div class="table-scroll"><table>${table(['Offer','Take-up','Peak P50 su','Without space · mean','Net vs no offer'],rows.map(r=>[r.lever==='drop_and_go'?'Drop & go':'Early arrival',pct(r.take_up),fmt(r.peak_su_p50),fmt(r.unaccommodated_mean),money(r.net_vs_no_action_usd)]))}</table></div><small>Take-up is unknown; 10–30% are tested cases, not forecasts. Incentive figures are separate from parking-plan effects.</small>`;
}

function renderTrust(){
  $('#never-allowed').textContent=data.meta.never_allowed;
  const rows=data.accuracy.backtest.filter(r=>r.target==='arrivals'&&r.window==='all_2025_origins').sort((a,b)=>a.wape-b.wape),model=rows.find(r=>r.model==='model');
  $('#accuracy-head').textContent=`${pct(model.wape,1)} average error`;
  $('#accuracy-copy').textContent=`Rolling seven-day backtest across ${model.n} 2025 origins. The model's nominal 90% interval covered ${pct(model.coverage_90,1)} of evaluated days. WAPE is average daily error as a share of actual traffic; these tests do not prove Super Bowl accuracy.`;
  const labels={model:'Ramp / 27 model',weekday_mean_8w:'8-week weekday',seasonal_naive_last_year:'Same day last year',overall_mean:'Overall mean',naive_last_week:'Last week'};
  $('#accuracy-bars').innerHTML=rows.map(r=>`<div class="accuracy-row"><span>${labels[r.model]||esc(r.model)}</span><div class="accuracy-track"><span style="width:${r.wape/.24*100}%"></span></div><strong>${pct(r.wape,1)}</strong></div>`).join('');
  const eventRows=data.super_bowl_test.filter(r=>r.metric==='air_taxi'&&r.event!=='LVI_ALL6');
  const inRange=eventRows.filter(r=>['low_to_medium','medium_to_high','within_range'].includes(r.position)).length;
  $('#event-copy').textContent=`Across eight host-airport groups, ${inRange} air-taxi effect estimates fall inside the Low–High envelope. Other hosts differ sharply; the LAX 2022 observation anchors Medium, not a guarantee for 2027.`;
  $('#event-table').innerHTML=table(['Host / event','Airports','Excess vs control','Position'],eventRows.map(r=>[esc(r.event.replace('_',' ')),esc(r.airports),`${r.excess>=0?'+':''}${pct(r.excess,1)}`,esc(r.position.replaceAll('_',' '))]));
  const weather=data.weather.effects.filter(r=>r.category==='part91_general_aviation'&&['rain','heavy_rain','fog'].includes(r.weather_type));
  $('#weather-table').innerHTML=table(['Condition','Observed effect','95% interval','Days'],weather.map(r=>[esc(r.weather_type.replaceAll('_',' ')),`${r.effect>=0?'+':''}${pct(r.effect,1)}`,`${pct(r.ci_low,1)} to ${pct(r.ci_high,1)}`,whole(r.n_days)]));
  renderHistory();
  $('#assumptions').innerHTML=data.key_assumptions.map(a=>`<div class="assumption"><div class="assumption-name">${esc(a.name)} ${tag(a.class)}</div><p>${Array.isArray(a.value)?a.value.join(' / '):esc(a.value)} ${esc(a.unit||'')} ${a.note?`· ${esc(a.note)}`:''}</p></div>`).join('');
  $('#method-note').textContent=`Parking: ${data.parking.standard.method} Heavy-rain and delay variants are stress cases, not weather forecasts. The security restriction variant uses the same daily parking totals as normal operations; it changes timing constraints rather than the daily totals in this dataset.`;
  $('#sources').innerHTML=data.sources.map(s=>`<li><a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.name)} ↗</a></li>`).join('');
}

function renderHistory(){
  const months=new Map();
  data.history_daily_faa.forEach(r=>{const key=r.date.slice(0,7),m=months.get(key)||{key,n:0,p91:0,p135:0};m.n++;m.p91+=r.part91_general_aviation;m.p135+=r.part135_air_taxi;months.set(key,m);});
  const rows=[...months.values()].map(m=>({key:m.key,p91:m.p91/m.n,p135:m.p135/m.n}));
  const max=Math.max(...rows.flatMap(r=>[r.p91,r.p135]));
  $('#history-chart').innerHTML=rows.map(r=>`<div class="history-month" title="${esc(r.key)}: Part 91 ${fmt(r.p91)}, Part 135 ${fmt(r.p135)} daily average"><i style="height:${r.p91/max*100}%"></i><i style="height:${r.p135/max*100}%"></i></div>`).join('');
  $('#history-table').innerHTML=table(['Month','Part 91 / day','Part 135 / day'],rows.map(r=>[esc(r.key),fmt(r.p91),fmt(r.p135)]));
}

function renderRawData(){const section=$('#data-section').value;$('#raw-data').textContent=JSON.stringify(data[section],null,2);}

async function start(){
  initTheme();
  try{
    const response=await fetch('./fbo_data.json');if(!response.ok)throw new Error(`HTTP ${response.status}`);
    data=await response.json();
    initControls();render();renderTrust();
  }catch(error){
    $('#brief-headline').textContent='The dataset could not be loaded.';
    $('#brief-detail').textContent=`Serve this folder with python3 -m http.server. ${error.message}`;
    console.error(error);
  }
}
start();
