"""No private model or data needed for the Phase 9 source/security checks."""
import base64
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import pytest
import yaml
from fastapi.testclient import TestClient
from backend.phase9_runtime import PublicGuard, tree_hash,verify_bundle,read_secret
from backend.phase6_gateway import create_gateway
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('phase9_launcher',ROOT/'scripts/run_phase9.py'); launcher=importlib.util.module_from_spec(spec); spec.loader.exec_module(launcher)
PASSWORD='unit-test-viewer-password-123456789'
KEY='unit-test-api-key-1234567890123456'
AUTH={'Authorization':'Basic '+base64.b64encode(('viewer:'+PASSWORD).encode()).decode()}
ORIGIN='https://example.test'

@pytest.fixture
def public(tmp_path):
    p=tmp_path/'frontend/phase6/dist'; p.mkdir(parents=True); (p/'index.html').write_text('<html>Dashboard</html>')
    return TestClient(PublicGuard(create_gateway(tmp_path,KEY),ORIGIN,PASSWORD),base_url=ORIGIN)

def test_auth_required(public):
    r=public.get('/'); assert r.status_code==401 and 'Basic' in r.headers['www-authenticate'] and PASSWORD not in r.text

def test_valid_auth(public):
    r=public.get('/',headers=AUTH); assert r.status_code==200 and 'Dashboard' in r.text and KEY not in r.text

def test_bad_auth(public): assert public.get('/',headers={'Authorization':'Basic !'}).status_code==401

def test_bad_host(public): assert public.get('/',headers={**AUTH,'Host':'evil.test'}).status_code==403

def test_bad_origin(public): assert public.get('/',headers={**AUTH,'Origin':'https://evil.test'}).status_code==403

def test_valid_origin(public): assert public.get('/',headers={**AUTH,'Origin':ORIGIN}).status_code==200

def test_dashboard_guard_preserved(public): assert public.get('/dashboard-api/model',headers=AUTH).status_code==403

@pytest.mark.parametrize('origin',['http://example.test','https://example.test/path','https://u:p@example.test','https://example.test:8006'])
def test_public_origin_validation(origin,tmp_path):
    with pytest.raises(ValueError): PublicGuard(create_gateway(tmp_path,KEY),origin,PASSWORD)

@pytest.mark.parametrize('domain,valid',[('demo.example.com',True),('http://demo.example.com',False),('127.0.0.1',False),('bad;command.com',False),('-abc.com',False)])
def test_domain(domain,valid): assert launcher.domain_ok(domain)==valid

def test_secret_creation(tmp_path,monkeypatch):
    path=launcher.secret_files(tmp_path); first=(path/'api_key').read_text(); assert first==(launcher.secret_files(tmp_path)/'api_key').read_text(); assert len(first.strip())>=24
    assert stat.S_IMODE(path.stat().st_mode)==0o700
    monkeypatch.setenv('TASK6_API_KEY_FILE',str(path/'api_key')); assert read_secret('API_KEY')==first.strip()

def test_secret_symlink(tmp_path):
    f=tmp_path/'outside'; f.write_text(KEY); d=tmp_path/launcher.SECRET; d.mkdir(); (d/'api_key').symlink_to(f)
    with pytest.raises(ValueError): launcher.secret_files(tmp_path)

def test_bundle_hash(tmp_path):
    names=('data','reports','visualizations','champion/model')
    for name in names:
        d=tmp_path/name; d.mkdir(parents=True); (d/'example').write_text(name)
    meta={'hashes':{n:tree_hash(tmp_path/n) for n in names}}
    (tmp_path/'champion/deployment.json').write_text(json.dumps(meta)); assert verify_bundle(tmp_path)==meta
    (tmp_path/'data/example').write_text('modified')
    with pytest.raises(ValueError): verify_bundle(tmp_path)

def test_tree_rejects_symlink(tmp_path):
    (tmp_path/'file').symlink_to('/etc/passwd')
    with pytest.raises(ValueError): tree_hash(tmp_path)

def test_source_allowlist(tmp_path):
    for name in ('backend/a.py','backend/secret.env','frontend/phase6/src/main.jsx','frontend/phase6/node_modules/leak.js','data/raw/house_prices.csv','reports/secret.json','models/bundle.joblib','screenshots/a.png','.env.phase5','mlartifacts/a.py'):
        p=tmp_path/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text('fixture')
    allowed=launcher.source_files(tmp_path); assert 'backend/a.py' in allowed and 'frontend/phase6/src/main.jsx' in allowed
    for name in ('data/','reports/','models/','screenshots/','mlartifacts/','.env','node_modules','secret.env'): assert not any(name in p for p in allowed)

def test_stage_real_source(tmp_path):
    for name in launcher.source_files(ROOT): launcher.copy_file(ROOT,tmp_path,name)
    launcher.stage(tmp_path); out=tmp_path/launcher.BUILD
    assert (out/'Dockerfile').is_file() and (out/'backend/phase9_runtime.py').is_file()
    assert not any((out/n).exists() for n in ('data','reports','models','.env.phase5','mlruns','screenshots'))
    launcher.stage(tmp_path)

def test_unmanaged_stage_refusal(tmp_path):
    d=tmp_path/'existing'; d.mkdir(); new=tmp_path/'new'; new.mkdir()
    with pytest.raises(ValueError): launcher.install_dir(new,d)

def test_compose():
    base=yaml.safe_load((ROOT/launcher.INFRA/'compose.yml').read_text()); services=base['services']; assert set(services)=={'app','prometheus','grafana'}
    assert all(port.startswith('127.0.0.1:') for s in services.values() for port in s['ports'])
    assert all(v.endswith(':ro') for v in services['app']['volumes'])
    assert 'api_key' in services['app']['secrets'] and 'viewer_password' in services['app']['secrets']
    cloud=yaml.safe_load((ROOT/launcher.INFRA/'cloud.yml').read_text()); assert cloud['services']['caddy']['ports']==['80:80','443:443']
    prom=yaml.safe_load((ROOT/launcher.INFRA/'prometheus.yml').read_text()); assert prom['scrape_configs'][0]['static_configs'][0]['targets']==['app:8006']

def test_kubernetes():
    docs=list(yaml.safe_load_all((ROOT/launcher.INFRA/'kubernetes/app.yaml').read_text())); deploy=next(x for x in docs if x['kind']=='Deployment'); svc=next(x for x in docs if x['kind']=='Service'); pod=deploy['spec']['template']['spec']
    assert svc['spec']['type']=='ClusterIP' and pod['securityContext']['runAsNonRoot'] and pod['automountServiceAccountToken'] is False
    assert all(m['readOnly'] for m in pod['containers'][0]['volumeMounts'])

def test_ci_source_only():
    workflow=yaml.safe_load((ROOT/'.github/workflows/phase9.yml').read_text()); assert set(workflow['jobs'])=={'test-build','publish'}
    assert workflow['jobs']['publish']['permissions']['packages']=='write' and 'workflow_dispatch' in workflow['jobs']['publish']['if']
