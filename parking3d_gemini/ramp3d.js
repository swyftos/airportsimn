/**
 * ramp3d.js
 * Explorable 3D Ramp Simulation for LAX FBO Super Bowl LXI.
 * Built with Three.js from pinned CDN via import map. No build step.
 *
 * Features:
 * - Free orbit camera (OrbitControls with panning, zooming, 360 rotation)
 * - Light theme aesthetic with daylight/night lighting following simulated clock
 * - Dynamic sun position, sky gradient, and high-mast ramp floodlight towers
 * - 15 su Main Ramp to scale, Remote Overflow Apron, and Awaiting Manager Decision Area
 * - Low-poly readable executive jet models sized proportionally (1.0 su, 1.5 su, 2.5 su)
 * - Raycaster click-to-inspect on any aircraft
 * - WebGL fallback detection and hidden-tab render pausing
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

export class Ramp3DScene {
  constructor(canvasContainer, onSelectAircraft) {
    this.container = canvasContainer;
    this.onSelectAircraft = onSelectAircraft;

    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.controls = null;

    // Lighting objects
    this.sunLight = null;
    this.ambientLight = null;
    this.hemiLight = null;
    this.floodlights = [];
    this.mastLights = [];
    this.hazardBeacons = [];

    // Mesh maps
    this.aircraftMeshes = new Map(); // flightId -> THREE.Group
    this.standPositions = new Map();  // standId -> { x, z, rotation, type }
    this.selectedFlightId = null;

    // Interaction
    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();

    // Animation & Clock
    this.clock = new THREE.Clock();
    this.isRendering = true;
    this.animationFrameId = null;

    // Camera preset targets
    this.cameraPresets = {
      overview: { pos: [0, 85, 110], target: [0, 0, 5] },
      mainRamp: { pos: [-15, 38, 45], target: [-15, 0, 0] },
      overflow: { pos: [55, 35, 45], target: [55, 0, 0] },
      decisionArea: { pos: [-65, 30, 40], target: [-65, 0, 0] },
      tower: { pos: [0, 22, -45], target: [0, 2, 20] }
    };

    this.cameraLerp = null;

    this.init();
  }

  // Check WebGL availability
  static isWebGLAvailable() {
    try {
      const canvas = document.createElement('canvas');
      return !!(window.WebGLRenderingContext && (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')));
    } catch (e) {
      return false;
    }
  }

  init() {
    if (!Ramp3DScene.isWebGLAvailable()) {
      this.showFallbackMessage();
      return;
    }

    const width = this.container.clientWidth || 800;
    const height = this.container.clientHeight || 500;

    // 1. Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0xdbeafe);
    this.scene.fog = new THREE.FogExp2(0xdbeafe, 0.0025);

    // 2. Camera
    this.camera = new THREE.PerspectiveCamera(45, width / height, 1, 1000);
    this.camera.position.set(0, 85, 110);

    // 3. Renderer
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;
    this.container.appendChild(this.renderer.domElement);

    // 4. OrbitControls
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.screenSpacePanning = true;
    this.controls.minDistance = 15;
    this.controls.maxDistance = 250;
    this.controls.maxPolarAngle = Math.PI / 2 - 0.04; // Don't go below ground
    this.controls.target.set(0, 0, 5);
    this.controls.update();

    // 5. Lighting Setup
    this.setupLighting();

    // 6. World Environment & Ground Layout
    this.buildAirfield();

    // 7. Event Listeners
    window.addEventListener('resize', this.onWindowResize.bind(this));
    this.renderer.domElement.addEventListener('pointerdown', this.onPointerDown.bind(this));
    document.addEventListener('visibilitychange', () => {
      this.isRendering = !document.hidden;
      if (this.isRendering) {
        this.clock.start();
        this.animate();
      }
    });

    // Start render loop
    this.animate();
  }

  showFallbackMessage() {
    this.container.innerHTML = `
      <div class="webgl-fallback-card" role="alert" style="padding: 2rem; text-align: center; background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px;">
        <h3 style="margin-bottom: 0.5rem; color: #0f172a;">3D Ramp Visualizer Notice</h3>
        <p style="color: #475569; margin-bottom: 1rem;">WebGL hardware acceleration is not supported or is disabled in your browser. The full 2D operational analysis, charts, data tables, and preparation plan are fully functional below.</p>
        <div style="font-size: 0.85rem; color: #64748b;">All operational numbers, risk evaluations, and capacity data remain 100% accessible.</div>
      </div>
    `;
  }

  setupLighting() {
    // Hemisphere light (sky/ground)
    this.hemiLight = new THREE.HemisphereLight(0xdbeafe, 0x94a3b8, 0.6);
    this.hemiLight.position.set(0, 100, 0);
    this.scene.add(this.hemiLight);

    // Ambient light
    this.ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
    this.scene.add(this.ambientLight);

    // Directional Sun Light
    this.sunLight = new THREE.DirectionalLight(0xfffaed, 1.25);
    this.sunLight.position.set(60, 90, 40);
    this.sunLight.castShadow = true;
    this.sunLight.shadow.mapSize.width = 2048;
    this.sunLight.shadow.mapSize.height = 2048;
    this.sunLight.shadow.camera.near = 10;
    this.sunLight.shadow.camera.far = 300;
    const shadowDist = 95;
    this.sunLight.shadow.camera.left = -shadowDist;
    this.sunLight.shadow.camera.right = shadowDist;
    this.sunLight.shadow.camera.top = shadowDist;
    this.sunLight.shadow.camera.bottom = -shadowDist;
    this.sunLight.shadow.bias = -0.0005;
    this.scene.add(this.sunLight);

    // High Mast Floodlight Towers setup
    this.createFloodlightMasts();
  }

  createFloodlightMasts() {
    // 4 High Mast floodlight towers around main ramp and overflow apron
    const mastCoords = [
      { x: -40, z: -25, rot: Math.PI / 4 },    // Main Ramp NW
      { x: 10, z: -25, rot: -Math.PI / 4 },    // Main Ramp NE
      { x: -15, z: 32, rot: 3 * Math.PI / 4 }, // Main Ramp S
      { x: 50, z: -25, rot: 0 }                // Overflow Apron N
    ];

    mastCoords.forEach((coord, i) => {
      const mastGroup = new THREE.Group();
      mastGroup.position.set(coord.x, 0, coord.z);

      // Steel pole
      const poleGeo = new THREE.CylinderGeometry(0.4, 0.7, 24, 8);
      const poleMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.7, roughness: 0.3 });
      const pole = new THREE.Mesh(poleGeo, poleMat);
      pole.position.y = 12;
      pole.castShadow = true;
      mastGroup.add(pole);

      // Crossbar with light fixtures
      const headGeo = new THREE.BoxGeometry(4.5, 0.6, 1.2);
      const headMat = new THREE.MeshStandardMaterial({ color: 0x475569 });
      const head = new THREE.Mesh(headGeo, headMat);
      head.position.y = 23.8;
      mastGroup.add(head);

      // Spot light targeting down onto the ramp
      const spot = new THREE.SpotLight(0xfff7ed, 0, 75, Math.PI / 3.2, 0.45, 1.2);
      spot.position.set(coord.x, 23.5, coord.z);
      const targetObj = new THREE.Object3D();
      targetObj.position.set(coord.x + (i % 2 === 0 ? 10 : -10), 0, coord.z + 20);
      this.scene.add(targetObj);
      spot.target = targetObj;
      spot.castShadow = true;
      spot.shadow.mapSize.width = 512;
      spot.shadow.mapSize.height = 512;
      this.scene.add(spot);
      this.floodlights.push(spot);

      // Top red obstacle warning LED
      const obsGeo = new THREE.SphereGeometry(0.25, 8, 8);
      const obsMat = new THREE.MeshBasicMaterial({ color: 0xff0000 });
      const obsMesh = new THREE.Mesh(obsGeo, obsMat);
      obsMesh.position.y = 24.5;
      mastGroup.add(obsMesh);
      this.mastLights.push(obsMesh);

      this.scene.add(mastGroup);
    });
  }

  // Update sun position, lighting tones, and ramp floodlights based on simulated hour (0-24)
  updateDayNightLighting(hourFloat) {
    const hour = (hourFloat + 24) % 24;

    // Sun trajectory: rises east ~6.5, peaks ~12.5, sets west ~18.5
    // Theta runs around azimuth; phi runs zenith
    const sunProgress = (hour - 6.5) / 12.0; // 0 at dawn, 0.5 at noon, 1 at dusk
    const isDay = hour >= 6.2 && hour <= 18.8;

    let sunIntensity = 0;
    let sunColor = new THREE.Color(0xfffbeb);
    let skyColor = new THREE.Color(0xdbeafe);
    let hemiSky = new THREE.Color(0xdbeafe);
    let hemiGround = new THREE.Color(0x94a3b8);
    let floodIntensity = 0;

    if (isDay) {
      // Daylight calculation
      const angle = sunProgress * Math.PI; // 0 to PI
      const sunHeight = Math.sin(angle);
      const sunX = Math.cos(angle) * -90;
      const sunY = Math.max(10, sunHeight * 95);
      const sunZ = 35 + Math.cos(angle) * 20;

      this.sunLight.position.set(sunX, sunY, sunZ);

      if (hour < 7.5 || hour > 17.5) {
        // Sunrise / Sunset golden hour
        const blend = hour < 7.5 ? (hour - 6.2) / 1.3 : (18.8 - hour) / 1.3;
        sunColor.setHex(0xf97316); // Golden orange
        skyColor.setHex(0xfde68a); // Pale warm sky
        hemiSky.setHex(0xfcd34d);
        sunIntensity = 0.5 + blend * 0.5;
        floodIntensity = (1 - blend) * 1.5;
      } else {
        // Crisp high noon sunlight
        sunColor.setHex(0xfffef5);
        skyColor.setHex(0xdbeafe);
        hemiSky.setHex(0xe2e8f0);
        hemiGround.setHex(0x94a3b8);
        sunIntensity = 1.35;
        floodIntensity = 0;
      }
    } else {
      // Night Operations
      this.sunLight.position.set(0, -50, 0);
      sunIntensity = 0;
      skyColor.setHex(0x0f172a); // Deep midnight navy
      hemiSky.setHex(0x1e293b);
      hemiGround.setHex(0x090d16);
      this.ambientLight.intensity = 0.22;
      floodIntensity = 2.4; // Floodlights illuminate the ramp brightly!
    }

    // Apply smooth updates
    this.sunLight.color.copy(sunColor);
    this.sunLight.intensity = sunIntensity;
    this.scene.background.copy(skyColor);
    this.scene.fog.color.copy(skyColor);
    this.hemiLight.color.copy(hemiSky);
    this.hemiLight.groundColor.copy(hemiGround);

    // Update floodlights
    this.floodlights.forEach(spot => {
      spot.intensity = floodIntensity;
    });

    // Pulse red obstacle LEDs and manager hazard beacons at night
    const time = this.clock.getElapsedTime();
    const pulse = (Math.sin(time * 3.5) + 1) / 2;
    this.mastLights.forEach(mesh => {
      mesh.material.color.setRGB(1, pulse * 0.2, pulse * 0.2);
    });

    this.hazardBeacons.forEach(mesh => {
      mesh.material.color.setRGB(1, 0.6 * pulse + 0.2, 0);
    });
  }

  buildAirfield() {
    // 1. Base Ground (Grass & Surrounding terrain)
    const groundGeo = new THREE.PlaneGeometry(350, 300);
    const groundMat = new THREE.MeshStandardMaterial({
      color: 0x64748b, // Airport perimeter terrain
      roughness: 0.9,
      metalness: 0.05
    });
    const ground = new THREE.Mesh(groundGeo, groundMat);
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.05;
    ground.receiveShadow = true;
    this.scene.add(ground);

    // 2. Concrete/Asphalt Pavement for Ramps & Taxiways
    this.createPavement();

    // 3. Stand Markings & Painted Lines
    this.createStandMarkings();

    // 4. Buildings & Hangars
    this.createStructures();

    // 5. Taxiway Edge Lights
    this.createTaxiwayLights();
  }

  createPavement() {
    // Main Apron Tarmac (15 su capacity ramp)
    // Width: 85m, Depth: 55m
    const mainRampGeo = new THREE.PlaneGeometry(88, 56);
    const mainRampMat = new THREE.MeshStandardMaterial({
      color: 0x94a3b8, // Light concrete / asphalt tarmac
      roughness: 0.75,
      metalness: 0.1
    });
    const mainRamp = new THREE.Mesh(mainRampGeo, mainRampMat);
    mainRamp.rotation.x = -Math.PI / 2;
    mainRamp.position.set(-15, 0.01, 0);
    mainRamp.receiveShadow = true;
    this.scene.add(mainRamp);

    // Taxiway connecting Main Ramp to Remote Overflow & Runway
    const taxiwayGeo = new THREE.PlaneGeometry(240, 22);
    const taxiwayMat = new THREE.MeshStandardMaterial({
      color: 0x64748b, // Darker asphalt taxiway
      roughness: 0.7,
      metalness: 0.1
    });
    const taxiway = new THREE.Mesh(taxiwayGeo, taxiwayMat);
    taxiway.rotation.x = -Math.PI / 2;
    taxiway.position.set(0, 0.005, 38);
    taxiway.receiveShadow = true;
    this.scene.add(taxiway);

    // Remote Overflow Apron Tarmac (East side)
    const overflowGeo = new THREE.PlaneGeometry(62, 50);
    const overflowMat = new THREE.MeshStandardMaterial({
      color: 0xa1a1aa, // Concrete overflow pad
      roughness: 0.8,
      metalness: 0.05
    });
    const overflow = new THREE.Mesh(overflowGeo, overflowMat);
    overflow.rotation.x = -Math.PI / 2;
    overflow.position.set(62, 0.01, 3);
    overflow.receiveShadow = true;
    this.scene.add(overflow);

    // Awaiting Manager Decision Area (Holding Pad on West side)
    const decisionGeo = new THREE.PlaneGeometry(36, 44);
    const decisionMat = new THREE.MeshStandardMaterial({
      color: 0x71717a, // Staging pad
      roughness: 0.7,
      metalness: 0.15
    });
    const decisionPad = new THREE.Mesh(decisionGeo, decisionMat);
    decisionPad.rotation.x = -Math.PI / 2;
    decisionPad.position.set(-74, 0.01, 6);
    decisionPad.receiveShadow = true;
    this.scene.add(decisionPad);
  }

  createStandMarkings() {
    // Generate stand positions and yellow lead-in lines
    // Main Ramp Stands (15 su capacity):
    // 4 Light stands (1.0 su each): S1, S2, S3, S4
    // 4 Midsize stands (1.5 su each): S5, S6, S7, S8
    // 2 Large stands (2.5 su each): S9, S10
    // Total = 4*1.0 + 4*1.5 + 2*2.5 = 15.0 su!

    const stands = [
      // Light Stands (Front row, closer to taxiway)
      { id: 'S1', x: -44, z: 16, su: 1.0, type: 'light', label: 'STAND S-1 (1.0 su)' },
      { id: 'S2', x: -30, z: 16, su: 1.0, type: 'light', label: 'STAND S-2 (1.0 su)' },
      { id: 'S3', x: -16, z: 16, su: 1.0, type: 'light', label: 'STAND S-3 (1.0 su)' },
      { id: 'S4', x:  -2, z: 16, su: 1.0, type: 'light', label: 'STAND S-4 (1.0 su)' },
      // Midsize Stands (Back row west)
      { id: 'S5', x: -44, z: -12, su: 1.5, type: 'midsize', label: 'STAND S-5 (1.5 su)' },
      { id: 'S6', x: -28, z: -12, su: 1.5, type: 'midsize', label: 'STAND S-6 (1.5 su)' },
      { id: 'S7', x: -12, z: -12, su: 1.5, type: 'midsize', label: 'STAND S-7 (1.5 su)' },
      { id: 'S8', x:   4, z: -12, su: 1.5, type: 'midsize', label: 'STAND S-8 (1.5 su)' },
      // Large Stands (Back row east)
      { id: 'S9', x: 16, z: 14, su: 2.5, type: 'large', label: 'STAND S-9 (2.5 su)' },
      { id: 'S10', x: 20, z: -10, su: 2.5, type: 'large', label: 'STAND S-10 (2.5 su)' },
      // Supplementary Packed Stand for +10% tow packing gain (+1.5 su = 16.5 su)
      { id: 'S-PACK1', x: 10, z: 2, su: 1.5, type: 'midsize', label: 'STAND S-PACK (TOW PACKING)' }
    ];

    stands.forEach(s => {
      this.standPositions.set(s.id, { x: s.x, z: s.z, rotation: Math.PI, type: s.type, su: s.su });
      this.drawStandMarking(s.x, s.z, s.su, s.id, 0xfacc15); // Aviation yellow
    });

    // Remote Overflow Apron Stands: O1 - O6
    const overflowStands = [
      { id: 'O1', x: 48, z: 15, su: 2.5, type: 'large', label: 'OVERFLOW O-1' },
      { id: 'O2', x: 74, z: 15, su: 2.5, type: 'large', label: 'OVERFLOW O-2' },
      { id: 'O3', x: 48, z: -9, su: 1.5, type: 'midsize', label: 'OVERFLOW O-3' },
      { id: 'O4', x: 64, z: -9, su: 1.5, type: 'midsize', label: 'OVERFLOW O-4' },
      { id: 'O5', x: 78, z: -9, su: 1.0, type: 'light', label: 'OVERFLOW O-5' },
      { id: 'O6', x: 82, z: 4, su: 1.0, type: 'light', label: 'OVERFLOW O-6' }
    ];

    overflowStands.forEach(s => {
      this.standPositions.set(s.id, { x: s.x, z: s.z, rotation: Math.PI, type: s.type, su: s.su });
      this.drawStandMarking(s.x, s.z, s.su, s.id, 0x38bdf8); // Sky blue markings for overflow
    });

    // Awaiting Manager Decision Area slots
    const decisionSlots = [
      { id: 'DEC-1', x: -68, z: 16 },
      { id: 'DEC-2', x: -80, z: 16 },
      { id: 'DEC-3', x: -68, z: 0 },
      { id: 'DEC-4', x: -80, z: 0 },
      { id: 'DEC-5', x: -68, z: -14 },
      { id: 'DEC-6', x: -80, z: -14 }
    ];

    decisionSlots.forEach(s => {
      this.standPositions.set(s.id, { x: s.x, z: s.z, rotation: Math.PI * 0.9, type: 'overflow' });
    });

    // Draw Manager Decision Area Hazard Striping & Perimeter
    this.drawManagerDecisionPerimeter();

    // Taxiway Centerlines (Yellow lines)
    this.drawTaxiwayCenterlines();
  }

  drawStandMarking(x, z, su, label, colorHex) {
    const boxSize = su >= 2.5 ? 15 : (su >= 1.5 ? 12 : 9);

    // T-Line (nosewheel stop bar & centerline)
    const tLineGeo = new THREE.PlaneGeometry(0.3, boxSize * 0.85);
    const tLineMat = new THREE.MeshBasicMaterial({ color: colorHex });
    const tLine = new THREE.Mesh(tLineGeo, tLineMat);
    tLine.rotation.x = -Math.PI / 2;
    tLine.position.set(x, 0.02, z);
    this.scene.add(tLine);

    // Crossbar
    const crossGeo = new THREE.PlaneGeometry(3.5, 0.35);
    const cross = new THREE.Mesh(crossGeo, tLineMat);
    cross.rotation.x = -Math.PI / 2;
    cross.position.set(x, 0.02, z - boxSize * 0.25);
    this.scene.add(cross);

    // Safety bounding box corners
    const borderGeo = new THREE.RingGeometry(boxSize * 0.48, boxSize * 0.5, 16);
    const borderMat = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.4 });
    const border = new THREE.Mesh(borderGeo, borderMat);
    border.rotation.x = -Math.PI / 2;
    border.position.set(x, 0.015, z);
    this.scene.add(border);
  }

  drawManagerDecisionPerimeter() {
    // High-visibility hazard striped boundary around Manager Decision Area
    const padX = -74;
    const padZ = 6;
    const width = 36;
    const depth = 44;

    // Corner beacon towers with flashing warning lights
    const corners = [
      [-width / 2 + 1, -depth / 2 + 1],
      [ width / 2 - 1, -depth / 2 + 1],
      [-width / 2 + 1,  depth / 2 - 1],
      [ width / 2 - 1,  depth / 2 - 1]
    ];

    corners.forEach(([cx, cz]) => {
      const pylonGeo = new THREE.CylinderGeometry(0.2, 0.35, 3.5, 8);
      const pylonMat = new THREE.MeshStandardMaterial({ color: 0xf59e0b, roughness: 0.3 });
      const pylon = new THREE.Mesh(pylonGeo, pylonMat);
      pylon.position.set(padX + cx, 1.75, padZ + cz);
      this.scene.add(pylon);

      const beaconGeo = new THREE.SphereGeometry(0.35, 8, 8);
      const beaconMat = new THREE.MeshBasicMaterial({ color: 0xf59e0b });
      const beacon = new THREE.Mesh(beaconGeo, beaconMat);
      beacon.position.set(padX + cx, 3.6, padZ + cz);
      this.scene.add(beacon);
      this.hazardBeacons.push(beacon);
    });

    // Ground boundary lines
    const lineMat = new THREE.MeshBasicMaterial({ color: 0xf59e0b });
    const borderGeoH = new THREE.PlaneGeometry(width, 0.5);
    const borderGeoV = new THREE.PlaneGeometry(0.5, depth);

    const northBorder = new THREE.Mesh(borderGeoH, lineMat);
    northBorder.rotation.x = -Math.PI / 2;
    northBorder.position.set(padX, 0.02, padZ - depth / 2);
    this.scene.add(northBorder);

    const southBorder = new THREE.Mesh(borderGeoH, lineMat);
    southBorder.rotation.x = -Math.PI / 2;
    southBorder.position.set(padX, 0.02, padZ + depth / 2);
    this.scene.add(southBorder);

    const westBorder = new THREE.Mesh(borderGeoV, lineMat);
    westBorder.rotation.x = -Math.PI / 2;
    westBorder.position.set(padX - width / 2, 0.02, padZ);
    this.scene.add(westBorder);

    const eastBorder = new THREE.Mesh(borderGeoV, lineMat);
    eastBorder.rotation.x = -Math.PI / 2;
    eastBorder.position.set(padX + width / 2, 0.02, padZ);
    this.scene.add(eastBorder);
  }

  drawTaxiwayCenterlines() {
    // Main taxiway line
    const mainLineGeo = new THREE.PlaneGeometry(230, 0.4);
    const yellowMat = new THREE.MeshBasicMaterial({ color: 0xfacc15 });
    const mainLine = new THREE.Mesh(mainLineGeo, yellowMat);
    mainLine.rotation.x = -Math.PI / 2;
    mainLine.position.set(0, 0.015, 38);
    this.scene.add(mainLine);

    // Lead-in connector to Main Ramp
    const leadInGeo = new THREE.PlaneGeometry(0.4, 25);
    const leadIn1 = new THREE.Mesh(leadInGeo, yellowMat);
    leadIn1.rotation.x = -Math.PI / 2;
    leadIn1.position.set(-25, 0.015, 26);
    this.scene.add(leadIn1);

    const leadIn2 = new THREE.Mesh(leadInGeo, yellowMat);
    leadIn2.rotation.x = -Math.PI / 2;
    leadIn2.position.set(5, 0.015, 26);
    this.scene.add(leadIn2);

    // Connector to Overflow Apron
    const overflowLead = new THREE.Mesh(leadInGeo, yellowMat);
    overflowLead.rotation.x = -Math.PI / 2;
    overflowLead.position.set(60, 0.015, 26);
    this.scene.add(overflowLead);

    // Connector to Manager Decision Area
    const decLead = new THREE.Mesh(leadInGeo, yellowMat);
    decLead.rotation.x = -Math.PI / 2;
    decLead.position.set(-70, 0.015, 27);
    this.scene.add(decLead);
  }

  createTaxiwayLights() {
    // Blue edge lights along taxiway margins
    const lightGeo = new THREE.CylinderGeometry(0.12, 0.12, 0.5, 6);
    const blueMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8 });

    for (let x = -110; x <= 110; x += 15) {
      // North edge of taxiway
      const lightN = new THREE.Mesh(lightGeo, blueMat);
      lightN.position.set(x, 0.25, 27.5);
      this.scene.add(lightN);

      // South edge of taxiway
      const lightS = new THREE.Mesh(lightGeo, blueMat);
      lightS.position.set(x, 0.25, 48.5);
      this.scene.add(lightS);
    }
  }

  createStructures() {
    // 1. VIP FBO Executive Terminal Building (Along North edge of Main Ramp)
    const terminalGroup = new THREE.Group();
    terminalGroup.position.set(-15, 0, -38);

    // Main terminal body
    const termGeo = new THREE.BoxGeometry(45, 9, 16);
    const termMat = new THREE.MeshStandardMaterial({
      color: 0xf1f5f9, // Architectural off-white
      roughness: 0.4,
      metalness: 0.2
    });
    const termMesh = new THREE.Mesh(termGeo, termMat);
    termMesh.position.y = 4.5;
    termMesh.castShadow = true;
    termMesh.receiveShadow = true;
    terminalGroup.add(termMesh);

    // Panoramic glass facade facing the ramp
    const glassGeo = new THREE.BoxGeometry(42, 5.5, 0.5);
    const glassMat = new THREE.MeshStandardMaterial({
      color: 0x0284c7, // Blue architectural glass
      roughness: 0.1,
      metalness: 0.8,
      transparent: true,
      opacity: 0.75
    });
    const glass = new THREE.Mesh(glassGeo, glassMat);
    glass.position.set(0, 4.5, 8.1);
    terminalGroup.add(glass);

    // Roof canopy overhang
    const canopyGeo = new THREE.BoxGeometry(47, 0.6, 20);
    const canopyMat = new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.5 });
    const canopy = new THREE.Mesh(canopyGeo, canopyMat);
    canopy.position.set(0, 9.3, 1);
    terminalGroup.add(canopy);

    // FBO Signboard
    const signGeo = new THREE.BoxGeometry(16, 1.8, 0.4);
    const signMat = new THREE.MeshStandardMaterial({ color: 0x0f172a });
    const sign = new THREE.Mesh(signGeo, signMat);
    sign.position.set(0, 10.6, 6);
    terminalGroup.add(sign);

    this.scene.add(terminalGroup);

    // 2. Executive Maintenance Hangar (NW corner)
    const hangarGroup = new THREE.Group();
    hangarGroup.position.set(-75, 0, -32);

    const hangarGeo = new THREE.BoxGeometry(32, 13, 26);
    const hangarMat = new THREE.MeshStandardMaterial({
      color: 0xe2e8f0,
      roughness: 0.5,
      metalness: 0.3
    });
    const hangar = new THREE.Mesh(hangarGeo, hangarMat);
    hangar.position.y = 6.5;
    hangar.castShadow = true;
    hangarGroup.add(hangar);

    // Sliding hangar door
    const doorGeo = new THREE.BoxGeometry(26, 10, 0.5);
    const doorMat = new THREE.MeshStandardMaterial({ color: 0x64748b, roughness: 0.6 });
    const door = new THREE.Mesh(doorGeo, doorMat);
    door.position.set(0, 5, 13.1);
    hangarGroup.add(door);

    this.scene.add(hangarGroup);

    // 3. Windsock Mast (Near taxiway entrance)
    const windsockGroup = new THREE.Group();
    windsockGroup.position.set(-105, 0, 30);
    const poleGeo = new THREE.CylinderGeometry(0.15, 0.2, 7, 6);
    const poleMat = new THREE.MeshStandardMaterial({ color: 0xffffff });
    const pole = new THREE.Mesh(poleGeo, poleMat);
    pole.position.y = 3.5;
    windsockGroup.add(pole);

    // Orange striped cone
    const coneGeo = new THREE.ConeGeometry(0.7, 3.2, 8);
    const coneMat = new THREE.MeshStandardMaterial({ color: 0xf97316 });
    const cone = new THREE.Mesh(coneGeo, coneMat);
    cone.rotation.z = Math.PI / 2 + 0.2;
    cone.position.set(1.6, 6.7, 0);
    windsockGroup.add(cone);
    this.scene.add(windsockGroup);
  }

  /**
   * Procedural low-poly, clean 3D executive jet models to scale.
   * Proportional footprints:
   * - Light jet: 1.0 su (~16.3m wingspan x 15.6m length, e.g. Citation CJ3)
   * - Midsize jet: 1.5 su (~21.0m wingspan x 20.9m length, e.g. Challenger 350)
   * - Large jet: 2.5 su (~30.4m wingspan x 30.4m length, e.g. Gulfstream G650)
   */
  createAircraftMesh(flight) {
    const group = new THREE.Group();
    group.name = flight.id;
    group.userData = { flight };

    const type = flight.type; // 'light', 'midsize', 'large'

    // Scale factors: 1 unit in 3D = ~2 meters
    // Light: span ~8.2 units, length ~7.8 units
    // Midsize: span ~10.5 units, length ~10.4 units
    // Large: span ~15.2 units, length ~15.2 units
    let span, len, fusRadius, wingChord;
    if (type === 'large') {
      span = 15.2;
      len = 15.2;
      fusRadius = 0.95;
      wingChord = 3.6;
    } else if (type === 'midsize') {
      span = 10.5;
      len = 10.4;
      fusRadius = 0.72;
      wingChord = 2.6;
    } else {
      // Light
      span = 8.2;
      len = 7.8;
      fusRadius = 0.55;
      wingChord = 2.0;
    }

    // Corporate stripe color accents
    const corporateColors = [0x1e3a8a, 0x831843, 0x065f46, 0xb45309, 0x475569, 0x0369a1];
    const accentColor = corporateColors[flight.colorIndex % corporateColors.length];

    const bodyMat = new THREE.MeshStandardMaterial({
      color: 0xf8fafc, // Pearl aviation white
      roughness: 0.3,
      metalness: 0.15
    });

    const accentMat = new THREE.MeshStandardMaterial({
      color: accentColor,
      roughness: 0.35,
      metalness: 0.2
    });

    const glassMat = new THREE.MeshStandardMaterial({
      color: 0x0f172a,
      roughness: 0.1,
      metalness: 0.9
    });

    // 1. Fuselage
    const fusGeo = new THREE.CylinderGeometry(fusRadius * 0.9, fusRadius, len * 0.65, 12);
    const fus = new THREE.Mesh(fusGeo, bodyMat);
    fus.rotation.x = Math.PI / 2;
    fus.position.y = fusRadius + 0.7; // Above ground gear
    fus.castShadow = true;
    group.add(fus);

    // Nosecone
    const noseGeo = new THREE.ConeGeometry(fusRadius * 0.9, len * 0.22, 12);
    const nose = new THREE.Mesh(noseGeo, bodyMat);
    nose.rotation.x = -Math.PI / 2;
    nose.position.set(0, fusRadius + 0.7, len * 0.43);
    nose.castShadow = true;
    group.add(nose);

    // Tailcone
    const tailConeGeo = new THREE.ConeGeometry(fusRadius, len * 0.25, 12);
    const tailCone = new THREE.Mesh(tailConeGeo, bodyMat);
    tailCone.rotation.x = Math.PI / 2;
    tailCone.position.set(0, fusRadius + 0.7, -len * 0.44);
    tailCone.castShadow = true;
    group.add(tailCone);

    // Cockpit windshield
    const glassGeo = new THREE.BoxGeometry(fusRadius * 1.3, fusRadius * 0.6, len * 0.14);
    const glass = new THREE.Mesh(glassGeo, glassMat);
    glass.position.set(0, fusRadius * 1.55 + 0.7, len * 0.28);
    glass.rotation.x = -0.3;
    group.add(glass);

    // 2. Main Wings (Swept)
    const wingShape = new THREE.Shape();
    const halfSpan = span / 2;
    const sweepBack = span * 0.35;
    wingShape.moveTo(0, wingChord * 0.5);
    wingShape.lineTo(halfSpan, -sweepBack + wingChord * 0.2);
    wingShape.lineTo(halfSpan, -sweepBack - wingChord * 0.15);
    wingShape.lineTo(0, -wingChord * 0.5);
    wingShape.lineTo(-halfSpan, -sweepBack - wingChord * 0.15);
    wingShape.lineTo(-halfSpan, -sweepBack + wingChord * 0.2);
    wingShape.closePath();

    const extrudeSettings = { depth: 0.15, bevelEnabled: false };
    const wingGeo = new THREE.ExtrudeGeometry(wingShape, extrudeSettings);
    const wings = new THREE.Mesh(wingGeo, bodyMat);
    wings.rotation.x = Math.PI / 2;
    wings.position.set(0, fusRadius + 0.6, 0);
    wings.castShadow = true;
    group.add(wings);

    // Winglets on tips
    const wingletGeo = new THREE.BoxGeometry(0.12, fusRadius * 1.2, wingChord * 0.35);
    const wingletL = new THREE.Mesh(wingletGeo, accentMat);
    wingletL.position.set(-halfSpan, fusRadius + 1.2, -sweepBack);
    group.add(wingletL);

    const wingletR = new THREE.Mesh(wingletGeo, accentMat);
    wingletR.position.set(halfSpan, fusRadius + 1.2, -sweepBack);
    group.add(wingletR);

    // 3. T-Tail / Vertical Fin
    const finGeo = new THREE.BoxGeometry(0.2, fusRadius * 2.8, len * 0.24);
    const fin = new THREE.Mesh(finGeo, accentMat);
    fin.position.set(0, fusRadius * 2.2 + 0.7, -len * 0.4);
    fin.rotation.x = -0.3;
    fin.castShadow = true;
    group.add(fin);

    // Horizontal Stabilizer
    const horizGeo = new THREE.BoxGeometry(span * 0.42, 0.12, len * 0.16);
    const horizStab = new THREE.Mesh(horizGeo, bodyMat);
    horizStab.position.set(0, fusRadius * 3.4 + 0.7, -len * 0.45);
    horizStab.castShadow = true;
    group.add(horizStab);

    // 4. Twin Turbofan Engines (Mounted on aft fuselage)
    const engGeo = new THREE.CylinderGeometry(fusRadius * 0.38, fusRadius * 0.35, len * 0.3, 10);
    const engMat = new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.4 });

    const engL = new THREE.Mesh(engGeo, engMat);
    engL.rotation.x = Math.PI / 2;
    engL.position.set(-fusRadius * 1.25, fusRadius + 0.9, -len * 0.22);
    engL.castShadow = true;
    group.add(engL);

    const engR = new THREE.Mesh(engGeo, engMat);
    engR.rotation.x = Math.PI / 2;
    engR.position.set(fusRadius * 1.25, fusRadius + 0.9, -len * 0.22);
    engR.castShadow = true;
    group.add(engR);

    // 5. Landing Gear (Tires & Struts)
    const tireGeo = new THREE.CylinderGeometry(0.35, 0.35, 0.25, 8);
    const tireMat = new THREE.MeshBasicMaterial({ color: 0x18181b });

    const noseGear = new THREE.Mesh(tireGeo, tireMat);
    noseGear.rotation.z = Math.PI / 2;
    noseGear.position.set(0, 0.35, len * 0.32);
    group.add(noseGear);

    const mainGearL = new THREE.Mesh(tireGeo, tireMat);
    mainGearL.rotation.z = Math.PI / 2;
    mainGearL.position.set(-fusRadius * 1.1, 0.35, -len * 0.05);
    group.add(mainGearL);

    const mainGearR = new THREE.Mesh(tireGeo, tireMat);
    mainGearR.rotation.z = Math.PI / 2;
    mainGearR.position.set(fusRadius * 1.1, 0.35, -len * 0.05);
    group.add(mainGearR);

    // 6. Navigation Lights (Red port, Green starboard)
    const navGeo = new THREE.SphereGeometry(0.15, 6, 6);
    const redMat = new THREE.MeshBasicMaterial({ color: 0xef4444 });
    const greenMat = new THREE.MeshBasicMaterial({ color: 0x10b981 });

    const portLight = new THREE.Mesh(navGeo, redMat);
    portLight.position.set(-halfSpan - 0.1, fusRadius + 0.6, -sweepBack);
    group.add(portLight);

    const stbdLight = new THREE.Mesh(navGeo, greenMat);
    stbdLight.position.set(halfSpan + 0.1, fusRadius + 0.6, -sweepBack);
    group.add(stbdLight);

    // 7. Interactive selection ring (invisible until clicked)
    const ringGeo = new THREE.RingGeometry(span * 0.52, span * 0.58, 24);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0x3b82f6,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0
    });
    const selectRing = new THREE.Mesh(ringGeo, ringMat);
    selectRing.name = 'selectRing';
    selectRing.rotation.x = -Math.PI / 2;
    selectRing.position.y = 0.05;
    group.add(selectRing);

    return group;
  }

  /**
   * Synchronize the 3D scene with the simulation state from sim-engine.js.
   * Positions active aircraft on stands, handles arrival/departure animations,
   * updates daytime/night lighting, and removes departed planes.
   */
  updateSimulationState(simState) {
    if (!this.scene) return;

    // Update Sun & Ramp floodlights
    this.updateDayNightLighting(simState.hourFloat);

    const activeAircraft = simState.activeAircraft || [];
    const activeIds = new Set(activeAircraft.map(a => a.id));

    // 1. Remove aircraft that have departed
    for (const [id, mesh] of this.aircraftMeshes.entries()) {
      if (!activeIds.has(id)) {
        this.scene.remove(mesh);
        this.aircraftMeshes.delete(id);
      }
    }

    // 2. Update or create active aircraft
    activeAircraft.forEach(plane => {
      let mesh = this.aircraftMeshes.get(plane.id);
      if (!mesh) {
        mesh = this.createAircraftMesh(plane);
        this.scene.add(mesh);
        this.aircraftMeshes.set(plane.id, mesh);
      }

      // Update metadata on mesh
      mesh.userData.flight = plane;

      // Find target stand coordinates
      const standInfo = this.standPositions.get(plane.standId) || { x: 0, z: 0, rotation: 0 };
      const targetX = standInfo.x;
      const targetZ = standInfo.z;
      const targetRot = standInfo.rotation || 0;

      // Dynamic motion based on flight phase:
      if (plane.phase === 'taxi_in') {
        // Taxiing in from taxiway threshold (z = 38)
        const progress = Math.min(1, Math.max(0, (simState.simSeconds - plane.arrivalTime) / 120));
        // Interpolate along taxiway to stand
        mesh.position.x = -110 + progress * (targetX - (-110));
        mesh.position.z = 38 - progress * (38 - targetZ);
        mesh.rotation.y = targetRot + (1 - progress) * 0.5;
      } else if (plane.phase === 'taxi_out') {
        // Taxiing out to runway
        const progress = Math.min(1, Math.max(0, (plane.departureTime - simState.simSeconds) / 120));
        mesh.position.x = targetX + (1 - progress) * 70;
        mesh.position.z = targetZ + (1 - progress) * (38 - targetZ);
        mesh.rotation.y = 0;
      } else {
        // Parked solidly on assigned stand
        mesh.position.set(targetX, 0, targetZ);
        mesh.rotation.y = targetRot;
      }

      // Special highlight for Manager Decision Holding Area!
      const isAwaitingManager = plane.location === 'manager_decision_area';
      const selectRing = mesh.getObjectByName('selectRing');
      if (selectRing) {
        if (this.selectedFlightId === plane.id) {
          selectRing.material.color.setHex(0x2563eb);
          selectRing.material.opacity = 0.9;
        } else if (isAwaitingManager) {
          // Warning pulsing ring for unaccommodated aircraft waiting for manager
          selectRing.material.color.setHex(0xf59e0b);
          selectRing.material.opacity = 0.7;
        } else {
          selectRing.material.opacity = 0;
        }
      }
    });
  }

  // Camera presets
  setCameraPreset(presetName) {
    const preset = this.cameraPresets[presetName];
    if (!preset) return;

    this.cameraLerp = {
      startPos: this.camera.position.clone(),
      endPos: new THREE.Vector3(...preset.pos),
      startTarget: this.controls.target.clone(),
      endTarget: new THREE.Vector3(...preset.target),
      progress: 0,
      duration: 1.0 // seconds
    };
  }

  // Raycaster click handler for aircraft inspection
  onPointerDown(event) {
    if (!this.camera || !this.renderer) return;

    const rect = this.renderer.domElement.getBoundingClientRect();
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, this.camera);

    // Intersect all aircraft groups
    const aircraftList = Array.from(this.aircraftMeshes.values());
    const intersects = this.raycaster.intersectObjects(aircraftList, true);

    if (intersects.length > 0) {
      // Find top group containing flight userData
      let obj = intersects[0].object;
      while (obj && !obj.userData?.flight && obj.parent) {
        obj = obj.parent;
      }

      if (obj && obj.userData?.flight) {
        const flight = obj.userData.flight;
        this.selectedFlightId = flight.id;
        if (this.onSelectAircraft) {
          this.onSelectAircraft(flight);
        }
      }
    } else {
      // Clicked ground: clear selection
      this.selectedFlightId = null;
      if (this.onSelectAircraft) {
        this.onSelectAircraft(null);
      }
    }
  }

  onWindowResize() {
    if (!this.container || !this.renderer || !this.camera) return;
    const width = this.container.clientWidth;
    const height = this.container.clientHeight;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }

  animate() {
    if (!this.isRendering) return;
    this.animationFrameId = requestAnimationFrame(this.animate.bind(this));

    const delta = this.clock.getDelta();

    // Smooth camera transition if active
    if (this.cameraLerp) {
      this.cameraLerp.progress += delta / this.cameraLerp.duration;
      const t = Math.min(1, this.cameraLerp.progress);
      // Smooth step
      const ease = t * t * (3 - 2 * t);
      this.camera.position.lerpVectors(this.cameraLerp.startPos, this.cameraLerp.endPos, ease);
      this.controls.target.lerpVectors(this.cameraLerp.startTarget, this.cameraLerp.endTarget, ease);

      if (t >= 1) {
        this.cameraLerp = null;
      }
    }

    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }

  dispose() {
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
    }
    window.removeEventListener('resize', this.onWindowResize);
    if (this.renderer && this.renderer.domElement) {
      this.container.removeChild(this.renderer.domElement);
      this.renderer.dispose();
    }
  }
}
