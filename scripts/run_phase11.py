"""Render deployment preparation, local tests, clipboard and hosted smoke check."""
import argparse
import base64
import getpass
import hashlib
import importlib.metadata as md
import io
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import tarfile
import tempfile
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPSHandler, ProxyHandler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.phase11_render import MAX_ENCODED, MAX_UNPACKED, MAX_FILES, RUNTIME_FILE, allowed_file, allowed_dir, unpack, public_origin

CORE = ('mlflow','cloudpickle','numpy','pandas','scikit-learn','joblib','xgboost','scipy',
        'fastapi','pydantic','uvicorn','httpx','prometheus-client','starlette','anyio')


def test():
    subprocess.run([sys.executable,'-m','pytest','-q','tests/test_phase11.py'],cwd=ROOT,check=True)


def private_dir(root=ROOT):
    base = Path.home()/'.task6-render'
    out = base/hashlib.sha256(str(Path(root).resolve()).encode()).hexdigest()[:16]
    for p in (base, out):
        if p.is_symlink(): raise ValueError('Private output directory is a symlink')
        p.mkdir(mode=0o700, exist_ok=True)
        if not p.is_dir() or p.stat().st_uid != os.getuid(): raise ValueError('Private directory not owned by current user')
        p.chmod(0o700)
    return out


