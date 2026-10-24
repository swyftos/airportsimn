"""The FBO agent app (agent_gemini/): the page is wired up, it serves, its planning math is right on the real
data, and the presentation demo works in a real browser. The JavaScript checks need node; the browser check
also needs Google Chrome (or CHROME=/path/to/chrome); each is skipped when missing."""
import functools
import http.server
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import unittest
import urllib.request

REPO=Path(__file__).resolve().parents[2]
APP=REPO/'agent_gemini'
HERE=Path(__file__).resolve().parent
NODE=shutil.which('node')
CHROME=os.environ.get('CHROME') or next((p for p in ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    shutil.which('google-chrome'),shutil.which('chromium'),shutil.which('chromium-browser')) if p and Path(p).exists()),None)

def free_port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a):pass
def serve():
    httpd=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(APP)))
    threading.Thread(target=httpd.serve_forever,daemon=True).start();return httpd

class PageTests(unittest.TestCase):
    def test_every_element_the_script_uses_is_on_the_page(self):
        html=(APP/'index.html').read_text(encoding='utf-8');js=(APP/'app.js').read_text(encoding='utf-8')
        ids=set(re.findall(r"getElementById\('([^']+)'\)",js))
        self.assertGreater(len(ids),40)
        self.assertEqual(sorted(i for i in ids if f'id="{i}"' not in html),[])
    def test_page_files_are_served(self):
        httpd=serve()
        try:
            base=f'http://127.0.0.1:{httpd.server_address[1]}/'
            with urllib.request.urlopen(base) as r:html=r.read().decode()
            for f in ('app.js','styles.css','agent_data.json'):
                self.assertIn(f,html+'agent_data.json')  # the data file is fetched by app.js, not linked
                with urllib.request.urlopen(base+f) as r:self.assertEqual(r.status,200)
            with urllib.request.urlopen(base+'agent_data.json') as r:json.loads(r.read())
        finally:httpd.shutdown();httpd.server_close()

@unittest.skipUnless(NODE,'node not installed')
class PlanningMathTests(unittest.TestCase):
    """app.js run on the real agent_data.json, without a browser (agent_app_harness.js)."""
    @classmethod
    def setUpClass(cls):
        out=subprocess.run([NODE,str(HERE/'agent_app_harness.js'),str(APP/'app.js'),str(APP/'agent_data.json')],capture_output=True,text=True,timeout=60)
        if out.returncode:raise AssertionError(out.stderr)
        cls.r=json.loads(out.stdout);cls.data=json.loads((APP/'agent_data.json').read_text(encoding='utf-8'))
    def by_date(self,key):return {x['date']:x for x in self.r[key]}
    def test_clear_weather_shows_the_forecast_unchanged(self):
        for s in ('Low','Medium','High'):
            for x,d in zip(self.r['clear_'+s],self.data['days']):
                self.assertAlmostEqual(x['arr'],d['scenarios'][s]['expected_arrivals'],places=6)
                self.assertAlmostEqual(x['dep'],d['scenarios'][s]['expected_departures'],places=6)
                self.assertEqual(x['arrRange'],d['scenarios'][s]['arrivals_range90'])
    def test_hours_add_up_to_the_day(self):
        days=self.by_date('clear_Medium')
        for h in self.r['hourly']:
            self.assertAlmostEqual(h['arr'],days[h['date']]['arr'],delta=0.001)
            self.assertAlmostEqual(h['dep'],days[h['date']]['dep'],delta=0.001)
    def test_game_day_pause(self):
        hours={h['date']:h for h in self.r['hourly']}
        self.assertEqual(hours['2027-02-14']['pause_hours'],list(range(14,21)))
        self.assertTrue(all(not h['pause_hours'] for d,h in hours.items() if d!='2027-02-14'))
        self.assertEqual(self.r['in_restriction'],{'sun_1400_1500':True,'sun_1300_1400':False,'sun_2000_2100':True,'sun_2030_2100':False,'sat_1500_1600':False})
        # 14:00-14:30 and 20:30-21:00 are open; nothing is planned in between
        g=self.data['game_day_restriction']['hour_shares']
        for t in ('arrivals','departures'):self.assertEqual(g[t][15:20],[0]*5)
    def test_heavy_rain_on_game_day_moves_flights_to_monday(self):
        clear,rain=self.by_date('clear_Medium'),self.by_date('sunday_heavy_rain')
        sun,mon=rain['2027-02-14'],rain['2027-02-15']
        self.assertLess(sun['effect'],0)
        self.assertAlmostEqual(mon['dep'],clear['2027-02-15']['dep']+sun['lostDep'],places=6)
        self.assertEqual(round(clear['2027-02-15']['dep'],1),10.0);self.assertEqual(round(mon['dep'],1),10.3)
        for k in ('arr','dep'):  # nothing is lost over the week, it only moves a day
            self.assertAlmostEqual(sum(x[k] for x in rain.values()),sum(x[k] for x in clear.values()),places=6)
        for d in ('2027-02-11','2027-02-12','2027-02-13','2027-02-16','2027-02-17'):self.assertEqual(rain[d]['arr'],clear[d]['arr'])
    def test_rain_on_the_last_day_drops_flights_outside_the_week(self):
        last=self.r['last_day_rain'][-1]
        self.assertGreater(last['lostArr'],0)
        self.assertLess(sum(x['arr'] for x in self.r['last_day_rain']),sum(x['arr'] for x in self.r['clear_Medium']))
    def test_weather_effect_is_weighted_by_the_part91_part135_split(self):
        fri=self.data['days'][1]['scenarios']['Medium'];eff=self.data['weather']['effects']
        for w,days in self.r['every_weather'].items():
            want=fri['share_part91']*eff[w]['part91']['effect']+fri['share_part135']*eff[w]['part135']['effect']
            self.assertAlmostEqual(days[1]['effect'],want,places=9,msg=w)
    def test_peak_windows(self):
        p=self.r['peak']
        self.assertEqual((p['weekday_arrivals']['start'],p['weekday_arrivals']['end']),(9,12))
        self.assertEqual((p['weekday_departures']['start'],p['weekday_departures']['end']),(7,10))
        self.assertEqual(round(p['after_pause_departures']*100),40)
        self.assertEqual(p['flat']['start'],0,'ties go to the earliest window')
    def test_demo_booked_vs_forecast(self):
        d=self.r['demo']
        self.assertEqual((d['booked_arrivals'],d['booked_departures']),(4,1))
        self.assertEqual(d['hours_with_flights'],[9,10,11,12,16])
        self.assertEqual(round(d['expected_arrivals']-d['booked_arrivals']),3,'plan for about 3 unannounced landings')
    def test_csv_import_skips_bad_rows(self):
        self.assertEqual(self.r['csv'],{'imported':['DEMO-01','(none)'],'saved':2})
    def test_html_is_escaped(self):
        self.assertNotIn('<',self.r['escape'])

