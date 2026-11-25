"""Phase 9: safe source staging, private champion export, Compose and cloud handoff."""
import argparse
import base64
import importlib.metadata
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import urllib.error

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
BUILD='.phase9-build'; PRIVATE='.phase9-private'; SECRET='.phase9-secrets'; MARKER='.task6-phase9-generated'
INFRA='infrastructure/phase9'
CORE=('mlflow','cloudpickle','numpy','pandas','scikit-learn','joblib','xgboost','scipy','fastapi','pydantic','uvicorn','httpx','prometheus-client')
RUNTIME_FILES=('data/manifest.json','data/raw/house_prices.csv','data/processed/train.csv','data/processed/split_manifest.json','reports/phase3_model_summary.json','reports/phase3_model_comparison.csv','visualizations/phase3_model_performance.png','visualizations/phase3_neural_network_training.png','visualizations/phase3_prediction_evaluation.png')
# Explicit source allowlist; no generic git add . or unrestricted Docker context.
REQUIREMENTS=('requirements.txt','requirements-phase2.txt','requirements-phase3.txt','requirements-phase4.txt','requirements-phase5.txt','requirements-phase7.txt')

def run(args,root=ROOT,**kwargs): return subprocess.run(args,cwd=root,check=True,**kwargs)

def copy_file(root, dest, name):
    src=root/name
    if not src.is_file() or src.is_symlink(): raise FileNotFoundError('Required regular file missing: '+name)
    out=dest/name; out.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(src,out); out.chmod(0o644)

def files_with(root,folder,extensions):
    return sorted(p.relative_to(root).as_posix() for p in (root/folder).rglob('*') if p.is_file() and not p.is_symlink() and p.suffix in extensions and not any(x in ('node_modules','dist','__pycache__','.venv','.git') for x in p.relative_to(root).parts))

def source_files(root):
    root=Path(root)
    fixed=list(REQUIREMENTS)+[INFRA+'/Dockerfile','frontend/phase6/index.html','frontend/phase6/package.json']
    if (root/'frontend/phase6/package-lock.json').is_file(): fixed.append('frontend/phase6/package-lock.json')
    return sorted(set(fixed+files_with(root,'backend',{'.py'})+files_with(root,'ml-pipeline/registry',{'.py'})+files_with(root,'frontend/phase6/src',{'.jsx','.js','.mjs','.css','.svg'})))

def install_dir(tmp,dest):
    if dest.exists():
        if dest.is_symlink() or not (dest/MARKER).is_file(): raise ValueError('Refusing to replace unmanaged directory: '+str(dest))
        shutil.rmtree(dest)
    tmp.rename(dest)

def stage(root=ROOT, lock=False):
    root=Path(root)
    with tempfile.TemporaryDirectory(dir=root) as td:
        dest=Path(td)/'build'; dest.mkdir()
        for name in source_files(root): copy_file(root,dest,name)
        shutil.move(dest/INFRA/'Dockerfile',dest/'Dockerfile')
        shutil.rmtree(dest/'infrastructure')
        # Preserve the original code; require corrected strict integer Area rather than silently changing it.
        schema=(dest/'backend/schemas/phase5.py').read_text()
        if not re.search(r'Area\s*:\s*Annotated\[int\s*,',schema): raise ValueError('Phase 5 Area fix missing: Area: Annotated[int, Field(gt=0)]')
        versions=[f'{p}=={importlib.metadata.version(p)}' for p in CORE] if lock else []
        (dest/'constraints.txt').write_text('\n'.join(versions)+'\n')
        (dest/MARKER).touch(); install_dir(dest,root/BUILD)
    print('Source-only Docker build context prepared.',flush=True)