def write_private(path, data):
    path = Path(path)
    if path.is_symlink(): raise ValueError('Private output path is a symlink')
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f: f.write(data)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def pack(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir(): raise ValueError('Phase 9 private snapshot missing or unsafe')
    from backend.phase9_runtime import verify_bundle
    verify_bundle(root)
    paths = sorted(root.rglob('*')); size = 0
    if len(paths)>MAX_FILES: raise ValueError('Too many runtime entries')
    data = io.BytesIO()
    with tarfile.open(fileobj=data,mode='w:gz',format=tarfile.PAX_FORMAT) as tar:
        for path in paths:
            name = path.relative_to(root).as_posix()
            if path.is_symlink() or not ((path.is_dir() and allowed_dir(name)) or (path.is_file() and allowed_file(name))):
                raise ValueError('Unexpected file in private snapshot; no archive generated')
            if path.is_file():
                size += path.stat().st_size
                if size > MAX_UNPACKED: raise ValueError('Snapshot too large')
            info = tar.gettarinfo(str(path),arcname=name)
            info.uid=info.gid=0; info.uname=info.gname=''; info.mode=0o700 if path.is_dir() else 0o600
            info.mtime=0; info.pax_headers={}
            if path.is_file():
                with path.open('rb') as f: tar.addfile(info,f)
            else: tar.addfile(info)
    compressed=data.getvalue(); encoded=base64.b64encode(compressed)
    if len(encoded)>MAX_ENCODED: raise ValueError('Runtime exceeds safe Render secret limit')
    return encoded, hashlib.sha256(compressed).hexdigest()


def lock_versions(root):
    lines = [f'{pkg}=={md.version(pkg)}' for pkg in CORE]
    # MLflow's exported model pins must agree with the local environment. Fail rather than guess.
    model_req = Path(root)/'.phase9-private/champion/model/requirements.txt'
    if not model_req.is_file(): raise ValueError('MLflow artifact requirements.txt missing')
    from packaging.requirements import Requirement
    for line in model_req.read_text().splitlines():
        line=line.strip()
        if not line or line.startswith('#'): continue
        req=Requirement(line)
        if req.marker and not req.marker.evaluate(): continue
        if req.url or not req.specifier.contains(md.version(req.name),prereleases=True):
            raise ValueError('Local model dependency mismatch: '+req.name)
        # Add exact installed versions of any additional artifact dependencies.
        item=f'{req.name}=={md.version(req.name)}'
        if req.name.lower().replace('_','-') not in CORE: lines.append(item)
    content='# Generated from the verified local model environment; no credentials.\n'+'\n'.join(sorted(set(lines)))+'\n'
    path=Path(root)/'requirements-render-lock.txt'
    if path.is_symlink(): raise ValueError('Unsafe lock file')
    if path.exists() and path.read_text()!=content:
        raise ValueError('Existing Render lock differs; review and rename it before deliberately regenerating')
    if not path.exists():
        with path.open('x') as f: f.write(content)
    return path


def prepare(authorized):
    if not authorized: raise ValueError('Confirm dataset/model hosting permission before running prepare --allow-private-cloud')
    if sys.version_info[:2]!=(3,12): raise ValueError('Activate the existing Python 3.12 environment')
    test()
    encoded, digest = pack(ROOT/'.phase9-private')
    with tempfile.TemporaryDirectory() as td:
        meta=unpack(encoded,digest,Path(td))
    lock=lock_versions(ROOT)
    folder=private_dir()
    write_private(folder/RUNTIME_FILE,encoded)
    write_private(folder/'sha256.txt',(digest+'\n').encode())
    print('Runtime checksums verified; model version '+str(meta['model_version']))
    print('Encoded runtime bytes:',len(encoded))
    print('Runtime SHA256:',digest)
    print('Private bundle stored outside Git:',folder/RUNTIME_FILE)
    print('Source-only dependency lock:',lock.name)
    print('No files uploaded. Review source-only git diff. Use copy-bundle only after permission.')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None


def hosted_smoke(url):
    origin=public_origin(url)
    if not origin.endswith('.onrender.com'): raise ValueError('Use the exact Render HTTPS service URL')
    password=getpass.getpass('Render viewer password (hidden): ')
    auth='Basic '+base64.b64encode(('viewer:'+password).encode()).decode()
    opener=build_opener(ProxyHandler({}),NoRedirect(),HTTPSHandler(context=ssl.create_default_context()))
    def call(path,expected=200,authenticated=True,body=None,extra=None):
        headers={'X-Dashboard-Request':'1',**(extra or {})}
        if authenticated: headers['Authorization']=auth
        if body is not None: headers['Content-Type']='application/json'
        req=Request(origin+path,headers=headers,data=None if body is None else json.dumps(body).encode())
        try:
            with opener.open(req,timeout=120) as r: code=r.status; payload=r.read(2_000_000)
        except HTTPError as e: code=e.code; payload=e.read(2_000_000)
        if code!=expected: raise RuntimeError(f'{path}: expected {expected}, received {code}')
        return payload
    call('/healthz',authenticated=False)
    call('/',expected=401,authenticated=False)
    call('/dashboard-api/model',expected=401,authenticated=False)
    call('/')
    call('/dashboard-api/model',expected=403,extra={'Origin':'https://invalid.example'})
    call('/api/v1/model/info',expected=404)
    info=json.loads(call('/dashboard-api/model'))
    row={k:int(v['min']) for k,v in info['training_ranges'].items()}
    row.update({k:v[0] for k,v in info['categories'].items()})
    one=json.loads(call('/dashboard-api/predict',body=row))
    batch=json.loads(call('/dashboard-api/batch',body={'properties':[row,row]}))
    if batch['count']!=2 or one['model_version']!=info['model_version'] or any(v['predicted_price']!=one['predicted_price'] for v in batch['predictions']):
        raise RuntimeError('Hosted prediction consistency failed')
    call('/dashboard-api/predict',expected=422,body={**row,'Area':1.5})
    call('/dashboard-api/market'); call('/dashboard-api/reports')
    print('PASS: HTTPS, authentication, origin rejection, private API isolation, single and batch predictions, strict schema, analytics and reports.')
    print('Verified hosted URL:',origin)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',nargs='?',default='test',choices=('test','prepare','copy-bundle','copy-digest','smoke'))
    p.add_argument('--allow-private-cloud',action='store_true'); p.add_argument('--url')
    a=p.parse_args()
    if a.action=='test': return test()
    if a.action=='prepare': return prepare(a.allow_private_cloud)
    if a.action=='smoke': return hosted_smoke(a.url)
    if not a.allow_private_cloud: raise ValueError('Hosting permission confirmation required')
    name=RUNTIME_FILE if a.action=='copy-bundle' else 'sha256.txt'
    path=private_dir()/name
    if not path.is_file() or path.is_symlink(): raise ValueError('Prepare the authorized runtime first')
    subprocess.run(['pbcopy'],input=path.read_bytes(),check=True)
    print('Copied to clipboard. Paste only into the corresponding Render configuration field; clear clipboard afterward.')

if __name__=='__main__':
    try: main()
    except KeyboardInterrupt: sys.exit(130)
    except Exception as exc: print('Render preparation stopped:',type(exc).__name__,str(exc),file=sys.stderr); sys.exit(1)
