#!/usr/bin/env python3
"""Local FBO planning dashboard. Run: python3 dashboard/app.py

Demo identities are intentionally available to everyone on this local server.
Do not expose this server publicly or treat demo sign-in as real authentication.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import mimetypes
import secrets
import threading
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from readiness.contracts import ContractError, load_bundle, summarize
from readiness.data import sample_bundle, team_bundle, team_status, native_bundle, native_status
from readiness.storage import ReviewStore
from readiness.release_status import sources_reference
from readiness.what_if import plan as what_if_plan
from readiness.design_view import view as design_view, catalog as design_catalog, parse_bookings

ROOT=Path(__file__).resolve().parent
PROFILES={
    'manager':{'id':'maya-demo','name':'Maya Chen','role':'manager','position':'FBO manager','initials':'MC'},
    'reservations':{'id':'alex-demo','name':'Jordan Rivera','role':'reservations','position':'Reservations coordinator','initials':'JR'},
    'operations':{'id':'jordan-demo','name':'Sam Ellis','role':'operations','position':'Operations supervisor','initials':'SE'},
}

class Application:
    def __init__(self,state_dir=None,repo_root=None):
        self.lock=threading.RLock()
        self.store=ReviewStore(state_dir or ROOT/'.state')
        self.repo_root=Path(repo_root or ROOT.parent)
        self.sessions={}
        self.source,self.imported=self.store.source()
        self.load_error=None
        try: self.bundle=self.read_source(self.source,self.imported)
        except (ContractError,OSError,ValueError,TypeError,KeyError) as exc:
            self.bundle=None; self.load_error=str(exc)
    def read_source(self,source,files=None):
        if source=='sample': return sample_bundle(ROOT)
        if source=='team': return team_bundle(self.repo_root)
        if source=='team-native': return native_bundle(self.repo_root)
        if source=='import': return load_bundle(files)
        raise ContractError('Unknown data source.')
    def activate(self,source,files=None):
        candidate=self.read_source(source,files)
        self.store.save_source(source,files if source=='import' else None)
        self.bundle=candidate; self.source=source; self.imported=files if source=='import' else None; self.load_error=None
    def input_status(self):
        if not self.bundle:return {'stale':True,'message':self.load_error or 'No valid dataset is loaded.'}
        if self.source=='import':return {'stale':False,'message':'Imported snapshot; re-import to use updated files.'}
        try:
            candidate=self.read_source(self.source,self.imported)
            if candidate['version']!=self.bundle['version']:
                return {'stale':True,'message':'Inputs changed since this plan was loaded. Refresh the current source before reviewing or exporting; the screen still shows the previous snapshot.'}
        except (ContractError,OSError,ValueError,TypeError,KeyError) as exc:
            return {'stale':True,'message':'Current source cannot be verified: '+str(exc)+' The screen still shows the previous snapshot.'}
        return {'stale':False,'message':'Loaded snapshot matches current source files.'}
    def snapshot(self):
        return {'bundle':self.bundle,'source':self.source,'load_error':self.load_error,
                'input_status':self.input_status(),'sources_reference':sources_reference(self.repo_root),
                'summaries':{s:{v:summarize(self.bundle,s,v) for v in self.bundle['variants']} for s in ('low','medium','high')} if self.bundle else {},
                'native_files':native_status(self.repo_root), 'team_files':team_status(self.repo_root),'history':self.store.history(self.bundle['version'] if self.bundle else '')}

    def design_snapshot(self,scenario,variant):
        if not self.bundle:raise ContractError(self.load_error or 'No valid dataset loaded.')
        bookings=self.store.design_state('bookings',{'visits':[],'updated_at':None})
        version=hashlib.sha256(json.dumps([self.bundle['version'],scenario,variant,bookings],sort_keys=True).encode()).hexdigest()
        return {**design_view(self.bundle,scenario,variant,bookings),'version':version,
                'history':self.store.history(version),'checks':self.store.design_state('checks',{}),
                'ramp_checks':self.store.design_state('ramp_checks',{}),'input_status':self.input_status()}

class Handler(BaseHTTPRequestHandler):
    server_version='IntelligentFBOLocal/1.0'
    def log_message(self,format,*args): pass
    @property
    def app(self): return self.server.application
    def reply(self,status,data,ctype='application/json; charset=utf-8',extra=None):
        payload=json.dumps(data,allow_nan=False).encode() if ctype.startswith('application/json') else data
        self.send_response(status)
        self.send_header('Content-Type',ctype)
        self.send_header('Content-Length',str(len(payload)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if extra:
            for k,v in extra.items(): self.send_header(k,v)
        self.end_headers()
        self.wfile.write(payload)
    def session(self):
        cookie=SimpleCookie()
        try: cookie.load(self.headers.get('Cookie',''))
        except Exception: return None
        token=cookie.get('readiness_session')
        return self.app.sessions.get(token.value) if token else None
    def allowed_host(self):
        host=self.headers.get('Host','')
        return host in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}')
    def do_GET(self):
        if not self.allowed_host(): return self.reply(403,{'error':'Use the local server URL.'})
        url=urlsplit(self.path)
        if url.path=='/api/session':
            session=self.session()
            return self.reply(200,{'profile':session['profile'] if session else None,'csrf':session['csrf'] if session else None})
        if url.path.startswith('/api/'):
            session=self.session()
            if not session: return self.reply(401,{'error':'Choose a demo account first.'})
            with self.app.lock:
                if url.path=='/api/dashboard': return self.reply(200,self.app.snapshot())
                if url.path=='/api/design':
                    q=parse_qs(url.query)
                    try:return self.reply(200,self.app.design_snapshot(q.get('scenario',['medium'])[0],q.get('variant',['standard'])[0]))
                    except (ContractError,ValueError,KeyError) as exc:return self.reply(400,{'error':str(exc)})
                if url.path=='/api/export':
                    q=parse_qs(url.query)
                    if not self.app.bundle: return self.reply(409,{'error':'No valid dataset is loaded.'})
                    freshness=self.app.input_status()
                    if freshness['stale']: return self.reply(409,{'error':freshness['message']})
                    try:
                        sc=q.get('scenario',['medium'])[0]; variant=q.get('variant',['standard'])[0]
                        data={'release_review':self.app.bundle.get('release_review',{'status':'unreviewed','label':'Review status not supplied'}),'dataset':self.app.bundle['meta'],'source':self.app.source,'assumptions':self.app.bundle['assumptions'],'basis':'Daily P50 parking peaks from P3' if self.app.bundle.get('native') else 'Supplied daily peak parking fixtures/outputs','version':self.app.bundle['version'],'scenario':sc,'variant':variant,
                            'summary':summarize(self.app.bundle,sc,variant),
                            'simulation_impact':self.app.bundle.get('impacts_by_variant',{}).get(variant,self.app.bundle.get('impacts',{})).get(sc),
                            'baseline':self.app.bundle['baseline'],
                            'resources':[r for r in self.app.bundle['resources'] if r['scenario']==sc and r['variant']==variant],
                            'carryover':[r for r in self.app.bundle.get('carryover',[]) if r['variant']=='ordinary' or (r['variant']==variant and r['scenario']==sc)],
                            'delay_definition':self.app.bundle.get('delay_definition') if variant=='departure_delay_24h' else None,
                            'forecast_drivers':[r for r in self.app.bundle.get('forecast_drivers',[]) if r['scenario']==sc],
                            'input_limitations':self.app.bundle.get('limitations',[]),
                            'recommendations':[r for r in self.app.bundle['recommendations'] if r['scenario']==sc and r['variant']==variant],
                            'reviews':[r for r in self.app.store.history(self.app.bundle['version']) if not r['stale'] and r['scenario']==sc and r['variant']==variant],
                            'limitations':'Planning review only. No capacity is reserved, money committed, or aircraft movement authorized. Demo reviewer identities are unverified.'}
                    except ContractError as exc: return self.reply(400,{'error':str(exc)})
                    return self.reply(200,json.dumps(data,indent=2).encode(),'application/octet-stream',{'Content-Disposition':'attachment; filename="readiness-plan.json"'})
            return self.reply(404,{'error':'Unknown endpoint.'})
        allowed={'/':'index.html','/legacy':'legacy.html','/app.js':'app.js','/styles.css':'styles.css','/what-if.js':'what-if.js','/what-if.css':'what-if.css','/design-tools.js':'design-tools.js','/design.js':'design.js','/design.css':'design.css'}
        for name in ('Signin','Main','Day','Plan','Bookings','Ramp','Numbers'):
            allowed['/templates/'+name+'.html']='templates/'+name+'.html'
        if url.path not in allowed: return self.reply(404,{'error':'Not found.'})
        file=ROOT/'static'/allowed[url.path]
        return self.reply(200,file.read_bytes(),(mimetypes.guess_type(str(file))[0] or 'text/plain')+'; charset=utf-8')
    def do_POST(self):
        if not self.allowed_host(): return self.reply(403,{'error':'Use the local server URL.'})
        origin=self.headers.get('Origin')
        if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'):
            return self.reply(403,{'error':'Cross-origin writes are not allowed.'})
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':
            return self.reply(415,{'error':'Send application/json.'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=5_000_000: return self.reply(413,{'error':'Request must be between 1 byte and 5 MB.'})
            body=json.loads(self.rfile.read(length))
            if not isinstance(body,dict): raise ValueError('Expected a JSON object.')
        except (ValueError,UnicodeError) as exc: return self.reply(400,{'error':str(exc)})
        path=urlsplit(self.path).path
        with self.app.lock:
            if path=='/api/login':
                role=body.get('role')
                if not isinstance(role,str) or role not in PROFILES: return self.reply(400,{'error':'Select one of the three demo profiles.'})
                token=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(32)
                self.app.sessions[token]={'profile':PROFILES[role].copy(),'csrf':csrf}
                return self.reply(200,{'profile':PROFILES[role],'csrf':csrf},'application/json; charset=utf-8',
                    {'Set-Cookie':f'readiness_session={token}; HttpOnly; SameSite=Strict; Path=/'})
            session=self.session()
            if not session: return self.reply(401,{'error':'Choose a demo account first.'})
            if self.headers.get('X-CSRF-Token')!=session['csrf']: return self.reply(403,{'error':'Refresh your session before making changes.'})
            if path=='/api/logout':
                self.app.sessions={k:v for k,v in self.app.sessions.items() if v is not session}
                return self.reply(200,{'ok':True},extra={'Set-Cookie':'readiness_session=; Max-Age=0; HttpOnly; SameSite=Strict; Path=/'})
            if path=='/api/what-if':
                freshness=self.app.input_status()
                if freshness['stale']: return self.reply(409,{'error':freshness['message']})
                if not self.app.bundle or body.get('version')!=self.app.bundle['version']:
                    return self.reply(409,{'error':'Source changed. Refresh the forecast before recalculating this experiment.'})
                try:
                    if set(body)!={'version','settings'}: raise ContractError('Provide only version and settings.')
                    return self.reply(200,what_if_plan(self.app.bundle,body['settings']))
                except (ContractError,ValueError,KeyError,TypeError) as exc:
                    return self.reply(400,{'error':str(exc)})
            if path.startswith('/api/design/'):
                from datetime import datetime, timezone
                try:
                    role=session['profile']['role']
                    scenario=body.get('scenario','medium');variant=body.get('variant','standard')
                    current=self.app.design_snapshot(scenario,variant)
                    if current['input_status']['stale'] or body.get('version')!=current['version']:
                        return self.reply(409,{'error':'Inputs changed. Refresh the plan before saving.'})
                    if path=='/api/design/bookings':
                        if role not in ('manager','reservations'):return self.reply(403,{'error':'Use a reservations or manager account to upload visits.'})
                        visits=parse_bookings(body.get('csv'))
                        self.app.store.save_design_state('bookings',{'visits':visits,'updated_at':datetime.now(timezone.utc).isoformat()})
                    elif path=='/api/design/check':
                        kind=body.get('kind');key=body.get('key');checked=body.get('checked')
                        if kind not in ('checks','ramp_checks') or not isinstance(checked,bool):raise ContractError('Invalid checklist update.')
                        needed=('manager','reservations') if kind=='checks' else ('manager','operations')
                        if role not in needed:return self.reply(403,{'error':'Use the role responsible for this checklist.'})
                        valid=([v['id'] for v in current['illustration']['visits']]+[v['id'] for v in current['bookings']['visits']]) if kind=='checks' else ['capacity','access','lighting','reserve','briefing','partner']
                        if key not in valid:raise ContractError('Unknown checklist item.')
                        state=self.app.store.design_state(kind,{})
                        state[current['version']+':'+key]={'checked':checked,'reviewer':session['profile']['name'],'time':datetime.now(timezone.utc).isoformat()}
                        self.app.store.save_design_state(kind,state)
                    elif path=='/api/design/review':
                        if role!='manager':return self.reply(403,{'error':'Use the manager account to review the preparation plan.'})
                        rid=body.get('recommendation_id');decision=body.get('decision');note=body.get('note','');checks=body.get('checks',{})
                        if rid not in [r['id'] for r in current['actions']]:raise ContractError('This action is not part of the current plan.')
                        if decision not in ('approved','changes_requested','rejected'):raise ContractError('Invalid review decision.')
                        if not isinstance(note,str) or not 5<=len(note.strip())<=600:raise ContractError('Add a review note of 5–600 characters.')
                        if not isinstance(checks,dict) or set(checks)-{'assumptions','availability','cost'}:raise ContractError('Invalid review checks.')
                        if decision=='approved' and any(checks.get(k) is not True for k in ('assumptions','availability','cost')):raise ContractError('Confirm assumptions, availability and costs before approval.')
                        self.app.store.add(current['version'],scenario,variant,rid,decision,note.strip(),session['profile']['name']+' (demo)',checks)
                    else:return self.reply(404,{'error':'Unknown design action.'})
                    return self.reply(200,self.app.design_snapshot(scenario,variant))
                except (ContractError,ValueError,KeyError,TypeError) as exc:return self.reply(400,{'error':str(exc)})
            if session['profile']['role']!='manager': return self.reply(403,{'error':'The manager demo role is required for reviews or data changes.'})
            try:
                if path in ('/api/source','/api/import'):
                    source='import' if path=='/api/import' else body.get('source')
                    files=body.get('files')
                    if source=='import' and path=='/api/source': files=self.app.imported
                    self.app.activate(source,files)
                    return self.reply(200,self.app.snapshot())
                if path=='/api/review':
                    freshness=self.app.input_status()
                    if freshness['stale']: return self.reply(409,{'error':freshness['message']})
                    bundle=self.app.bundle
                    if not bundle or body.get('version')!=bundle['version']:
                        return self.reply(409,{'error':'This plan is stale. Refresh the data and review the new version.'})
                    sc=body.get('scenario'); variant=body.get('variant'); rid=body.get('recommendation_id')
                    rec=next((r for r in bundle['recommendations'] if r['scenario']==sc and r['variant']==variant and r['id']==rid),None)
                    if not rec: raise ContractError('Recommendation does not exist in this plan.')
                    decision=body.get('decision'); note=body.get('note',''); checks=body.get('checks',{})
                    if decision not in ('approved','changes_requested','rejected'): raise ContractError('Unsupported review decision.')
                    if not isinstance(note,str) or not 5<=len(note.strip())<=600: raise ContractError('Add a review note of 5–600 characters.')
                    if decision=='approved' and (not isinstance(checks,dict) or any(checks.get(k) is not True for k in ('assumptions','availability','cost'))):
                        raise ContractError('Confirm assumptions, resource availability and costs before recording approval.')
                    if not isinstance(checks,dict) or set(checks)-{'assumptions','availability','cost'}:
                        raise ContractError('Unsupported review checks.')
                    seq=self.app.store.add(bundle['version'],sc,variant,rid,decision,note.strip(),session['profile']['name']+' (demo)',checks)
                    return self.reply(201,{'sequence':seq,'history':self.app.store.history(bundle['version'])})
            except (ContractError,ValueError,TypeError,KeyError,OSError) as exc:
                return self.reply(400,{'error':str(exc)})
        return self.reply(404,{'error':'Unknown endpoint.'})

def create_server(port=4180,state_dir=None,repo_root=None):
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.application=Application(state_dir,repo_root)
    return server

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=4180)
    args=parser.parse_args()
    server=create_server(args.port)
    print(f'The Intelligent FBO: http://127.0.0.1:{server.server_port}',flush=True)
    print('Local demonstration only. Press Ctrl+C to stop.',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
