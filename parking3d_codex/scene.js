import * as THREE from 'three';

const palette = {
  ground: 0x0c1a23, ramp: 0x1a333d, remote: 0x1a2c35, waiting: 0x3b2429,
  stripe: 0x668994, edge: 0x84afb7, remoteEdge: 0x8eb7b2, warning: 0xed8d7f
};

function slab(scene, x, z, width, depth, color, edge, opacity = 1) {
  const surface = new THREE.Mesh(new THREE.BoxGeometry(width, .34, depth), new THREE.MeshStandardMaterial({ color, roughness: .94, transparent: opacity < 1, opacity }));
  surface.position.set(x, .18, z);
  surface.receiveShadow = true;
  scene.add(surface);
  const border = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(width, .36, depth)), new THREE.LineBasicMaterial({ color: edge, transparent: true, opacity: .85 }));
  border.position.copy(surface.position);
  scene.add(border);
  return surface;
}

function line(scene, x1, z1, x2, z2, color, opacity = .8) {
  const geometry = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(x1, .38, z1), new THREE.Vector3(x2, .38, z2)]);
  scene.add(new THREE.Line(geometry, new THREE.LineBasicMaterial({ color, transparent: true, opacity })));
}

function aircraftMesh(size, status) {
  const group = new THREE.Group();
  const bodyColor = status === 'waiting' ? 0xf29a8d : size === 'large' ? 0xbac9d1 : size === 'midsize' ? 0x82d6ce : 0xe5eee9;
  const material = new THREE.MeshStandardMaterial({ color: bodyColor, metalness: .2, roughness: .55 });
  const dark = new THREE.MeshStandardMaterial({ color: 0x375767, metalness: .1, roughness: .45 });
  const scale = Math.sqrt(size === 'large' ? 2.5 : size === 'midsize' ? 1.5 : 1);
  const fuselage = new THREE.Mesh(new THREE.CapsuleGeometry(.25, 2.7, 3, 7), material);
  fuselage.rotation.x = Math.PI / 2;
  fuselage.position.y = .95;
  group.add(fuselage);
  const nose = new THREE.Mesh(new THREE.ConeGeometry(.25, .7, 7), material);
  nose.rotation.x = -Math.PI / 2;
  nose.position.set(0, .95, -1.95);
  group.add(nose);
  const wings = new THREE.Mesh(new THREE.BoxGeometry(3.8, .07, .57), material);
  wings.position.set(0, .9, .12);
  group.add(wings);
  const tail = new THREE.Mesh(new THREE.BoxGeometry(1.55, .07, .31), material);
  tail.position.set(0, 1.01, 1.48);
  group.add(tail);
  const fin = new THREE.Mesh(new THREE.BoxGeometry(.08, .7, .52), dark);
  fin.position.set(0, 1.26, 1.45);
  group.add(fin);
  const canopy = new THREE.Mesh(new THREE.BoxGeometry(.37, .12, .8), dark);
  canopy.position.set(0, 1.15, -1.12);
  group.add(canopy);
  group.scale.setScalar(scale);
  group.traverse(object => { if (object.isMesh) { object.castShadow = true; object.receiveShadow = true; } });
  return group;
}

function positionFleet(fleet, rampCapacity, remoteCapacity) {
  const groups = { ramp: [], remote: [], waiting: [] };
  const remaining = { ramp: rampCapacity, remote: remoteCapacity };
  for (const aircraft of [...fleet].sort((a, b) => a.id.localeCompare(b.id))) {
    if (aircraft.su <= remaining.ramp + 0.001) { groups.ramp.push(aircraft); remaining.ramp -= aircraft.su; }
    else if (aircraft.su <= remaining.remote + 0.001) { groups.remote.push(aircraft); remaining.remote -= aircraft.su; }
    else groups.waiting.push(aircraft);
  }
  const result = [];
  const layouts = {
    ramp: { x: -29, z: [-14, -5, 4], rowSu: rampCapacity / 3, unit: 4 },
    remote: { x: 1, z: [-23, -14, -5, 4, 13], rowSu: 8, unit: 4 },
    waiting: { x: -33, z: [14, 23, 32], rowSu: 8, unit: 4 }
  };
  for (const [area, planes] of Object.entries(groups)) {
    const layout = layouts[area];
    let row = 0, used = 0;
    for (const aircraft of planes) {
      if (used + aircraft.su > layout.rowSu + .001 && row < layout.z.length - 1) { row++; used = 0; }
      const x = layout.x + (used + aircraft.su / 2) * layout.unit;
      result.push({ ...aircraft, area, x, z: layout.z[row] });
      used += aircraft.su;
    }
  }
  return { placed: result, ramp: groups.ramp.reduce((sum, item) => sum + item.su, 0), remote: groups.remote.reduce((sum, item) => sum + item.su, 0), waiting: groups.waiting.reduce((sum, item) => sum + item.su, 0) };
}

