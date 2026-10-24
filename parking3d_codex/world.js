import * as THREE from 'three';
import { CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';
import { AREA_LABELS } from './layout.js';

// Dimensions below describe a fictional illustration, never additional capacity.
export function createWorld(scene, data, layout) {
  const u = layout.unit, ramp = layout.areas.ramp;
  const environment = new THREE.Group(); environment.name = 'Fictional FBO world'; scene.add(environment);
  const cube = new THREE.BoxGeometry(1, 1, 1), matrix = new THREE.Matrix4(), labels = [];
  const materials = {
    ground: new THREE.MeshStandardMaterial({ color: 0x768379, roughness: 1 }),
    apron: new THREE.MeshStandardMaterial({ color: 0xd1d3cc, roughness: .92 }),
    packed: new THREE.MeshStandardMaterial({ color: 0xa9a493, roughness: .92 }),
    remote: new THREE.MeshStandardMaterial({ color: 0x8f9c98, roughness: .92 }),
    waiting: new THREE.MeshStandardMaterial({ color: 0xb4a39a, roughness: .92 }),
    asphalt: new THREE.MeshStandardMaterial({ color: 0x47565e, roughness: .96 }),
    wall: new THREE.MeshStandardMaterial({ color: 0xd8ddd7, roughness: .75 }),
    hangarWall: new THREE.MeshStandardMaterial({ color: 0x9ca9b0, roughness: .7, metalness: .25 }),
    hangarDoor: new THREE.MeshStandardMaterial({ color: 0x3f5663, roughness: .55, metalness: .4 }),
    roof: new THREE.MeshStandardMaterial({ color: 0x2b3d45, metalness: .45, roughness: .55 }),
    trim: new THREE.MeshStandardMaterial({ color: 0x203840, metalness: .5, roughness: .45 }),
    canopy: new THREE.MeshStandardMaterial({ color: 0x1b2c33, metalness: .6, roughness: .35 }),
    glass: new THREE.MeshStandardMaterial({ color: 0x3a7082, emissive: 0x82b8c0, emissiveIntensity: .15, metalness: .7, roughness: .15 }),
    warmGlass: new THREE.MeshStandardMaterial({ color: 0x588c9a, emissive: 0xffd090, emissiveIntensity: .18, metalness: .5, roughness: .2 }),
    paint: new THREE.MeshStandardMaterial({ color: 0xf4e28e, roughness: .85 }),
    paintWhite: new THREE.MeshStandardMaterial({ color: 0xedf2f2, roughness: .85 }),
    seam: new THREE.MeshStandardMaterial({ color: 0xa4ada8, roughness: 1 }),
    barrier: new THREE.MeshStandardMaterial({ color: 0xe7c877, roughness: .6 }),
    dark: new THREE.MeshStandardMaterial({ color: 0x223238, roughness: .9 }),
    gpuBody: new THREE.MeshStandardMaterial({ color: 0xe0ad43, roughness: .6 }),
    gpuDark: new THREE.MeshStandardMaterial({ color: 0x2b363a, roughness: .85 })
  };

  function box(x, y, z, width, height, depth, material, parent = environment) {
    const object = new THREE.Mesh(cube, material); object.position.set(x, y, z); object.scale.set(width, height, depth);
    object.receiveShadow = true; object.castShadow = height > 1; parent.add(object); return object;
  }

  function label(text, position, kind = 'area') {
    const element = document.createElement('span'); element.className = `world-label ${kind}`; element.textContent = text;
    const object = new CSS2DObject(element); object.position.set(...position); environment.add(object); labels.push({ object, kind }); return object;
  }

  function instances(items, material, geometry = cube) {
    const group = new THREE.InstancedMesh(geometry, material, items.length);
    items.forEach((item, index) => {
      matrix.compose(new THREE.Vector3(...item.position), new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), item.rotation || 0), new THREE.Vector3(...(item.scale || [1, 1, 1])));
      group.setMatrixAt(index, matrix);
    });
    group.receiveShadow = true; group.castShadow = true;
    environment.add(group); return group;
  }

  // Base grass/ground
  box(layout.width / 2, -.7, layout.depth / 2, layout.width + u * 30, 1, layout.depth + u * 30, materials.ground);

  // Apron concrete pads and expansion seams
  const seamItems = [];
  for (const [area, bounds] of Object.entries(layout.areas)) {
    box(bounds.x + bounds.width / 2, .01, bounds.z + bounds.depth / 2, bounds.width, .18, bounds.depth, materials[area === 'ramp' ? 'apron' : area]);
    const areaLabel = label(AREA_LABELS[area], [bounds.x + bounds.width / 2, 3.2, bounds.z - u * .18]);
    areaLabel.userData.area = area;
    for (let x = bounds.x + u * .7; x < bounds.x + bounds.width; x += u * .7) seamItems.push({ position: [x, .12, bounds.z + bounds.depth / 2], scale: [.08, .015, bounds.depth] });
    for (let z = bounds.z + u * .7; z < bounds.z + bounds.depth; z += u * .7) seamItems.push({ position: [bounds.x + bounds.width / 2, .12, z], scale: [bounds.width, .015, .08] });
  }
  instances(seamItems, materials.seam);

  // Continuous taxilane, runway and curved runway exit
  box(layout.width / 2, .025, layout.laneZ, layout.width + u * 6, .18, u * .82, materials.asphalt);
  const runwayX = -u * 4.2, runwayZ = -u * 1.2, runwayDepth = layout.depth + u * 12;
  box(runwayX, -.04, runwayZ, u * 1.8, .18, runwayDepth, materials.asphalt);
  const exitPoints = [
    new THREE.Vector3(runwayX, .14, layout.laneZ - u * 2.2),
    new THREE.Vector3(runwayX + u * .2, .14, layout.laneZ - u),
    new THREE.Vector3(-u * 2.8, .14, layout.laneZ),
    new THREE.Vector3(layout.entry.x, .14, layout.entry.z)
  ];
  const exitCurve = new THREE.CatmullRomCurve3(exitPoints), exitSamples = exitCurve.getSpacedPoints(24);
  const vertices = [], triangles = [];
  exitSamples.forEach((point, i) => {
    const tangent = exitCurve.getTangentAt(i / 24), normal = new THREE.Vector3(-tangent.z, 0, tangent.x).multiplyScalar(u * .41);
    vertices.push(point.x + normal.x, .14, point.z + normal.z, point.x - normal.x, .14, point.z - normal.z);
    if (i < 24) { const a = i * 2; triangles.push(a, a + 2, a + 1, a + 1, a + 2, a + 3); }
  });
  const exitGeo = new THREE.BufferGeometry(); exitGeo.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3)); exitGeo.setIndex(triangles); exitGeo.computeVertexNormals();
  const exitRoad = new THREE.Mesh(exitGeo, materials.asphalt); exitRoad.receiveShadow = true; environment.add(exitRoad);

  // Markings, centerlines and hold lines
  const markings = [], centerLights = [], edgeLights = [];
  for (let x = -u * 2; x < layout.width + u * 2.8; x += u * .45) {
    markings.push({ position: [x, .16, layout.laneZ], scale: [u * .26, .025, .22] });
    centerLights.push({ position: [x, .2, layout.laneZ], scale: [.18, .12, .18] });
    for (const side of [-1, 1]) edgeLights.push({ position: [x, .3, layout.laneZ + side * u * .39], scale: [.22, .22, .22] });
  }
  for (let z = runwayZ - runwayDepth / 2 + u; z < runwayZ + runwayDepth / 2; z += u * 1.5) {
    markings.push({ position: [runwayX, .1, z], scale: [.95, .02, u * .6] });
  }
  exitSamples.forEach((p, i) => {
    const tangent = exitCurve.getTangentAt(i / 24), normal = new THREE.Vector3(-tangent.z, 0, tangent.x);
    markings.push({ position: [p.x, .18, p.z], scale: [.2, .02, u * .17], rotation: Math.atan2(tangent.x, tangent.z) });
    centerLights.push({ position: [p.x, .22, p.z], scale: [.18, .12, .18] });
    if (i % 2 === 0) for (const side of [-1, 1]) edgeLights.push({ position: [p.x + normal.x * u * .39 * side, .3, p.z + normal.z * u * .39 * side], scale: [.22, .22, .22] });
  });

  // Brief item D: Painted lead-in lines and stand numbers on the apron, hold lines
  const holdShortMarkings = [];
  const holdZ = layout.laneZ + u * .42;
  for (let x = -u * 1.5; x < layout.width + u * 2; x += u * .35) {
    holdShortMarkings.push({ position: [x, .17, holdZ], scale: [u * .18, .025, .12] });
    holdShortMarkings.push({ position: [x, .17, holdZ + .2], scale: [u * .18, .025, .12] });
  }
  instances(holdShortMarkings, materials.paint);

  // Stand lead-in lines: from taxilane into each stand
  const leadInLines = [];
  for (const stand of layout.stands) {
    const startZ = holdZ + .3;
    const len = stand.z - startZ;
    if (len > 0) {
      leadInLines.push({ position: [stand.x, .16, startZ + len / 2], scale: [.18, .025, len] });
    }
    // Stand boundary T-stop bar at the head of the stand
    leadInLines.push({ position: [stand.x, .17, stand.z + stand.depth * .38], scale: [stand.width * .5, .025, .2] });
    // Painted stand number placard on tarmac
    markings.push({ position: [stand.x, .17, stand.z - stand.depth * .4], scale: [u * .42, .025, u * .25] });
  }
  instances(leadInLines, materials.paint);
  instances(markings, materials.paint);

  // Runway edge & center lights
  const centerMat = new THREE.MeshStandardMaterial({ color: 0x80ddb0, emissive: 0x32ee88, emissiveIntensity: 2 });
  const edgeMat = new THREE.MeshStandardMaterial({ color: 0x64b4e4, emissive: 0x428bff, emissiveIntensity: 2 });
  const bulb = new THREE.SphereGeometry(1, 6, 4);
  instances(centerLights, centerMat, bulb); instances(edgeLights, edgeMat, bulb);
  label('Runway exit · taxiway', [runwayX + u, 3, layout.laneZ - u * 2.1]);

  // Brief item D: Terminal with glass and a canopy
  const terminalX = ramp.width * .38, terminalZ = -u * 3.1, terminalWidth = ramp.width * .82;
  box(terminalX, 6.2, terminalZ, terminalWidth, 12.4, u * .95, materials.wall);
  box(terminalX, 12.6, terminalZ, terminalWidth + u * .15, .75, u * 1.05, materials.roof);
  // Multi-tier curtain wall glass
  box(terminalX, 6.0, terminalZ + u * .48, terminalWidth * .92, 8.2, .22, materials.warmGlass);
  // Architectural Canopy: cantilevered steel canopy projecting out over the apron walk
  const canopyDepth = u * .95;
  const canopyZ = terminalZ + u * .48 + canopyDepth / 2;
  box(terminalX, 5.8, canopyZ, terminalWidth * .72, .38, canopyDepth, materials.canopy);
  // Canopy fascia trim and support columns
  box(terminalX, 5.8, canopyZ + canopyDepth / 2, terminalWidth * .73, .55, .15, materials.trim);
  const canopyColumns = [
    { position: [terminalX - terminalWidth * .34, 2.9, canopyZ + canopyDepth * .42], scale: [.3, 5.8, .3] },
    { position: [terminalX - terminalWidth * .12, 2.9, canopyZ + canopyDepth * .42], scale: [.3, 5.8, .3] },
    { position: [terminalX + terminalWidth * .12, 2.9, canopyZ + canopyDepth * .42], scale: [.3, 5.8, .3] },
    { position: [terminalX + terminalWidth * .34, 2.9, canopyZ + canopyDepth * .42], scale: [.3, 5.8, .3] }
  ];
  instances(canopyColumns, materials.trim);
  // Glass entrance doors under canopy
  box(terminalX, 2.4, terminalZ + u * .5, terminalWidth * .35, 4.6, .28, materials.glass);

  // Terminal structural mullions
  const terminalMullions = [];
  for (let x = terminalX - terminalWidth * .45; x <= terminalX + terminalWidth * .46; x += u * .24) {
    terminalMullions.push({ position: [x, 6.0, terminalZ + u * .5], scale: [.22, 8.4, .25] });
  }
  instances(terminalMullions, materials.roof);

  // Brief item D: Hangar with doors
  const hangarX = ramp.width + u * .8, hangarZ = terminalZ - u * .35, hangarWidth = u * 2.5, hangarDepth = u * 1.9;
  box(hangarX, 10.5, hangarZ, hangarWidth, 21, hangarDepth, materials.hangarWall);
  box(hangarX, 21.2, hangarZ, hangarWidth + 1.6, 1.1, hangarDepth + 1.6, materials.roof);
  // Hangar sliding doors: multi-panel industrial doors
  const doorWidth = hangarWidth * .88;
  const doorHeight = 15.2;
  const doorZ = hangarZ + hangarDepth / 2 + .15;
  box(hangarX, doorHeight / 2 + .1, doorZ, doorWidth, doorHeight, .32, materials.hangarDoor);
  // Vertical sliding door panel mullions and bottom runner track
  box(hangarX, .18, doorZ + .2, doorWidth + 1, .15, .35, materials.dark);
  const doorPanels = [];
  const panelStep = doorWidth / 6;
  for (let i = 0; i <= 6; i++) {
    const px = hangarX - doorWidth / 2 + i * panelStep;
    doorPanels.push({ position: [px, doorHeight / 2 + .1, doorZ + .18], scale: [.28, doorHeight, .25] });
  }
  instances(doorPanels, materials.trim);
  // Transom windows above hangar doors
  box(hangarX, 17.5, doorZ + .1, doorWidth * .96, 3.2, .2, materials.glass);

  label('FBO terminal', [terminalX, 15, terminalZ]);
  label('Executive hangar', [hangarX, 24, hangarZ]);

  // Brief item D: Ground Power Units (GPU carts) stationed on the apron
  const gpuItems = [], gpuDetailItems = [];
  const activeStands = layout.stands.filter(s => s.area === 'ramp' || s.area === 'packed');
  for (const s of activeStands.slice(0, 8)) {
    const gx = s.x - s.width * .44, gz = s.z + s.depth * .35;
    gpuItems.push({ position: [gx, .65, gz], scale: [1.6, 1.1, 2.2] });
    gpuDetailItems.push({ position: [gx, 1.25, gz], scale: [1.2, .25, 1.6] });
  }
  instances(gpuItems, materials.gpuBody);
  instances(gpuDetailItems, materials.gpuDark);

  // Brief item D: Light masts that glow at night
  const lightPoints = Object.entries(layout.areas).flatMap(([area, b]) => [
    { area, x: b.x + 2, z: b.z + b.depth * .15 },
    { area, x: b.x + b.width - 2, z: b.z + b.depth * .85 }
  ]);
  const mastBaseItems = [], mastTowerItems = [], lampHeadItems = [], apronLights = [];
  const lampMaterial = new THREE.MeshStandardMaterial({ color: 0xfff0cb, emissive: 0xffdca0, emissiveIntensity: .3 });

  for (const p of lightPoints) {
    mastBaseItems.push({ position: [p.x, .8, p.z], scale: [1.2, 1.6, 1.2] });
    mastTowerItems.push({ position: [p.x, 9.5, p.z], scale: [.42, 18, .42] });
    lampHeadItems.push({ position: [p.x, 18.2, p.z], scale: [3.4, .55, 1.4] });

    const light = new THREE.PointLight(0xffecd0, 0, u * 4.5, 1.4);
    light.position.set(p.x, 17.5, p.z);
    light.userData.area = p.area;
    scene.add(light);
    apronLights.push(light);
  }
  instances(mastBaseItems, materials.dark);
  instances(mastTowerItems, materials.roof);

  const lamps = Object.keys(layout.areas).map(area => {
    const mat = lampMaterial.clone();
    const mesh = instances(lampHeadItems.filter((_, index) => lightPoints[index].area === area), mat);
    return { area, material: mat, mesh };
  });
  lampMaterial.dispose();

  // Overflow entrance barrier that opens when approved
  const remote = layout.areas.remote, gateX = remote.x - u * .18, gateZ = remote.z - u * .02;
  box(gateX, 1.1, gateZ, 1.3, 2.2, 1.3, materials.dark);
  const barrier = new THREE.Group(); barrier.position.set(gateX, 2.3, gateZ); environment.add(barrier);
  const armLength = u * .75; box(armLength / 2, 0, 0, armLength, .48, .55, materials.barrier, barrier);
  for (let x = 1.4; x < armLength; x += 3.2) box(x, 0, .29, 1.3, .5, .025, materials.dark, barrier);
  const gateLabel = label('Overflow apron · not approved / closed', [gateX + armLength / 2, 4.2, gateZ - 3], 'gate');

  const packedMaterial = new THREE.MeshStandardMaterial({ color: 0x766b48, emissive: 0xeac166, emissiveIntensity: 0 });
  const remoteMaterial = new THREE.MeshStandardMaterial({ color: 0x516861, emissive: 0x79d5b1, emissiveIntensity: 0 });
  for (const [area, mat] of [['packed', packedMaterial], ['remote', remoteMaterial]]) {
    const b = layout.areas[area]; box(b.x + b.width / 2, .22, b.z + .25, b.width, .12, .38, mat);
  }

  // Dimmed perimeter outline for the overflow apron (Fix 4: closed dimmed outline when not approved)
  const rBounds = layout.areas.remote;
  const rx0 = rBounds.x, rx1 = rBounds.x + rBounds.width;
  const rz0 = rBounds.z, rz1 = rBounds.z + rBounds.depth;
  const ry = .15;
  const remoteOutlineGeo = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(rx0, ry, rz0),
    new THREE.Vector3(rx1, ry, rz0),
    new THREE.Vector3(rx1, ry, rz1),
    new THREE.Vector3(rx0, ry, rz1),
    new THREE.Vector3(rx0, ry, rz0)
  ]);
  const remoteOutlineMat = new THREE.LineBasicMaterial({ color: 0x5a6d67, transparent: true, opacity: .75 });
  const remoteOutline = new THREE.Line(remoteOutlineGeo, remoteOutlineMat);
  environment.add(remoteOutline);

  // Sky dome and lighting
  const sky = new THREE.Mesh(new THREE.SphereGeometry(layout.width * 8, 24, 12), new THREE.ShaderMaterial({
    uniforms: { top: { value: new THREE.Color(0x77b6e1) }, horizon: { value: new THREE.Color(0xe1edf1) } },
    vertexShader: 'varying vec3 vPosition; void main(){vPosition=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
    fragmentShader: `uniform vec3 top; uniform vec3 horizon; varying vec3 vPosition;
      void main(){float t=smoothstep(-0.08,0.68,normalize(vPosition).y);gl_FragColor=vec4(mix(horizon,top,t),1.0);
      #include <tonemapping_fragment>
      #include <colorspace_fragment>
      }`,
    side: THREE.BackSide, depthWrite: false, fog: false
  })); sky.renderOrder = -10; scene.add(sky);
  scene.fog = new THREE.Fog(0xc5dce4, layout.width * 1.3, layout.width * 5.2);

  const hemisphere = new THREE.HemisphereLight(0xdff2ff, 0x8e9a82, 3.2); scene.add(hemisphere);
  const sun = new THREE.DirectionalLight(0xfff4dc, 4.4);
  sun.castShadow = true; scene.add(sun, sun.target);
  sun.target.position.set(ramp.width / 2, 0, ramp.depth / 2);

  // Soft shadows with tight ramp focus
  const shadowExtent = Math.max(ramp.width, ramp.depth) * .85;
  Object.assign(sun.shadow.camera, {
    left: -shadowExtent, right: shadowExtent,
    top: shadowExtent, bottom: -shadowExtent,
    near: 1, far: layout.width * 3.5
  });
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.normalBias = .2;
  sun.shadow.bias = -.00015;
  sun.shadow.radius = 3.5;

  let daylight = 1, packed = false, remoteOpen = false, gateTarget = 0;
  const color = new THREE.Color();

  function updateLighting() {
    const night = 1 - daylight;
    materials.warmGlass.emissiveIntensity = .14 + night * 1.3;
    materials.glass.emissiveIntensity = .12 + night * .75;
    centerMat.emissiveIntensity = .8 + night * 3.2;
    edgeMat.emissiveIntensity = .6 + night * 3.2;

    apronLights.forEach(light => {
      const active = light.userData.area === 'packed' ? packed : light.userData.area === 'remote' ? remoteOpen : true;
      light.intensity = active ? night * 480 : 0;
    });

    lamps.forEach(lamp => {
      const active = lamp.area === 'packed' ? packed : lamp.area === 'remote' ? remoteOpen : true;
      lamp.material.color.set(active ? 0xfff0cb : 0x24323a);
      lamp.material.emissiveIntensity = active ? .25 + night * 3.5 : 0;
    });

    packedMaterial.emissiveIntensity = packed ? .7 + night * 2.2 : 0;
    remoteMaterial.emissiveIntensity = remoteOpen ? .7 + night * 2.2 : 0;
  }

  function setHour(hour) {
    daylight = Math.max(0, Math.sin((hour - 6) / 12 * Math.PI));
    hemisphere.intensity = 1.05 + daylight * 2.5; sun.intensity = daylight * 4.4;
    hemisphere.color.set(0x8badde).lerp(color.set(0xdff2ff), daylight);
    sun.position.set(ramp.width / 2 + Math.cos(hour / 24 * Math.PI * 2) * layout.width * .4, 50 + daylight * layout.width * .85, ramp.depth * .25 - layout.unit * 2);
    sky.material.uniforms.top.value.set(0x07132c).lerp(color.set(0x72b6e2), daylight);
    sky.material.uniforms.horizon.value.set(0x213750).lerp(color.set(0xe4eff0), daylight);
    scene.fog.color.copy(sky.material.uniforms.horizon.value);
    updateLighting();
  }

  function update(frame, instant = false) {
    packed = frame.capacity.packed > 0;
    remoteOpen = frame.capacity.remote > 0;
    gateTarget = remoteOpen ? Math.PI * .47 : 0;
    gateLabel.element.textContent = remoteOpen ? 'Overflow apron · approved / open' : 'Overflow apron · not approved / closed';
    if (instant) barrier.rotation.z = gateTarget;
    if (remoteOpen) {
      materials.remote.color.setHex(0x8f9c98);
      materials.remote.opacity = 1;
      materials.remote.transparent = false;
      remoteOutlineMat.color.setHex(0x79d5b1);
      remoteOutlineMat.opacity = .9;
    } else {
      materials.remote.color.setHex(0x384742);
      materials.remote.opacity = .38;
      materials.remote.transparent = true;
      remoteOutlineMat.color.setHex(0x5a6d67);
      remoteOutlineMat.opacity = .75;
    }
    updateLighting();
  }

  function animate(delta, reduced) {
    barrier.rotation.z = reduced ? gateTarget : THREE.MathUtils.damp(barrier.rotation.z, gateTarget, 5, delta);
  }

  setHour(12);
  return { environment, label, labels, cube, setHour, update, animate, exitPoints, sky };
}
