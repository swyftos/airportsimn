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
  shape.moveTo(0, -root / 2);
  shape.lineTo(span / 2, sweep - tip / 2);
  shape.lineTo(span / 2, sweep + tip / 2);
  shape.lineTo(0, root / 2);
  shape.lineTo(-span / 2, sweep + tip / 2);
  shape.lineTo(-span / 2, sweep - tip / 2);
  shape.closePath();
  const wing = new THREE.Mesh(new THREE.ExtrudeGeometry(shape, { depth: .18, bevelEnabled: false }), material);
  wing.rotation.x = Math.PI / 2;
  return wing;
}

function winglet(height, chord, sweep, material) {
  const shape = new THREE.Shape();
  shape.moveTo(0, -chord / 2);
  shape.lineTo(height, sweep + chord / 4);
  shape.lineTo(height, sweep + chord / 2);
  shape.lineTo(0, chord / 2);
  shape.closePath();
  const geo = new THREE.ExtrudeGeometry(shape, { depth: .08, bevelEnabled: false });
  const m = new THREE.Mesh(geo, material);
  return m;
}

// Bake primitive parts by material so each cloned jet is only a few draw calls.
function mergeParts(group) {
  group.updateMatrixWorld(true);
  const byMaterial = new Map(), separate = [];
  group.traverse(child => {
    if (!child.isMesh) return;
    if (child.name === 'engine-beacon' || child.name === 'nav-light') {
      separate.push(child);
      return;
    }
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

// Brief item D: Business jets with: rounded fuselage, cabin windows, cockpit windscreen,
// swept wings with winglets, T-tail, rear-mounted engine nacelles with intakes, landing gear,
// red/green navigation lights and a beacon that blinks while moving, a livery stripe.
function jetTemplate(size) {
  const group = new THREE.Group();
  const white = new THREE.MeshStandardMaterial({ color: 0xf0f4f4, metalness: .25, roughness: .4 });
  const trim = new THREE.MeshStandardMaterial({ color: 0x1f4e5b, metalness: .3, roughness: .35 });
  const gold = new THREE.MeshStandardMaterial({ color: 0xd4a84b, metalness: .4, roughness: .35 });
  const glass = new THREE.MeshStandardMaterial({ color: 0x142b34, metalness: .7, roughness: .2 });
  const engineDark = new THREE.MeshStandardMaterial({ color: 0x1b2326, roughness: .75 });
  const rubber = new THREE.MeshStandardMaterial({ color: 0x151d21, roughness: .9 });

  // Fuselage: rounded capsule body
  const body = mesh(new THREE.CapsuleGeometry(.72, 9.4, 6, 16), white, [0, 1.8, 0], group);
  body.rotation.x = Math.PI / 2; body.scale.z = 1.05;

  // Streamlined nose cone
  const nose = mesh(new THREE.SphereGeometry(.74, 14, 10), white, [0, 1.76, -5.0], group);
  nose.scale.set(1, .92, 2.2);

  // Cockpit windscreen
  const windshield = mesh(new THREE.SphereGeometry(.72, 12, 10), glass, [0, 2.16, -4.2], group);
  windshield.scale.set(.9, .62, 1.4);

  // Swept wings
  const wingSpan = 13.8;
  const wings = sweptWing(wingSpan, 3.4, .65, 2.4, white);
  wings.position.set(0, 1.45, .25);
  group.add(wings);

  // Winglets at both wingtips
  for (const side of [-1, 1]) {
    const w = winglet(1.1, .6, .45, white);
    w.rotation.z = side * Math.PI / 2.15;
    w.rotation.y = side * .06;
    w.position.set(side * (wingSpan / 2 - .05), 1.55, 2.5);
    group.add(w);

    // Red (port) and Green (starboard) navigation lights
    const navMat = new THREE.MeshStandardMaterial({
      color: side === -1 ? 0xff2222 : 0x22ff44,
      emissive: side === -1 ? 0xff1111 : 0x11ee33,
      emissiveIntensity: 2.5
    });
    const nav = mesh(new THREE.SphereGeometry(.09, 8, 6), navMat, [side * (wingSpan / 2 + .06), 1.62, 2.5], group);
    nav.name = 'nav-light';
  }

  // T-Tail vertical fin
  const fin = mesh(new THREE.BoxGeometry(.19, 3.0, 1.9), trim, [0, 3.2, 4.1], group);
  fin.rotation.x = -.22;

  // T-Tail horizontal stabilizer atop the fin
  const tail = sweptWing(5.2, 1.3, .48, .6, white);
  tail.position.set(0, 4.65, 4.25);
  group.add(tail);

  // Rear-mounted engine nacelles with dark hollow intakes
  const engineGeo = new THREE.CylinderGeometry(.48, .42, 2.3, 12);
  const intakeLipGeo = new THREE.CylinderGeometry(.48, .48, .08, 12);
  const intakeHoleGeo = new THREE.CylinderGeometry(.38, .38, .12, 12);
  const exhaustGeo = new THREE.ConeGeometry(.28, .6, 10);

  for (const side of [-1, 1]) {
    const engine = mesh(engineGeo, white, [side * 1.18, 2.28, 2.7], group);
    engine.rotation.x = Math.PI / 2;
    const lip = mesh(intakeLipGeo, trim, [side * 1.18, 2.28, 1.52], group);
    lip.rotation.x = Math.PI / 2;
    const intakeHole = mesh(intakeHoleGeo, engineDark, [side * 1.18, 2.28, 1.5], group);
    intakeHole.rotation.x = Math.PI / 2;
    const exhaust = mesh(exhaustGeo, engineDark, [side * 1.18, 2.28, 3.9], group);
    exhaust.rotation.x = -Math.PI / 2;

    // Row of passenger cabin windows
    for (let i = 0; i < 6; i++) {
      const window = mesh(new THREE.SphereGeometry(.14, 8, 6), glass, [side * .73, 2.12, -2.4 + i * .78], group);
      window.scale.set(.18, 1, 1.35);
    }

    // Livery accent stripe
    const stripe = mesh(new THREE.BoxGeometry(.025, .14, 7.4), gold, [side * .73, 1.9, -.15], group);
    stripe.rotation.y = side * .01;
  }

  // Landing gear: nose gear + main gear
  for (const [x, z, h] of [[-.98, 1.1, .9], [.98, 1.1, .9], [0, -3.4, .9]]) {
    mesh(new THREE.CylinderGeometry(.075, .075, h, 6), trim, [x, .72, z], group);
    const wheel = mesh(new THREE.CylinderGeometry(.28, .28, .18, 10), rubber, [x, .28, z], group);
    wheel.rotation.z = Math.PI / 2;
  }

  // Blinking anti-collision beacon light on top of fuselage
  const beacon = mesh(new THREE.SphereGeometry(.11, 8, 6), new THREE.MeshBasicMaterial({ color: 0xff3b20 }), [0, 2.7, .35], group);
  beacon.name = 'engine-beacon';

  const dimensions = [...size.example.matchAll(/([\d.]+)\s*m/g)].map(match => Number(match[1]));
  const span = dimensions[0], length = dimensions[1] || span;
  const jet = mergeParts(group);
  jet.scale.set(span / 13.8, span / 13.8, length / 12.8);
  jet.userData.span = span; jet.userData.length = length;
  return jet;
}

// Brief item D: Tugs with an enclosed cab
function tugTemplate(unit) {
  const group = new THREE.Group();
  const body = new THREE.MeshStandardMaterial({ color: 0xe6b333, roughness: .6 });
  const cabWall = new THREE.MeshStandardMaterial({ color: 0x1f343e, roughness: .7 });
  const cabGlass = new THREE.MeshStandardMaterial({ color: 0x1b3b47, metalness: .7, roughness: .2 });
  const dark = new THREE.MeshStandardMaterial({ color: 0x1c272c, roughness: .85 });

  // Chassis body
  mesh(new THREE.BoxGeometry(2.4, .85, 3.6), body, [0, .75, 0], group);
  // Heavy bumpers
  mesh(new THREE.BoxGeometry(2.5, .4, .3), dark, [0, .55, -1.85], group);
  mesh(new THREE.BoxGeometry(2.5, .4, .3), dark, [0, .55, 1.85], group);

  // Enclosed Cab with roof and glass windows
  mesh(new THREE.BoxGeometry(1.8, .95, 1.5), cabWall, [0, 1.6, .4], group);
  mesh(new THREE.BoxGeometry(1.6, .7, .1), cabGlass, [0, 1.65, -.36], group); // windshield
  mesh(new THREE.BoxGeometry(.1, .65, 1.1), cabGlass, [-0.91, 1.65, .4], group); // side left
  mesh(new THREE.BoxGeometry(.1, .65, 1.1), cabGlass, [0.91, 1.65, .4], group); // side right
  mesh(new THREE.BoxGeometry(1.9, .14, 1.6), body, [0, 2.12, .4], group); // cab roof

  // 4 wheels
  for (const x of [-1.22, 1.22]) for (const z of [-1.05, 1.05]) {
    const wheel = mesh(new THREE.CylinderGeometry(.42, .42, .32, 10), dark, [x, .42, z], group);
    wheel.rotation.z = Math.PI / 2;
  }
  // Towbar
  mesh(new THREE.BoxGeometry(.16, .16, 2.5), body, [0, .4, 2.8], group);
  const tug = mergeParts(group);
  tug.scale.setScalar(unit / 26);
  return tug;
}

export function createRampScene(container, data, layout, callbacks) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.15;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.domElement.setAttribute('aria-label', 'Interactive ramp. Drag to orbit; use camera buttons or stand map to inspect.');
  container.appendChild(renderer.domElement);

  const labelRenderer = new CSS2DRenderer();
  labelRenderer.domElement.className = 'scene-label-layer';
  container.appendChild(labelRenderer.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x172b39);

  const camera = new THREE.PerspectiveCamera(43, 1, .5, Math.max(4000, layout.width * 20));
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = .08;
  controls.minPolarAngle = .08;
  controls.maxPolarAngle = Math.PI * .47;
  controls.minDistance = layout.unit * 1.5;
  controls.maxDistance = layout.width * 5;
  controls.screenSpacePanning = false;

  const world = createWorld(scene, data, layout);
  const { environment, labels } = world;
  const aircraftGroup = new THREE.Group();
  scene.add(aircraftGroup);

  const color = new THREE.Color(), matrix = new THREE.Matrix4(), rotation = new THREE.Quaternion();
  const standMesh = new THREE.InstancedMesh(new THREE.BoxGeometry(1, .08, 1), new THREE.MeshStandardMaterial({ roughness: 1, transparent: true, opacity: .32 }), layout.stands.length);
  standMesh.receiveShadow = true;
  environment.add(standMesh);

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
      if (index >= layout.stands.length) return;
      const enabled = stand.enabled ?? (stand.area === 'ramp' || stand.area === 'waiting');
      const isVisible = stand.area !== 'remote' || enabled;
      if (isVisible) {
        matrix.compose(new THREE.Vector3(stand.x, .2, stand.z), rotation, new THREE.Vector3(stand.width, 1, stand.depth));
        standMesh.setColorAt(index, color.set(colors[stand.status || 'free']).multiplyScalar(enabled ? 1 : .24));
      } else {
        // Fix 4: When lease not approved, draw no stands on overflow apron; when approved show only leased stands
        matrix.compose(new THREE.Vector3(stand.x, -50, stand.z), rotation, new THREE.Vector3(0, 0, 0));
        standMesh.setColorAt(index, color.set(0x000000));
      }
      standMesh.setMatrixAt(index, matrix);

      const detail = standDetails[index];
      if (detail) {
        detail.edge.position.set(stand.x, .29, stand.z); detail.edge.scale.set(stand.width, 1, stand.depth);
        detail.center.position.set(stand.x, .3, stand.z); detail.center.scale.set(1, 1, stand.depth);
        detail.label.position.set(stand.x, .7, stand.z + stand.depth * .4);
        detail.edge.visible = isVisible && enabled;
        detail.center.visible = isVisible && enabled;
        detail.label.userData.enabled = isVisible && enabled;
        if (!isVisible || !enabled) {
          detail.label.element.style.display = 'none';
        } else {
          detail.label.element.style.display = '';
          detail.label.element.style.opacity = '1';
        }
      }
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

  let frame, progress = 1, currentMinuteInHour = 0, selected = null, hover = null, cameraTween = null, currentPreset = 'ramp', animationFrame = 0, disposed = false, autoOrbit = false, followId = null;
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
      const record = model(movement.plane);
      record.movement = movement;
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

  // Brief item C: Movement is continuous, minute by minute; positions are interpolated every frame
  // and never jump at hour boundaries; scrubbing to any minute shows aircraft mid-taxi correctly.
  function pose() {
    if (!frame) return;
    const positions = [];
    const focus = hover || selected;
    const focusId = focus?.aircraftId || frame.placed.find(plane => plane.standId === focus?.standId)?.id;
    const elapsedTime = clock.getElapsedTime();

    for (const [id, record] of models) {
      const { jet, plane, movement, label: tail, tug: vehicle } = record;
      jet.visible = true; vehicle.visible = false;
      jet.position.set(plane.x, .35, plane.z); jet.rotation.y = 0;

      let status = plane.area === 'waiting' ? 'Awaiting manager decision' : 'Parked · engines off';
      let isMoving = false;

      // Minute-by-minute continuous movement evaluation
      if (movement?.type === 'arrival') {
        const startMin = movement.minute ?? 10;
        const dur = 4; // 4 simulated minutes to taxi to stand
        if (currentMinuteInHour < startMin) {
          jet.visible = false;
          status = 'En route · landing';
        } else if (currentMinuteInHour < startMin + dur) {
          const t = motionQuery.matches ? 1 : clamp((currentMinuteInHour - startMin) / dur);
          placeOnPath(jet, record.path, ease(t));
          isMoving = true;
          status = plane.area === 'remote' || plane.area === 'packed'
            ? (t < .3 ? 'Taxi to tow staging' : 'Tug towing to approved space')
            : 'Taxi in · stand reserved';
          vehicle.visible = (plane.area === 'remote' || plane.area === 'packed') && t >= .3;
        } else {
          status = 'Stand reached · engines shutting down';
        }
      } else if (movement?.type === 'tow') {
        const startMin = movement.minute ?? 15;
        const dur = 3;
        if (currentMinuteInHour >= startMin && currentMinuteInHour < startMin + dur) {
          const t = motionQuery.matches ? 1 : clamp((currentMinuteInHour - startMin) / dur);
          placeOnPath(jet, record.path, ease(t));
          vehicle.visible = true;
          isMoving = true;
          status = plane.area === 'ramp' ? 'Repositioning tow · ramp' : 'Tow to approved space';
        }
      } else if (movement?.type === 'departure') {
        const startMin = movement.minute ?? 25;
        const dur = 5; // 5 simulated minutes total pushback & taxi out
        if (currentMinuteInHour < startMin) {
          status = 'Parked · preparing for departure';
        } else if (currentMinuteInHour < startMin + 1) {
          vehicle.visible = true;
          status = 'Tug approaching / attaching';
        } else if (currentMinuteInHour < startMin + 2.5) {
          const t = motionQuery.matches ? 1 : clamp((currentMinuteInHour - (startMin + 1)) / 1.5);
          placeOnPath(jet, record.push, ease(t), true);
          vehicle.visible = true;
          isMoving = true;
          status = 'Tug pushback';
        } else if (currentMinuteInHour < startMin + 3) {
          placeOnPath(jet, record.push, 1, true);
          const tangent = record.path.getTangentAt(0), nextHeading = Math.atan2(-tangent.x, -tangent.z);
          const angle = THREE.MathUtils.euclideanModulo(nextHeading - jet.rotation.y + Math.PI, Math.PI * 2) - Math.PI;
          const t = motionQuery.matches ? 1 : clamp((currentMinuteInHour - (startMin + 2.5)) / .5);
          jet.rotation.y += angle * ease(t);
          vehicle.visible = true;
          status = 'Tug disconnects · ready to taxi';
        } else if (currentMinuteInHour < startMin + dur) {
          const t = motionQuery.matches ? 1 : clamp((currentMinuteInHour - (startMin + 3)) / 2);
          placeOnPath(jet, record.path, ease(t));
          isMoving = true;
          status = 'Taxi out to runway exit';
        } else {
          jet.visible = false;
          status = 'Departed illustration';
        }
      } else if (movement?.type === 'carry-in') {
        status = plane.parkedSince ? `Parked since ${plane.parkedSince}` : 'Parked · on site';
      }

      if (vehicle.visible) {
        const offset = jet.userData.length / 12.8 * 3.4 + 3.75 * tug.scale.x;
        vehicle.position.copy(jet.position).add(new THREE.Vector3(0, 0, -offset).applyAxisAngle(new THREE.Vector3(0, 1, 0), jet.rotation.y));
        vehicle.rotation.y = jet.rotation.y;
      }

      // Brief item D: Beacon that blinks while moving
      const beacon = jet.getObjectByName('engine-beacon');
      if (beacon) {
        const blink = Math.sin(elapsedTime * 10) > .15;
        beacon.visible = jet.visible && isMoving && blink;
      }

      // Brief item E: Declutter labels
      // Tail labels only show for selected/hovered plane or when camera is close
      const cameraDist = camera.position.distanceTo(jet.position);
      tail.position.copy(jet.position).add(new THREE.Vector3(0, jet.userData.span * .45, 0));
      const showTail = id === focusId || (cameraDist < layout.unit * 3.5 && models.size < 16);
      tail.visible = jet.visible && showTail;
      tail.element.classList.toggle('highlight', id === focusId);

      positions.push({ id, x: jet.position.x, z: jet.position.z, rotation: jet.rotation.y, visible: jet.visible, status });
    }

    const activeModel = focusId && models.get(focusId);
    const stand = focus?.standId && currentStand(focus.standId);
    selection.visible = Boolean(activeModel?.jet.visible || stand);
    if (activeModel) {
      selection.position.set(activeModel.jet.position.x, .5, activeModel.jet.position.z);
      selection.scale.setScalar(layout.unit * Math.sqrt(activeModel.plane.su) * .54);
    } else if (stand) {
      selection.position.set(stand.x, .5, stand.z);
      selection.scale.setScalar(stand.width * .6);
    }

    // Brief item E: Declutter stand labels - only show when camera zoomed close, never in overview/isometric
    const isIsoOrOverview = currentPreset === 'isometric' || currentPreset === 'overview';
    labels.forEach(({ object, kind }) => {
      if (kind === 'stand') {
        const d = camera.position.distanceTo(object.position);
        object.visible = !isIsoOrOverview && object.userData.enabled && d < layout.unit * (container.clientWidth < 600 ? 3.5 : 5.5);
      } else {
        object.visible = true;
      }
    });

    skyline.updateLabels(camera, currentPreset, container.clientWidth < 600);
    callbacks.onPositions?.(positions);
  }

  function setAutoOrbit(enabled) {
    autoOrbit = Boolean(enabled) && !motionQuery.matches;
    controls.autoRotate = autoOrbit; controls.autoRotateSpeed = .24;
    if (autoOrbit) { cameraTween = null; followId = null; }
    callbacks.onAutoOrbitChange?.(autoOrbit);
  }

  // Brief item E: The default camera and "Overview" frame every area that holds aircraft
  // Brief item F: Fix the isometric view with classic 35.26°/45° angle and narrow FOV
  function preset(name, instant = false) {
    name = ({ overflow: 'remote', decision: 'waiting' })[name] || name;
    if (autoOrbit) setAutoOrbit(false);
    currentPreset = name; followId = null;

    let bounds, direction, targetFov = 43;

    if (name === 'follow') {
      const id = selected?.aircraftId || frame?.placed.find(p => p.standId === selected?.standId)?.id;
      const record = id && models.get(id);
      if (!record) return;
      followId = id;
      const span = record.jet.userData.span;
      bounds = { x: record.jet.position.x - span, z: record.jet.position.z - span, width: span * 2, depth: span * 2 };
      direction = new THREE.Vector3(.45, .8, 1).normalize();
    } else if (name === 'overview' || name === 'isometric') {
      // Fix 4: Overview and Isometric frame the areas actually in use so the jets are larger on screen
      const activeAreas = [layout.areas.ramp, layout.areas.packed];
      if (frame?.sums?.waiting > 0 || frame?.placed?.some(p => p.area === 'waiting')) {
        activeAreas.push(layout.areas.waiting);
      }
      if (frame?.capacity?.remote > 0 || frame?.placed?.some(p => p.area === 'remote')) {
        activeAreas.push(layout.areas.remote);
      }
      const padX = name === 'isometric' ? layout.unit * .3 : layout.unit * .5;
      const padZ = name === 'isometric' ? layout.unit * .5 : layout.unit * .8;
      const minX = Math.min(...activeAreas.map(a => a.x)) - padX;
      const maxX = Math.max(...activeAreas.map(a => a.x + a.width)) + padX;
      const minZ = Math.min(...activeAreas.map(a => a.z), layout.laneZ) - padZ;
      const maxZ = Math.max(...activeAreas.map(a => a.z + a.depth)) + padZ;
      bounds = { x: minX, z: minZ, width: maxX - minX, depth: maxZ - minZ };
      if (name === 'isometric') {
        targetFov = 18;
        direction = new THREE.Vector3(1, 1, 1).normalize();
      } else {
        direction = new THREE.Vector3(.25, .95, .9).normalize();
      }
    } else if (name === 'skyline') {
      bounds = skyline.bounds;
      direction = new THREE.Vector3(.25, .42, 1).normalize();
    } else if (name === 'ramp') {
      bounds = { x: -.2 * layout.unit, z: -layout.unit * 1.5, width: layout.areas.ramp.width + layout.areas.packed.width + layout.unit * .8, depth: layout.areas.ramp.depth + layout.unit * 1.8 };
      direction = new THREE.Vector3(.45, .88, 1).normalize();
    } else {
      bounds = layout.areas[name] || layout.areas.ramp;
      direction = new THREE.Vector3(.45, .88, 1).normalize();
    }

    camera.fov = targetFov;
    camera.updateProjectionMatrix();

    const target = new THREE.Vector3(bounds.x + bounds.width / 2, name === 'skyline' ? skyline.height * .43 : 0, bounds.z + bounds.depth / 2);
    const size = Math.max(bounds.depth, bounds.width / Math.max(.45, camera.aspect), name === 'skyline' ? skyline.height * 1.4 : 0);
    const distanceMultiplier = name === 'isometric' ? 1.05 : name === 'overview' ? 1.15 : 1.25;
    const distance = (size / (2 * Math.tan(THREE.MathUtils.degToRad(targetFov / 2)))) * distanceMultiplier;
    const position = target.clone().addScaledVector(direction, distance);

    if (instant || motionQuery.matches) {
      camera.position.copy(position); controls.target.copy(target); controls.update(); cameraTween = null;
    } else {
      cameraTween = { from: camera.position.clone(), to: position, targetFrom: controls.target.clone(), targetTo: target, elapsed: 0, duration: 1 };
    }
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

  // Fix 5: Hide world labels that collide with each other or with the HTML controls and panels
  function declutterLabels() {
    const stage = container.parentElement || container;
    const obstacles = [];
    const obstacleSelectors = [
      '.camera-controls',
      '.camera-controls button',
      '.scene-heading',
      '.scene-actions',
      '.scene-hud',
      '.timeline',
      '.scene-corner',
      '.pause-stage-banner'
    ];
    for (const sel of obstacleSelectors) {
      const els = stage.querySelectorAll(sel);
      for (const el of els) {
        if (el && el.offsetParent !== null) {
          const r = el.getBoundingClientRect();
          if (r.width > 0 && r.height > 0) obstacles.push(r);
        }
      }
    }

    const stageRect = stage.getBoundingClientRect();
    const labelEls = labelRenderer.domElement.querySelectorAll('.world-label');
    const visibleRects = [];

    // Priority rank: tail labels > area labels > gate labels > stand labels
    const sorted = Array.from(labelEls).sort((a, b) => {
      const rank = el => {
        if (el.classList.contains('tail')) return 1;
        if (el.classList.contains('area')) return 2;
        if (el.classList.contains('gate')) return 3;
        return 4;
      };
      return rank(a) - rank(b);
    });

    const pad = 2;
    for (const el of sorted) {
      if (el.style.display === 'none') continue;
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;

      if (r.left < stageRect.left || r.right > stageRect.right || r.top < stageRect.top || r.bottom > stageRect.bottom) {
        el.style.visibility = 'hidden';
        continue;
      }

      let collides = false;
      for (const obs of obstacles) {
        if (!(r.right + pad <= obs.left || r.left - pad >= obs.right || r.bottom + pad <= obs.top || r.top - pad >= obs.bottom)) {
          collides = true;
          break;
        }
      }

      if (!collides) {
        for (const vis of visibleRects) {
          if (!(r.right + pad <= vis.left || r.left - pad >= vis.right || r.bottom + pad <= vis.top || r.top - pad >= vis.bottom)) {
            collides = true;
            break;
          }
        }
      }

      if (collides) {
        el.style.visibility = 'hidden';
      } else {
        el.style.visibility = '';
        visibleRects.push(r);
      }
    }
  }

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
    declutterLabels();
    animationFrame = requestAnimationFrame(animate);
  }

  function visibility() {
    if (document.hidden) { cancelAnimationFrame(animationFrame); animationFrame = 0; clock.stop(); }
    else if (!animationFrame) { clock.start(); animationFrame = requestAnimationFrame(animate); }
  }
  document.addEventListener('visibilitychange', visibility); visibility();

  return {
    update,
    setProgress(value, hour) {
      progress = value;
      currentMinuteInHour = ((hour % 1) + 1e-7) * 60;
      world.setHour(hour);
    },
    setForecast: skyline.setForecast, setAutoOrbit,
    select(value) {
      selected = value;
      if (currentPreset === 'follow') {
        if (value) preset('follow');
        else { followId = null; cameraTween = null; }
      }
    },
    highlight(value) { hover = value; },
    preset,
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
