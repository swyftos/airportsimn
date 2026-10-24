import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { createWorld } from './world.js';
import { createSkyline } from './skyline.js';

const colors = { free: 0x658679, occupied: 0x91a8b3, packed: 0xe7b967, overflow: 0x78baa0, waiting: 0xf08d7d };
const ease = t => t < .5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2;
const clamp = value => THREE.MathUtils.clamp(value, 0, 1);

function mesh(geometry, material, position, parent) {
  const object = new THREE.Mesh(geometry, material);
  object.position.set(...position); object.castShadow = true; object.receiveShadow = true;
  parent.add(object); return object;
}

function sweptWing(span, root, tip, sweep, material) {
  const shape = new THREE.Shape();
  shape.moveTo(0, -root / 2); shape.lineTo(span / 2, sweep - tip / 2);
  shape.lineTo(span / 2, sweep + tip / 2); shape.lineTo(0, root / 2);
  shape.lineTo(-span / 2, sweep + tip / 2); shape.lineTo(-span / 2, sweep - tip / 2); shape.closePath();
  const wing = new THREE.Mesh(new THREE.ExtrudeGeometry(shape, { depth: .15, bevelEnabled: false }), material);
  wing.rotation.x = Math.PI / 2; return wing;
}

// Bake primitive parts by material so each cloned jet is only a few draw calls.
function mergeParts(group) {
  group.updateMatrixWorld(true);
  const byMaterial = new Map(), separate = [];
  group.traverse(child => {
    if (!child.isMesh) return;
    if (child.name === 'engine-beacon') { separate.push(child); return; }
    const geometry = child.geometry.index ? child.geometry.toNonIndexed() : child.geometry.clone();
    geometry.applyMatrix4(child.matrixWorld);
    if (!byMaterial.has(child.material)) byMaterial.set(child.material, []);
    byMaterial.get(child.material).push(geometry);
  });
  const merged = new THREE.Group();
  byMaterial.forEach((geometries, material) => {
    const object = new THREE.Mesh(mergeGeometries(geometries, false), material);
    object.castShadow = true; object.receiveShadow = true; merged.add(object);
    geometries.forEach(geometry => geometry.dispose());
  });
  separate.forEach(object => merged.add(object));
  const originals = new Set(); group.traverse(object => { if (object.geometry) originals.add(object.geometry); });
  originals.forEach(geometry => geometry.dispose());
  return merged;
}

function jetTemplate(size) {
  const group = new THREE.Group();
  const white = new THREE.MeshStandardMaterial({ color: 0xe9eeed, metalness: .25, roughness: .45 });
  const trim = new THREE.MeshStandardMaterial({ color: 0x285564, metalness: .2, roughness: .4 });
  const glass = new THREE.MeshStandardMaterial({ color: 0x17333e, metalness: .6, roughness: .24 });
  const rubber = new THREE.MeshStandardMaterial({ color: 0x182329, roughness: .9 });
  const body = mesh(new THREE.CapsuleGeometry(.7, 9.2, 5, 12), white, [0, 1.8, 0], group);
  body.rotation.x = Math.PI / 2; body.scale.z = 1.05;
  const nose = mesh(new THREE.SphereGeometry(.72, 12, 8), white, [0, 1.76, -4.9], group);
  nose.scale.set(1, .9, 2.1);
  const windshield = mesh(new THREE.SphereGeometry(.7, 10, 8), glass, [0, 2.14, -4.15], group);
  windshield.scale.set(.88, .6, 1.35);
  const wings = sweptWing(13.4, 3.3, .6, 2.3, white); wings.position.set(0, 1.45, .25); group.add(wings);
  const fin = mesh(new THREE.BoxGeometry(.18, 2.8, 1.8), trim, [0, 3.08, 4.05], group); fin.rotation.x = -.18;
  const tail = sweptWing(5, 1.25, .45, .55, white); tail.position.set(0, 4.4, 4.1); group.add(tail);
  const engineGeo = new THREE.CylinderGeometry(.47, .4, 2.1, 10);
  const intakeGeo = new THREE.CylinderGeometry(.35, .35, .05, 10);
  for (const side of [-1, 1]) {
    const engine = mesh(engineGeo, white, [side * 1.15, 2.25, 2.6], group); engine.rotation.x = Math.PI / 2;
    const intake = mesh(intakeGeo, glass, [side * 1.15, 2.25, 1.52], group); intake.rotation.x = Math.PI / 2;
    for (let i = 0; i < 5; i++) {
      const window = mesh(new THREE.SphereGeometry(.14, 6, 5), glass, [side * .71, 2.1, -2.3 + i * .8], group);
      window.scale.set(.16, 1, 1.4);
    }
    const stripe = mesh(new THREE.BoxGeometry(.025, .12, 7), trim, [side * .71, 1.9, -.2], group);
    stripe.rotation.y = side * .01;
  }
  for (const [x, z] of [[-.95, 1], [.95, 1], [0, -3.4]]) {
    mesh(new THREE.CylinderGeometry(.075, .075, .9, 6), trim, [x, .7, z], group);
    const wheel = mesh(new THREE.CylinderGeometry(.27, .27, .18, 8), rubber, [x, .27, z], group); wheel.rotation.z = Math.PI / 2;
  }
  const beacon = mesh(new THREE.SphereGeometry(.1, 6, 4), new THREE.MeshBasicMaterial({ color: 0xf9bc69 }), [0, 2.65, .3], group);
  beacon.name = 'engine-beacon';
  const dimensions = [...size.example.matchAll(/([\d.]+)\s*m/g)].map(match => Number(match[1]));
  const span = dimensions[0], length = dimensions[1] || span;
  const jet = mergeParts(group);
  jet.scale.set(span / 13.4, span / 13.4, length / 12.7);
  jet.userData.span = span; jet.userData.length = length;
  return jet;
}

