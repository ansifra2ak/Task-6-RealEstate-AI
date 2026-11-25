"""Single local launcher: install optionally, run tests, load champion, serve API."""
import argparse
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['MLFLOW_ENABLE_TELEMETRY']='false'


def get_key():
    override=os.environ.get('TASK6_API_KEY')
    if override:
        if len(override)<24: raise ValueError('TASK6_API_KEY must contain at least 24 characters')
        return override
    path=ROOT/'.env.phase5'
    if not path.exists():
        try:
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,'w',encoding='utf-8') as f:
                f.write('TASK6_API_KEY='+secrets.token_urlsafe(32)+'\n')
        except FileExistsError:
            pass
    path.chmod(0o600)
    line=path.read_text(encoding='utf-8').strip()
    if not line.startswith('TASK6_API_KEY=') or len(line.split('=',1)[1])<24:
        raise ValueError('Invalid local .env.phase5 key file')
    return line.split('=',1)[1]


def run_tests():
    p=subprocess.run([sys.executable,'-m','pytest','-q','tests/test_phase5.py'],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (ROOT/'reports').mkdir(exist_ok=True)
    (ROOT/'reports/phase5_test_results.txt').write_text(p.stdout,encoding='utf-8')
    print(p.stdout,flush=True)
    if p.returncode: raise SystemExit(p.returncode)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',nargs='?',default='run',choices=['run','test','serve'])
    parser.add_argument('--setup',action='store_true',help='Install Phase 5 requirements first')
    args=parser.parse_args()
    if args.setup:
        subprocess.run([sys.executable,'-m','pip','install','-r',str(ROOT/'requirements-phase5.txt')],cwd=ROOT,check=True)
    if args.action in ('run','test'): run_tests()
    if args.action=='test': return
    from backend.services.phase5 import load_service
    from backend.phase5_app import create_app
    from fastapi.testclient import TestClient
    import uvicorn
    print('PHASE 5 — loading the local MLflow champion',flush=True)
    service=load_service(ROOT)
    key=get_key()
    app=create_app(service,key,ROOT)
    # Real registered-model HTTP smoke test. No private input or key is printed.
    with TestClient(app) as client:
        row=service.frame[service.info()['raw_features']].iloc[0].to_dict()
        response=client.post('/api/v1/predict',json=row,headers={'X-API-Key':key})
        if response.status_code!=200 or response.json()['model_version']!=service.version:
            raise RuntimeError(f'Registry-backed API smoke test failed (HTTP {response.status_code})')
        if client.post('/api/v1/predict',json=row).status_code!=401:
            raise RuntimeError('API authentication smoke test failed')
        batch=client.post('/api/v1/predict/batch',json={'properties':[row,row]},headers={'X-API-Key':key})
        if batch.status_code!=200 or batch.json()['count']!=2:
            raise RuntimeError('Batch API smoke test failed')
    print(f'Champion version {service.version} ({service.selected_model}) — real registry API smoke tests passed',flush=True)
    print('PHASE 5 READY — http://127.0.0.1:8006/docs',flush=True)
    print('Swagger API key: use TASK6_API_KEY from .env.phase5 (or your environment override). Do not screenshot the key.',flush=True)
    uvicorn.run(app,host='127.0.0.1',port=8006,log_level='info')

if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        print(f'Phase 5 stopped: {exc}',file=sys.stderr)
        sys.exit(1)
