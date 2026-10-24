'use strict';
const root=document.getElementById('app');
const state={session:null,snapshot:null,design:null,scenario:'medium',variant:'standard',day:'2027-02-14',page:'signin',bookingFilter:'check',dayFilter:'all',query:'',limit:12,bookingLimit:12};
const templates=new Map();let generation=0,noticeTimer,reviewPending;
const pages={signin:'Signin',main:'Main',day:'Day',plan:'Plan',bookings:'Bookings',ramp:'Ramp',numbers:'Numbers'};
const round=n=>Number.isFinite(Number(n))?Math.round(Number(n)):0;
const whole=n=>Math.ceil(Number(n)||0);
const num=n=>Number.isFinite(Number(n))?Math.round(Number(n)).toLocaleString('en-US'):'—';
const pct=n=>`${Math.max(0,Math.min(100,n||0))}%`;
const date=d=>new Date(d.length===10?d+'T12:00:00-08:00':d);
const dayName=d=>date(d).toLocaleDateString('en-US',{weekday:'long',timeZone:'America/Los_Angeles'});
const shortDate=d=>date(d).toLocaleDateString('en-US',{month:'short',day:'numeric',timeZone:'America/Los_Angeles'});
const stamp=d=>d?date(d).toLocaleString('en-US',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',timeZone:'America/Los_Angeles'}):'Not supplied';
const hour=d=>date(d).toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'America/Los_Angeles'});
const names={light_jet:'Small jet',midsize_jet:'Midsize jet',large_jet:'Large jet'};
const owners={manager:['Maya, manager','M'],reservations:['Jordan, reservations','J'],operations:['Sam, operations','S']};

