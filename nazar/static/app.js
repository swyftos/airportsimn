'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = n => new Intl.NumberFormat('en-US', {maximumFractionDigits:1}).format(n);
const money = n => new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(n);
const day = (date, options={month:'short',day:'numeric'}) => new Date(date+'T12:00:00-08:00').toLocaleDateString('en-US',{...options,timeZone:'America/Los_Angeles'});
const names = {low:'Lower',medium:'Expected',high:'Higher'};
const roles = {manager:'FBO manager',reservations:'Reservations coordinator',operations:'Operations supervisor'};
const decisions = {approved:'Approved for planning',changes_requested:'Changes requested',rejected:'Rejected'};
const fields = {parking_units:'Parking demand',capacity_units:'On-site capacity',prepared_capacity_units:'Proposed total capacity',staff_required:'Staff required',staff_available:'Staff available',prepared_staff:'Proposed staffing',fuel_gallons:'Fuel demand (gal)',fuel_available_gallons:'Fuel available (gal)',preparation_cost:'Preparation cost ($)'};
const state = {profile:null,csrf:null,data:null,scenario:'medium',variant:'standard',date:'2027-02-14',view:'overview',review:null};
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
 $('source-badge').textContent=b?`${b.meta.data_classification==='synthetic'?'Synthetic':b.meta.data_classification==='mixed'?'Mixed inputs':'Producer-labelled observed'} · ${data.source==='sample'?'sample demonstration':data.source==='team'?'team outputs':'imported bundle'}`:'Inputs unavailable';
 $('review-count').textContent=data.history.length;
 $('no-data').hidden=!!b;$('dashboard-content').hidden=!b;$('export').disabled=!b;
 $('no-data-reason').textContent=data.load_error||'Load a valid complete output bundle.';
 $('version-footer').textContent=b?'Dataset '+b.version.slice(0,10):'No active version';
 ['load-team','load-sample','refresh-source','import-files','bundle-files'].forEach(id=>$(id).disabled=!manager);
 $('data-permission').textContent=manager?'Manager demo role: you can load validated inputs and record reviews.':'This demo role can inspect plans. Switch to the manager demo role to change inputs or record a review.';
 if(b){
  if(!b.variants.includes(state.variant))state.variant='standard';
  $('stress-toggle').disabled=!b.variants.includes('departure_delay_24h');$('stress-toggle').checked=state.variant==='departure_delay_24h';
  $('stress-description').textContent=$('stress-toggle').disabled?'No delay output supplied by resource module':'Uses a separate supplied resource scenario';
  document.querySelectorAll('[data-scenario]').forEach(el=>{const selected=el.dataset.scenario===state.scenario;el.classList.toggle('selected',selected);el.setAttribute('aria-pressed',selected);});
  renderOverview();
 }
 renderEvidence();renderHistory();
}
function renderOverview(){
 const b=state.data.bundle,s=state.data.summaries[state.scenario][state.variant],rows=currentRows();
 const shortage=s.peak_shortfall>0;
 $('hero-kicker').textContent=shortage?'Preparation needed':'Capacity outlook';
 $('hero-title').textContent=shortage?`Prepare for a ${fmt(s.peak_shortfall)}-unit parking gap.`:'Your forecast fits on-site capacity.';
 $('hero-description').textContent=shortage?`Demand first exceeds on-site capacity on ${day(s.first_shortage,{weekday:'long',month:'short',day:'numeric'})}. ${s.remaining_shortfall>0?`The proposed plan still leaves up to ${fmt(s.remaining_shortfall)} units uncovered.`:'The proposed capacity covers the modelled gap if those resources are confirmed.'}`:'Keep checking bookings and departure plans. These estimates are conditional on the supplied assumptions.';
 $('peak').textContent=fmt(s.peak_demand);$('capacity').textContent=fmt(s.capacity_at_peak);$('remaining').textContent=fmt(s.remaining_shortfall);
 $('role-task').textContent={manager:'Your role: verify resources and record the team’s planning decisions.',reservations:'Your role: verify booking estimates and planned departure times.',operations:'Your role: check usable parking capacity and ground-team readiness.'}[state.profile.role];
 const scale=Math.max(...rows.map(r=>Math.max(r.parking_units,r.capacity_units)),...b.baseline.map(r=>r.parking_units))*1.17;
 $('chart').innerHTML=rows.map(r=>{
  const base=b.baseline.find(x=>x.date===r.date),selected=r.date===state.date;
  return `<button class="day ${selected?'selected':''}" data-day="${r.date}" aria-pressed="${selected}" aria-label="${esc(day(r.date))}: ordinary ${fmt(base.parking_units)}, event ${fmt(r.parking_units)}, capacity ${fmt(r.capacity_units)} parking units"><span class="bars"><span class="cap-line" style="bottom:${r.capacity_units/scale*100}%"></span><span class="bar" style="height:${base.parking_units/scale*100}%"></span><span class="bar event" style="height:${r.parking_units/scale*100}%"><b>${fmt(r.parking_units)}</b></span></span><span class="day-label">${day(r.date,{weekday:'short'})}<strong>${day(r.date)}${r.date==='2027-02-14'?' · Game':''}</strong></span></button>`;
 }).join('');
 $('week-table').innerHTML=`<table><thead><tr><th>Date</th><th>Ordinary peak</th><th>Event peak</th><th>On-site capacity</th><th>Proposed total</th><th>Remaining gap</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${day(r.date)}</td><td>${fmt(b.baseline.find(x=>x.date===r.date).parking_units)}</td><td>${fmt(r.parking_units)}</td><td>${fmt(r.capacity_units)}</td><td>${fmt(r.prepared_capacity_units)}</td><td>${fmt(Math.max(0,r.parking_units-r.prepared_capacity_units))}</td></tr>`).join('')}</tbody></table>`;
 renderDay();
 $('impact-days').textContent=`${s.days_over_capacity} → ${s.remaining_days}`;$('impact-gap').textContent=`${fmt(s.peak_shortfall)} → ${fmt(s.remaining_shortfall)}`;$('impact-cost').textContent=money(s.preparation_cost);
 $('plan-notice').textContent=s.remaining_shortfall>0?`Capacity is still insufficient on ${s.remaining_days} day(s). Escalate the unresolved gap to the FBO manager; this app cannot approve additional parking or reroute aircraft.`:'Proposed resources are not confirmed. This comparison assumes they are available and suitable on the dates supplied.';
 const recs=b.recommendations.filter(r=>r.scenario===state.scenario&&r.variant===state.variant);
 $('actions').innerHTML=recs.length?recs.map((r,i)=>{
  const review=latestReview(r.id);
  return `<article class="action"><span class="action-number">${i+1}</span><div><h3>${esc(r.title)}</h3><p>${esc(r.reason)}</p><div class="action-meta"><span>Owner: ${esc(roles[r.owner])}</span><span>Review by ${esc(day(r.due_date))}</span><span>Source: ${esc(r.source)}</span></div><div>${r.evidence.map(e=>`<span class="evidence-chip">${esc(day(e.date))} · ${esc(fields[e.field])}: ${fmt(e.value)}</span>`).join('')}</div></div><div class="action-control"><small>${review?esc(decisions[review.decision]):'Awaiting human review'}</small><button class="secondary" data-review="${esc(r.id)}" ${state.profile.role==='manager'?'':'disabled'}>${review?'Review again':'Review action'} →</button></div></article>`;
 }).join(''):'<p class="empty">No recommendations were supplied for this scenario. Ask the resource module owner for preparation advice.</p>';
 $('support-values').innerHTML=`<div class="support-values"><div><strong>${fmt(s.max_staff)}</strong><small>Peak people required</small></div><div><strong>${fmt(s.total_fuel)}</strong><small>Week’s fuel estimate · gal</small></div></div>`;
 $('uncertainty-copy').textContent=b.meta.interval_description+' '+(b.meta.data_classification==='synthetic'?'These synthetic outputs demonstrate the workflow; they do not establish forecast accuracy.':'Source and model descriptions are supplied by your team. Confirm validation with the model owner.');
}
function renderDay(){
 const r=currentRows().find(x=>x.date===state.date),d=state.data.bundle.demand.find(x=>x.scenario===state.scenario&&x.date===state.date);if(!r||!d)return;
 $('day-detail').innerHTML=`<div class="day-summary"><small>SELECTED DAY</small><strong>${esc(day(r.date,{weekday:'long',month:'short',day:'numeric'}))}</strong></div><div><small>Arrival estimate · ${state.variant==='standard'?'standard':'original demand input'}</small><strong>${fmt(d.arrivals)}</strong> <small>Supplied range ${fmt(d.arrivals_lower)}–${fmt(d.arrivals_upper)}</small></div><div><small>Planned departures · before delay</small><strong>${fmt(d.departures)}</strong></div><div><small>Gap after proposed capacity</small><strong>${fmt(Math.max(0,r.parking_units-r.prepared_capacity_units))} units</strong></div>`;
}
function renderEvidence(){
 const {data}=state,b=data.bundle;
 $('dataset-version').textContent=b?'Version '+b.version.slice(0,10):'No active version';
 $('connection-list').innerHTML=data.team_files.map(f=>`<div class="connection"><div><strong>${esc(f.file)}</strong><small>${esc(f.path)}</small></div><span class="${f.present?'':'missing'}">${f.present?'File found':'Not supplied'}</span></div>`).join('');
 $('evidence-meta').innerHTML=b?`<h2>Active dataset</h2><dl>${[['Dataset',b.meta.dataset_name],['Source',data.source],['Classification',b.meta.data_classification+' (declared by producer)'],['Operator',b.meta.fbo_name+' · '+b.meta.airport],['Model version',b.meta.model_version],['Generated',b.meta.generated_at],['Arrival range',b.meta.interval_kind+' — '+b.meta.interval_description],['Window',b.meta.window_start+' to '+b.meta.window_end+' · '+b.meta.timezone],['Notes',b.meta.notes]].map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>`:'<p>No dataset is active. Inspect the loading error and supply all required files.</p>';
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
 try{state.data=await api(files?'/api/import':'/api/source',files?{files}:{source});render();$('source-result').textContent='Validated and loaded. Reviews from a different dataset version are marked as previous.';$('source-result').classList.remove('error');toast('Dataset loaded successfully.');}
 catch(e){$('source-result').textContent=e.message+' The previously active dataset has been kept.';$('source-result').classList.add('error');}
 $('source-result').hidden=false;
}
$('login-form').addEventListener('submit',async e=>{e.preventDefault();$('login-error').textContent='';await busy(e.submitter,async()=>{try{await enter(await api('/api/login',{role:$('profile-select').value}));}catch(e){$('login-error').textContent=e.message;}});});
$('logout').addEventListener('click',async()=>{try{await api('/api/logout',{});state.profile=null;state.csrf=null;$('workspace').hidden=true;$('login').hidden=false;error('');}catch(e){error(e.message);}});
document.addEventListener('click',e=>{
 const el=e.target.closest('button');if(!el)return;
 if(el.dataset.view)showView(el.dataset.view);if(el.dataset.goto)showView(el.dataset.goto);
 if(el.dataset.scenario){state.scenario=el.dataset.scenario;render();}
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
$('load-team').addEventListener('click',e=>busy(e.currentTarget,()=>changeSource('team')));
$('load-sample').addEventListener('click',e=>busy(e.currentTarget,()=>changeSource('sample')));
$('refresh-source').addEventListener('click',e=>busy(e.currentTarget,()=>changeSource(state.data.source)));
$('import-files').addEventListener('click',e=>busy(e.currentTarget,async()=>{
 const chosen=[...$('bundle-files').files];
 if(chosen.length!==7||new Set(chosen.map(f=>f.name)).size!==7){$('source-result').hidden=false;$('source-result').textContent='Select exactly seven files with distinct names, matching the documented contract.';return;}
 if(chosen.some(f=>f.size>2000000)||chosen.reduce((sum,f)=>sum+f.size,0)>4500000){$('source-result').hidden=false;$('source-result').textContent='Files are too large. Keep each below 2 MB and the bundle below 4.5 MB.';return;}
 try{const files=Object.fromEntries(await Promise.all(chosen.map(async f=>[f.name,await f.text()])));await changeSource('import',files);}catch(e){$('source-result').hidden=false;$('source-result').textContent=e.message;}
}));
$('export').addEventListener('click',()=>{const a=document.createElement('a');a.href='/api/export?'+new URLSearchParams({scenario:state.scenario,variant:state.variant});a.download='readiness-plan.json';a.click();});
window.addEventListener('hashchange',()=>{if(state.profile)showView(location.hash.slice(1));});
(async()=>{try{const session=await api('/api/session');if(session.profile)await enter(session);}catch(e){$('login-error').textContent=e.message;}})();
