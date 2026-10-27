// Clicks through the presentation demo in headless Chrome and prints what the page showed, as JSON.
// Used by test_agent_app.py: node agent_app_browser.mjs <chrome> <app url> <profile dir> <debug port>
import { spawn } from 'node:child_process';
const [, , chromePath, base, profile, port] = process.argv;
const chrome = spawn(chromePath, ['--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const out = { errors: [] };
try {
  let url;
  for (let i = 0; i < 60 && !url; i++) {
    try { url = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find(x => x.type === 'page')?.webSocketDebuggerUrl; } catch {}
    if (!url) await sleep(250);
  }
  const ws = new WebSocket(url);
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
  let id = 0; const pending = {};
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.id && pending[m.id]) { pending[m.id](m.result); delete pending[m.id]; }
    if (m.method === 'Runtime.exceptionThrown') out.errors.push(m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text);
    if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') out.errors.push(m.params.args.map(a => a.value ?? a.description).join(' '));
  };
  const send = (method, params = {}) => new Promise(r => { const i = ++id; pending[i] = r; ws.send(JSON.stringify({ id: i, method, params })); });
  const js = async e => (await send('Runtime.evaluate', { expression: e, awaitPromise: true, returnByValue: true })).result?.value;
  const text = sel => js(`document.querySelector(${JSON.stringify(sel)})?.textContent.replace(/\\s+/g, ' ').trim() ?? null`);
  await send('Page.enable'); await send('Runtime.enable');
  await send('Page.navigate', { url: base }); await sleep(1500);
  await js('localStorage.clear()');
  await send('Page.navigate', { url: base }); await sleep(2000);

  // 1. Week view
  out.heatmap_rows = await js(`document.querySelectorAll('.heatmap-row').length`);
  out.day_buttons = await js(`document.querySelectorAll('.btn-open-day').length`);
  // 2. Open Friday, 3. log the demo flights
  await js(`document.querySelector('.btn-open-day[data-date="2027-02-12"]').click()`); await sleep(800);
  out.friday_next_hours_before = await text('#next-hours-stats');
  await js(`document.getElementById('tab-movements').click()`); await sleep(500);
  const flights = [['09:15', 'arrival', 'DEMO-01'], ['10:40', 'arrival', 'DEMO-02'], ['11:05', 'arrival', 'DEMO-03'], ['12:20', 'arrival', 'DEMO-04'], ['16:45', 'departure', 'DEMO-05']];
  for (const [time, type, tail] of flights) {
    await js(`(() => { const s = (i, v) => { const el = document.getElementById(i); el.value = v; el.dispatchEvent(new Event('change', { bubbles: true })); };
      s('form-date', '2027-02-12'); s('form-time', '${time}'); s('form-type', '${type}'); s('form-tail', '${tail}'); s('form-size', 'midsize'); s('form-status', 'confirmed');
      document.getElementById('movement-form').requestSubmit(); })()`);
    await sleep(250);
  }
  out.saved_movements = await js(`JSON.parse(localStorage.getItem('lax_fbo_movements_v2') || '[]').map(m => m.tail)`);
  // 4. Booked vs forecast on Friday
  await js(`document.getElementById('tab-week').click()`); await sleep(400);
  await js(`document.querySelector('.btn-open-day[data-date="2027-02-12"]').click()`); await sleep(800);
  out.friday_next_hours_after = await text('#next-hours-stats');
  // 5. Heavy rain on game day, then open Sunday
  await js(`document.getElementById('tab-week').click()`); await sleep(400);
  await js(`(() => { const s = document.querySelector('.weather-select[data-date="2027-02-14"]'); s.value = 'heavy_rain'; s.dispatchEvent(new Event('change', { bubbles: true })); })()`); await sleep(600);
  out.saved_weather = await js(`JSON.parse(localStorage.getItem('lax_fbo_weather_v1') || '{}')['2027-02-14']`);
  await js(`document.querySelector('.btn-open-day[data-date="2027-02-14"]').click()`); await sleep(800);
  out.sunday_page = await js(`document.querySelector('.tab-view:not([hidden])')?.textContent.replace(/\\s+/g, ' ') ?? ''`);
  // 6. Acknowledge the first proposal
  await js(`document.getElementById('tab-week').click()`); await sleep(400);
  out.proposal_buttons = await js(`document.querySelectorAll('.btn-ack-prop').length`);
  await js(`document.querySelector('.btn-ack-prop')?.click()`); await sleep(400);
  out.saved_proposals = await js(`Object.values(JSON.parse(localStorage.getItem('lax_fbo_proposals_v1') || '{}')).map(p => p.status)`);
  // Trust view
  await js(`document.getElementById('tab-trust').click()`); await sleep(600);
  out.backtest = await text('#backtest-bars');
  // Survives a reload
  await send('Page.navigate', { url: base }); await sleep(1500);
  out.movements_after_reload = await js(`JSON.parse(localStorage.getItem('lax_fbo_movements_v2') || '[]').length`);
  ws.close();
} catch (e) {
  out.errors.push(`harness: ${e}`);
} finally {
  chrome.kill();
  console.log(JSON.stringify(out));
  process.exit(0);
}