async function api(path,body){
 const response=await fetch(path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json','X-CSRF-Token':state.session?.csrf||''}:{},body:body?JSON.stringify(body):undefined});
 const data=await response.json();if(!response.ok)throw new Error(data.error||'Could not load the planning data.');return data;
}
function notice(message){const el=document.getElementById('message');el.textContent=message;el.hidden=false;clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>el.hidden=true,9000);}
function value(path,ctx){path=path.trim();if(path==='true')return true;if(path==='false')return false;return path.split('.').reduce((a,k)=>a?.[k],ctx);}
function interpolate(text,ctx){return text.replace(/\{\{(.*?)\}\}/g,(_,key)=>{const v=value(key,ctx);return v==null?'':String(v);});}
// A small, own-template renderer. No design-tool runtime, code evaluation or raw
// producer HTML is used. Model text is written through textContent/attributes.
function materialize(node,ctx){
 if(node.nodeType===Node.TEXT_NODE){node.textContent=interpolate(node.textContent,ctx);return;}
 if(node.nodeType!==Node.ELEMENT_NODE)return;
 if(node.tagName==='SC-FOR'||node.matches('template[data-list]')){
  const list=value((node.getAttribute('list')||node.getAttribute('data-list')||'').replace(/[{}]/g,''),ctx)||[];const as=node.getAttribute('as');const frag=document.createDocumentFragment();
  for(const item of list){for(const child of [...(node.content?.childNodes||node.childNodes)]){const clone=child.cloneNode(true);const wrapper=document.createDocumentFragment();wrapper.append(clone);materialize(clone,{...ctx,[as]:item});frag.append(wrapper);}}
  node.replaceWith(frag);return;
 }
 if(node.tagName==='SC-IF'||node.matches('template[data-if]')){
  const enabled=value((node.getAttribute('value')||node.getAttribute('data-if')||'').replace(/[{}]/g,''),ctx);
  if(!enabled){node.remove();return;}const content=node.content||node;for(const child of [...content.childNodes])materialize(child,ctx);node.replaceWith(...content.childNodes);return;
 }
 for(const attr of [...node.attributes]){
  if(attr.name.startsWith('on')){
   const fn=value(attr.value.replace(/[{}]/g,''),ctx);node.removeAttribute(attr.name);
   if(typeof fn==='function')node.addEventListener(attr.name.slice(2),e=>{try{Promise.resolve(fn(e)).catch(x=>notice(x.message));}catch(x){notice(x.message);}});
  }else if(['checked','disabled','selected'].includes(attr.name)&&attr.value.includes('{{')){
   const enabled=!!value(attr.value.replace(/[{}]/g,''),ctx);node.toggleAttribute(attr.name,enabled);node[attr.name]=enabled;
  }else if(attr.value.includes('{{'))node.setAttribute(attr.name,interpolate(attr.value,ctx));
 }
 for(const child of [...node.childNodes])materialize(child,ctx);
}
async function loadTemplate(page){if(!templates.has(page)){const r=await fetch('/templates/'+pages[page]+'.html');if(!r.ok)throw new Error('Page template could not be loaded.');templates.set(page,await r.text());}return templates.get(page);}
function param(name,fallback){return new URLSearchParams(location.hash.split('?')[1]||'').get(name)||fallback;}
function route(){const page=location.hash.slice(1).split('?')[0]||'main';state.page=pages[page]?page:'main';state.day=param('date',state.day);if(!/^2027-02-(11|12|13|14|15|16|17)$/.test(state.day))state.day='2027-02-14';return render();}
async function refresh(){state.snapshot=await api('/api/dashboard');if(!state.snapshot.bundle)throw new Error(state.snapshot.load_error||'No valid model output is loaded.');state.design=await api(`/api/design?scenario=${state.scenario}&variant=${state.variant}`);}
async function setCase(scenario,variant=state.variant){root.inert=true;try{state.scenario=scenario;state.variant=variant;await refresh();await render();}finally{root.inert=false;}}
async function mutate(path,data){state.design=await api('/api/design/'+path,{version:state.design.version,scenario:state.scenario,variant:state.variant,...data});await render();}
function ledgerMap(){return Object.fromEntries(state.snapshot.bundle.assumptions.map(a=>[a.id,a]));}
function assumption(id,fallback=null){const v=ledgerMap()[id]?.value;return v==null?fallback:Number(v);}
function currentRows(s=state.scenario,v=state.variant){return state.snapshot.bundle.resources.filter(r=>r.scenario===s&&r.variant===v).sort((a,b)=>a.date.localeCompare(b.date));}
function reviews(){const result={};for(const r of state.design.history){if(!r.stale&&!result[r.recommendation_id])result[r.recommendation_id]=r;}return result;}
function actionValues(){const known=reviews();return state.design.actions.map((a,i)=>{
 const review=known[a.id],status=({approved:'Approved',changes_requested:'Changed',rejected:'Declined'})[review?.decision]||'Waiting';const who=owners[a.owner]||owners.manager;
 return {...a,n:String(i+1),t:a.title,why:a.reason,who:who[0],ini:who[1],due:shortDate(a.due_date),note:review?.note||a.source,hasNote:true,status,
  ok:status==='Approved',notOk:status!=='Approved',needsNote:false,aCls:status==='Approved'?'sel':'',cCls:status==='Changed'?'sel':'',dCls:status==='Declined'?'sel':'',
  toggle:()=>openReview(a,'approved'),approve:()=>openReview(a,'approved'),change:()=>openReview(a,'changes_requested'),decline:()=>openReview(a,'rejected')};
 });}