export function createRampScene(container, data) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(palette.ground);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  container.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(palette.ground);
  scene.fog = new THREE.Fog(palette.ground, 90, 150);
  const camera = new THREE.OrthographicCamera(-51, 51, 37, -37, .1, 300);
  camera.position.set(58, 67, 85);
  camera.lookAt(0, 0, 2);
  scene.add(new THREE.HemisphereLight(0xcee8e7, 0x16252d, 2.1));
  const sun = new THREE.DirectionalLight(0xffffff, 2.2);
  sun.position.set(-22, 45, 25); sun.castShadow = true;
  sun.shadow.mapSize.set(1024, 1024);
  sun.shadow.camera.left = -65; sun.shadow.camera.right = 65;
  sun.shadow.camera.top = 65; sun.shadow.camera.bottom = -65;
  sun.shadow.bias = -.001;
  scene.add(sun);
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(92, 78), new THREE.MeshStandardMaterial({ color: palette.ground, roughness: 1 }));
  ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; scene.add(ground);
  const grid = new THREE.GridHelper(92, 23, 0x29434d, 0x223640);
  grid.position.y = .03; grid.material.opacity = .45; grid.material.transparent = true; scene.add(grid);
  const remoteDepth = (26 * 29) * (data.capacity.overflow_apron_su / data.capacity.ramp_su) / 36;
  slab(scene, -17, -5, 26, 29, palette.ramp, palette.edge);
  slab(scene, 18, -4.5, 36, remoteDepth, palette.remote, palette.remoteEdge);
  slab(scene, -17, 23, 34, 27, palette.waiting, palette.warning);
  for (const z of [-18.5, -9.5, -.5, 8.5]) line(scene, -29, z, -5, z, palette.stripe, .45);
  for (const z of [-27.5, -18.5, -9.5, -.5, 8.5, 17.5]) line(scene, 1, z, 35, z, palette.stripe, .35);
  for (const z of [9.5, 18.5, 27.5, 36.5]) line(scene, -33, z, -1, z, palette.warning, .34);
  for (let x = -25; x < -5; x += 4) line(scene, x, -18, x, 8, palette.stripe, .25);
  line(scene, -33, 10, 37, 10, palette.stripe, .85);
  const beaconMaterial = new THREE.MeshBasicMaterial({ color: palette.warning });
  for (const x of [-33, -1]) for (const z of [10, 36]) {
    const beacon = new THREE.Mesh(new THREE.SphereGeometry(.18, 6, 5), beaconMaterial);
    beacon.position.set(x, .75, z); scene.add(beacon);
  }
  const models = new Map();
  let frame = 0;
  let visible = !document.hidden;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function resize() {
    const width = container.clientWidth, height = container.clientHeight;
    if (!width || !height) return;
    renderer.setSize(width, height, false);
    const aspect = width / height;
    const worldHeight = width < 600 ? 84 : 72;
    camera.left = -worldHeight * aspect / 2; camera.right = worldHeight * aspect / 2;
    camera.top = worldHeight / 2; camera.bottom = -worldHeight / 2;
    camera.updateProjectionMatrix();
    render();
  }
  function render() { if (visible) renderer.render(scene, camera); }
  function animate() {
    frame = 0;
    if (!visible) return;
    let moving = false;
    for (const [id, state] of models) {
      const dx = state.target.x - state.mesh.position.x;
      const dz = state.target.z - state.mesh.position.z;
      if (Math.abs(dx) + Math.abs(dz) > .08 && !reducedMotion) {
        state.mesh.position.x += dx * .22;
        state.mesh.position.z += dz * .22;
        moving = true;
      } else {
        state.mesh.position.set(state.target.x, 0, state.target.z);
        if (state.leaving) { scene.remove(state.mesh); models.delete(id); }
      }
    }
    render();
    if (moving) frame = requestAnimationFrame(animate);
  }
  function requestRender() { if (!frame) frame = requestAnimationFrame(animate); }
  function update(snapshot, prepared, preparedCapacity) {
    const rampCapacity = data.capacity.ramp_su * (prepared ? 1 + data.capacity.tow_packing_gain : 1);
    const remoteCapacity = prepared ? Math.max(0, preparedCapacity - rampCapacity) : 0;
    const layout = positionFleet(snapshot.fleet, rampCapacity, remoteCapacity);
    const keep = new Set();
    for (const item of layout.placed) {
      keep.add(item.id);
      let state = models.get(item.id);
      if (!state || state.area !== item.area || state.size !== item.name) {
        if (state) { scene.remove(state.mesh); models.delete(item.id); }
        const mesh = aircraftMesh(item.name, item.area);
        mesh.position.set(reducedMotion ? item.x : -39, 0, reducedMotion ? item.z : 10);
        scene.add(mesh);
        state = { mesh, target: { x: item.x, z: item.z }, area: item.area, size: item.name, leaving: false };
        models.set(item.id, state);
      }
      state.target = { x: item.x, z: item.z };
      state.leaving = false;
    }
    for (const [id, state] of models) if (!keep.has(id)) { state.target = { x: 42, z: 10 }; state.leaving = true; }
    requestRender();
    return layout;
  }
  const observer = new ResizeObserver(resize);
  observer.observe(container);
  const visibility = () => { visible = !document.hidden; if (visible) requestRender(); else if (frame) { cancelAnimationFrame(frame); frame = 0; } };
  document.addEventListener('visibilitychange', visibility);
  resize();
  return { update, dispose() { observer.disconnect(); document.removeEventListener('visibilitychange', visibility); if (frame) cancelAnimationFrame(frame); renderer.dispose(); container.replaceChildren(); } };
}
