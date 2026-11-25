"""Start the monitored API, existing React dashboard, Prometheus and Grafana together."""
import argparse, importlib.util, os, secrets, shutil, socket, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['MLFLOW_ENABLE_TELEMETRY']='false'
STACK=ROOT/'monitoring/phase7/compose.yml'


def run(args, **kwargs): return subprocess.run(args,cwd=ROOT,check=True,**kwargs)
def occupied(port):
    with socket.socket() as s:
        s.settimeout(.3); return s.connect_ex(('127.0.0.1',port))==0

def key():
    spec=importlib.util.spec_from_file_location('phase5_launcher',ROOT/'scripts/run_phase5.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod.get_key()

def test():
    p=subprocess.run([sys.executable,'-m','pytest','-q','tests/test_phase7.py'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    (ROOT/'reports').mkdir(exist_ok=True)
    (ROOT/'reports/phase7_test_results.txt').write_text(p.stdout)
    print(p.stdout,flush=True)
    if p.returncode: raise RuntimeError('Phase 7 tests failed')

def serve():
    from backend.phase7_monitoring import create_instrumented
    import uvicorn
    app=create_instrumented(ROOT,key())
    uvicorn.run(app,host='127.0.0.1',port=8006,log_level='info')

def wait_for(url, children, check=lambda r:r.status_code==200, seconds=180, headers=None):
    import httpx
    for _ in range(seconds):
        if any(p.poll() is not None for p in children): raise RuntimeError('A required child server stopped; review the terminal output')
        try:
            r=httpx.get(url,headers=headers,timeout=2,trust_env=False)
            if check(r): return r
        except (httpx.HTTPError,ValueError,KeyError): pass
        time.sleep(1)
    raise RuntimeError('Service not ready: '+url)

def smoke(api_key):
    import httpx
    with httpx.Client(base_url='http://127.0.0.1:8006',headers={'X-API-Key':api_key},timeout=30,trust_env=False) as c:
        info=c.get('/api/v1/model/info'); info.raise_for_status(); info=info.json()
        row={k:int(v['min']) for k,v in info['training_ranges'].items()}; row.update({k:v[0] for k,v in info['categories'].items()})
        single=c.post('/api/v1/predict',json=row); single.raise_for_status()
        batch=c.post('/api/v1/predict/batch',json={'properties':[row,row]}); batch.raise_for_status()
        if batch.json()['count']!=2 or single.json()['model_version']!=info['model_version']: raise RuntimeError('Live prediction check failed')
        if c.post('/api/v1/predict',json=row,headers={'X-API-Key':''}).status_code!=401: raise RuntimeError('Authentication check failed')
        for _ in range(20):
            report=c.get('/monitoring/drift'); report.raise_for_status()
            if report.json()['live']['samples']>=3 and report.json()['demo']['ready']: break
            time.sleep(.25)
        else: raise RuntimeError('Monitoring samples missing')
    print('Live single/batch/authentication and monitoring checks passed',flush=True)

def demo_load():
    """Optional clearly user-triggered test traffic; uses valid training scenarios, not real customers."""
    import httpx, pandas as pd
    frame=pd.read_csv(ROOT/'data/processed/train.csv')
    cols=['Area','Bedrooms','Bathrooms','Age','Location','Property_Type']
    rows=frame[cols].sample(n=40,random_state=13,replace=len(frame)<40).to_dict('records')
    with httpx.Client(base_url='http://127.0.0.1:8006',headers={'X-API-Key':key()},timeout=30,trust_env=False) as c:
        for i in range(0,40,5):
            r=c.post('/api/v1/predict/batch',json={'properties':rows[i:i+5]}); r.raise_for_status()
    print('40 test properties sent via actual API. Observed traffic includes these user-triggered test requests; not customer traffic.',flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',nargs='?',default='run',choices=['run','test','serve','load','stop'])
    p.add_argument('--setup',action='store_true'); a=p.parse_args()
    if a.setup: run([sys.executable,'-m','pip','install','-r','requirements-phase7.txt'])
    if a.action=='test': return test()
    if a.action=='serve': return serve()
    if a.action=='load': return demo_load()
    docker=shutil.which('docker'); npm=shutil.which('npm')
    if not docker: raise RuntimeError('Install/start Docker Desktop for Mac first')
    env={**os.environ,'TASK6_GRAFANA_PASSWORD':secrets.token_urlsafe(32)}
    compose=[docker,'compose','-p','task6phase7','-f',str(STACK)]
    if a.action=='stop': return run(compose+['down'],env=env)
    run([docker,'info'],stdout=subprocess.DEVNULL); run([docker,'compose','version'])
    if not npm: raise RuntimeError('Node.js/npm required for the existing React dashboard')
    busy=[port for port in (8006,5176,9090,3000) if occupied(port)]
    if busy: raise RuntimeError(f'Ports in use: {busy}. Stop the previous Task 6 servers/stack, then retry. No processes killed.')
    test()
    if not (ROOT/'frontend/phase6/node_modules/vite').exists(): run([npm,'--prefix',str(ROOT/'frontend/phase6'),'install','--no-audit','--no-fund'])
    # Phase 6 launcher builds its own UI and validates/reuses the monitored Phase 5 instance.
    children=[]; stack_started=False
    api_key=key(); child_env={**os.environ,'TASK6_API_KEY':api_key}
    try:
        children.append(subprocess.Popen([sys.executable,__file__,'serve'],cwd=ROOT,env=child_env))
        wait_for('http://127.0.0.1:8006/metrics',children)
        smoke(api_key)
        children.append(subprocess.Popen([sys.executable,'scripts/run_phase6.py'],cwd=ROOT,env=child_env))
        wait_for('http://127.0.0.1:5176/',children,seconds=240)
        stack_started=True; run(compose+['up','-d'],env=env)
        wait_for('http://127.0.0.1:9090/-/ready',children)
        wait_for('http://127.0.0.1:3000/api/health',children)
        wait_for('http://127.0.0.1:9090/api/v1/query?query=up%7Bjob%3D%22task6-api%22%7D',children,check=lambda r:r.status_code==200 and any(x['value'][1]=='1' for x in r.json()['data']['result']),seconds=60)
        wait_for('http://127.0.0.1:3000/api/dashboards/uid/task6-phase7',children)
        print('\nPHASE 7 READY\nReact: http://127.0.0.1:5176\nMetrics: http://127.0.0.1:8006/metrics\nPrometheus: http://127.0.0.1:9090\nGrafana: http://127.0.0.1:3000/d/task6-phase7\nDrift: http://127.0.0.1:8006/monitoring/drift\nAlerts: http://127.0.0.1:9090/alerts\nKeep terminal running; Ctrl+C shuts down owned services.',flush=True)
        while all(c.poll() is None for c in children): time.sleep(1)
        raise RuntimeError('A child server exited')
    finally:
        for c in reversed(children):
            if c.poll() is None: c.terminate()
            try: c.wait(timeout=10)
            except subprocess.TimeoutExpired: c.kill(); c.wait()
        if stack_started: subprocess.run(compose+['down'],cwd=ROOT,env=env,check=False)

if __name__=='__main__':
    try: main()
    except KeyboardInterrupt: pass
    except Exception as e: print('Phase 7 stopped:',e,file=sys.stderr); sys.exit(1)
