'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = n => new Intl.NumberFormat('en-US', {maximumFractionDigits:1}).format(n);
const money = n => new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(n);
const day = (date, options={month:'short',day:'numeric'}) => new Date(date+'T12:00:00-08:00').toLocaleDateString('en-US',{...options,timeZone:'America/Los_Angeles'});
const names = {low:'Lower',medium:'Expected',high:'Higher'};
const roles = {manager:'FBO manager',reservations:'Reservations coordinator',operations:'Operations supervisor'};
const decisions = {approved:'Approved for planning',changes_requested:'Changes requested',rejected:'Rejected'};
const fields = {parking_units:'Parking demand',capacity_units:'On-site capacity',prepared_capacity_units:'Proposed total capacity',staff_required:'Staff required',staff_available:'Staff available',prepared_staff:'Proposed staffing',fuel_gallons:'Fuel demand (gal)',fuel_available_gallons:'Fuel available (gal)',preparation_cost:'Preparation cost ($)',parking_p90:'Parking P90'};
const state = {profile:null,csrf:null,data:null,scenario:'medium',variant:'standard',date:'2027-02-14',view:'overview',review:null,chart:'parking'};
let toastTimer;
function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,5000);}
function error(message){$('global-error').textContent=message;$('global-error').hidden=!message;}
async function api(path,body){
 const response=await fetch(path,{credentials:'same-origin',method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json','X-CSRF-Token':state.csrf||''},body:body===undefined?undefined:JSON.stringify(body)});
 let data;try{data=await response.json();}catch{throw new Error('The server returned an unreadable response. Check that the local app is running.');}
 if(!response.ok)throw new Error(data.error||'The request could not be completed.');return data;
}
async function busy(button,work){const old=button.textContent;button.disabled=true;button.textContent='Working…';try{await work();}finally{button.textContent=old;button.disabled=false;}}
function showView(view){
 if(!['overview','evidence','history'].includes(view))view='overview';state.view=view;
 document.querySelectorAll('.view').forEach(el=>el.hidden=el.id!=='view-'+view);
 document.querySelectorAll('[data-view]').forEach(el=>{el.classList.toggle('selected',el.dataset.view===view);el.setAttribute('aria-current',el.dataset.view===view?'page':'false');});
 history.replaceState(null,'','#'+view);
}
async function enter(session){state.profile=session.profile;state.csrf=session.csrf;state.data=await api('/api/dashboard');$('login').hidden=true;$('workspace').hidden=false;render();showView(location.hash.slice(1)||'overview');}
function currentRows(){return state.data.bundle.resources.filter(r=>r.scenario===state.scenario&&r.variant===state.variant).sort((a,b)=>a.date.localeCompare(b.date));}
function latestReview(id){return state.data.history.find(r=>!r.stale&&r.scenario===state.scenario&&r.variant===state.variant&&r.recommendation_id===id);}
function render(){
 const {profile,data}=state;const b=data.bundle;const manager=profile.role==='manager';
 $('avatar').textContent=profile.initials;$('employee-name').textContent=profile.name;$('employee-role').textContent=profile.position+' · demo';
 $('greeting').textContent=`${profile.name.split(' ')[0]}, start with the capacity gap. Then review the preparations your team needs.`;
 $('org-name').textContent=b?.meta.fbo_name||'No valid dataset loaded';
 $('sample-notice').hidden=!b||data.source!=='sample';
 $('use-team-overview').disabled=!manager;
 $('source-badge').textContent=b?`${b.meta.data_classification==='synthetic'?'Synthetic':b.meta.data_classification==='mixed'?'Mixed inputs':'Producer-labelled observed'} · ${data.source==='sample'?'sample demonstration':['team','team-native'].includes(data.source)?'team outputs':'imported bundle'}`:'Inputs unavailable';
 $('review-count').textContent=data.history.length;
 $('no-data').hidden=!!b;$('dashboard-content').hidden=!b;$('export').disabled=!b||!!data.input_status?.stale;
 $('no-data-reason').textContent=data.load_error||'Load a valid complete output bundle.';
 $('version-footer').textContent=b?'Dataset '+b.version.slice(0,10):'No active version';
 ['load-contract','load-team','load-sample','refresh-source','import-files','bundle-files'].forEach(id=>$(id).disabled=!manager);
 $('data-permission').textContent=manager?'Manager demo role: you can load validated inputs and record reviews.':'This demo role can inspect plans. Switch to the manager demo role to change inputs or record a review.';
 if(b){
  if(!b.variants.includes(state.variant))state.variant='standard';
  $('stress-toggle').disabled=!b.variants.includes('departure_delay_24h');$('stress-toggle').checked=state.variant==='departure_delay_24h';
  $('stress-description').textContent=$('stress-toggle').disabled?'No delay output supplied by resource module':b.delay_definition?`${fmt(b.delay_definition.share*100)}% of departures from ${day(b.delay_definition.start_date)} shift one day`:'Uses a separate supplied resource scenario';
  document.querySelectorAll('[data-scenario]').forEach(el=>{const selected=el.dataset.scenario===state.scenario;el.classList.toggle('selected',selected);el.setAttribute('aria-pressed',selected);});
  renderOverview();
 }
 renderEvidence();renderHistory();renderReleaseStatus();
}
function renderReleaseStatus(){
 const b=state.data?.bundle,review=b?.release_review,stale=state.data?.input_status?.stale;
 const banner=$('release-banner');banner.hidden=!(stale||review||(b&&state.data.source!=='sample'));
 if(banner.hidden)return;
 const title=stale?'Displayed plan is out of date':review?.label||'Provisional inputs — review not recorded';
 const message=stale?state.data.input_status.message:review?.message||'Source classification does not establish team approval. Review this dataset before presenting it as the agreed forecast.';
 banner.innerHTML=`<div class="release-heading"><strong>${esc(title)}</strong><button class="text-button" data-goto="evidence">${stale?'Inspect & refresh inputs':'Inspect assumptions'} →</button></div>${stale?`<p>${esc(message)}</p>`:`<details><summary>What this means</summary><p>${esc(message)}</p>${review?.run_id?`<small>Release ${esc(review.run_id.slice(0,12))} · file hashes matched · human review remains separate</small>`:''}</details>`}`;
}
function renderOverview(){
 const b=state.data.bundle,s=state.data.summaries[state.scenario][state.variant],rows=currentRows();
 const shortage=s.peak_shortfall>0;
 const peakDay=rows.reduce((peak,row)=>row.parking_units>peak.parking_units?row:peak,rows[0]);
 $('hero-risk').hidden=!b.native;
 $('hero-risk').textContent=b.native?`Remaining uncertainty: on ${day(peakDay.date)}, simulated demand exceeds proposed capacity in ${fmt(peakDay.prob_over_prepared*100)}% of runs. This is not a validated event probability.`:'';
 $('peak-label').textContent=b.native?'Peak parking need · median':'Parking needed at peak';
 $('gap-label').textContent=b.native?'Gap after preparation · median':'Uncovered after proposed plan';
 $('hero-kicker').textContent=shortage?'Preparation needed':'Capacity outlook';
 $('hero-title').textContent=shortage?`Prepare for a ${fmt(s.peak_shortfall)}-unit parking gap.`:'Median demand fits on-site capacity.';
 $('hero-description').textContent=shortage?`Demand first exceeds on-site capacity on ${day(s.first_shortage,{weekday:'long',month:'short',day:'numeric'})}. ${s.remaining_shortfall>0?`The proposed plan still leaves up to ${fmt(s.remaining_shortfall)} units uncovered.`:'The proposed capacity covers the modelled gap if those resources are confirmed.'}`:'Keep checking bookings and departure plans. These estimates are conditional on the supplied assumptions.';
 if(b.native)$('hero-description').textContent+=' This is a median planning estimate; higher demand can still exceed capacity.';
 $('peak').textContent=fmt(s.peak_demand);$('capacity').textContent=fmt(s.capacity_at_peak);$('remaining').textContent=fmt(s.remaining_shortfall);
 $('role-task').textContent={manager:'Your role: verify resources and record the team’s planning decisions.',reservations:'Your role: verify booking estimates and planned departure times.',operations:'Your role: check usable parking capacity and ground-team readiness.'}[state.profile.role];
 renderChart();
 $('week-table').innerHTML=`<table><thead><tr><th>Date</th><th>Ordinary parking</th><th>${b.native?'Event P50':'Event peak'}</th><th>On-site capacity</th><th>Proposed total</th><th>Remaining gap</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${day(r.date)}</td><td>${b.baseline.find(x=>x.date===r.date).parking_units===null?'Not supplied':fmt(b.baseline.find(x=>x.date===r.date).parking_units)}</td><td>${fmt(r.parking_units)}</td><td>${fmt(r.capacity_units)}</td><td>${fmt(r.prepared_capacity_units)}</td><td>${fmt(Math.max(0,r.parking_units-r.prepared_capacity_units))}</td></tr>`).join('')}</tbody></table>`;
 renderDay();
 renderCarryover();
 $('impact-days').textContent=`${s.days_over_capacity} → ${s.remaining_days}`;$('impact-gap').textContent=`${fmt(s.peak_shortfall)} → ${fmt(s.remaining_shortfall)}`;$('impact-cost').textContent=money(s.preparation_cost);
 const impact=b.impacts_by_variant?.[state.variant]?.[state.scenario] ?? b.impacts?.[state.scenario];
 $('simulation-impact').hidden=!impact;
 if(impact){
  const measures=[['Aircraft unaccommodated · simulated mean','unaccommodated_aircraft',fmt],['Delayed turns · simulated mean','delayed_turns',fmt],['Total modeled cost · simulated mean','total_cost_usd',money]];
  $('simulation-impact').innerHTML=`<h3>What does preparation change?</h3><p>Conditional comparison across ${fmt(impact.runs)} simulated weeks. These are model results, not measured savings.</p><table><thead><tr><th>Weekly outcome</th><th>No preparation</th><th>Proposed preparation</th></tr></thead><tbody>${measures.map(([label,key,format])=>`<tr><td>${esc(label)}</td><td>${format(impact.no_preparation[key].mean)}</td><td>${format(impact.ai_preparation[key].mean)}</td></tr>`).join('')}<tr><td>Simulated chance of any unaccommodated aircraft</td><td>${fmt(impact.no_preparation.prob_any_unaccommodated*100)}%</td><td>${fmt(impact.ai_preparation.prob_any_unaccommodated*100)}%</td></tr></tbody></table><p>Modeled net benefit: median <strong>${money(impact.net_benefit_usd.p50)}</strong>; P10–P90 ${money(impact.net_benefit_usd.p10)} to ${money(impact.net_benefit_usd.p90)}. Preparation pays off in ${fmt(impact.prob_preparation_pays_off*100)}% of simulations.</p><p class="fine">Negative net benefit means preparation costs exceed the modeled avoided losses. Cost assumptions are in the evidence tab. This is separate from the daily median parking-gap comparison above.</p>`;
 }
 $('plan-notice').textContent=s.remaining_shortfall>0?`Capacity is still insufficient on ${s.remaining_days} day(s). Escalate the unresolved gap to the FBO manager; this app cannot approve additional parking or reroute aircraft.`:'Proposed resources are not confirmed. This comparison assumes they are available and suitable on the dates supplied.';
 if(b.native)$('plan-notice').textContent+=' Comparison uses daily P50 parking demand, not a guarantee. Inspect the P10–P90 range and exceedance risk for each day. Cost is P3’s weekly action total.';
 const recs=b.recommendations.filter(r=>r.scenario===state.scenario&&r.variant===state.variant);
 $('actions').innerHTML=recs.length?recs.map((r,i)=>{
  const review=latestReview(r.id);
  return `<article class="action"><span class="action-number">${i+1}</span><div><h3>${esc(r.title)}</h3><p>${esc(r.reason)}</p><div class="action-meta"><span>Owner: ${esc(roles[r.owner])}</span><span>Review by ${esc(day(r.due_date))}</span><span>Source: ${esc(r.source)}</span></div><div>${r.evidence.map(e=>`<span class="evidence-chip">${esc(day(e.date))} · ${esc(fields[e.field])}: ${fmt(e.value)}</span>`).join('')}</div></div><div class="action-control"><small>${review?esc(decisions[review.decision]):'Awaiting human review'}</small><button class="secondary" data-review="${esc(r.id)}" ${state.profile.role==='manager'&&!state.data.input_status?.stale?'':'disabled'}>${review?'Review again':'Review action'} →</button></div></article>`;
 }).join(''):'<p class="empty">No recommendations were supplied for this scenario. Ask the resource module owner for preparation advice.</p>';
 $('support-values').innerHTML=`<div class="support-values"><div><strong>${fmt(s.max_staff)}</strong><small>${b.native?'Peak proposed technicians per shift':'Peak people required'}</small></div><div><strong>${fmt(s.total_fuel)}</strong><small>Week’s fuel estimate · gal</small></div></div>`;
 $('uncertainty-copy').textContent=b.meta.interval_description+' '+(b.meta.data_classification==='synthetic'?'These synthetic outputs demonstrate the workflow; they do not establish forecast accuracy.':'Estimated inputs measure assumed traffic, not observed FBO accuracy. Source and model descriptions require review with the model owner.');
}
function renderChart(){
 const b=state.data.bundle,parking=state.chart==='parking',rs=currentRows();
 $('ordinary-legend').hidden=parking&&b.baseline.every(r=>r.parking_units===null);$('capacity-legend').hidden=!parking;
 const points=rs.map(r=>{const base=b.baseline.find(x=>x.date===r.date),d=b.demand.find(x=>x.date===r.date&&x.scenario===state.scenario);return {date:r.date,ordinary:parking?base.parking_units:base.arrivals,value:parking?r.parking_units:d.arrivals,capacity:parking?r.capacity_units:null};});
 const scale=Math.max(1,...points.map(r=>Math.max(r.value,r.capacity||0,r.ordinary||0)))*1.17;
 document.querySelectorAll('[data-chart]').forEach(el=>{el.classList.toggle('selected',el.dataset.chart===state.chart);el.setAttribute('aria-pressed',el.dataset.chart===state.chart);});
 $('chart-basis').textContent=parking&&b.native?(b.carryover?`P3 ordinary vs ${state.variant==='standard'?'standard event':'delayed event'} daily P50 peaks · space units`:'P3 simulated P50 peaks · ordinary parking not supplied'):parking?'Daily peak parking units':'P2 ordinary baseline vs event arrival point estimates';
 $('chart-caption').textContent=parking?'Parking units · select a day':'Aircraft arrivals per day · select a day';
 $('chart').innerHTML=points.map(r=>{
  const selected=r.date===state.date;
  return `<button class="day ${selected?'selected':''}" data-day="${r.date}" aria-pressed="${selected}" aria-label="${esc(day(r.date))}: ordinary ${r.ordinary===null?'not supplied':fmt(r.ordinary)}, event ${fmt(r.value)}${parking?', capacity '+fmt(r.capacity)+' parking units':' arrivals'}"><span class="bars">${r.capacity!==null?`<span class="cap-line" style="bottom:${r.capacity/scale*100}%"></span>`:''}${r.ordinary!==null?`<span class="bar" style="height:${r.ordinary/scale*100}%"></span>`:''}<span class="bar event" style="height:${r.value/scale*100}%"><b>${fmt(r.value)}</b></span></span><span class="day-label">${day(r.date,{weekday:'short'})}<strong>${day(r.date)}${r.date==='2027-02-14'?' · Game':''}</strong></span></button>`;
 }).join('');
}
function renderDay(){
 const b=state.data.bundle,r=currentRows().find(x=>x.date===state.date),d=b.demand.find(x=>x.scenario===state.scenario&&x.date===state.date);if(!r||!d)return;
 $('day-detail').innerHTML=`<div class="day-summary"><small>SELECTED DAY</small><strong>${esc(day(r.date,{weekday:'long',month:'short',day:'numeric'}))}</strong></div><div><small>Arrival estimate · ${state.variant==='standard'?'standard':'original demand input'}</small><strong>${fmt(d.arrivals)}</strong> <small>${b.native?'P2 category point forecasts summed':`Supplied range ${fmt(d.arrivals_lower)}–${fmt(d.arrivals_upper)}`}</small></div><div><small>${b.native?'Simulated departures · '+(state.variant==='standard'?'standard':'24-hour delay'):'Planned departures · before delay'}</small><strong>${fmt(b.native?r.departures_p50:d.departures)}</strong>${b.native?`<small>Daily P50 · original P2 estimate ${fmt(d.departures)}</small>`:''}</div><div><small>${b.native?'P50 gap':'Gap'} after proposed capacity</small><strong>${fmt(Math.max(0,r.parking_units-r.prepared_capacity_units))} units</strong></div>`;
 $('category-detail').innerHTML=b.native?`<div class="native-risk"><strong>Parking P10–P90: ${fmt(r.parking_p10)}–${fmt(r.parking_p90)} units</strong><span>Simulated probability of exceeding proposed capacity: ${fmt(r.prob_over_prepared*100)}%</span><small>Unvalidated event-week model outputs. P50 is the median of simulations, not a safe capacity limit.</small></div><details class="inline-details"><summary>Inspect arrival ranges by aircraft category and staffing by shift</summary><table><thead><tr><th>Category</th><th>P2 arrival estimate</th><th>Event planning range · unvalidated</th></tr></thead><tbody>${b.category_ranges.filter(x=>x.date===state.date&&x.scenario===state.scenario&&x.direction==='arrivals').map(x=>`<tr><td>${esc(x.category.replace('_',' '))}</td><td>${fmt(x.expected)}</td><td>${fmt(x.lower)}–${fmt(x.upper)}</td></tr>`).join('')}</tbody></table>${renderForecastDrivers()}<p>Do not sum category interval endpoints into a total interval. Event-week coverage is unvalidated.</p><p>Proposed technicians by shift: morning ${fmt(r.staff_shifts.morning)}, day ${fmt(r.staff_shifts.day)}, night ${fmt(r.staff_shifts.night)}. Ordinary staffing: ${fmt(r.staff_available)} per shift.</p></details>`:'';
}
function renderCarryover(){
 const b=state.data.bundle,rows=(b.carryover||[]).filter(r=>r.variant==='ordinary'||(r.variant===state.variant&&r.scenario===state.scenario));
 $('carryover').hidden=!rows.length;
 if(!rows.length)return;
 const metrics=[['Opening aircraft',r=>fmt(r.opening_aircraft)],['Remaining aircraft · P50',r=>fmt(r.aircraft_remaining_p50)],['Remaining aircraft · P10–P90',r=>`${fmt(r.aircraft_remaining_p10)}–${fmt(r.aircraft_remaining_p90)}`],['Remaining space units · P50',r=>fmt(r.parking_su_remaining_p50)],['Departures shifted beyond window · P50',r=>fmt(r.departures_pushed_past_window_p50)]];
 $('carryover').innerHTML=`<h3>Demand remaining after February 17</h3><p>Unconstrained simulation: aircraft that would remain if parking were unlimited. These are not confirmed on-site counts.</p><table><thead><tr><th>Measure</th>${rows.map(r=>`<th>${r.variant==='ordinary'?'Ordinary':state.variant==='standard'?'Event · standard':'Event · 24-hour delay'}</th>`).join('')}</tr></thead><tbody>${metrics.map(([label,format])=>`<tr><td>${label}</td>${rows.map(r=>`<td>${format(r)}</td>`).join('')}</tr>`).join('')}</tbody></table><p class="fine">Aircraft counts and size-weighted space units are different quantities. Departures shifted beyond the window are a scheduled flow, not another inventory to add to remaining aircraft.</p>`;
}
function renderForecastDrivers(){
 const b=state.data.bundle;
 return b.forecast_drivers.filter(x=>x.date===state.date&&x.scenario===state.scenario&&x.direction==='arrivals').map(x=>`<p><strong>${esc(x.category.replaceAll('_',' '))}</strong>: event multiplier ${fmt(x.multiplier)}×; reservation floor ${fmt(x.reservation_floor)} (${esc(x.reservation_class)}). Source: ${esc(x.source)}</p>`).join('');
}
function renderEvidence(){
 const {data}=state,b=data.bundle;
 const ref=data.alan_reference;
 $('alan-reference').innerHTML=`<h2>Alan’s ordinary-week reference</h2><p>${esc(ref?.message||'Reference not supplied.')}</p>${ref?.available?`<div class="table-scroll"><table><thead><tr><th>Date</th><th>Estimated arrivals</th><th>Estimated departures</th><th>Estimated parked aircraft</th></tr></thead><tbody>${ref.rows.map(r=>`<tr><td>${esc(day(r.date))}</td><td>${fmt(r.arrivals)}</td><td>${fmt(r.departures)}</td><td>${fmt(r.parking_units)}</td></tr>`).join('')}</tbody></table></div>${ref.assumptions.map(a=>`<p class="fine"><strong>${esc(a.label)}:</strong> ${esc(a.value)}. ${esc(a.note)}</p>`).join('')}`:''}`;
 $('dataset-version').textContent=b?'Version '+b.version.slice(0,10):'No active version';
 $('connection-list').innerHTML=(data.source==='team'?data.team_files:(data.native_files||data.team_files)).map(f=>`<div class="connection"><div><strong>${esc(f.file)}</strong><small>${esc(f.path)}</small></div><span class="${f.present?'':'missing'}">${f.present?'File found':'Not supplied'}</span></div>`).join('');
 $('evidence-meta').innerHTML=b?`<h2>Active dataset</h2><dl>${[['Dataset',b.meta.dataset_name],['Source',data.source],['Classification',b.meta.data_classification+' (declared by producer)'],['Operator',b.meta.fbo_name+' · '+b.meta.airport],['Model version',b.meta.model_version],['Generated',b.meta.generated_at],['Uncertainty',b.meta.interval_kind+' — '+b.meta.interval_description],['Window',b.meta.window_start+' to '+b.meta.window_end+' · '+b.meta.timezone],['Notes',b.meta.notes]].map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>`:'<p>No dataset is active. Inspect the loading error and supply all required files.</p>';
 $('forecast-evaluation').hidden=!b?.native;
 if(b?.native)$('forecast-evaluation').innerHTML=`<h2>Forecast evaluation · ordinary historical weeks</h2><p>These are producer-reported holdout results. Performance against estimated or synthetic inputs does not establish observed FBO accuracy or validate the Super Bowl uplift.</p><div class="table-scroll"><table><thead><tr><th>Category / direction</th><th>Data / scope</th><th>Model MAE</th><th>Baseline MAE</th><th>90% interval coverage</th><th>Test observations</th></tr></thead><tbody>${b.forecast_metrics.map(m=>`<tr><td>${esc(m.aircraft_category)} / ${esc(m.direction)}</td><td>${esc(m.evaluation_data)} / ${esc(m.scope)}</td><td>${m.model_mae.toFixed(3)}</td><td>${m.baseline_mae.toFixed(3)}</td><td>${fmt(m.interval_coverage90*100)}%</td><td>${fmt(m.n_test)}</td></tr>`).join('')}</tbody></table></div><p class="fine">MAE = mean absolute error; smaller is better. Historical coverage is separate from event-week prediction ranges.</p>`;
 $('assumptions').innerHTML=b?`<table><thead><tr><th>Assumption</th><th>Value</th><th>Classification</th><th>Source</th><th>Note</th></tr></thead><tbody>${b.assumptions.map(a=>`<tr><td>${esc(a.label)}</td><td>${esc(a.value)} ${esc(a.unit)}</td><td>${esc(a.classification)}</td><td>${esc(a.source)}</td><td>${esc(a.note)}</td></tr>`).join('')}</tbody></table>`:'';
}
function renderHistory(){
 $('history-list').innerHTML=state.data.history.length?state.data.history.map(r=>`<article class="history-item"><span class="pill">${r.stale?'PREVIOUS DATASET':'CURRENT DATASET'}</span><h3>${esc(decisions[r.decision])}</h3><small>${esc(r.recommendation_id)} · ${esc(names[r.scenario])} demand · ${r.variant==='standard'?'Standard departures':'24-hour departure delay'}</small><p>${esc(r.note)}</p><small>${esc(r.reviewer)} · ${esc(new Date(r.reviewed_at).toLocaleString())} · Input ${esc(r.version.slice(0,10))}${r.stale?' · Does not apply to the active data':''}</small></article>`).join(''):'<div class="empty"><h3>No decisions recorded yet.</h3><p>Review a proposed preparation as the manager to start the record.</p></div>';
}
function openReview(id){
 const b=state.data.bundle,r=b.recommendations.find(r=>r.id===id&&r.scenario===state.scenario&&r.variant===state.variant);if(!r||state.profile.role!=='manager')return;
 state.review={version:b.version,scenario:state.scenario,variant:state.variant,recommendation_id:r.id};
 $('review-form').reset();$('review-checks').hidden=false;$('review-error').textContent='';$('review-title').textContent=r.title;$('review-reason').textContent=r.reason;$('review-dialog').showModal();
}
async function changeSource(source,files){
 $('source-result').hidden=true;
 try{error('');state.data=await api(files?'/api/import':'/api/source',files?{files}:{source});render();$('source-result').textContent='Validated and loaded. Reviews from a different dataset version are marked as previous.';$('source-result').classList.remove('error');toast('Dataset loaded successfully.');}
 catch(e){error(e.message+' The previous dataset has been kept.');$('source-result').textContent=e.message+' The previously active dataset has been kept.';$('source-result').classList.add('error');}
 $('source-result').hidden=false;
}
$('login-form').addEventListener('submit',async e=>{e.preventDefault();$('login-error').textContent='';await busy(e.submitter,async()=>{try{await enter(await api('/api/login',{role:$('profile-select').value}));}catch(e){$('login-error').textContent=e.message;}});});
$('logout').addEventListener('click',async()=>{try{await api('/api/logout',{});state.profile=null;state.csrf=null;$('workspace').hidden=true;$('login').hidden=false;error('');}catch(e){error(e.message);}});
document.addEventListener('click',e=>{
 const el=e.target.closest('button');if(!el)return;
 if(el.dataset.view)showView(el.dataset.view);if(el.dataset.goto)showView(el.dataset.goto);
 if(el.dataset.scenario){state.scenario=el.dataset.scenario;render();}
 if(el.dataset.chart){state.chart=el.dataset.chart;renderOverview();}
 if(el.dataset.day){state.date=el.dataset.day;renderOverview();}
 if(el.dataset.review)openReview(el.dataset.review);
});
$('stress-toggle').addEventListener('change',e=>{state.variant=e.target.checked?'departure_delay_24h':'standard';render();});
$('go-plan').addEventListener('click',()=>$('preparations').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'}));
$('close-review').addEventListener('click',()=>$('review-dialog').close());
$('decision').addEventListener('change',()=>$('review-checks').hidden=$('decision').value!=='approved');
$('review-form').addEventListener('submit',async e=>{e.preventDefault();$('review-error').textContent='';await busy($('save-review'),async()=>{
 try{const result=await api('/api/review',{...state.review,decision:$('decision').value,note:$('review-note').value,checks:{assumptions:$('check-assumptions').checked,availability:$('check-availability').checked,cost:$('check-cost').checked}});state.data.history=result.history;$('review-dialog').close();render();toast('Planning decision recorded. No operational action was sent.');}
 catch(e){$('review-error').textContent=e.message;}
 });});
$('use-team-overview').addEventListener('click',e=>busy(e.currentTarget,()=>changeSource('team-native')));
$('load-team').addEventListener('click',e=>busy(e.currentTarget,()=>changeSource('team-native')));
$('load-contract').addEventListener('click',e=>busy(e.currentTarget,()=>changeSource('team')));
$('load-sample').addEventListener('click',e=>busy(e.currentTarget,()=>changeSource('sample')));
$('refresh-source').addEventListener('click',e=>busy(e.currentTarget,()=>changeSource(state.data.source)));
$('import-files').addEventListener('click',e=>busy(e.currentTarget,async()=>{
 const chosen=[...$('bundle-files').files];
 if(chosen.length!==7||new Set(chosen.map(f=>f.name)).size!==7){$('source-result').hidden=false;$('source-result').textContent='Select exactly seven files with distinct names, matching the documented contract.';return;}
 if(chosen.some(f=>f.size>2000000)||chosen.reduce((sum,f)=>sum+f.size,0)>4500000){$('source-result').hidden=false;$('source-result').textContent='Files are too large. Keep each below 2 MB and the bundle below 4.5 MB.';return;}
 try{const files=Object.fromEntries(await Promise.all(chosen.map(async f=>[f.name,await f.text()])));await changeSource('import',files);}catch(e){$('source-result').hidden=false;$('source-result').textContent=e.message;}
}));
$('export').addEventListener('click',async()=>{try{const response=await fetch('/api/export?'+new URLSearchParams({scenario:state.scenario,variant:state.variant}),{credentials:'same-origin'});if(!response.ok){const result=await response.json();throw new Error(result.error);}const url=URL.createObjectURL(await response.blob()),a=document.createElement('a');a.href=url;a.download='readiness-plan.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){error(e.message);}});
window.addEventListener('hashchange',()=>{if(state.profile)showView(location.hash.slice(1));});
(async()=>{try{const session=await api('/api/session');if(session.profile)await enter(session);}catch(e){$('login-error').textContent=e.message;}})();

// Refresh status from the server; source files are never silently activated.
setInterval(async()=>{
 if(!state.profile||document.hidden||$('review-dialog').open)return;
 try{const next=await api('/api/dashboard');if(JSON.stringify(next)!==JSON.stringify(state.data)){state.data=next;render();}}catch(e){error('Could not refresh input status: '+e.message);}
},30000);
