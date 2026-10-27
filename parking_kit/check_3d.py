"""Deep 3D check for the parking prototypes (Playwright + Pillow; hooks three.module.js in the test browser, no app change).
usage: python parking_kit/check_3d.py ramp_control 8181 /tmp/shots   (needs: pip install playwright pillow; playwright install chromium)"""
import subprocess, sys, time, json, statistics
from playwright.sync_api import sync_playwright
folder, port, shots = sys.argv[1], sys.argv[2], sys.argv[3]
THREE_URL = 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js'
HOOK = """
;(() => { window.__frames = 0; const prev = Scene.prototype.onBeforeRender;
  Scene.prototype.onBeforeRender = function (renderer, scene, camera) { window.__three = { scene: this, camera, renderer, Vector3, Box3 }; window.__frames++; return prev.apply(this, arguments); }; })();
"""
GL = ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']
SCENE_JS = """() => { const T = window.__three; if (!T) return null;
  const jets = new Map();
  T.scene.traverse(o => { const id = o.userData && o.userData.aircraftId; if (!id || !o.isMesh) return;
    let vis = true; for (let p = o; p; p = p.parent) if (!p.visible) { vis = false; break; }
    if (!jets.has(id)) jets.set(id, { box: new T.Box3(), visible: false });
    const j = jets.get(id); if (vis) { j.visible = true; j.box.union(new T.Box3().setFromObject(o)); } });
  const out = {};
  for (const [id, j] of jets) if (j.visible && !j.box.isEmpty()) { const c = j.box.getCenter(new T.Vector3()), s = j.box.getSize(new T.Vector3());
    const p = c.clone().project(T.camera); out[id] = { x: c.x, z: c.z, span: Math.max(s.x, s.z), sx: p.x, sy: p.y, inView: Math.abs(p.x) < 1 && Math.abs(p.y) < 1 && p.z < 1 }; }
  const cam = T.camera.position; const info = T.renderer.info;
  return { jets: out, camera: [cam.x, cam.y, cam.z], geometries: info.memory.geometries, textures: info.memory.textures, calls: info.render.calls, frames: window.__frames }; }"""
R, errs = {}, []
def ok(name, cond, detail=''):
    R[name] = ('PASS ' if cond else 'FAIL ') + str(detail)[:300]
def hook(route):
    resp = route.fetch(); route.fulfill(response=resp, body=resp.text() + HOOK, headers={**resp.headers, 'content-type': 'application/javascript'})
def lum(png):
    from PIL import Image; import io
    im = Image.open(io.BytesIO(png)).convert('L').resize((96, 54)); px = list(im.get_flattened_data()) if hasattr(im, 'get_flattened_data') else list(im.getdata())
    return statistics.mean(px), statistics.pstdev(px)