function signInValues(){
 const maps=['pmpbpmeppbpmnn','bpmppbmpmpbpnn','pmbpepmpbpmpnn'];return {rows:maps.map((m,r)=>({stalls:[...m].map(c=>({cls:c==='n'?'need':'',plane:'pmb'.includes(c),pcls:'pl'+(c==='b'?' big':c==='m'?'':' small')+(r%2?' down':'')}))}))};
}
function baseValues(){
 const b=state.snapshot.bundle,rows=currentRows(),summary=state.snapshot.summaries[state.scenario][state.variant],peak=rows.reduce((a,r)=>r.parking_units>a.parking_units?r:a,rows[0]);
 const capacity=Math.floor(peak.capacity_units),peakUnits=whole(peak.parking_units),shortage=Math.max(0,...rows.map(r=>whole(r.parking_units)-Math.floor(r.capacity_units))),days=rows.map(r=>r.date);
 const visits=state.design.illustration.visits,bookings=state.design.bookings.visits,booked=bookings.filter(v=>v.status==='Booked').length;
 const total=round(b.demand.filter(r=>r.scenario===state.scenario).reduce((a,r)=>a+r.arrivals,0));
 const openingValue=assumption('initial_transient_aircraft'),opening=openingValue==null?'—':round(openingValue),steps=actionValues(),approved=steps.filter(s=>s.ok).length;
 const dataBadge=state.snapshot.source==='sample'?'Sample data':b.release_review?.status?.startsWith('provisional')?'Provisional estimates':'Model estimates';
 const footer=`${dataBadge} for a fictional FBO. RampReady suggests and people decide: nothing here moves a plane, books space or spends money.`;
 return {b,rows,summary,peak,capacity,peakUnits,shortage,days,visits,bookings,booked,total,opening,steps,approved,est:total,dataBadge,footer,
  userInitial:state.session.profile.name[0],userName:state.session.profile.name.split(' ')[0],
  scenario:state.scenario,variant:state.variant,versionLabel:state.design.version.slice(0,8),late:state.variant==='departure_delay_24h',
  sourceExplanation:'Forecasts come from the current P2 release; parking comes from the matching P3 simulation. FAA general-aviation and air-taxi categories are proxies, not observed private-jet customers. The source assumes an FBO share and aircraft mix. No booking-completion percentage is used.',
  cleared:state.design.history.some(r=>r.stale&&r.decision==='approved'),stale:state.design.input_status.stale,staleReason:state.design.input_status.message,
  planSummary:`${steps.length} steps, ${approved} approved`,hasPlan:steps.length>0,approvedText:`${approved} of ${steps.length} approved`,
  planIntro:shortage?'Sort out extra space before the busy days. Review each step.':'No extra space is modeled as necessary. Verify the inputs and keep an eye on new bookings.',
  toggleLate:()=>setCase(state.scenario,state.variant==='standard'?'departure_delay_24h':'standard'),
  scenarios:[['low','Quiet'],['medium','Expected'],['high','Busy']].map(([s,label])=>({label,cls:state.scenario===s?'on':'',pressed:String(state.scenario===s),pick:()=>setCase(s)}))};
}
function mainValues(x){
 const gaps=x.rows.map(r=>Math.max(0,whole(r.parking_units)-Math.floor(r.capacity_units))),maxGap=Math.max(...gaps),gapIndex=gaps.indexOf(maxGap);
 const p=maxGap?x.rows[gapIndex]:x.peak,peak=whole(p.parking_units),cap=Math.floor(p.capacity_units),over=x.rows.filter((r,i)=>gaps[i]>0);
 const span=over.length?`${dayName(over[0].date)}${over.length>1?' to '+dayName(over.at(-1).date):''}`:'';
 const headline=maxGap?`We're ${maxGap} spaces short ${p.date==='2027-02-14'?'on game day':'on '+dayName(p.date)}.`:'Our ramp has room all week.';
 const subline=maxGap?`${dayName(p.date)} needs ${peak} spaces and our ramp holds ${cap}. We need extra room ${span}.`:`The busiest day, ${dayName(p.date)}, needs ${peak} of our ${cap} spaces.`;
 const scale=Math.max(...x.rows.map(r=>r.parking_units),cap)*1.08,total=Math.max(peak,cap),used=Math.min(peak,cap),selected=x.rows.find(r=>r.date===state.day)||p;
 const selectedHours=state.design.illustration.hours.filter(h=>h.time.startsWith(selected.date)),hpeak=selectedHours.reduce((a,h)=>h.units>a.units?h:a,{units:0,aircraft:0});
 const forecast=x.b.demand.find(r=>r.date===selected.date&&r.scenario===state.scenario);
 const uncertainty=p.parking_p10!=null&&p.parking_p90!=null?`On the busiest day, the model’s 10th–90th percentile range is ${Math.floor(p.parking_p10)}–${whole(p.parking_p90)} units. These are simulated outcomes, not measured forecast accuracy.`:'This release does not supply a parking uncertainty range.';
 return {...x,headline,subline,uncertainty,hero:{short:maxGap>0,spare:!maxGap&&peak<cap,nw:pct(used/total*100),ns:pct(used?100/used:100),ow:pct(maxGap/total*100),os:pct(maxGap?100/maxGap:100),ew:pct((cap-peak)/total*100),es:pct(cap>peak?100/(cap-peak):100),nNum:maxGap?cap:peak,nLabel:maxGap?'spaces on our ramp':'spaces in use on '+dayName(p.date),rNum:maxGap?'+'+maxGap:String(cap-peak),rLabel:maxGap?'more we need to find':'spaces to spare',rColor:maxGap?'#B93F0B':'#14213D',aria:subline},
  capPos:pct(cap/scale*100),week:x.rows.map((r,i)=>{const baseline=x.b.baseline.find(b=>b.date===r.date)?.parking_units;return {dn:date(r.date).toLocaleDateString('en-US',{weekday:'short',day:'numeric',timeZone:'America/Los_Angeles'}),sub:r.date==='2027-02-14'?'Game day':'Usually '+(baseline==null?'not supplied':whole(baseline)),v:whole(r.parking_units),note:gaps[i]?gaps[i]+' short':'Fits',ntCls:gaps[i]?'s':'f',hasShort:gaps[i]>0,tnCls:gaps[i]?'tn':'tn full',nw:pct(Math.min(r.parking_units,r.capacity_units)/scale*100),ow:pct(Math.max(0,r.parking_units-r.capacity_units)/scale*100),gw:pct((baseline||0)/scale*100),cls:r.date===state.day?'on':'',pressed:String(r.date===state.day),pick:()=>{state.day=r.date;render();}};}),
  day:{title:`${dayName(selected.date)}, ${shortDate(selected.date)}${selected.date==='2027-02-14'?', game day':''}`,arr:round(selected.arrivals_p50??forecast?.arrivals),dep:round(selected.departures_p50??forecast?.departures),parked:state.design.illustration.available?hpeak.aircraft:'—',spaces:whole(selected.parking_units)}};
}
function dayValues(x){
 const r=x.rows.find(r=>r.date===state.day)||x.peak,hs=state.design.illustration.hours.filter(h=>h.time.startsWith(r.date));
 const peak=hs.reduce((a,h)=>h.units>a.units?h:a,{units:0,aircraft:0,time:r.date+'T00:00:00-08:00'}),cap=r.capacity_units,scale=Math.max(cap,...hs.map(h=>h.units))*1.08;
 const start=date(r.date+'T00:00:00-08:00').getTime(),end=start+86400000;
 const all=x.visits.filter(v=>date(v.arrival).getTime()<end&&date(v.departure).getTime()>start),arr=all.filter(v=>date(v.arrival).getTime()>=start),dep=all.filter(v=>date(v.departure).getTime()<end);
 const picked=state.dayFilter==='arr'?arr:state.dayFilter==='dep'?dep:all,shown=picked.slice(0,state.limit);
 const forecast=x.b.demand.find(d=>d.date===r.date&&d.scenario===state.scenario);
 return {...x,dayTitle:date(r.date).toLocaleDateString('en-US',{weekday:'long',month:'long',day:'numeric',timeZone:'America/Los_Angeles'}),dayBadge:r.date==='2027-02-14'?'Game day':r.date==='2027-02-15'?'Presidents Day':'Planning day',
  dayExplanation:`The daily parking model needs ${whole(r.parking_units)} of ${Math.floor(cap)} spaces at its median peak. The hourly view below is a separate planning illustration, not an observed schedule.`,
  arrivals:round(r.arrivals_p50??forecast?.arrivals),departures:round(r.departures_p50??forecast?.departures),parked:state.design.illustration.available?peak.aircraft:'—',shortage:Math.max(0,whole(r.parking_units)-Math.floor(cap)),
  shortageColor:r.parking_units>cap?'#B93F0B':'#14213D',hourNote:state.design.illustration.available?'Illustration only: assumed times from rounded forecasts. Each bar is one hour; orange is what does not fit.':state.design.illustration.note,hourDetails:state.design.illustration.note,hourAria:`Estimated hourly occupancy for ${r.date}. Assumed timing; peak ${whole(peak.units)} units.`,
  hours:hs.map((h,i)=>({nh:pct(Math.min(h.units,cap)/scale*100),oh:pct(Math.max(0,h.units-cap)/scale*100),lab:i%3===0?String(i).padStart(2,'0'):''})),capPos:pct(cap/scale*100),
  filters:[['all','All '+all.length],['arr','Arriving '+arr.length],['dep','Leaving '+dep.length]].map(([f,label])=>({label,cls:f===state.dayFilter?'on':'',pressed:String(f===state.dayFilter),pick:()=>{state.dayFilter=f;state.limit=12;render();}})),
  rows:shown.map(v=>{const a=Math.max(0,(date(v.arrival)-start)/3600000),d=Math.min(24,(date(v.departure)-start)/3600000),z=({light_jet:'s',midsize_jet:'m',large_jet:'l'})[v.category];return {id:v.id,size:names[v.category],when:`${shortDate(v.arrival)} ${hour(v.arrival)} to ${shortDate(v.departure)} ${hour(v.departure)}`,left:pct(a/24*100),width:pct((d-a)/24*100),cls:`sb e z${z}${a===0?' l0':''}${d===24?' r0':''}`};}),
  countText:`Showing ${shown.length} of ${picked.length} estimated visits`,allShown:shown.length>=picked.length,showMore:()=>{state.limit+=12;render();}};
}
function bookingValues(x){
 const imported=x.bookings.length>0,all=(imported?x.bookings:x.visits).map(v=>{const checked=state.design.checks[state.design.version+':'+v.id]?.checked;return {...v,flag:!checked,done:!!checked,reason:imported?'Confirm the uploaded timing':'Assumed timing; not a customer booking',size:names[v.category],arr:stamp(v.arrival),dep:stamp(v.departure),stay:`${round((date(v.departure)-date(v.arrival))/3600000)} hours`,tcls:v.status==='Booked'?'t-b':'t-e',check:()=>mutate('check',{kind:'checks',key:v.id,checked:true})};});
 const toCheck=all.filter(v=>v.flag).length,filtered=all.filter(v=>(state.bookingFilter==='all'||state.bookingFilter==='check'&&v.flag||state.bookingFilter==='b'&&v.status==='Booked'||state.bookingFilter==='e'&&v.status==='Estimated')&&v.id.toLowerCase().includes(state.query.toLowerCase()));
 return {...x,headline:toCheck?`${toCheck} ${imported?(toCheck===1?'visit':'visits'):(toCheck===1?'estimated stay':'estimated stays')} ${toCheck===1?'needs':'need'} a quick check.`:'Every loaded visit is checked.',toCheck,estimated:all.filter(v=>v.status==='Estimated').length,
  bookingUpdate:imported?'Bookings file loaded '+stamp(state.design.bookings.updated_at):'No customer bookings file loaded',
  bookingNote:imported?'Uploaded visits are shown separately from the producer forecast. Review changes, then regenerate the model upstream to include them.':'These E-codes illustrate the model’s daily estimates. Upload a CSV with visit_id, category, arrival, departure and status to review actual pseudonymous records. No names or tail numbers.',
  filters:[['check','To check'],['all','All'],['b','Booked'],['e','Estimated']].map(([f,label])=>({label,cls:state.bookingFilter===f?'on':'',pressed:String(state.bookingFilter===f),pick:()=>{state.bookingFilter=f;state.bookingLimit=12;render();}})),
  rows:filtered.slice(0,state.bookingLimit),shown:Math.min(state.bookingLimit,filtered.length),filteredCount:filtered.length,allShown:state.bookingLimit>=filtered.length,showMore:()=>{state.bookingLimit+=12;render();},totalVisits:all.length,empty:!filtered.length,q:state.query,setQ:e=>{state.query=e.target.value;state.bookingLimit=12;render();},emptyReason:imported?'No visits match this filter. Switch to All or clear the search.':'No recorded bookings have been supplied. Switch to Estimated to inspect the modeled stays, or upload your booking file.'};
}
function planValues(x){
 const rows=x.rows,over=rows.filter(r=>r.parking_units>r.capacity_units),first=over[0]?.date,last=over.at(-1)?.date;
 const extra=Math.max(...rows.map(r=>r.prepared_capacity_units-r.capacity_units));
 // Use this plan's SAME per-date capacity across stress cases, not each case's
 // independently optimized plan (which would make the comparison misleading).
 const stress=(s,v)=>{const rs=currentRows(s,v);return Math.max(0,...rs.map(r=>whole(r.parking_units)-Math.floor(rows.find(p=>p.date===r.date).prepared_capacity_units)));};
 const expected=stress('medium','standard'),late=stress('medium','departure_delay_24h'),busy=stress('high','standard');
 const remaining=Math.max(0,...rows.map(r=>whole(r.parking_units)-Math.floor(r.prepared_capacity_units))),afterFirst=rows.find(r=>r.parking_units>r.prepared_capacity_units)?.date;
 const comparison=[{label:'First day we run out',before:first?shortDate(first):'None',after:afterFirst?shortDate(afterFirst):'None'},
  {label:'Biggest shortfall',before:num(x.shortage)+' spaces',after:num(remaining)},
  {label:'Days over capacity',before:num(over.length),after:num(rows.filter(r=>r.parking_units>r.prepared_capacity_units).length)},
  {label:'Hours over capacity',before:'Not in daily output',after:'Not in daily output'},
  {label:'Space-hours short',before:'Not in daily output',after:'Not in daily output'},
  {label:'Illustrative preparation cost',before:'No added preparation',after:'$'+num(x.summary.preparation_cost)}].map(r=>({...r,color:x.shortage?'#B93F0B':'#14213D'}));
 const history=state.design.history.map(r=>({time:stamp(r.reviewed_at),text:`${r.reviewer} ${r.decision.replace('_',' ')} ${r.recommendation_id}. ${r.note}${r.stale?' Out of date for these inputs.':''}`}));
 if(!history.length)history.push({time:'Current release',text:'No planning decisions saved yet. Reviews will appear here with their exact input version.'});
 const peakDay=dayName(x.peak.date),briefing=`${peakDay} is the busiest modeled day: ${x.peakUnits} parking units against ${x.capacity} usable units. ${x.shortage?`The peak gap is ${x.shortage} units. Review the model’s proposed extra capacity before making arrangements.`:'The central daily peaks fit without extra space.'} The model uses estimates, not confirmed customer bookings. Verify the assumed aircraft mix, operating areas and departure timings.`;
 return {...x,progress:`${x.steps.filter(s=>s.status!=='Waiting').length} of ${x.steps.length} decided`,reviewText:x.steps.every(s=>s.status!=='Waiting')?'Fully reviewed.':'Waiting for your review.',
  planHeadline:x.shortage?`Find ${x.shortage} more spaces for ${dayName(first)}${first!==last?' to '+dayName(last):''}.`:'Our ramp has room. Keep the plan ready.',
  aiDown:true,aiUp:false,briefing,stressIntro:`With ${num(extra)} extra units in this plan, here’s what happens if the week goes differently.`,
  stressExpected:`${expected} spaces short at the daily peak.`,stressLate:`${late} spaces short at the daily peak.`,stressBusy:`${busy} spaces short at the daily peak.`,
  expectedPath:expected?'M4 4l8 8M12 4l-8 8':'M3 8.5l3.2 3.2L13 4.8',latePath:late?'M4 4l8 8M12 4l-8 8':'M3 8.5l3.2 3.2L13 4.8',busyPath:busy?'M4 4l8 8M12 4l-8 8':'M3 8.5l3.2 3.2L13 4.8',expectedClass:expected?'no':'ok',lateClass:late?'no':'ok',busyClass:busy?'no':'ok',
  stressNote:'These comparisons keep the selected plan’s capacity fixed. The producer’s day-late test shifts departures from game day onward. No partner space is reserved by this screen.',
  comparison,comparisonNote:'Daily peaks cannot establish hours or space-hours short. Costs are producer assumptions, not quotes. The hourly illustration is kept separate from these P3 results.',history};
}
function rampValues(x){
 const overflowValue=assumption('overflow_capacity_su'),overflow=overflowValue??0,total=x.capacity+overflow;
 const defs=[['capacity',`Check the ${x.capacity} model ramp units against the usable layout`],['access','Check tow routes and access for large jets'],['lighting','Check lighting for the proposed overflow area'],['reserve','Confirm protected reserve and access lanes'],['briefing','Walk the line crew through the parking plan'],['partner','Verify partner terms before any arrangement']];
 const items=defs.map(([id,t])=>{const on=!!state.design.ramp_checks[state.design.version+':'+id]?.checked;return {t,meta:'Operations lead, before '+shortDate(x.days[0]),on,tcls:on?'done-t':'',toggle:e=>mutate('check',{kind:'ramp_checks',key:id,checked:e.target.checked})};});
 const weight=id=>{const n=assumption(id);return n==null?'Not supplied':Number.isInteger(n)?String(n):`${round(n*2)} per 2 jets`;};
 return {...x,rampExplanation:`The model plans with ${x.capacity} usable units and up to ${round(overflow)} additional overflow units. Access allowances are already part of its capacity estimate. A separate reserve count is not supplied; do not invent extra usable space.`,
  rampAria:`${x.capacity} main ramp units and ${overflow} potential overflow units. Reserve count not supplied.`,overflow:overflowValue==null?'—':round(overflow),reserve:'—',mainWidth:pct(x.capacity/total*100),overflowWidth:pct(overflow/total*100),reserveWidth:'0%',
  weightLight:weight('su_light'),weightMid:weight('su_midsize'),weightLarge:weight('su_large'),items,progress:`${items.filter(i=>i.on).length} of ${items.length} done`,pct:pct(items.filter(i=>i.on).length/items.length*100),
  partnerExplanation:'No request has been sent and no partner has confirmed dates, access or price. The model’s extra-space proposal is a planning assumption only.',partnerNeeded:whole(Math.max(...x.rows.map(r=>r.prepared_capacity_units-r.capacity_units))),confirmed:'—'};
}
function numbersValues(x){
 const ids=['ramp_capacity_su','overflow_capacity_su','initial_transient_aircraft','opening_dwell_days','dep_share_before_peak','planning_quantile','delay_24h_first_day'];
 const labels={ramp_capacity_su:'Spaces we plan with',overflow_capacity_su:'Possible overflow',initial_transient_aircraft:'Aircraft before the week',opening_dwell_days:'Opening inventory dwell',dep_share_before_peak:'Departures before the daily peak',planning_quantile:'Parking preparation percentile',delay_24h_first_day:'Day-late test begins'};
 const map=ledgerMap(),ledger=ids.filter(id=>map[id]).map(id=>{const a=map[id],v=Number(a.value);return {label:labels[id],value:id==='opening_dwell_days'?num(v*24)+' hours':id==='dep_share_before_peak'||id==='planning_quantile'?num(v*100)+'%':id==='delay_24h_first_day'?shortDate(x.days[v]):num(v),type:a.classification==='synthetic'?'Sample':'Assumption',source:a.source,note:a.note};});
 ledger.splice(2,0,{label:'Spaces kept empty',value:'Not supplied separately',type:'Unspecified',source:'P3 capacity ledger',note:'Access allowances are in the usable-share assumption. Do not count them twice.'});
 ledger.push({label:'Recorded reservations',value:num(x.booked)+' loaded',type:x.booked?'Uploaded':'Not supplied',source:'Bookings page',note:'Uploads are separate from P2 until the team regenerates its forecast.'});
 return {...x,headline:`We expect ${x.total} arrivals. ${x.booked} bookings are loaded.`,explain:'The forecast uses historical airport categories and event assumptions. It does not estimate demand from a percentage of bookings received. Daily point estimates are rounded here; the exports retain their precision.',
  dots:Array.from({length:Math.min(x.total,500)},()=>({cls:'d e'})),dotsLabel:`${x.total} estimated arrivals; ${x.booked} separate bookings loaded.`,est:x.total,shareLabel:'Not used',share:0,changed:false,ledger,
  changesNote:state.design.bookings.updated_at?'Booking file uploaded '+stamp(state.design.bookings.updated_at)+'. Regenerate upstream to incorporate it.':'No booking-change history was supplied. No cancellations or changed departures are invented.',
  releaseNote:state.snapshot.input_status.message+' '+(x.b.release_review?.label||''),scopeNote:'The connected P2/P3 release uses general-aviation and air-taxi categories. It is not a verified Part 91-only or private-jet count. The separate private-only research has not replaced this matched parking release.',
  diagnostics:JSON.stringify({source:state.snapshot.source,version:x.b.version,limitations:x.b.limitations,assumptions:x.b.assumptions,forecast_metrics:x.b.forecast_metrics},null,2)};
}
function viewModel(){if(state.page==='signin')return signInValues();const x=baseValues();return ({main:mainValues,day:dayValues,plan:planValues,bookings:bookingValues,ramp:rampValues,numbers:numbersValues}[state.page])(x);}
async function render(){
 const ticket=++generation;
 if(!state.session?.profile)state.page='signin';
 try{
  if(state.page!=='signin'&&!state.snapshot)await refresh();
  const text=await loadTemplate(state.page);if(ticket!==generation)return;
  const t=document.createElement('template');t.innerHTML=text;const model=viewModel();
  for(const n of [...t.content.childNodes])materialize(n,model);
  root.replaceChildren(t.content);document.title=pages[state.page]+' · RampReady';
  root.querySelectorAll('[data-login]').forEach(a=>a.addEventListener('click',async e=>{e.preventDefault();try{state.session=await api('/api/login',{role:a.dataset.login});await refresh();location.hash=a.getAttribute('href');await route();}catch(x){notice(x.message);}}));
  root.querySelector('[data-email-login]')?.addEventListener('click',()=>notice('Email sign-in is not connected. Use one of the demo accounts below. No email was sent.'));
  root.querySelectorAll('[data-refresh]').forEach(b=>b.addEventListener('click',async()=>{try{await api('/api/source',{source:state.snapshot.source});await refresh();await render();notice('Model outputs refreshed. Earlier reviews are retained with their original version.');}catch(e){notice(e.message);}}));
  root.querySelector('[data-upload-bookings]')?.addEventListener('click',()=>document.getElementById('booking-file').click());
  if(state.page==='numbers')mountDesignTools();
  root.querySelectorAll('a[href="#day"]').forEach(a=>a.href='#day?date='+state.day);
  // Page changes reset scroll; changing a control preserves the current position.
 }catch(e){root.replaceChildren();const section=document.createElement('section');section.className='loading-state';const h=document.createElement('h1');h.textContent='The model data needs attention.';const p=document.createElement('p');p.textContent=e.message;const a=document.createElement('a');a.href='/legacy';a.textContent='Open data import and source recovery';section.append(h,p,a);root.append(section);}
}
function openReview(action,decision){
 if(state.session.profile.role!=='manager'){notice('Use the manager demo account to review the plan.');return;}
 if(state.design.input_status.stale){notice('Refresh the model outputs before reviewing this plan.');return;}
 reviewPending={action,decision,version:state.design.version};document.getElementById('review-title').textContent=({approved:'Approve preparation',changes_requested:'Request a change',rejected:'Decline preparation'})[decision];
 document.getElementById('review-action').textContent=action.title;document.getElementById('review-form').reset();document.getElementById('review-error').textContent='';
 document.getElementById('approval-checks').hidden=decision!=='approved';document.getElementById('review-dialog').showModal();
}
document.getElementById('cancel-review').addEventListener('click',()=>document.getElementById('review-dialog').close());
document.getElementById('review-form').addEventListener('submit',async e=>{
 e.preventDefault();const button=document.getElementById('save-review');button.disabled=true;
 try{const checks=Object.fromEntries([...document.querySelectorAll('#approval-checks input')].map(c=>[c.name,c.checked]));
  state.design=await api('/api/design/review',{version:reviewPending.version,scenario:state.scenario,variant:state.variant,recommendation_id:reviewPending.action.id,decision:reviewPending.decision,note:document.getElementById('review-note').value,checks});
  document.getElementById('review-dialog').close();await render();notice('Review saved with your name and this exact plan version.');
 }catch(x){document.getElementById('review-error').textContent=x.message;}finally{button.disabled=false;}
});
document.getElementById('booking-file').addEventListener('change',async e=>{const file=e.target.files[0];if(!file)return;try{if(file.size>2_000_000)throw new Error('Choose a CSV under 2 MB.');await mutate('bookings',{csv:await file.text()});notice('Booking file loaded separately. The producer forecast has not been changed.');}catch(x){notice(x.message);}finally{e.target.value='';}});
window.addEventListener('hashchange',()=>{window.scrollTo(0,0);route();});
(async()=>{try{state.session=await api('/api/session');await route();}catch(e){notice(e.message);}})();