def prepare(root=ROOT, refresh=False):
    from backend.phase9_runtime import tree_hash, verify_bundle
    from backend.services.phase5 import load_service,RAW
    import numpy as np
    root=Path(root); final=root/PRIVATE
    if final.exists() and (final.is_symlink() or not (final/MARKER).is_file()): raise ValueError('Unmanaged private directory')
    if final.exists() and not refresh:
        verify_bundle(final); print('Using existing verified private champion snapshot; use prepare --refresh to export the current alias.',flush=True); return
    os.environ['MLFLOW_ENABLE_TELEMETRY']='false'
    service=load_service(root)
    import mlflow
    with tempfile.TemporaryDirectory(dir=root) as td:
        dest=Path(td)/'private'; dest.mkdir(mode=0o700)
        for name in RUNTIME_FILES: copy_file(root,dest,name)
        target=dest/'champion'; target.mkdir()
        # MLflow resolves the exact version, not the moving alias. Artifact stays on this machine.
        download_dir = Path(td) / "download"
        download_dir.mkdir()

        downloaded = Path(
            mlflow.artifacts.download_artifacts(
                artifact_uri=f"models:/RealEstatePricePredictor/{service.version}",
                dst_path=str(download_dir)
            )
        ).resolve()

        model_target = (target / "model").resolve()

        if downloaded == model_target or downloaded in model_target.parents:
            raise RuntimeError("Recursive model copy prevented")

        if not (downloaded / "MLmodel").is_file():
            raise RuntimeError("Downloaded MLflow model is incomplete")

        shutil.copytree(downloaded, model_target, symlinks=True)
        raw=service.frame[RAW].head(3)
        values=np.asarray(service.predictor.predict(raw),dtype=float)
        portable=mlflow.pyfunc.load_model(str(target/'model'))
        np.testing.assert_allclose(portable.predict(raw),values,rtol=1e-7,atol=.01)
        meta={'model_version':service.version,'selected_model':service.selected_model,'source_sha256':service.source_sha256,'parity_predictions':values.tolist(),'hashes':{n:tree_hash(dest/n) for n in ('data','reports','visualizations','champion/model')},'note':'Private snapshot of the locally verified MLflow champion; not a live alias lookup.'}
        (target/'deployment.json').write_text(json.dumps(meta,indent=2)+'\n')
        # The host parent is private; the individually mounted subdirectories must be readable by container UID 10001.
        for p in dest.rglob('*'):
            if p.is_symlink(): raise ValueError('Unexpected symlink in portable artifact')
            p.chmod(0o755 if p.is_dir() else 0o644)
        (dest/MARKER).touch(); verify_bundle(dest); install_dir(dest,final); final.chmod(0o700)
    print(f'Private champion version {service.version} exported; local inference parity passed.',flush=True)


def secret_files(root=ROOT):
    root=Path(root); folder=root/SECRET
    if folder.is_symlink(): raise ValueError('Secret directory cannot be a symlink')
    folder.mkdir(mode=0o700,exist_ok=True); folder.chmod(0o700)
    for name in ('api_key','viewer_password','grafana_password'):
        path=folder/name
        if path.is_symlink(): raise ValueError('Secret file cannot be a symlink')
        if not path.exists():
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,'w') as f: f.write(secrets.token_urlsafe(40)+'\n')
        if len(path.read_text().strip())<24: raise ValueError('Invalid secret file')
        # Bind-mounted secrets must be readable by non-root container users. Parent remains 0700 on host.
        path.chmod(0o644)
    return folder


def domain_ok(domain):
    return bool(re.fullmatch(r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?',domain or ''))


def compose(root=ROOT,domain=None):
    root=Path(root).resolve()
    args=['docker','compose','-p','task6phase9','-f',str(root/INFRA/'compose.yml')]
    env={**os.environ,'TASK6_PHASE9_ROOT':str(root),'TASK6_PUBLIC_ORIGIN':''}
    if domain:
        if not domain_ok(domain): raise ValueError('Use a lowercase DNS hostname, not a URL or IP address')
        args+=['-f',str(root/INFRA/'cloud.yml')]; env.update(TASK6_DOMAIN=domain,TASK6_PUBLIC_ORIGIN='https://'+domain)
    return args,env


def http(path,port=8006,body=None,headers=None,expected=200):
    h=dict(headers or {})
    if body is not None: h['Content-Type']='application/json'
    req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=None if body is None else json.dumps(body).encode(),headers=h)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req,timeout=15) as res: code=res.status; data=res.read()
    except urllib.error.HTTPError as e: code=e.code; data=e.read()
    if code!=expected: raise RuntimeError(f'{path}: expected HTTP {expected}, received {code}')
    return data


