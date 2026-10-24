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
    apron: new THREE.MeshStandardMaterial({ color: 0xd1d3cc, roughness: .95 }),
    packed: new THREE.MeshStandardMaterial({ color: 0xa9a493, roughness: .95 }),
    remote: new THREE.MeshStandardMaterial({ color: 0x8f9c98, roughness: .95 }),
    waiting: new THREE.MeshStandardMaterial({ color: 0xb4a39a, roughness: .95 }),
    asphalt: new THREE.MeshStandardMaterial({ color: 0x52636a, roughness: 1 }),
    wall: new THREE.MeshStandardMaterial({ color: 0xd8ddd7, roughness: .78 }),
    roof: new THREE.MeshStandardMaterial({ color: 0x314c56, metalness: .4, roughness: .6 }),
    trim: new THREE.MeshStandardMaterial({ color: 0x305c66, metalness: .45, roughness: .5 }),
    glass: new THREE.MeshStandardMaterial({ color: 0x3e788c, emissive: 0x94c4c9, emissiveIntensity: .12, metalness: .65, roughness: .17 }),
    warmGlass: new THREE.MeshStandardMaterial({ color: 0x6497a4, emissive: 0xffd8a0, emissiveIntensity: .12, metalness: .48, roughness: .2 }),
    paint: new THREE.MeshStandardMaterial({ color: 0xf2e4b7, roughness: .9 }),
    seam: new THREE.MeshStandardMaterial({ color: 0xadb6b1, roughness: 1 }),
    barrier: new THREE.MeshStandardMaterial({ color: 0xe7c877, roughness: .6 }),
    dark: new THREE.MeshStandardMaterial({ color: 0x293c41, roughness: .9 })
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
    }); group.receiveShadow = true; environment.add(group); return group;
  }
  box(layout.width / 2, -.7, layout.depth / 2, layout.width + u * 26, 1, layout.depth + u * 26, materials.ground);
  const seamItems = [];
  for (const [area, bounds] of Object.entries(layout.areas)) {
    box(bounds.x + bounds.width / 2, .01, bounds.z + bounds.depth / 2, bounds.width, .18, bounds.depth, materials[area === 'ramp' ? 'apron' : area]);
    const areaLabel = label(AREA_LABELS[area], [bounds.x + bounds.width / 2, 3, bounds.z - u * .15]);
    areaLabel.userData.area = area;
    for (let x = bounds.x + u * .7; x < bounds.x + bounds.width; x += u * .7) seamItems.push({ position: [x, .12, bounds.z + bounds.depth / 2], scale: [.09, .015, bounds.depth] });
    for (let z = bounds.z + u * .7; z < bounds.z + bounds.depth; z += u * .7) seamItems.push({ position: [bounds.x + bounds.width / 2, .12, z], scale: [bounds.width, .015, .09] });
  }
  instances(seamItems, materials.seam);
  // Continuous taxilane, runway and a curved runway exit connect the airframes' routes.
  box(layout.width / 2, .025, layout.laneZ, layout.width + u * 5, .18, u * .77, materials.asphalt);
  const runwayX = -u * 4.1, runwayZ = -u * 1.2, runwayDepth = layout.depth + u * 11;
  box(runwayX, -.04, runwayZ, u * 1.7, .18, runwayDepth, materials.asphalt);
  const exitPoints = [new THREE.Vector3(runwayX, .14, layout.laneZ - u * 2.2), new THREE.Vector3(runwayX + u * .18, .14, layout.laneZ - u), new THREE.Vector3(-u * 2.8, .14, layout.laneZ), new THREE.Vector3(layout.entry.x, .14, layout.entry.z)];
  const exitCurve = new THREE.CatmullRomCurve3(exitPoints), exitSamples = exitCurve.getSpacedPoints(24);
  const vertices = [], triangles = [];
  exitSamples.forEach((point, i) => {
    const tangent = exitCurve.getTangentAt(i / 24), normal = new THREE.Vector3(-tangent.z, 0, tangent.x).multiplyScalar(u * .385);
    vertices.push(point.x + normal.x, .14, point.z + normal.z, point.x - normal.x, .14, point.z - normal.z);
    if (i < 24) { const a = i * 2; triangles.push(a, a + 2, a + 1, a + 1, a + 2, a + 3); }
  });
  const exitGeo = new THREE.BufferGeometry(); exitGeo.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3)); exitGeo.setIndex(triangles); exitGeo.computeVertexNormals();
  const exitRoad = new THREE.Mesh(exitGeo, materials.asphalt); exitRoad.receiveShadow = true; environment.add(exitRoad);
  const markings = [], centerLights = [], edgeLights = [];
  for (let x = -u * 2; x < layout.width + u * 2.5; x += u * .45) {
    markings.push({ position: [x, .16, layout.laneZ], scale: [u * .26, .025, .22] });
    centerLights.push({ position: [x, .2, layout.laneZ], scale: [.18, .12, .18] });
    for (const side of [-1, 1]) edgeLights.push({ position: [x, .3, layout.laneZ + side * u * .36], scale: [.22, .22, .22] });
  }
  for (let z = runwayZ - runwayDepth / 2 + u; z < runwayZ + runwayDepth / 2; z += u * 1.5) markings.push({ position: [runwayX, .1, z], scale: [.9, .02, u * .6] });
  exitSamples.forEach((p, i) => {
    const tangent = exitCurve.getTangentAt(i / 24), normal = new THREE.Vector3(-tangent.z, 0, tangent.x);
    markings.push({ position: [p.x, .18, p.z], scale: [.2, .02, u * .17], rotation: Math.atan2(tangent.x, tangent.z) });
    centerLights.push({ position: [p.x, .22, p.z], scale: [.18, .12, .18] });
    if (i % 2 === 0) for (const side of [-1, 1]) edgeLights.push({ position: [p.x + normal.x * u * .36 * side, .3, p.z + normal.z * u * .36 * side], scale: [.22, .22, .22] });
  });
  instances(markings, materials.paint);
  const centerMat = new THREE.MeshStandardMaterial({ color: 0x80ddb0, emissive: 0x32ee88, emissiveIntensity: 2 });
  const edgeMat = new THREE.MeshStandardMaterial({ color: 0x64b4e4, emissive: 0x428bff, emissiveIntensity: 2 });
  const bulb = new THREE.SphereGeometry(1, 6, 4);
  instances(centerLights, centerMat, bulb); instances(edgeLights, edgeMat, bulb);
  label('Runway exit · illustrated taxiway', [runwayX + u, 3, layout.laneZ - u * 2.1]);
  // Low terminal and adjoining hangar have glazed fronts and simple structural frames.
  const terminalX = ramp.width * .38, terminalZ = -u * 2.9, terminalWidth = ramp.width * .78;
  box(terminalX, 5.8, terminalZ, terminalWidth, 11.6, u * .9, materials.wall);
  box(terminalX, 12, terminalZ, terminalWidth + u * .13, .7, u * 1.02, materials.roof);
  box(terminalX, 5.6, terminalZ + u * .456, terminalWidth * .91, 7.2, .2, materials.warmGlass);
  box(terminalX, 3.5, terminalZ + u * .69, terminalWidth * .43, .45, u * .5, materials.trim);
  const structure = [];
  for (let x = terminalX - terminalWidth * .45; x <= terminalX + terminalWidth * .46; x += u * .26) structure.push({ position: [x, 5.6, terminalZ + u * .47], scale: [.35, 7.5, .35] });
  const hangarX = ramp.width + u * .7, hangarZ = terminalZ - u * .35, hangarWidth = u * 2.2, hangarDepth = u * 1.7;
  box(hangarX, 10, hangarZ, hangarWidth, 20, hangarDepth, materials.wall);
  box(hangarX, 20.5, hangarZ, hangarWidth + 1.5, 1, hangarDepth + 1.5, materials.roof);
  box(hangarX, 7.5, hangarZ + hangarDepth / 2 + .12, hangarWidth * .87, 14.5, .25, materials.trim);
  box(hangarX, 15.8, hangarZ + hangarDepth / 2 + .3, hangarWidth * .86, 3.2, .2, materials.glass);
  for (let x = hangarX - hangarWidth * .43; x <= hangarX + hangarWidth * .44; x += hangarWidth / 8) structure.push({ position: [x, 9, hangarZ + hangarDepth / 2 + .45], scale: [.25, 16.8, .3] });
  instances(structure, materials.roof);
  label('FBO terminal', [terminalX, 15, terminalZ]); label('Hangar', [hangarX, 24, hangarZ]);
  // Roof service boxes and an airside access walk make the buildings read at orbit distance.
  box(terminalX - terminalWidth * .25, 13, terminalZ, u * .25, 1.5, u * .3, materials.wall);
  box(terminalX + terminalWidth * .25, 13, terminalZ, u * .25, 1.5, u * .3, materials.wall);
  box(terminalX, .08, terminalZ + u * .72, terminalWidth + u * .4, .2, u * .48, materials.apron);
  // Floodlight hardware is instanced. Only a few non-shadowed lights illuminate the aprons.
  const lightPoints = Object.entries(layout.areas).flatMap(([area, b]) => [
    { area, x: b.x + 2, z: b.z + b.depth * .15 }, { area, x: b.x + b.width - 2, z: b.z + b.depth * .85 }
  ]);
  const poleItems = [], lampItems = [], apronLights = [];
  const lampMaterial = new THREE.MeshStandardMaterial({ color: 0xffe6b1, emissive: 0xffd7a0, emissiveIntensity: .3 });
  for (const p of lightPoints) {
    poleItems.push({ position: [p.x, 8, p.z], scale: [.36, 16, .36] });
    lampItems.push({ position: [p.x, 16, p.z], scale: [3.2, .4, 1.25] });
    const light = new THREE.PointLight(0xffe7c3, 0, u * 4, 1.5); light.position.set(p.x, 15, p.z); light.userData.area = p.area;
    scene.add(light); apronLights.push(light);
  }
  instances(poleItems, materials.roof);
  const lamps = Object.keys(layout.areas).map(area => {
    const material = lampMaterial.clone();
    const mesh = instances(lampItems.filter((_, index) => lightPoints[index].area === area), material);
    return { area, material, mesh };
  });
  lampMaterial.dispose();
  // A physical entrance barrier changes only with recorded, date-valid lease approval.
  const remote = layout.areas.remote, gateX = remote.x - u * .16, gateZ = remote.z - u * .02;
  box(gateX, 1, gateZ, 1.2, 2, 1.2, materials.dark);
  const barrier = new THREE.Group(); barrier.position.set(gateX, 2.2, gateZ); environment.add(barrier);
  const armLength = u * .72; box(armLength / 2, 0, 0, armLength, .48, .55, materials.barrier, barrier);
  for (let x = 1.4; x < armLength; x += 3.2) box(x, 0, .29, 1.3, .5, .025, materials.dark, barrier);
  const gateLabel = label('Overflow apron · not approved / closed', [gateX + armLength / 2, 4, gateZ - 3], 'gate');
  const packedMaterial = new THREE.MeshStandardMaterial({ color: 0x766b48, emissive: 0xeac166, emissiveIntensity: 0 });
  const remoteMaterial = new THREE.MeshStandardMaterial({ color: 0x516861, emissive: 0x79d5b1, emissiveIntensity: 0 });
  const strips = {};
  for (const [area, mat] of [['packed', packedMaterial], ['remote', remoteMaterial]]) {
    const b = layout.areas[area]; strips[area] = box(b.x + b.width / 2, .22, b.z + .25, b.width, .12, .38, mat);
  }
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
  scene.fog = new THREE.Fog(0xc5dce4, layout.width * 1.3, layout.width * 5);
  const hemisphere = new THREE.HemisphereLight(0xdff2ff, 0x8e9a82, 3.2); scene.add(hemisphere);
  const sun = new THREE.DirectionalLight(0xfff4dc, 4.2); sun.castShadow = true; scene.add(sun, sun.target);
  sun.target.position.set(ramp.width / 2, 0, ramp.depth / 2);
  const shadowExtent = Math.max(ramp.width, ramp.depth) * .8;
  Object.assign(sun.shadow.camera, { left: -shadowExtent, right: shadowExtent, top: shadowExtent, bottom: -shadowExtent, near: 1, far: layout.width * 3 });
  sun.shadow.mapSize.set(2048, 2048); sun.shadow.normalBias = .2; sun.shadow.bias = -.00015; sun.shadow.radius = 3;
  let daylight = 1, packed = false, remoteOpen = false, gateTarget = 0;
  const color = new THREE.Color();
  function updateLighting() {
    const night = 1 - daylight;
    materials.warmGlass.emissiveIntensity = .12 + night * 1.1; materials.glass.emissiveIntensity = .1 + night * .65;
    centerMat.emissiveIntensity = .8 + night * 3; edgeMat.emissiveIntensity = .6 + night * 3;
    apronLights.forEach((light, index) => {
      const active = light.userData.area === 'packed' ? packed : light.userData.area === 'remote' ? remoteOpen : true;
      light.intensity = active ? night * 430 : 0;
    });
    lamps.forEach(lamp => {
      const active = lamp.area === 'packed' ? packed : lamp.area === 'remote' ? remoteOpen : true;
      lamp.material.color.set(active ? 0xffe8bd : 0x25323b);
      lamp.material.emissiveIntensity = active ? .2 + night * 3 : 0;
    });
    packedMaterial.emissiveIntensity = packed ? .65 + night * 2 : 0;
    remoteMaterial.emissiveIntensity = remoteOpen ? .65 + night * 2 : 0;
  }
  function setHour(hour) {
    daylight = Math.max(0, Math.sin((hour - 6) / 12 * Math.PI));
    hemisphere.intensity = 1.05 + daylight * 2.5; sun.intensity = daylight * 4.1;
    hemisphere.color.set(0x8badde).lerp(color.set(0xdff2ff), daylight);
    sun.position.set(ramp.width / 2 + Math.cos(hour / 24 * Math.PI * 2) * layout.width * .4, 50 + daylight * layout.width * .85, ramp.depth * .25 - layout.unit * 2);
    sky.material.uniforms.top.value.set(0x07132c).lerp(color.set(0x72b6e2), daylight);
    sky.material.uniforms.horizon.value.set(0x213750).lerp(color.set(0xe4eff0), daylight);
    scene.fog.color.copy(sky.material.uniforms.horizon.value); updateLighting();
  }
  function update(frame, instant = false) {
    packed = frame.capacity.packed > 0; remoteOpen = frame.capacity.remote > 0;
    gateTarget = remoteOpen ? Math.PI * .47 : 0;
    gateLabel.element.textContent = remoteOpen ? 'Overflow apron · approved / open' : 'Overflow apron · not approved / closed';
    if (instant) barrier.rotation.z = gateTarget; updateLighting();
  }
  function animate(delta, reduced) {
    barrier.rotation.z = reduced ? gateTarget : THREE.MathUtils.damp(barrier.rotation.z, gateTarget, 5, delta);
  }
  setHour(12);
  return { environment, label, labels, cube, setHour, update, animate, exitPoints, sky };
}