@unittest.skipUnless(NODE and CHROME,'node or Chrome not installed')
class DemoInBrowserTests(unittest.TestCase):
    """The presentation demo clicked through in headless Chrome (agent_app_browser.mjs)."""
    @classmethod
    def setUpClass(cls):
        httpd=serve();tmp=tempfile.TemporaryDirectory()
        try:
            out=subprocess.run([NODE,str(HERE/'agent_app_browser.mjs'),CHROME,f'http://127.0.0.1:{httpd.server_address[1]}/',tmp.name,str(free_port())],
                               capture_output=True,text=True,timeout=120)
            cls.r=json.loads(out.stdout)
        finally:httpd.shutdown();httpd.server_close();tmp.cleanup()
    def test_no_javascript_errors(self):self.assertEqual(self.r['errors'],[])
    def test_week_view_shows_seven_days(self):
        self.assertEqual(self.r['heatmap_rows'],7);self.assertEqual(self.r['day_buttons'],7)
    def test_logged_flights_are_saved_and_survive_a_reload(self):
        self.assertEqual(self.r['saved_movements'],['DEMO-01','DEMO-02','DEMO-03','DEMO-04','DEMO-05'])
        self.assertEqual(self.r['movements_after_reload'],5)
    def test_next_three_hours_count_the_booked_landings(self):
        self.assertIn('(0 Booked)',self.r['friday_next_hours_before'])
        self.assertIn('(3 Booked)',self.r['friday_next_hours_after'])  # 10:40, 11:05, 12:20 fall in 10:00-13:00
        for text in (self.r['friday_next_hours_before'],self.r['friday_next_hours_after']):
            for expected,booked in re.findall(r'([\d.]+) Exp \w+ \((\d+) Booked\)',text):
                self.assertGreaterEqual(float(expected),int(booked),text)
    def test_game_day_page_shows_the_pause(self):
        self.assertIn('Weather: Heavy rain',self.r['sunday_page'])
        self.assertEqual(self.r['saved_weather'],'heavy_rain')
        self.assertIn('Sunday 14 February 2027',self.r['sunday_page']);self.assertIn('14:30–20:30',self.r['sunday_page'])
    def test_proposals_can_be_acknowledged(self):
        self.assertGreater(self.r['proposal_buttons'],0);self.assertEqual(self.r['saved_proposals'],['acknowledged'])
    def test_trust_view_shows_the_backtest(self):
        for v in ('14.9%','16.6%','17.8%','18.4%','21.5%'):self.assertIn(v,self.r['backtest'])

if __name__=='__main__':unittest.main()