def smoke(root=ROOT,domain=None):
    folder=Path(root)/SECRET; key=(folder/'api_key').read_text().strip(); h={'X-API-Key':key}
    info=json.loads(http('/api/v1/model/info',headers=h))
    row={k:int(v['min']) for k,v in info['training_ranges'].items()}; row.update({k:v[0] for k,v in info['categories'].items()})
    one=json.loads(http('/api/v1/predict',body=row,headers=h)); batch=json.loads(http('/api/v1/predict/batch',body={'properties':[row,row]},headers=h))
    if batch['count']!=2 or one['model_version']!=info['model_version'] or any(v['predicted_price']!=one['predicted_price'] for v in batch['predictions']): raise RuntimeError('Prediction parity failed')
    http('/api/v1/predict',body=row,expected=401)
    http('/api/v1/predict',body={**row,'Area':1.5},headers=h,expected=422)
    gh={'X-Dashboard-Request':'1'}
    if domain:
        gh['Host']=domain; http('/',5176,headers=gh,expected=401)
        password=(folder/'viewer_password').read_text().strip()
        gh['Authorization']='Basic '+base64.b64encode(('viewer:'+password).encode()).decode()
    http('/',5176,headers=gh)
    result=json.loads(http('/dashboard-api/predict',5176,body=row,headers=gh))
    if result['predicted_price']!=one['predicted_price']: raise RuntimeError('Gateway parity failed')
    for p in ('model','market','reports'): http('/dashboard-api/'+p,5176,headers=gh)
    if b'task6_api_requests_total' not in http('/metrics'): raise RuntimeError('Metrics missing')
    prom=json.loads(http('/api/v1/query?query=up%7Bjob%3D%22task6-api%22%7D',9090))
    if not any(v['value'][1]=='1' for v in prom['data']['result']): raise RuntimeError('Prometheus scrape not yet ready')
    http('/api/dashboards/uid/task6-phase7',3000)
    print('Live champion, single/batch predictions, authentication, dashboard, reports, Prometheus scrape and Grafana verified.',flush=True)


def publish_files(root=ROOT):
    root=Path(root)
    names=set(source_files(root))
    for folder,exts in [('scripts',{'.py','.coveragerc'}),('frontend/src',{'.tsx','.ts','.css','.jsx','.js'}),('tests',{'.py'}),('ml-pipeline',{'.py'}),('docs',{'.md'}),('monitoring/phase7',{'.yml','.json'}),('infrastructure/phase9',{'.yml','.yaml','.tf','.md','.sh'})]: names.update(files_with(root,folder,exts))
    names.update(n for n in ('README.md','LICENSE_PENDING.md','.gitignore','requirements-phase8.txt','main.py','run.py','package.json','pytest.ini','frontend/index.html','frontend/package.json','frontend/package-lock.json','frontend/tsconfig.json','frontend/vite.config.ts',INFRA+'/Caddyfile','.github/workflows/phase9.yml') if (root/n).is_file())
    # Restrict to versioned source extensions and explicit paths; review even these before committing.
    return sorted(names)


def git_stage(root=ROOT):
    root=Path(root).resolve(); top=subprocess.run(['git','rev-parse','--show-toplevel'],cwd=root,text=True,capture_output=True)
    if top.returncode or Path(top.stdout.strip()).resolve()!=root: run(['git','init','-b','main'],root)
    # Existing tracked or staged non-allowlisted content is never silently published or removed.
    allowed=set(publish_files(root)); existing=run(['git','ls-files','-z'],root,stdout=subprocess.PIPE).stdout.decode().split('\0')
    blocked=sorted(set(existing)-allowed-{''})
    if blocked: raise ValueError('Existing tracked paths outside source allowlist; review before publishing: '+', '.join(blocked[:12]))
    exclude=root/'.git/info/exclude'
    if exclude.is_file():
        with exclude.open('a') as f: f.write('\n# Phase 9 private/generated files\n.phase9-*\n.env*\ndata/\nmodels/\nmlruns/\nmlartifacts/\nreports/\nvisualizations/\nnotebooks/\nscreenshots/\n*.tfstate*\n.terraform/\n*.tfvars\n*.tfplan\n')
    run(['git','add','--',*sorted(allowed)],root)
    run(['git','diff','--cached','--stat'],root)
    print('Source paths staged only. Review git diff --cached and repository history for secrets before committing/pushing.',flush=True)


