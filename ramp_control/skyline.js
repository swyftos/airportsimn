import * as THREE from 'three';
import { CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';

// A spatial companion to the exact, accessible chart and evidence table.
export function createSkyline(scene, data, layout, onDaySelect) {
  const u = layout.unit, group = new THREE.Group(); group.name = 'Week demand skyline'; scene.add(group);
  const bounds = { x: layout.areas.remote.x - u * .35, z: -u * 3.5, width: u * 5.8, depth: u * 1.1 };
  const yScale = u * .095, cube = new THREE.BoxGeometry(1, 1, 1), columns = [], pickables = [];
  const plinth = new THREE.Mesh(cube, new THREE.MeshStandardMaterial({ color: 0x637d83, roughness: .9 }));
  plinth.position.set(bounds.x + bounds.width / 2, .1, bounds.z + bounds.depth / 2); plinth.scale.set(bounds.width + 5, .6, bounds.depth + 6); group.add(plinth);
  function label(text, x, y, z, kind = 'skyline-label') {
    const element = document.createElement('span'); element.className = `world-label ${kind}`; element.textContent = text;
    const object = new CSS2DObject(element); object.position.set(x, y, z); group.add(object); return object;
  }
  const title = label('Week skyline · demand in su', bounds.x + bounds.width / 2, 2, bounds.z + bounds.depth + 7);
  const subtitle = label('P10–P90 · solid P50 · ordinary week behind', bounds.x + bounds.width / 2, 1, bounds.z + bounds.depth + 16);
  const columnWidth = bounds.width / data.days.length * .61;
  data.days.forEach((day, index) => {
    const x = bounds.x + (index + .5) * bounds.width / data.days.length, z = bounds.z + bounds.depth * .35;
    const rangeMat = new THREE.MeshStandardMaterial({ color: 0x5495ad, emissive: 0x183744, emissiveIntensity: .25, transparent: true, opacity: .39, roughness: .45, metalness: .1, depthWrite: false });
    const medianMat = new THREE.MeshStandardMaterial({ color: 0xdceef2, emissive: 0xc5e8f3, emissiveIntensity: .2, roughness: .45 });
    const range = new THREE.Mesh(cube, rangeMat), marker = new THREE.Mesh(cube, medianMat);
    const ghost = new THREE.Mesh(cube, new THREE.MeshStandardMaterial({ color: 0xd4e6e2, transparent: true, opacity: .15, depthWrite: false, roughness: .9 }));
    const ghostMarker = new THREE.Mesh(cube, new THREE.MeshBasicMaterial({ color: 0xaec5c1, transparent: true, opacity: .65 }));
    for (const object of [range, marker, ghost, ghostMarker]) { object.position.set(x, 0, object === ghost || object === ghostMarker ? z + bounds.depth * .48 : z); group.add(object); }
    const outline = new THREE.LineSegments(new THREE.EdgesGeometry(cube), new THREE.LineBasicMaterial({ color: 0x94d4e4, transparent: true, opacity: .65 })); group.add(outline);
    range.userData.dayIndex = index; marker.userData.dayIndex = index; pickables.push(range, marker);
    const dayLabel = label(`${day.weekday.slice(0, 3)} ${Number(day.date.slice(-2))}`, x, 1.4, bounds.z - 5);
    const probability = label('', x, 0, z);
    const button = document.createElement('button'); button.type = 'button'; button.style.cssText = 'font:inherit;color:inherit;background:transparent;border:0;padding:0;cursor:pointer;pointer-events:auto;';
    probability.element.replaceChildren(button); button.addEventListener('click', event => { event.stopPropagation(); onDaySelect(index); });
    columns.push({ x, z, range, marker, ghost, ghostMarker, outline, dayLabel, probability, button });
  });
  function plane(color) {
    const object = new THREE.Mesh(cube, new THREE.MeshBasicMaterial({ color, transparent: true, opacity: .13, depthWrite: false }));
    object.position.set(bounds.x + bounds.width / 2, 0, bounds.z + bounds.depth / 2); object.scale.set(bounds.width + 3, .24, bounds.depth + 4); group.add(object);
    const edge = new THREE.LineSegments(new THREE.EdgesGeometry(cube), new THREE.LineBasicMaterial({ color, transparent: true, opacity: .9 })); edge.scale.copy(object.scale); group.add(edge);
    const text = label('', bounds.x + bounds.width + 5, 0, bounds.z + bounds.depth / 2, 'skyline-capacity'); return { object, edge, text };
  }
  const rampPlane = plane(0xe9be71), preparedPlane = plane(0x81dbb1);
  let selected = 0, forecast = [];
  function setForecast(days, selectedDay = 0) {
    forecast = days; selected = selectedDay;
    columns.forEach((column, index) => {
      const day = days[index]; if (!day) return;
      const p10 = day.parking_demand_su_p10, p90 = day.parking_demand_su_p90, ordinary = day.ordinary;
      column.range.position.y = (p10 + p90) / 2 * yScale; column.range.scale.set(columnWidth, Math.max(.04, p90 - p10) * yScale, columnWidth * .72);
      column.outline.position.copy(column.range.position); column.outline.scale.copy(column.range.scale);
      column.marker.position.y = day.parking_demand_su_p50 * yScale; column.marker.scale.set(columnWidth * 1.1, .8, columnWidth * .82);
      column.ghost.position.y = (ordinary.parking_demand_su_p10 + ordinary.parking_demand_su_p90) / 2 * yScale;
      column.ghost.scale.set(columnWidth * .8, Math.max(.04, ordinary.parking_demand_su_p90 - ordinary.parking_demand_su_p10) * yScale, columnWidth * .4);
      column.ghostMarker.position.y = ordinary.parking_demand_su_p50 * yScale; column.ghostMarker.scale.set(columnWidth * .9, .4, columnWidth * .48);
      column.range.material.color.set(day.parking_demand_su_p50 > day.capacity ? 0xe3947e : 0x62a4b7);
      column.range.material.opacity = index === selected ? .61 : .35;
      column.marker.material.emissiveIntensity = index === selected ? .65 : .15;
      column.dayLabel.element.classList.toggle('highlight', index === selected);
      const riskLevel = day.risk_level;
      const riskMeaning = data.demand_levels.labels[riskLevel];
      column.dayLabel.element.textContent = `${day.weekday.slice(0, 3)} ${Number(day.date.slice(-2))} · ${riskLevel}`;
      column.dayLabel.element.title = `${riskLevel} demand: ${riskMeaning}`;
      column.probability.position.y = p90 * yScale + 5;
      const chance = Math.round(day.probability * 100);
      column.button.textContent = `${riskLevel} · ${chance}% over capacity`;
      column.button.setAttribute('aria-label', `${day.weekday}, ${day.date}: ${riskLevel} demand (${riskMeaning}); P10 ${p10.toFixed(1)}, P50 ${day.parking_demand_su_p50.toFixed(1)}, P90 ${p90.toFixed(1)} su; ${chance}% over ${day.capacity.toFixed(1)} su. Jump to busiest hour.`);
      column.button.title = `${day.weekday}: ${riskLevel} demand (${riskMeaning}). P10 ${p10.toFixed(1)} · P50 ${day.parking_demand_su_p50.toFixed(1)} · P90 ${p90.toFixed(1)} su. Select busiest hour.`;
    });
    const day = days[selected]; if (!day) return;
    for (const [layer, capacity, text] of [
      [rampPlane, data.capacity.ramp_su, `Ramp · ${data.capacity.ramp_su.toFixed(1)} su`],
      [preparedPlane, day.capacity_prepared_su, `Prepared ${day.weekday.slice(0, 3)} · ${day.capacity_prepared_su.toFixed(1)} su`]
    ]) {
      layer.object.position.y = capacity * yScale; layer.edge.position.copy(layer.object.position);
      layer.text.position.y = capacity * yScale; layer.text.element.textContent = text;
    }
  }
  function updateLabels(camera, preset, mobile) {
    const close = preset === 'skyline' || camera.position.distanceTo(plinth.position) < u * 11;
    group.visible = forecast.length > 0;
    title.visible = close; subtitle.visible = close && !mobile;
    columns.forEach((c, i) => {
      c.dayLabel.visible = close && (!mobile || i === selected);
      c.probability.visible = close && (!mobile || i === selected);
    });
    rampPlane.text.visible = close; preparedPlane.text.visible = close;
  }
  return { bounds, group, pickables, setForecast, updateLabels, yScale, get height() { return Math.max(data.capacity.ramp_su, ...forecast.map(day => day.parking_demand_su_p90)) * yScale; } };
}
