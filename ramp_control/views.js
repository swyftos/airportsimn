import { AREA_LABELS, STATE_LABELS, standIntervals } from './layout.js';
import { HOURS, clockLabel, dateLabel, su } from './model.js';

export const escapeHTML = value => String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
const $ = selector => document.querySelector(selector);

export function createStandViews(data, layout, callbacks) {
  let frame, placements, selection = null, hover = null, area = 'ramp', timelineArea = 'ramp', timelineKey = '', generation = 0;
  let livePositions = new Map();
  const rowsFor = name => name === 'all' ? (frame?.states || layout.stands) : (frame?.states || layout.stands).filter(stand => stand.area === name || name === 'ramp' && stand.area === 'packed');
  const relevant = focus => {
    const direct = focus?.aircraftId && (frame?.placed.find(p => p.id === focus.aircraftId) || frame?.movements.find(m => m.plane.id === focus.aircraftId)?.plane);
    const stand = frame?.states.find(s => s.id === (direct?.standId || focus?.standId));
    return { plane: direct || (stand && frame?.placed.find(p => p.standId === stand.id)), stand };
  };
  function focusValue(element) { return element?.dataset.aircraft ? { aircraftId: element.dataset.aircraft } : element?.dataset.stand ? { standId: element.dataset.stand } : null; }

  function bindSurface(element) {
    element.addEventListener('click', event => {
      const target = event.target.closest('[data-aircraft],[data-stand]'), focus = focusValue(target);
      if (target?.dataset.startTick !== undefined) callbacks.onSeek?.(Number(target.dataset.startTick));
      if (focus) callbacks.onSelect(focus);
    });
    element.addEventListener('keydown', event => {
      if (event.target.tagName === 'BUTTON') return;
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); const focus = focusValue(event.target.closest('[data-aircraft],[data-stand]')); if (focus) callbacks.onSelect(focus); }
    });
    element.addEventListener('pointerover', event => callbacks.onHover(focusValue(event.target.closest('[data-aircraft],[data-stand]'))));
    element.addEventListener('pointerleave', () => callbacks.onHover(null));
    element.addEventListener('focusin', event => callbacks.onHover(focusValue(event.target.closest('[data-aircraft],[data-stand]'))));
    element.addEventListener('focusout', () => callbacks.onHover(null));
  }
  for (const selector of ['#stand-map', '#stand-timeline', '#stand-register']) bindSurface($(selector));

  $('#map-area').innerHTML = `<option value="all">All areas</option>${Object.entries(AREA_LABELS).filter(([key]) => key !== 'packed').map(([key, label]) => `<option value="${key}">${label}</option>`).join('')}`;
  $('#map-area').value = area;
  $('#timeline-area').innerHTML = $('#map-area').innerHTML; $('#timeline-area').value = timelineArea;
  $('#map-area').addEventListener('change', event => { area = event.target.value; renderMap(); });
  $('#timeline-area').addEventListener('change', event => { timelineArea = event.target.value; timelineKey = ''; renderTimeline(); });
  $('#clear-selection').addEventListener('click', () => callbacks.onSelect(null));

  function renderMap() {
    if (!frame) return;
    const rows = rowsFor(area);
    const margin = layout.unit * .75;
    const minX = Math.min(...rows.map(s => s.x - s.width / 2)) - margin;
    const minZ = Math.min(...rows.map(s => s.z - s.depth / 2)) - margin;
    const maxX = Math.max(...rows.map(s => s.x + s.width / 2)) + margin;
    const maxZ = Math.max(...rows.map(s => s.z + s.depth / 2)) + margin;
    $('#stand-map').setAttribute('viewBox', `${minX} ${minZ} ${maxX - minX} ${maxZ - minZ}`);
    const groups = [...new Set(rows.map(stand => stand.area))].map(name => {
      const bounds = layout.areas[name];
      return `<g class="map-apron"><rect x="${bounds.x}" y="${bounds.z}" width="${bounds.width}" height="${bounds.depth}"/><text x="${bounds.x}" y="${bounds.z - layout.unit * .22}">${AREA_LABELS[name]}</text></g>`;
    }).join('');
    const stands = frame.states.filter(stand => rows.some(row => row.id === stand.id)).map(stand => {
      const summary = `${stand.id}, flexible ${stand.name} position, ${su(stand.su)}; ${STATE_LABELS[stand.status]}${stand.plane ? `; ${stand.plane.id}` : ''}${!stand.enabled ? '; approval required' : ''}`;
      return `<g class="map-stand ${stand.status} ${stand.enabled ? '' : 'unapproved'}" data-stand="${stand.id}" role="button" tabindex="0" aria-label="${escapeHTML(summary)}"><title>${escapeHTML(summary)}</title><rect x="${stand.x - stand.width / 2}" y="${stand.z - stand.depth / 2}" width="${stand.width}" height="${stand.depth}" rx="1"/><text class="stand-id" x="${stand.x}" y="${stand.z - stand.depth * .32}">${stand.id} · ${stand.name}</text><text class="stand-aircraft" x="${stand.x}" y="${stand.z + stand.depth * .31}">${stand.plane?.id || 'Free'}</text><text class="stand-state" x="${stand.x}" y="${stand.z + stand.depth * .43}">${stand.enabled ? STATE_LABELS[stand.status] : 'Approval required'}</text></g>`;
    }).join('');
    const aircraft = [...frame.placed, ...frame.movements.filter(m => m.type === 'departure').map(m => m.plane)].filter(plane => rows.some(row => row.area === plane.area)).map(plane =>
      `<g class="map-aircraft" data-aircraft="${plane.id}" data-map-plane="${plane.id}" role="button" tabindex="0" aria-label="Inspect ${plane.id}" transform="translate(${plane.x} ${plane.z})"><title>${plane.id} · ${plane.name}</title><path transform="scale(${layout.bayWidths[plane.name] * .7 / 12})" d="M 0 -7 Q 1 -6 1 -2 L 6 1 L 6 2 L 1 .3 L 1 4 L 2.5 5 L 2.5 5.7 L 0 5 L -2.5 5.7 L -2.5 5 L -1 4 L -1 .3 L -6 2 L -6 1 L -1 -2 Q -1 -6 0 -7 Z"/></g>`).join('');
    $('#stand-map').innerHTML = `<title>Illustrative stand map at ${clockLabel(frame.hour)}</title>${groups}${stands}${aircraft}`;
    highlight(); updatePositions([...livePositions.values()]);
  }

  function renderFlow() {
    const count = name => frame.placed.filter(plane => plane.area === name).length;
    const stages = [
      ['Arrival', frame.arrivals, 'this illustrated hour'], ['Stand assignment', count('ramp'), 'main ramp positions'],
      ['Tow-in packing', count('packed'), frame.capacity.packed ? 'under recorded approval' : 'approval required'],
      ['Overflow apron', count('remote'), frame.capacity.remote ? 'under recorded lease' : 'lease approval required'],
      ['Decision area', count('waiting'), 'awaiting manager decision']
    ];
    $('#mechanism-flow').innerHTML = stages.map(([name, value, note], index) => `<li class="flow-step ${index === stages.length - 1 && value ? 'waiting' : ''}"><span>${name}</span><strong>${value}</strong><small>${note}</small></li>`).join('');
    const dayFrames = placements.slice(frame.dayIndex * HOURS, (frame.dayIndex + 1) * HOURS);
    const busiestFrame = dayFrames.reduce((acc, f) => f.used > acc.used ? f : acc);
    const medianCount = Math.round(data.ramp_aircraft.by_situation[callbacks.situation()][callbacks.scenario()][data.days[frame.dayIndex].date].aircraft_at_peak_p50);
    const peakComparison = busiestFrame.fleet.length !== medianCount
      ? `on the ramp at peak: ${busiestFrame.fleet.length}, model median: ${medianCount}`
      : `Model median at today’s peak: ${medianCount} aircraft`;
    $('#illustration-check').textContent = `Demand on ramp now: ${su(frame.used)} (${frame.placed.length} aircraft). ${peakComparison}. Hour-of-day timing uses data.hourly_profile (a placeholder curve). Aircraft from earlier days are model carry-over.`;
  }

  function renderTimeline() {
    if (!frame) return;
    const key = `${generation}/${frame.dayIndex}/${timelineArea}`;
    if (timelineKey === key) return; timelineKey = key;
    const intervals = standIntervals(placements, frame.dayIndex, HOURS);
    const hourMarks = Array.from({ length: 5 }, (_, i) => i * HOURS / 4);
    const axis = `<div class="stand-time-axis"><span>Stand</span><div>${hourMarks.map(hour => `<span style="left:${hour / HOURS * 100}%">${clockLabel(hour)}</span>`).join('')}</div></div>`;
    const rows = rowsFor(timelineArea).map(stand => `<div class="stand-time-row"><button type="button" class="stand-row-label" data-stand="${stand.id}" title="Flexible position; shares the ${AREA_LABELS[stand.area]} budget">${stand.id}<small>flex</small></button><div class="stand-time-track">${intervals.filter(interval => interval.standId === stand.id).map(interval => {
      const summary = `${interval.id} in ${stand.id}, ${clockLabel(interval.from)}–${clockLabel(interval.to)}`;
      return `<button type="button" class="occupancy-bar ${stand.area}" data-aircraft="${interval.id}" data-start-tick="${frame.dayIndex * HOURS + interval.from}" style="left:${interval.from / HOURS * 100}%;width:${(interval.to - interval.from) / HOURS * 100}%" title="${summary}" aria-label="${summary}">${interval.id}</button>`;
    }).join('')}<i class="stand-playhead" aria-hidden="true"></i></div></div>`).join('');
    $('#stand-timeline').innerHTML = axis + rows;
    $('#timeline-day').textContent = dateLabel(data.days[frame.dayIndex].date);
    highlight();
  }

  function renderRegister() {
    $('#stand-register').innerHTML = frame.states.map(stand => `<tr><th scope="row"><button data-stand="${stand.id}">${stand.id}</button></th><td>${AREA_LABELS[stand.area]}</td><td>Flexible · ${stand.name} · ${su(stand.su)}</td><td>${stand.plane ? `<button data-aircraft="${stand.plane.id}">${stand.plane.id}</button>` : '—'}</td><td>${STATE_LABELS[stand.status]}${stand.enabled ? '' : ' · approval required'}</td></tr>`).join('');
  }

  // Brief item B: Aircraft parked from earlier days are the model's carry-over; label them "parked since <day>" in the inspector.
  function inspector() {
    const { plane, stand } = relevant(selection);
    if (!plane && !stand) {
      const historic = selection?.aircraftId && placements.flatMap(p => p.placed).find(p => p.id === selection.aircraftId);
      $('#inspector-content').innerHTML = historic ? `<strong>${historic.id}</strong><p>This airframe is outside the current hour’s illustration. Scrub the clock to its timeline bar to inspect its stand.</p><p>${historic.parkedSince ? `Parked since ${historic.parkedSince}` : 'Model aircraft'}</p>` : '<strong>Inspect the illustration</strong><p>Select an aircraft or stand in either view. Stand assignments and routes are illustrative proposals; no individual aircraft decision is executed.</p>';
      $('#clear-selection').hidden = !selection; return;
    }
    const state = frame.states.find(s => s.id === stand?.id), occupant = plane || state?.plane;
    $('#clear-selection').hidden = false;

    const parkedOrigin = occupant ? (
      occupant.bornDay !== undefined && occupant.bornDay >= 0 && occupant.bornDay < frame.dayIndex
        ? `Parked since ${occupant.parkedSince || dateLabel(data.days[occupant.bornDay].date)}`
        : occupant.source === 'opening'
          ? 'Parked since before planning week (opening fleet)'
          : occupant.source === 'arrival' && occupant.bornDay === frame.dayIndex
            ? `Arrived today (${dateLabel(data.days[frame.dayIndex].date, true)})`
            : occupant.parkedSince ? `Parked since ${occupant.parkedSince}` : 'Model carry-over'
    ) : '—';

    $('#inspector-content').innerHTML = `<strong>${occupant ? `${occupant.id} · ${stand.id}` : stand.id}</strong><dl><div><dt>Area / state</dt><dd>${AREA_LABELS[stand.area]} · ${STATE_LABELS[state?.status || 'free']}</dd></div><div><dt>Position / envelope</dt><dd>${stand.name} · ${su(stand.su)}</dd></div><div><dt>Shared area budget</dt><dd>${stand.area === 'waiting' ? 'Decision area' : su(frame.capacity[stand.area])}</dd></div>${occupant ? `<div><dt>Aircraft class / footprint</dt><dd>${occupant.name} · ${su(occupant.su)}</dd></div><div><dt>Status</dt><dd>${escapeHTML(parkedOrigin)}</dd></div><div><dt>Movement</dt><dd id="inspector-motion">${escapeHTML(livePositions.get(occupant.id)?.status || 'Parked in stand')}</dd></div>` : ''}</dl><p>${stand.area === 'waiting' ? 'Awaiting manager decision. The system never accepts, refuses or diverts an aircraft.' : 'Proposed layout only. A named manager approves preparations.'}</p>`;
  }

  function highlight() {
    const focus = hover || selection, { plane, stand } = relevant(focus);
    for (const selector of ['#stand-map [data-stand]', '#stand-map [data-aircraft]', '#stand-timeline [data-stand]', '#stand-timeline [data-aircraft]']) {
      document.querySelectorAll(selector).forEach(element => element.classList.toggle('highlight', Boolean(
        element.dataset.stand && element.dataset.stand === stand?.id || element.dataset.aircraft && element.dataset.aircraft === (plane?.id || focus?.aircraftId))));
    }
  }

  function updatePositions(positions) {
    livePositions = new Map(positions.map(position => [position.id, position]));
    for (const element of $('#stand-map').querySelectorAll('[data-map-plane]')) {
      const position = livePositions.get(element.dataset.mapPlane); if (!position) continue;
      element.setAttribute('transform', `translate(${position.x} ${position.z}) rotate(${-position.rotation * 180 / Math.PI})`);
      element.style.visibility = position.visible ? 'visible' : 'hidden';
    }
    const { plane, stand } = relevant(selection);
    const current = plane || frame?.states.find(s => s.id === stand?.id)?.plane;
    const motion = $('#inspector-motion');
    if (motion && current && livePositions.has(current.id) && motion.textContent !== livePositions.get(current.id).status) {
      motion.textContent = livePositions.get(current.id).status;
    }
  }

  return {
    setLedger(value) { placements = value; generation++; timelineKey = ''; },
    update(value) { frame = value; renderMap(); renderFlow(); renderTimeline(); renderRegister(); inspector(); },
    updatePositions,
    setTime(hour) { $('#stand-timeline').style.setProperty('--playhead', `${hour / HOURS * 100}%`); },
    select(value) {
      selection = value;
      const { stand } = relevant(value);
      if (stand && area !== 'all' && !(area === 'ramp' && stand.area === 'packed') && area !== stand.area) {
        area = stand.area === 'packed' ? 'ramp' : stand.area; $('#map-area').value = area; renderMap();
      }
      highlight(); inspector();
    },
    highlight(value) { hover = value; highlight(); }
  };
}