def cloud_package(root=ROOT):
    from backend.phase9_runtime import verify_bundle
    root=Path(root); verify_bundle(root/PRIVATE)
    if not (root/BUILD/MARKER).is_file(): raise ValueError('Run stage/prepare first')
    names=[BUILD,PRIVATE+'/data',PRIVATE+'/reports',PRIVATE+'/visualizations',PRIVATE+'/champion',PRIVATE+'/'+MARKER,INFRA+'/compose.yml',INFRA+'/cloud.yml',INFRA+'/Caddyfile',INFRA+'/prometheus.yml','monitoring/phase7/alerts.yml','monitoring/phase7/grafana/provisioning/dashboards/phase7.yml','monitoring/phase7/grafana/provisioning/datasources/phase7.yml','monitoring/phase7/grafana/dashboards/task6.json','scripts/run_phase9.py','backend/phase9_runtime.py']
    # Transfer only these source/config/runtime paths. No local secrets, Git history, or unrelated datasets.
    target=root/'.phase9-transfer.tar.gz'; fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as raw,tarfile.open(fileobj=raw,mode='w:gz') as tar:
        tar.add(root/PRIVATE,arcname=PRIVATE,recursive=False)
        for name in names: tar.add(root/name,arcname=name)
    print('Private transfer archive created: .phase9-transfer.tar.gz. Transfer by authenticated SSH only; never upload to GitHub.',flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',nargs='?',default='up',choices=['up','prepare','stage','test','status','stop','smoke','git-stage','cloud-package'])
    p.add_argument('--setup',action='store_true'); p.add_argument('--refresh',action='store_true'); p.add_argument('--use-prepared',action='store_true'); p.add_argument('--cloud-domain'); p.add_argument('--allow-private-cloud',action='store_true'); p.add_argument('--lock',action='store_true')
    a=p.parse_args()
    if (a.cloud_domain or a.action=='cloud-package') and not a.allow_private_cloud: raise ValueError('Confirm you have permission to transfer/host the dataset and model using --allow-private-cloud')
    if a.setup: run([sys.executable,'-m','pip','install','-r','requirements-phase7.txt'])
    if a.action=='test': return run([sys.executable,'-m','pytest','-q','tests/test_phase9.py'])
    if a.action=='stage': return stage(lock=a.lock)
    if a.action=='prepare': stage(lock=True); return prepare(refresh=a.refresh)
    if a.action=='git-stage': return git_stage()
    if a.action=='cloud-package': return cloud_package()
    if a.action=='smoke': return smoke(domain=a.cloud_domain)
    args,env=compose(domain=a.cloud_domain)
    if a.action=='stop': return run(args+['down','--remove-orphans'],env=env)
    if a.action=='status': return run(args+['ps'],env=env)
    run(['docker','info'],stdout=subprocess.DEVNULL)
    if not a.use_prepared:
        run([sys.executable,'-m','pytest','-q','tests/test_phase9.py'])
        stage(lock=True); prepare(refresh=a.refresh)
    else:
        from backend.phase9_runtime import verify_bundle
        verify_bundle(ROOT/PRIVATE)
        if not (ROOT/BUILD/MARKER).is_file(): raise ValueError('Source build context missing')
    secret_files(); run(args+['config','--quiet'],env=env); run(args+['up','-d','--build','--wait','--wait-timeout','240'],env=env)
    for i in range(60):
        try: smoke(domain=a.cloud_domain); break
        except (RuntimeError,OSError,ValueError):
            if i==59: raise
            time.sleep(3)
    run(args+['ps'],env=env)
    print('PHASE 9 READY — '+('https://'+a.cloud_domain if a.cloud_domain else 'http://127.0.0.1:5176'),flush=True)
    print('Containers continue running. Stop with run_phase9.py stop. Monitoring: localhost:9090 / localhost:3000.',flush=True)

if __name__=='__main__':
    try: main()
    except KeyboardInterrupt: sys.exit(130)
    except Exception as e: print('Phase 9 stopped:',e,file=sys.stderr); sys.exit(1)
