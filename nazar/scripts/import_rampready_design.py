"""Translate the user-supplied design templates; never ship its sample scripts.

Usage: python3 nazar/scripts/import_rampready_design.py /path/to/rampready-design
Only run during design updates, not on app startup.
"""
from pathlib import Path
import re
import sys

source=Path(sys.argv[1]);target=Path(__file__).resolve().parents[1]/'static'/'templates'
target.mkdir(parents=True,exist_ok=True)
for path in source.glob('*.dc.html'):
    name=path.name.split('.')[0]
    html=re.search(r'<x-dc>(.*?)</x-dc>',path.read_text(),re.S).group(1)
    html=html.replace('<helmet>','').replace('</helmet>','')
    html=re.sub(r' hint-placeholder-(?:count|val)="[^"]*"','',html)
    for page in ('Signin','Main','Day','Plan','Bookings','Ramp','Numbers'):
        html=html.replace(f'href="{page}.dc.html"',f'href="#{page.lower()}"')
    html=html.replace('>Sample data</span>','>{{dataBadge}}</span>')
    html=re.sub(r'(<a href="#signin"[^>]*>)<span class="av">[MJS]</span>(Maya|Jordan|Sam)</a>',r'\1<span class="av">{{userInitial}}</span>{{userName}}</a>',html)
    html=re.sub(r'<footer(.*?)</footer>',lambda m:re.sub(r'(<p[^>]*>).*?(</p>)',r'\1{{footer}}\2',m.group(0),flags=re.S),html,flags=re.S)
    if name=='Signin':
        html=html.replace('Sample data for a fictional FBO.','Model estimates for a fictional FBO.')
        html=html.replace('Your manager has to invite you first. Your role comes from that invite.','Email sign-in is not connected in this local demo. Choose a demo account below.')
        html=html.replace('<button class="btn" type="button" style="margin-top: 16px">','<button class="btn" type="button" data-email-login style="margin-top: 16px">')
        for role,page in [('manager','main'),('reservations','bookings'),('operations','ramp')]:
            html=html.replace(f'class="demo" href="#{page}"',f'class="demo" href="#{page}" data-login="{role}"')
    elif name=='Main':
        for a,b in [('Ramp full, 64','Ramp full, {{capacity}}'),('>60</div>','>{{booked}}</div>'),('>9</div>','>{{opening}}</div>'),('visits already booked','bookings loaded'),('planes parked at the busiest hour','planes in the hourly illustration'),('See game day hour by hour','See this day hour by hour')]:html=html.replace(a,b)
        html=html.replace('Each stripe is one parking space. Bigger jets take up to two and a half.','Each stripe is one model parking unit, not a measured stand. Bigger jets take more room. Daily bars show P3 median peaks.')
        html=re.sub(r'Usually about three quarters.*?large jet 2.5\.', '{{sourceExplanation}}',html)
        html=html.replace('expected, not booked yet','modeled arrivals for the week')
        html=html.replace('{{subline}}</p>','{{subline}}</p><p class="muted" style="margin:16px 0 0;max-width:65ch;font-size:14px">{{uncertainty}}</p>')
    elif name=='Day':
        for a,b in [('Sunday, February 14','{{dayTitle}}'),('>Game day</span>','>{{dayBadge}}</span>'),("The ramp is over capacity all day. It's fullest at 17:00, when planes need 96 spaces and we have 64.",'{{dayExplanation}}'),('>22</div>','>{{arrivals}}</div>'),('>8</div>','>{{departures}}</div>'),('>72</div>','>{{parked}}</div>'),('>32</div>','>{{shortage}}</div>'),('planes parked at 17:00','planes in the hourly illustration'),('spaces short at the peak','model spaces short at the daily peak'),('Ramp full, 64','Ramp full, {{capacity}}'),('aria-label="Spaces in use on Sunday by hour. Over 64 all day, peaking at 96 at 17:00."','aria-label="{{hourAria}}"')]:html=html.replace(a,b)
        html=html.replace("Each bar is one hour. Orange is what doesn't fit on our ramp.",'{{hourNote}}')
        html=html.replace('color: #B93F0B">{{shortage}}','color: {{shortageColor}}">{{shortage}}')
        html=html.replace('Every plane on the ramp','Every plane in the illustration')
        html=html.replace('Thicker bars take more space. Dashed bars are expected but not booked yet.','Generated E-codes with assumed timings. These are not bookings.')
        html=html.replace('{{hourNote}}</p>', '{{hourNote}}</p><details class="muted" style="margin:-12px 0 28px;font-size:14px"><summary>Timing assumptions</summary><p>{{hourDetails}}</p></details>')
        html=html.replace('<button class="btn" type="button">Show more planes</button>','<button class="btn" type="button" onClick="{{showMore}}" disabled="{{allShown}}">Show more planes</button>')
    elif name=='Bookings':
        for a,b in [('>60</div>','>{{booked}}</div>'),('>20</div>','>{{estimated}}</div>'),('>9</div>','>{{opening}}</div>'),('>booked</div>','>bookings loaded</div>'),('Bookings file updated today at 14:05','{{bookingUpdate}}'),('6 new and 2 cancelled since yesterday. Use a CSV with visit code, arrival, departure, plane size and status. Leave out names and tail numbers.','{{bookingNote}}'),('Showing {{shown}} of 89 visits.','Showing {{shown}} of {{totalVisits}} visits.'),('Every visit in this list has confirmed times. Switch to All to see the rest.','{{emptyReason}}')]:html=html.replace(a,b)
        html=html.replace('<button class="btn dark" type="button">Upload a new file</button>','<button class="btn dark" type="button" data-upload-bookings>Upload a new file</button>')
        html=html.replace("Every check makes the forecast sharper. Start with the visits that aren't booked yet.",'Check the estimated stays before making arrangements. Checking a row records a review; it does not turn it into a booking.')
        html=html.replace('expected, not booked yet','estimated stays in this list').replace('already parked','modeled opening inventory')
        html=html.replace('Showing {{shown}} of {{totalVisits}} visits.', 'Showing {{shown}} of {{filteredCount}} matching visits ({{totalVisits}} total).')
        html=html.replace('</section>', '<button class="btn" style="margin-top:16px" onClick="{{showMore}}" disabled="{{allShown}}">Show more visits</button></section>')
        html=html.replace('#B93F0B','#14213D').replace('#FF6A2B','#98A2B3').replace('#8A2F08','#5D6B82')
    elif name=='Numbers':
        html=html.replace('60 booked','{{booked}} bookings loaded').replace('expected, not booked yet','modeled arrivals')
        html=html.replace('Two weeks before past big events, this share of bookings had usually come in. It\'s our guess until we find real data.','The current model does not use a booking-completion curve. This control stays disabled until a supported booking model is supplied.')
        html=html.replace('value="{{share}}" onChange="{{setShare}}"','value="50" disabled aria-label="Booking share unavailable"')
        html=html.replace('{{share}}%','{{shareLabel}}')
        html=re.sub(r'(<table class="led">.*?<tbody>).*?(</tbody>)',r'\1<sc-for list="{{ledger}}" as="r"><tr><td style="font-weight:600">{{r.label}}</td><td>{{r.value}}</td><td><span class="tag k-s">{{r.type}}</span></td><td>{{r.source}}</td><td class="muted">{{r.note}}</td></tr></sc-for>\2',html,flags=re.S)
        html=html.replace("Expected is our best guess. Quiet and Busy change the visits that aren't booked yet and how long planes stay. They're what-ifs to test the plan, not a promise about the real week.",'Expected, Quiet and Busy use the model’s Medium, Low and High outputs. The day-late switch loads the separately modeled delay case. These are planning scenarios, not a promise about the real week.')
        html=re.sub(r'<li[^>]*>6 new bookings, 2 cancellations</li>.*?<li[^>]*>Sunday\'s peak went from 92 to 96 spaces</li>','<li style="padding:12px 0;border-top:1px solid #EAECF0">{{changesNote}}</li>',html,flags=re.S)
        html=html.replace('</main>','<section class="advanced-panel" id="planning-tools"><h2 class="w">Data and planning tools</h2><p class="muted">{{releaseNote}}</p><div class="tool-row"><button class="btn" data-refresh>Refresh model outputs</button><a class="btn" href="/api/export?scenario={{scenario}}&amp;variant={{variant}}">Export model plan</a><button class="btn" data-export-review>Export reviewed plan</button></div><p class="muted">{{scopeNote}}</p><details><summary>Forecast diagnostics and source assumptions</summary><pre class="diagnostics">{{diagnostics}}</pre></details><details><summary>Weather and Presidents Day</summary><p>Departures running a day late is the existing model’s disruption test. It is not a weather forecast. Test an additional holiday uplift in the daily what-if tool; no measured holiday effect is implied.</p></details></section></main>')
    elif name=='Ramp':
        for a,b in [('We plan with 64 spaces.','We plan with {{capacity}} spaces.'),('The ramp has 68 in total. Four always stay empty so towing and emergencies have room. We never use them to make the numbers fit.','{{rampExplanation}}'),('Main ramp 44 spaces, overflow area 20 spaces, reserve 4 spaces kept empty.','{{rampAria}}'),('64.7%','{{mainWidth}}'),('29.4%','{{overflowWidth}}'),('5.9%','{{reserveWidth}}'),('>44</div>','>{{capacity}}</div>'),('>20</div>','>{{overflow}}</div>'),('>4</div>','>{{reserve}}</div>'),('>1</div>','>{{weightLight}}</div>'),('>1.5</div>','>{{weightMid}}</div>'),('>2.5</div>','>{{weightLarge}}</div>'),('Waiting for a reply','Not arranged'),('Maya asked a partner FBO for 32 spaces from February 13 to 15. Don\'t count this space until they confirm dates, access and price in writing.','{{partnerExplanation}}'),('>32</div>','>{{partnerNeeded}}</div>'),('>0</div>','>{{confirmed}}</div>'),('Everything that has to be true before the first jets arrive on Saturday.','Verify these checks before the planning week. Saved checks are tied to the current model and scenario.'),('spaces asked for','additional units modeled'),('overflow area','possible overflow'),('kept empty','reserve not quantified')]:html=html.replace(a,b)
        html=html.replace('Need to change the number of spaces? Do it on the','Need to inspect capacity assumptions? Open the')
        html=html.replace('Any change makes the current plan out of date until it\'s reviewed again.','Refresh a coherent producer release after a model change; previous reviews then need checking again.')
    elif name=='Plan':
        html=html.replace('The booking share changed from 75% to 70% at 15:20, so approvals on version 3 no longer count.','{{staleReason}}')
        html=html.replace('<button class="btn dark" type="button">Make version 4</button>','<button class="btn dark" type="button" data-refresh>Refresh the plan</button>')
        html=html.replace("Standard summary. The AI writer isn't available right now, so this is a fixed template filled with the same numbers.", 'Model-based summary using a fixed template. No AI text service is connected.')
        html=html.replace('Version 3, made today at 14:05. {{reviewText}}','Plan {{versionLabel}}. {{reviewText}}')
        html=html.replace('Find 32 more spaces for Saturday to Monday.','{{planHeadline}}')
        html=re.sub(r'(<p style="margin: 0; font-size: 19px; line-height: 1.6">).*?(</p>)',r'\1{{briefing}}\2',html,flags=re.S)
        html=html.replace('Decisions are saved with your name, the time and plan version 3.','Decisions are saved with your name, the time and this exact plan version.')
        html=html.replace("With 32 partner spaces, here's what happens if the week goes differently.",'{{stressIntro}}')
        html=html.replace('Covered every hour. 0 spaces short.','{{stressExpected}}').replace('25 spaces short on Monday afternoon.','{{stressLate}}').replace('26 spaces short on Sunday evening.','{{stressBusy}}')
        html=html.replace('class="ok"','class="{{expectedClass}}"').replace('class="no"','class="{{lateClass}}"',1).replace('class="no"','class="{{busyClass}}"',1)
        html=html.replace('To cover a busy week too, ask the partner for 58 spaces instead of 32. To cover late departures, confirm Monday departure times early.','{{stressNote}}')
        html=html.replace('d="M3 8.5l3.2 3.2L13 4.8"','d="{{expectedPath}}"').replace('d="M4 4l8 8M12 4l-8 8"','d="{{latePath}}"',1).replace('d="M4 4l8 8M12 4l-8 8"','d="{{busyPath}}"',1)
        html=html.replace('The same expected week, with and without the plan. Tested on sample data.','The same model demand, with and without its proposed preparation. Simulation results, not observed savings.')
        html=re.sub(r'(<table class="cmp">.*?<tbody>).*?(</tbody>)',r'\1<sc-for list="{{comparison}}" as="r"><tr><td>{{r.label}}</td><td style="font-weight:600;color:{{r.color}}">{{r.before}}</td><td style="font-weight:600">{{r.after}}</td></tr></sc-for>\2',html,flags=re.S)
        html=html.replace("Space-hours add up every space we're missing, every hour. They aren't turned-away planes or delays. No partner has quoted a price yet, so there's no real cost to show.",'{{comparisonNote}}')
        a=html.index('<ul style="list-style: none; margin: 0; padding: 0">',html.index('>History</h2>'));b=html.index('</ul>',a)
        html=html[:a]+'<ul style="list-style:none;margin:0;padding:0"><sc-for list="{{history}}" as="r"><li style="display:flex;flex-wrap:wrap;gap:4px 24px;padding:16px 0;border-top:1px solid #EAECF0"><span class="muted" style="flex:0 0 140px">{{r.time}}</span><span style="flex:1 1 400px">{{r.text}}</span></li></sc-for>'+html[b:]
    if name in ('Bookings','Plan','Numbers'):
        html=html.replace('<div style="overflow-x: auto">', '<p class="mobile-table-hint muted">Swipe the table sideways for all columns.</p><div style="overflow-x: auto">')
    # Native templates are valid inside tables; custom elements would be foster-parented outside them.
    html=html.replace('<sc-for list=', '<template data-list=').replace('</sc-for>', '</template>').replace('<sc-if value=', '<template data-if=').replace('</sc-if>', '</template>')
    (target/(name+'.html')).write_text(html)
    print('Translated',name)