srv = subprocess.Popen([sys.executable, '-m', 'http.server', port, '--bind', '127.0.0.1'], cwd=folder, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1.2)
try:
  with sync_playwright() as p:
    b = p.chromium.launch(args=GL)
    def page(reduced, w=1440, h=950):
        ctx = b.new_context(viewport={'width': w, 'height': h}, reduced_motion='reduce' if reduced else 'no-preference')
        pg = ctx.new_page(); pg.route('**/three@0.160.0/build/three.module.js', hook)
        pg.on('pageerror', lambda e: errs.append('PAGEERROR ' + str(e)[:200])); pg.on('console', lambda m: m.type == 'error' and errs.append(m.text[:200]))
        pg.goto(f'http://127.0.0.1:{port}/', wait_until='networkidle'); pg.wait_for_timeout(2500); return pg
    def seek(pg, tick):
        pg.eval_on_selector('input[type=range]', '(e, t) => { e.value = t; e.dispatchEvent(new Event("input", {bubbles: true})); e.dispatchEvent(new Event("change", {bubbles: true})); }', tick)
    canvas_sel = 'canvas'
    # 1. reduced motion: settled frames, consistency 3D vs 2D map
    pg = page(True)
    s = pg.evaluate(SCENE_JS); ok('01 scene hook', bool(s), 'jets=%d frames=%s' % (len(s['jets']), s['frames']) if s else 'no render seen')
    box = pg.locator(canvas_sel).first.bounding_box(); vh = pg.viewport_size['height']
    ok('02 3D stage size', box and box['height'] >= 0.6 * vh and box['width'] >= 0.9 * pg.viewport_size['width'], box)
    mism = []
    for tick in (3 * 24 + 18, 4 * 24 + 12, 1 * 24 + 22):
        seek(pg, tick); pg.wait_for_timeout(900)
        s = pg.evaluate(SCENE_JS); ids3d = set(s['jets'])
        ids2d = set(pg.evaluate(r'''() => { const r = document.querySelector('#stand-register'); const t = r ? r.textContent : '';
          return [...new Set(t.match(/FBO-\d+/g) || [])]; }'''))
        if ids3d != ids2d: mism.append({'tick': tick, 'only3d': sorted(ids3d - ids2d)[:5], 'only2d': sorted(ids2d - ids3d)[:5]})
    ok('03 same aircraft in 3D and 2D map (3 hours)', not mism, mism or 'n=%d at last hour' % len(ids3d))
    spans = sorted(j['span'] for j in s['jets'].values())
    ok('04 jets have real size', spans and spans[0] > 5, 'spans min %.1f max %.1f' % (spans[0], spans[-1]) if spans else 'none')
    # 2. day vs night render
    seek(pg, 3 * 24 + 13); pg.wait_for_timeout(900); day = lum(pg.locator(canvas_sel).first.screenshot())
    seek(pg, 3 * 24 + 1); pg.wait_for_timeout(900); night = lum(pg.locator(canvas_sel).first.screenshot())
    pg.locator(canvas_sel).first.screenshot(path=f'{shots}/t3d_night.png')
    seek(pg, 3 * 24 + 13); pg.wait_for_timeout(900); pg.locator(canvas_sel).first.screenshot(path=f'{shots}/t3d_day.png')
    ok('05 not blank, day brighter than night', day[1] > 8 and night[1] > 4 and day[0] > night[0] + 10, 'day mean %.0f sd %.0f / night mean %.0f sd %.0f' % (day + night))
    # 3. camera presets
    cams, bad, covered = {}, [], []
    for btn in pg.locator('[data-camera]').all():
        name = btn.get_attribute('data-camera')
        try: btn.click(timeout=3000)
        except Exception: covered.append(name); btn.evaluate('e => e.click()')
        pg.wait_for_timeout(700)
        c = pg.evaluate(SCENE_JS)['camera']; cams[name] = [round(v, 1) for v in c]
        if any(v != v for v in c): bad.append(name)
    covered = [c for c in covered if not pg.locator(f'[data-camera="{c}"]').is_disabled()]
    ok('06b camera buttons clickable (not covered)', not covered, covered)
    cams = {k: v for k, v in cams.items() if not pg.locator(f'[data-camera="{k}"]').is_disabled()}
    ok('06 camera presets move the camera', len(cams) >= 3 and len({tuple(v) for v in cams.values()}) == len(cams) and not bad, cams)
    # 4. picking: click a visible jet near the screen centre
    pg.locator('[data-camera]').first.evaluate('e => e.click()'); pg.wait_for_timeout(1500)
    s = pg.evaluate(SCENE_JS); box = pg.locator(canvas_sel).first.bounding_box()
    cand = sorted((j['sx'] ** 2 + j['sy'] ** 2, i, j) for i, j in s['jets'].items() if j['inView'])
    if cand:
        _, jid, j = cand[0]
        pg.mouse.click(box['x'] + (j['sx'] + 1) / 2 * box['width'], box['y'] + (1 - j['sy']) / 2 * box['height']); pg.wait_for_timeout(600)
        insp = pg.inner_text('#inspector-content') if pg.locator('#inspector-content').count() else pg.inner_text('body')
        ok('07 click a jet in 3D selects it', jid in insp, jid)
    else: ok('07 click a jet in 3D selects it', False, 'no jet in view')
    # 5. memory: switch situations repeatedly
    sel = pg.locator('select').first; opts = sel.eval_on_selector_all('option', 'os => os.map(o => o.value)') if False else pg.eval_on_selector('select#situation, select', 's => [...s.options].map(o => o.value)')
    g0 = pg.evaluate(SCENE_JS)['geometries']
    for i in range(10):
        pg.select_option('select#situation' if pg.locator('select#situation').count() else 'select', opts[i % len(opts)]); pg.wait_for_timeout(350)
    pg.select_option('select#situation' if pg.locator('select#situation').count() else 'select', opts[0]); pg.wait_for_timeout(800)
    g1 = pg.evaluate(SCENE_JS)['geometries']
    ok('08 no geometry leak after 10 switches', g1 <= g0 * 1.3 + 20, 'geometries %d -> %d' % (g0, g1))
    pg.context.close()
    # 6. normal motion: aircraft actually move during an hour change
    pg = page(False)
    if pg.locator('#speed').count(): pg.select_option('#speed', index=pg.eval_on_selector('#speed', 's => s.options.length - 1'))
    seek(pg, 3 * 24 + 9); pg.wait_for_timeout(1500); before = pg.evaluate(SCENE_JS)['jets']
    play = pg.locator('#play, [aria-label*="Play" i], button:has-text("Play")').first; play.evaluate('e => e.click()'); samples = []
    for _ in range(30): pg.wait_for_timeout(300); samples.append(pg.evaluate(SCENE_JS)['jets'])
    play.evaluate('e => e.click()')
    ids = set().union(*[set(sm) for sm in samples])
    def track(i): return [(sm[i]['x'], sm[i]['z']) for sm in samples if i in sm]
    moving = {i for i in ids if len(track(i)) > 1 and max(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(track(i), track(i)[1:])) > 0.3}
    new = set(samples[-1]) - set(before)
    ok('09 aircraft move (taxi/tow/pushback) between hours', moving or new, 'moving %d, new %d' % (len(moving), len(new)))
    f0 = pg.evaluate('window.__frames'); pg.wait_for_timeout(3000); f1 = pg.evaluate('window.__frames')
    R['10 render rate (swiftshader, info only)'] = '%.1f fps' % ((f1 - f0) / 3)
    pg.context.close()
    # 7. phone
    pg = page(True, 390, 844); box = pg.locator(canvas_sel).first.bounding_box()
    ok('11 phone: no sideways scroll, 3D visible', pg.evaluate('document.documentElement.scrollWidth') <= 392 and box and box['height'] >= 0.5 * 844, {'scrollWidth': pg.evaluate('document.documentElement.scrollWidth'), 'canvas': box})
    pg.screenshot(path=f'{shots}/t3d_phone.png'); pg.context.close()
    b.close()
    # 8. no WebGL: readable fallback
    b = p.chromium.launch(args=['--disable-webgl', '--disable-3d-apis'])
    ctx = b.new_context(); pg = ctx.new_page(); pg.goto(f'http://127.0.0.1:{port}/', wait_until='networkidle'); pg.wait_for_timeout(1500)
    t = pg.inner_text('body'); ok('12 without WebGL the answer is still readable', '17.4' in t and '82%' in t, 'len %d' % len(t)); b.close()
finally: srv.terminate()
ok('00 no console errors', not errs, errs[:5])
for k in sorted(R): print(k.ljust(50), R[k])
