"""One launcher: test, build React, verify/start Phase 5, serve the local dashboard."""
import argparse, asyncio, importlib.util, os, shutil, socket, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
FRONT=ROOT/'frontend/phase6'

def occupied(port):
    with socket.socket() as s:
        return s.connect_ex(('127.0.0.1',port))==0

def check_backend(key):
    import httpx
    try:
        with httpx.Client(base_url='http://127.0.0.1:8006',timeout=3,trust_env=False) as c:
            h=c.get('/api/v1/health'); h.raise_for_status()
            if h.json().get('version')!='0.5.0' or not h.json().get('model_ready'): return False
            m=c.get('/api/v1/model/info',headers={'X-API-Key':key}); m.raise_for_status()
            return m.json().get('loaded_from_alias')=='champion'
    except (httpx.HTTPError,ValueError): return False

def run_tests(npm):
    output=[]
    for command,cwd in [([sys.executable,'-m','pytest','-q','tests/test_phase6.py'],ROOT),([npm,'test'],FRONT)]:
        p=subprocess.run(command,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        print(p.stdout,flush=True); output.append(p.stdout)
        (ROOT/'reports').mkdir(exist_ok=True)
        (ROOT/'reports/phase6_test_results.txt').write_text('\n'.join(output))
        if p.returncode: raise RuntimeError('Phase 6 tests failed')

def live_smoke(app):
    import httpx
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1:5176',headers={'X-Dashboard-Request':'1'}) as c:
            model=await c.get('/dashboard-api/model'); model.raise_for_status(); info=model.json()
            row={k:int(v['min']) for k,v in info['training_ranges'].items()}
            row.update({k:v[0] for k,v in info['categories'].items()})
            one=await c.post('/dashboard-api/predict',json=row); one.raise_for_status()
            batch=await c.post('/dashboard-api/batch',json={'properties':[row,row]}); batch.raise_for_status()
            if batch.json()['count']!=2 or one.json()['model_version']!=info['model_version']:
                raise RuntimeError('Unexpected live prediction response')
            for path in ('market','reports'):
                response=await c.get('/dashboard-api/'+path); response.raise_for_status()
            unauth=await c.get('/dashboard-api/model',headers={'X-Dashboard-Request':'0'})
            if unauth.status_code!=403: raise RuntimeError('Gateway request guard failed')
    asyncio.run(check())
    print('Live dashboard checks passed: model, single, batch, analytics, reports and request guard',flush=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--setup',action='store_true',help='Install frontend and Phase 5 dependencies')
    parser.add_argument('action',nargs='?',default='run',choices=['run','test'])
    args=parser.parse_args()
    npm=shutil.which('npm')
    if not npm: raise RuntimeError('Node.js 22 and npm are required (as in Phase 1)')
    if args.setup:
        subprocess.run([sys.executable,'-m','pip','install','-r','requirements-phase5.txt'],cwd=ROOT,check=True)
    run_tests(npm)
    if args.action=='test': return
    if occupied(5176): raise RuntimeError('Port 5176 is in use. Stop the old dashboard first; no process was killed.')
    if args.setup or not (FRONT/'node_modules/vite').is_dir():
        subprocess.run([npm,'install','--no-audit','--no-fund'],cwd=FRONT,check=True)
    subprocess.run([npm,'run','build'],cwd=FRONT,check=True)
    spec=importlib.util.spec_from_file_location('phase5_launcher',ROOT/'scripts/run_phase5.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    key=mod.get_key()
    child=None
    try:
        if occupied(8006):
            if not check_backend(key): raise RuntimeError('Port 8006 is occupied by a mismatched API. Stop the old server, then rerun.')
            print('Reusing verified Phase 5 API on port 8006',flush=True)
        else:
            child=subprocess.Popen([sys.executable,str(ROOT/'scripts/run_phase5.py'),'serve'],cwd=ROOT,env={**os.environ,'TASK6_API_KEY':key})
            for _ in range(120):
                if child.poll() is not None: raise RuntimeError('Phase 5 stopped; review its error above')
                if check_backend(key): break
                time.sleep(1)
            else: raise RuntimeError('Phase 5 API did not become ready')
        from backend.phase6_gateway import create_gateway
        import uvicorn
        app=create_gateway(ROOT,key)
        live_smoke(app)
        print('PHASE 6 READY — http://127.0.0.1:5176',flush=True)
        uvicorn.run(app,host='127.0.0.1',port=5176)
    finally:
        if child and child.poll() is None:
            child.terminate()
            try: child.wait(timeout=10)
            except subprocess.TimeoutExpired: child.kill(); child.wait()
if __name__=='__main__':
    try: main()
    except KeyboardInterrupt: pass
    except Exception as exc: print(f'Phase 6 stopped: {exc}',file=sys.stderr); sys.exit(1)