function tugTemplate(unit) {
  const group = new THREE.Group();
  const body = new THREE.MeshStandardMaterial({ color: 0xe6b858, roughness: .65 });
  const dark = new THREE.MeshStandardMaterial({ color: 0x253c46, roughness: .8 });
  mesh(new THREE.BoxGeometry(2.3, .85, 3.4), body, [0, .8, 0], group);
  mesh(new THREE.BoxGeometry(1.6, .8, 1.2), dark, [0, 1.5, .6], group);
  for (const x of [-1.15, 1.15]) for (const z of [-1, 1]) {
    const wheel = mesh(new THREE.CylinderGeometry(.4, .4, .3, 8), dark, [x, .4, z], group); wheel.rotation.z = Math.PI / 2;
  }
  mesh(new THREE.BoxGeometry(.15, .15, 2.3), body, [0, .4, 2.6], group);
  const tug = mergeParts(group); tug.scale.setScalar(unit / 26); return tug;
}

export function createRampScene(container, data, layout, callbacks) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.1;
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.domElement.setAttribute('aria-label', 'Interactive ramp. Drag to orbit; use camera buttons or the keyboard-accessible stand map to inspect.');
  container.appendChild(renderer.domElement);
  const labelRenderer = new CSS2DRenderer();
  labelRenderer.domElement.className = 'scene-label-layer'; container.appendChild(labelRenderer.domElement);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x172b39);
  const camera = new THREE.PerspectiveCamera(43, 1, .5, Math.max(4000, layout.width * 20));
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true; controls.dampingFactor = .08;
  controls.minPolarAngle = .08; controls.maxPolarAngle = Math.PI * .47;
  controls.minDistance = layout.unit * 1.5; controls.maxDistance = layout.width * 4;
  controls.screenSpacePanning = false;
  const world = createWorld(scene, data, layout);
  const { environment, labels } = world;
  const aircraftGroup = new THREE.Group(); scene.add(aircraftGroup);
  const color = new THREE.Color(), matrix = new THREE.Matrix4(), rotation = new THREE.Quaternion();
  const standMesh = new THREE.InstancedMesh(new THREE.BoxGeometry(1, .08, 1), new THREE.MeshStandardMaterial({ roughness: 1, transparent: true, opacity: .32 }), layout.stands.length);
  standMesh.receiveShadow = true; environment.add(standMesh);
  const stripeMat = new THREE.LineBasicMaterial({ color: 0xe6d8a5, transparent: true, opacity: .85 });
  const edgesGeo = new THREE.EdgesGeometry(new THREE.BoxGeometry(1, .08, 1));
  const centerGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, -.16), new THREE.Vector3(0, 0, .44)]);
  const standDetails = layout.stands.map(stand => {
    const edge = new THREE.LineSegments(edgesGeo, stripeMat); environment.add(edge);
    const center = new THREE.Line(centerGeo, stripeMat); environment.add(center);
    const label = world.label(stand.id, [stand.x, .7, stand.z + stand.depth * .4], 'stand');
    return { edge, center, label };
  });
  function updateStands(states) {
    states.forEach((stand, index) => {
      matrix.compose(new THREE.Vector3(stand.x, .2, stand.z), rotation, new THREE.Vector3(stand.width, 1, stand.depth));
      standMesh.setMatrixAt(index, matrix);
      const enabled = stand.enabled ?? (stand.area === 'ramp' || stand.area === 'waiting');
      standMesh.setColorAt(index, color.set(colors[stand.status || 'free']).multiplyScalar(enabled ? 1 : .24));
      const detail = standDetails[index];
      detail.edge.position.set(stand.x, .29, stand.z); detail.edge.scale.set(stand.width, 1, stand.depth);
      detail.center.position.set(stand.x, .3, stand.z); detail.center.scale.set(1, 1, stand.depth);
      detail.label.position.set(stand.x, .7, stand.z + stand.depth * .4);
      detail.edge.visible = enabled; detail.center.visible = enabled;
      detail.label.userData.enabled = enabled; detail.label.element.style.opacity = enabled ? '1' : '.45';
    });
    standMesh.instanceMatrix.needsUpdate = true; standMesh.instanceColor.needsUpdate = true;
    standMesh.computeBoundingSphere();
  }
  updateStands(layout.stands);
  const templates = Object.fromEntries(Object.entries(data.aircraft.sizes).map(([name, size]) => [name, jetTemplate(size)]));
  const tug = tugTemplate(layout.unit);
  const models = new Map();
  const selection = new THREE.Mesh(new THREE.RingGeometry(1, 1.06, 48), new THREE.MeshBasicMaterial({ color: 0x8ee9ff, side: THREE.DoubleSide, depthWrite: false }));
  selection.rotation.x = -Math.PI / 2; selection.position.y = .4; selection.visible = false; scene.add(selection);
  let frame, progress = 1, selected = null, hover = null, cameraTween = null, currentPreset = 'ramp', animationFrame = 0, disposed = false, autoOrbit = false, followId = null;
  const clock = new THREE.Clock();
  const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  const skyline = createSkyline(scene, data, layout, index => { callbacks.onDaySelect?.(index); preset('ramp'); });
  const currentStand = id => (frame?.states || layout.stands).find(stand => stand.id === id);
  const vector = p => new THREE.Vector3(p.x, .35, p.z);
  function curve(points) {
    return new THREE.CatmullRomCurve3(points.map(vector), false, 'centripetal');
  }
  function standRoute(plane, from) {
    const stand = currentStand(plane.standId), bounds = layout.areas[plane.area];
    const sideX = bounds.x - layout.unit * .35, rowZ = stand.z + stand.depth * .67;
    return curve([...world.exitPoints.slice(0, -1).map(p => ({ x: p.x, z: p.z })), from, { x: sideX, z: layout.laneZ }, { x: sideX, z: rowZ },
      { x: plane.x, z: rowZ }, { x: plane.x, z: plane.z }]);
  }
  function model(plane) {
    let record = models.get(plane.id);
    if (record && record.name !== plane.name) { aircraftGroup.remove(record.jet, record.tug, record.label); models.delete(plane.id); record = null; }
    if (!record) {
      const jet = templates[plane.name].clone(true), vehicle = tug.clone(true);
      jet.traverse(child => { if (child.isMesh) child.userData.aircraftId = plane.id; });
      const element = document.createElement('span'); element.className = 'world-label tail'; element.textContent = plane.id;
      const tail = new CSS2DObject(element); aircraftGroup.add(jet, vehicle, tail);
      record = { jet, tug: vehicle, label: tail, name: plane.name }; models.set(plane.id, record);
    }
    record.plane = plane; return record;
  }
  function update(next) {
    frame = next;
    const keep = new Set(next.placed.map(plane => plane.id));
    for (const movement of next.movements) if (movement.type === 'departure') keep.add(movement.plane.id);
    for (const [id, record] of models) if (!keep.has(id)) { aircraftGroup.remove(record.jet, record.tug, record.label); record.label.element.remove(); models.delete(id); }
    for (const plane of next.placed) { const record = model(plane); record.movement = null; }
    for (const movement of next.movements) {
      if (movement.type === 'carry-out') continue;
      const record = model(movement.plane); record.movement = movement;
      if (movement.type === 'arrival') record.path = standRoute(movement.plane, layout.entry);
      if (movement.type === 'tow') {
        const start = movement.from;
        record.path = curve([start, { x: start.x, z: start.z + layout.unit },
          { x: layout.areas[movement.plane.area].x - layout.unit * .4, z: start.z + layout.unit },
          { x: movement.plane.x, z: movement.plane.z + layout.unit }, movement.plane]);
      }
      if (movement.type === 'departure') {
        const plane = movement.plane, bounds = layout.areas[plane.area];
        record.push = curve([plane, { x: plane.x, z: plane.z + layout.unit * .45 }, { x: plane.x - layout.unit * .3, z: plane.z + layout.unit * .7 }]);
        record.path = curve([{ x: plane.x - layout.unit * .3, z: plane.z + layout.unit * .7 },
          { x: bounds.x - layout.unit * .45, z: plane.z + layout.unit * .7 },
          { x: bounds.x - layout.unit * .45, z: layout.laneZ }, layout.exit]);
      }
    }
    updateStands(next.states); world.update(next, motionQuery.matches);
  }
  function placeOnPath(object, path, t, reverse = false) {
    const fraction = clamp(t), point = path.getPointAt(fraction), tangent = path.getTangentAt(fraction);
    object.position.copy(point); object.rotation.y = Math.atan2(-tangent.x, -tangent.z) + (reverse ? Math.PI : 0);
  }
  function pose() {
    if (!frame) return;
    const positions = [];
    const t = motionQuery.matches ? 1 : progress;
    const focus = hover || selected;
    const focusId = focus?.aircraftId || frame.placed.find(plane => plane.standId === focus?.standId)?.id;
    for (const [id, record] of models) {
      const { jet, plane, movement, label: tail, tug: vehicle } = record;
      jet.visible = true; vehicle.visible = false; jet.position.set(plane.x, .35, plane.z); jet.rotation.y = 0;
      let status = plane.area === 'waiting' ? 'Awaiting manager decision' : 'Parked · engines off';
      if (movement?.type === 'arrival' && t < .88) {
        placeOnPath(jet, record.path, ease(clamp(t / .88)));
        status = plane.area === 'remote' || plane.area === 'packed' ? (t < .25 ? 'Taxi to tow staging' : 'Tug towing to approved space') : 'Taxi in · stand reserved';
        vehicle.visible = (plane.area === 'remote' || plane.area === 'packed') && t >= .25;
      } else if (movement?.type === 'arrival' && t < .98 && plane.area !== 'waiting') {
        status = 'Stand reached · engines shutting down';
      } else if (movement?.type === 'tow' && t < .9) {
        placeOnPath(jet, record.path, ease(clamp(t / .9))); vehicle.visible = true; status = plane.area === 'ramp' ? 'Illustrated repositioning tow · ramp space' : 'Illustrated tow under recorded plan';
      } else if (movement?.type === 'departure') {
        if (t < .2) { vehicle.visible = true; status = 'Tug approaching / attaching'; }
        else if (t < .48) { placeOnPath(jet, record.push, ease((t - .2) / .28), true); vehicle.visible = true; status = 'Tug pushback'; }
        else if (t < .6) {
          placeOnPath(jet, record.push, 1, true);
          const tangent = record.path.getTangentAt(0), nextHeading = Math.atan2(-tangent.x, -tangent.z);
          const angle = THREE.MathUtils.euclideanModulo(nextHeading - jet.rotation.y + Math.PI, Math.PI * 2) - Math.PI;
          jet.rotation.y += angle * ease((t - .48) / .12);
          vehicle.visible = true; status = 'Tug disconnects · preparing to taxi';
        }
        else if (t < .96) { placeOnPath(jet, record.path, ease((t - .6) / .36)); status = 'Taxi out'; }
        else { jet.visible = false; status = 'Departed illustration'; }
      } else if (movement?.type === 'carry-in') status = plane.area === 'waiting' ? 'Carry-over · manager decision' : 'Carry-over · already on site';
      if (vehicle.visible) {
        const offset = jet.userData.length / 12.7 * 3.4 + 3.75 * tug.scale.x; // towbar end meets the nose gear
        vehicle.position.copy(jet.position).add(new THREE.Vector3(0, 0, -offset).applyAxisAngle(new THREE.Vector3(0, 1, 0), jet.rotation.y));
        if (movement.type === 'departure' && t < .2) vehicle.position.x -= layout.unit * (1 - ease(t / .2));
        if (movement.type === 'departure' && t >= .48) vehicle.position.x -= layout.unit * ease(clamp((t - .48) / .12));
        vehicle.rotation.y = jet.rotation.y;
      }
      const beacon = jet.getObjectByName('engine-beacon'); if (beacon) beacon.visible = jet.visible && t < 1 && Boolean(movement) && !status.includes('off') && !status.includes('Carry-over');
      tail.position.copy(jet.position).add(new THREE.Vector3(0, jet.userData.span * .4, 0));
      tail.visible = jet.visible && (id === focusId || container.clientWidth >= 600 && camera.position.distanceTo(jet.position) < layout.unit * 8 && models.size < 24);
      tail.element.classList.toggle('highlight', id === focusId);
      positions.push({ id, x: jet.position.x, z: jet.position.z, rotation: jet.rotation.y, visible: jet.visible, status });
    }
    const activeModel = focusId && models.get(focusId);
    const stand = focus?.standId && currentStand(focus.standId);
    selection.visible = Boolean(activeModel?.jet.visible || stand);
    if (activeModel) { selection.position.set(activeModel.jet.position.x, .5, activeModel.jet.position.z); selection.scale.setScalar(layout.unit * Math.sqrt(activeModel.plane.su) * .54); }
    else if (stand) { selection.position.set(stand.x, .5, stand.z); selection.scale.setScalar(stand.width * .6); }
    labels.forEach(({ object, kind }) => { object.visible = kind !== 'stand' || object.userData.enabled && camera.position.distanceTo(object.position) < layout.unit * (container.clientWidth < 600 ? 5 : 9); });
    skyline.updateLabels(camera, currentPreset, container.clientWidth < 600);
    callbacks.onPositions?.(positions);
  }
  function setAutoOrbit(enabled) {
    autoOrbit = Boolean(enabled) && !motionQuery.matches;
    controls.autoRotate = autoOrbit; controls.autoRotateSpeed = .24;
    if (autoOrbit) { cameraTween = null; followId = null; }
    callbacks.onAutoOrbitChange?.(autoOrbit);
  }
  function preset(name, instant = false) {
    name = ({ overflow: 'remote', decision: 'waiting' })[name] || name;
    if (autoOrbit) setAutoOrbit(false);
    currentPreset = name; followId = null;
    let bounds;
    if (name === 'follow') {
      const id = selected?.aircraftId || frame?.placed.find(p => p.standId === selected?.standId)?.id;
      const record = id && models.get(id);
      if (!record) return;
      followId = id;
      const span = record.jet.userData.span;
      bounds = { x: record.jet.position.x - span, z: record.jet.position.z - span, width: span * 2, depth: span * 2 };
    } else if (name === 'overview' || name === 'isometric') {
      bounds = { x: -layout.unit * 4, z: -layout.unit * 5, width: layout.width + layout.unit * 5, depth: layout.depth + layout.unit * 6 };
    } else if (name === 'skyline') bounds = skyline.bounds;
    else if (name === 'ramp') bounds = { x: -.2 * layout.unit, z: -layout.unit * 1.6, width: layout.areas.ramp.width + layout.areas.packed.width + layout.unit * .8, depth: layout.areas.ramp.depth + layout.unit * 1.8 };
    else bounds = layout.areas[name];
    if (!bounds) return;
    const target = new THREE.Vector3(bounds.x + bounds.width / 2, name === 'skyline' ? skyline.height * .43 : 0, bounds.z + bounds.depth / 2);
    const size = Math.max(bounds.depth, bounds.width / Math.max(.45, camera.aspect), name === 'skyline' ? skyline.height * 1.4 : 0);
    const distance = size / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2))) * (name === 'ramp' ? 1.18 : 1.28);
    const direction = name === 'skyline' ? new THREE.Vector3(.25, .42, 1).normalize() : new THREE.Vector3(name === 'isometric' ? 1 : .48, name === 'isometric' ? 1 : .95, 1).normalize();
    const position = target.clone().addScaledVector(direction, distance);
    if (instant || motionQuery.matches) { camera.position.copy(position); controls.target.copy(target); controls.update(); cameraTween = null; }
    else cameraTween = { from: camera.position.clone(), to: position, targetFrom: controls.target.clone(), targetTo: target, elapsed: 0, duration: 1 };
  }
  function stopCameraMotion() { cameraTween = null; followId = null; if (autoOrbit) setAutoOrbit(false); }
  controls.addEventListener('start', stopCameraMotion);
  const raycaster = new THREE.Raycaster(), pointer = new THREE.Vector2();
  function hit(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
    raycaster.setFromCamera(pointer, camera);
    const jets = [...models.values()].filter(record => record.jet.visible).map(record => record.jet);
    const found = raycaster.intersectObjects([...jets, standMesh, ...skyline.pickables], true)[0];
    if (found?.object.userData.dayIndex !== undefined) return { dayIndex: found.object.userData.dayIndex };
    if (found?.object.userData.aircraftId) return { aircraftId: found.object.userData.aircraftId };
    if (found?.instanceId !== undefined) return { standId: (frame?.states || layout.stands)[found.instanceId].id };
    return null;
  }
  let down = null;
  const pointerDown = event => { down = { x: event.clientX, y: event.clientY }; };
  const pointerUp = event => {
    if (down && Math.hypot(event.clientX - down.x, event.clientY - down.y) < 5) {
      const picked = hit(event);
      if (picked?.dayIndex !== undefined) { callbacks.onDaySelect?.(picked.dayIndex); preset('ramp'); }
      else callbacks.onSelect?.(picked);
    }
    down = null;
  };
  renderer.domElement.addEventListener('pointerdown', pointerDown);
  renderer.domElement.addEventListener('pointerup', pointerUp);
  function resize() {
    const width = container.clientWidth, height = container.clientHeight; if (!width || !height) return;
    renderer.setSize(width, height, false); labelRenderer.setSize(width, height);
    camera.aspect = width / height; camera.updateProjectionMatrix(); preset(currentPreset, true);
  }
  const observer = new ResizeObserver(resize); observer.observe(container); resize();
  function animate() {
    animationFrame = 0; if (disposed || document.hidden) return;
    const delta = Math.min(clock.getDelta(), .1); callbacks.onFrame?.(delta);
    if (cameraTween && motionQuery.matches) {
      camera.position.copy(cameraTween.to); controls.target.copy(cameraTween.targetTo); cameraTween = null;
    }
    if (cameraTween) {
      cameraTween.elapsed += delta; const t = ease(clamp(cameraTween.elapsed / cameraTween.duration));
      camera.position.lerpVectors(cameraTween.from, cameraTween.to, t); controls.target.lerpVectors(cameraTween.targetFrom, cameraTween.targetTo, t);
      if (t === 1) cameraTween = null;
    }
    controls.enableDamping = !motionQuery.matches;
    if (motionQuery.matches && autoOrbit) setAutoOrbit(false);
    world.animate(delta, motionQuery.matches); pose();
    if (followId && !cameraTween) {
      const record = models.get(followId);
      if (record?.jet.visible) {
        const shift = record.jet.position.clone().sub(controls.target); shift.y = 0;
        camera.position.add(shift); controls.target.add(shift);
      } else followId = null;
    }
    controls.update(delta); renderer.render(scene, camera); labelRenderer.render(scene, camera);
    animationFrame = requestAnimationFrame(animate);
  }
  function visibility() {
    if (document.hidden) { cancelAnimationFrame(animationFrame); animationFrame = 0; clock.stop(); }
    else if (!animationFrame) { clock.start(); animationFrame = requestAnimationFrame(animate); }
  }
  document.addEventListener('visibilitychange', visibility); visibility();
  return {
    update, setProgress(value, hour) { progress = value; world.setHour(hour); },
    setForecast: skyline.setForecast, setAutoOrbit,
    select(value) {
      selected = value;
      if (currentPreset === 'follow') {
        if (value) preset('follow');
        else { followId = null; cameraTween = null; }
      }
    }, highlight(value) { hover = value; }, preset,
    dispose() {
      disposed = true; cancelAnimationFrame(animationFrame); observer.disconnect(); controls.dispose();
      document.removeEventListener('visibilitychange', visibility);
      renderer.domElement.removeEventListener('pointerdown', pointerDown); renderer.domElement.removeEventListener('pointerup', pointerUp);
      const geometries = new Set(), materials = new Set();
      for (const root of [scene, ...Object.values(templates), tug]) root.traverse(object => {
        if (object.geometry) geometries.add(object.geometry);
        if (object.material) for (const material of Array.isArray(object.material) ? object.material : [object.material]) materials.add(material);
      });
      geometries.forEach(geometry => geometry.dispose()); materials.forEach(material => material.dispose());
      renderer.dispose(); container.replaceChildren();
    }
  };
}
