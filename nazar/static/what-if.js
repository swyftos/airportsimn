'use strict';
// Scratch experiments never replace the producer forecast or planning reviews.
const experiment = {version:null, result:null, dirty:true, revision:0, running:false, initialized:false};
const eventLabel = date => date==='2027-02-14'?'Super Bowl':date==='2027-02-15'?'Presidents Day':'';

function inputSettings(){
 const days={};
 document.querySelectorAll('#wi-days tr').forEach(row=>{
  const override={},select=row.querySelector('select');
  if(select.value)override.scenario=select.value;
  for(const key of ['arrivals','departures']){
   const field=row.querySelector(`[data-flow="${key}"]`);
   if(field.value!=='')override[key]=field.valueAsNumber;
  }
  if(Object.keys(override).length)days[row.dataset.date]=override;
 });
 return {scenario:$('wi-scenario').value,days,holiday_arrival_pct:$('wi-holiday').valueAsNumber,extra_capacity_units:$('wi-extra').valueAsNumber,delay_departures:$('wi-delay').checked};
}
function markExperimentChanged(){
 experiment.dirty=true;experiment.revision++;
 $('wi-results').hidden=true;$('wi-export').disabled=true;
 $('wi-status').textContent='Changes not calculated. Recalculate to see the full week.';
 $('wi-error').textContent='';
 updatePlaceholders();
}
function updatePlaceholders(){
 const b=state.data?.bundle;if(!b?.native)return;
 document.querySelectorAll('#wi-days tr').forEach(row=>{
  const scenario=row.querySelector('select').value||$('wi-scenario').value;
  const d=b.demand.find(r=>r.date===row.dataset.date&&r.scenario===scenario);
  for(const key of ['arrivals','departures'])row.querySelector(`[data-flow="${key}"]`).placeholder=d?fmt(d[key]):'Not supplied';
 });
}
function resetExperiment(){
 $('wi-form').reset();$('wi-scenario').value=state.scenario;
 const dates=state.data.bundle.baseline.map(r=>r.date).sort();
 $('wi-days').innerHTML=dates.map(date=>`<tr data-date="${date}" class="${eventLabel(date)?'event-row':''}"><th scope="row">${esc(day(date,{weekday:'short',month:'short',day:'numeric'}))}${eventLabel(date)?`<small class="wi-event">${eventLabel(date)}</small>`:''}</th><td><select aria-label="${esc(day(date))} demand scenario"><option value="">Use week scenario</option><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></td><td><input type="number" data-flow="arrivals" min="0" max="5000" step="0.1" aria-label="${esc(day(date))} arrivals override"></td><td><input type="number" data-flow="departures" min="0" max="5000" step="0.1" aria-label="${esc(day(date))} departures override"></td></tr>`).join('');
 // The complete model date range stays fixed to the hackathon's seven-day window.
 $('wi-detail-date').innerHTML=dates.map(date=>`<option value="${date}">${esc(day(date,{weekday:'short',month:'short',day:'numeric'}))}</option>`).join('');
 $('wi-detail-date').value=dates.includes(state.date)?state.date:dates[0];
 experiment.result=null;experiment.initialized=true;markExperimentChanged();
}
window.syncWhatIf=function(){
 const b=state.data?.bundle,available=!!b?.native&&b.meta.airport==='LAX';
 $('wi-unavailable').hidden=available;$('wi-workspace').hidden=!available;
 if(!available){$('wi-unavailable').textContent='Load the validated LAX team outputs in Data & assumptions. The sample contract does not supply category inventory inputs for this calculator.';$('wi-export').disabled=true;return;}
 if(experiment.version!==b.version){experiment.version=b.version;resetExperiment();}
 const stale=!!state.data.input_status?.stale;
 $('wi-run').disabled=stale||experiment.running;
 $('wi-export').disabled=stale||experiment.dirty||!experiment.result||experiment.running;
 if(stale){$('wi-results').hidden=true;$('wi-status').textContent='Source files changed. Refresh the forecast before calculating or exporting.';}
 else if(state.view==='whatif'&&!experiment.result&&!experiment.running&&experiment.initialized){
  // Do not auto-run edited fields: the button makes each change reviewable.
  $('wi-status').textContent='Select assumptions, then recalculate the seven-day plan.';
 }
};
async function calculateExperiment(exportFile=false){
 if(!$('wi-form').reportValidity()||experiment.running)return;
 experiment.running=true;window.syncWhatIf();$('wi-error').textContent='';
 const revision=experiment.revision,version=state.data.bundle.version;
 $('wi-status').textContent='Recalculating all seven days…';
 try{
  const result=await api('/api/what-if',{version,settings:inputSettings()});
  if(revision!==experiment.revision||version!==state.data.bundle?.version){$('wi-status').textContent='Inputs changed during calculation. Recalculate again.';return;}
  experiment.result=result;experiment.dirty=false;renderExperiment();
  $('wi-status').textContent='Calculated from the current source. The producer forecast is unchanged.';
  if(!exportFile)$('wi-results').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});
  if(exportFile){
   const blob=new Blob([JSON.stringify(result,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),link=document.createElement('a');
   link.href=url;link.download='lax-parking-what-if.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
   toast('Experiment exported with assumptions and source version. No operational action was sent.');
  }
 }catch(e){experiment.dirty=true;$('wi-results').hidden=true;$('wi-error').textContent=e.message;$('wi-status').textContent='Calculation unavailable; no new results were applied.';}
 finally{experiment.running=false;window.syncWhatIf();}
}
function renderExperiment(){
 const result=experiment.result,s=result.summary;
 $('wi-results').hidden=false;
 const stats=[['First capacity gap',s.first_shortage?day(s.first_shortage):'None in this case','Conditional daily estimate'],['Largest parking gap',fmt(s.max_gap_units)+' units','After proposed extra capacity'],['Aircraft remaining',fmt(s.remaining_aircraft),'At the end of February 17'],['Change in carryover',(s.remaining_aircraft-result.reference.summary.remaining_aircraft>=0?'+':'')+fmt(s.remaining_aircraft-result.reference.summary.remaining_aircraft),'Versus unedited daily calculation']];
 $('wi-summary').innerHTML=stats.map(([label,value,note])=>`<div><small>${label}</small><strong>${value}</strong><span>${note}</span></div>`).join('');
 $('wi-action').textContent=s.max_gap_units>0?`Review up to ${fmt(s.max_gap_units)} additional space units or a booking contingency with the FBO manager. This model does not reserve overflow or redirect aircraft.`:'This daily case fits the proposed space. Confirm resources and inspect the forecast’s uncertainty before committing to a plan.';
 if(s.unmatched_departures>1e-6)$('wi-action').textContent+=` Check the inputs: ${fmt(s.unmatched_departures)} departure requests exceed available aircraft in their category and timing period. They are reported, not silently counted as completed flights.`;
 $('wi-table').innerHTML=`<table class="wi-result-table"><thead><tr><th>Day / case</th><th>Opening</th><th>Arrivals</th><th>Departures*</th><th>Closing</th><th>Peak space</th><th>Gap</th><th>Change in space†</th></tr></thead><tbody>${result.rows.map(r=>`<tr class="${r.gap_units>1e-9?'wi-shortage':''}"><th scope="row">${esc(day(r.date,{weekday:'short',day:'numeric'}))}<small>${esc(names[r.scenario])}${eventLabel(r.date)?' · '+eventLabel(r.date):''}</small></th><td>${fmt(r.opening_aircraft)}</td><td>${fmt(r.arrivals)}</td><td>${fmt(r.departures)}${r.unmatched_departures>1e-6?`<small>${fmt(r.unmatched_departures)} unmatched</small>`:''}</td><td><strong>${fmt(r.closing_aircraft)}</strong></td><td>${fmt(r.parking_units)} units</td><td>${fmt(r.gap_units)}</td><td>${r.delta_parking_units>=0?'+':''}${fmt(r.delta_parking_units)}</td></tr>`).join('')}</tbody></table><p class="fine">* Feasible in this inventory calculation, not authorized departures. † Versus the unedited ${esc(names[result.settings.scenario].toLowerCase())} case calculated with this same daily method; not a difference from P3’s Monte Carlo median.</p>`;
 $('wi-evidence').innerHTML=`<h3>Stay patterns need evidence</h3><p>Drop-and-go, same-day and overnight shares: <strong>not supplied</strong>. Airport air-taxi counts describe an operation category, not how long an aircraft parks. This calculator cannot infer those ratios from daily totals.</p><h3>Presidents Day</h3><p>${esc(result.holiday_status)} The current additional arrival sensitivity is ${fmt(result.settings.holiday_arrival_pct)}%. This is a user assumption, not a measured holiday uplift.</p><h3>Starting and ending inventory</h3><p>${fmt(s.opening_aircraft)} estimated aircraft are already parked at the start. ${fmt(s.remaining_aircraft)} remain after the window. ${fmt(s.departure_requests_shifted_beyond_window)} departure requests were shifted past February 17; that flow is not an additional inventory to add.</p><h3>Calculation basis</h3><p>${esc(result.method)} ${fmt(result.departure_share_before_peak*100)}% of each day’s departure requests are attempted before the assumed arrival peak, and the remainder afterward. No hourly schedule is inferred.</p><ul>${result.limitations.map(text=>`<li>${esc(text)}</li>`).join('')}</ul><div class="table-scroll"><table><thead><tr><th>Input</th><th>Value</th><th>Classification / source</th></tr></thead><tbody>${result.assumptions.map(a=>`<tr><td>${esc(a.label)}</td><td>${esc(a.value)} ${esc(a.unit)}</td><td>${esc(a.classification)} · ${esc(a.source)}<small>${esc(a.note)}</small></td></tr>`).join('')}</tbody></table></div><p class="fine">Source ${esc(result.source_version.slice(0,12))} · Experiment ${esc(result.plan_id.slice(0,12))}. Export retains the complete assumptions and identifiers.</p>`;
 renderCapacityGauge();
}
function renderCapacityGauge(){
 const result=experiment.result;if(!result)return;
 const r=result.rows.find(row=>row.date===$('wi-detail-date').value)||result.rows[0];
 const max=Math.max(1,r.parking_units,r.proposed_capacity_units),needWidth=100*r.parking_units/max,cap=100*r.proposed_capacity_units/max;
 $('wi-day-title').textContent=day(r.date,{weekday:'long',month:'short',day:'numeric'});
 $('wi-capacity').innerHTML=`<div class="wi-gauge-copy"><strong>${fmt(r.parking_units)} / ${fmt(r.proposed_capacity_units)} space units</strong><span>${r.gap_units>0?fmt(r.gap_units)+' units over capacity':fmt(r.headroom_units)+' units available in this case'}</span></div><div class="wi-gauge" role="img" aria-label="${fmt(r.parking_units)} units of demand against ${fmt(r.proposed_capacity_units)} proposed capacity"><span class="wi-gauge-demand ${r.gap_units>0?'over':''}" style="width:${needWidth}%"></span><span class="wi-gauge-limit" style="left:${Math.min(cap,99.5)}%"></span></div><div class="wi-mix">${Object.entries(r.category_at_space_peak).map(([category,count])=>`<div><span>${esc(category.replace('_jet','').replace('_',' '))} jets</span><strong>≈ ${fmt(count)}</strong></div>`).join('')}<div><span>Aircraft at space peak</span><strong>≈ ${fmt(r.aircraft_at_space_peak)}</strong></div></div><p>On-site: ${fmt(r.capacity_units)} space units. Proposed extra: ${fmt(result.settings.extra_capacity_units)}. These are size-weighted planning units, not individual stands.</p>`;
}
$('wi-form').addEventListener('input',markExperimentChanged);
$('wi-form').addEventListener('change',markExperimentChanged);
$('wi-form').addEventListener('submit',event=>{event.preventDefault();calculateExperiment();});
$('wi-reset').addEventListener('click',()=>{resetExperiment();calculateExperiment();});
$('wi-export').addEventListener('click',()=>calculateExperiment(true));
$('wi-detail-date').addEventListener('change',renderCapacityGauge);
