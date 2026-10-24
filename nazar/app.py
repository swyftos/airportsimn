#!/usr/bin/env python3
"""Local FBO planning dashboard. Run: python3 nazar/app.py

Demo identities are intentionally available to everyone on this local server.
Do not expose this server publicly or treat demo sign-in as real authentication.
"""
from __future__ import annotations
import argparse
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

ROOT=Path(__file__).resolve().parent
PROFILES={
    'manager':{'id':'maya-demo','name':'Maya Chen','role':'manager','position':'FBO manager','initials':'MC'},
    'reservations':{'id':'alex-demo','name':'Alex Rivera','role':'reservations','position':'Reservations coordinator','initials':'AR'},
    'operations':{'id':'jordan-demo','name':'Jordan Ellis','role':'operations','position':'Operations supervisor','initials':'JE'},
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
    def snapshot(self):
        return {'bundle':self.bundle,'source':self.source,'load_error':self.load_error,
                'summaries':{s:{v:summarize(self.bundle,s,v) for v in self.bundle['variants']} for s in ('low','medium','high')} if self.bundle else {},
                'native_files':native_status(self.repo_root), 'team_files':team_status(self.repo_root),'history':self.store.history(self.bundle['version'] if self.bundle else '')}

class Handler(BaseHTTPRequestHandler):
    server_version='RampReadyLocal/1.0'
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
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
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
                if url.path=='/api/export':
                    q=parse_qs(url.query)
                    if not self.app.bundle: return self.reply(409,{'error':'No valid dataset is loaded.'})
                    try:
                        sc=q.get('scenario',['medium'])[0]; variant=q.get('variant',['standard'])[0]
                        data={'dataset':self.app.bundle['meta'],'source':self.app.source,'assumptions':self.app.bundle['assumptions'],'basis':'Daily P50 parking peaks from P3' if self.app.bundle.get('native') else 'Supplied daily peak parking fixtures/outputs','version':self.app.bundle['version'],'scenario':sc,'variant':variant,
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
        allowed={'/':'index.html','/app.js':'app.js','/styles.css':'styles.css'}
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
            if session['profile']['role']!='manager': return self.reply(403,{'error':'The manager demo role is required for reviews or data changes.'})
            try:
                if path in ('/api/source','/api/import'):
                    source='import' if path=='/api/import' else body.get('source')
                    files=body.get('files')
                    if source=='import' and path=='/api/source': files=self.app.imported
                    self.app.activate(source,files)
                    return self.reply(200,self.app.snapshot())
                if path=='/api/review':
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
    print(f'RampReady: http://127.0.0.1:{server.server_port}',flush=True)
    print('Local demonstration only. Press Ctrl+C to stop.',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
