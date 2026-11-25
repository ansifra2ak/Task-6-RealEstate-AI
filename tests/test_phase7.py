from pathlib import Path
import sys
import json
import numpy as np
import pytest
from fastapi import FastAPI,Request,HTTPException
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from backend.phase7_monitoring import Monitor,psi,monitor_app,RAW,FEATURES,WINDOW,MIN_SAMPLE

def row(i=1): return {'Area':1000+i*10,'Bedrooms':2,'Bathrooms':1,'Age':i%20,'Location':'Rural','Property_Type':'House'}

def ref():
    rows=[row(i) for i in range(100)]
    return {**{k:[r[k] for r in rows] for k in RAW},'predicted_price':[i*100. for i in range(100)]}

@pytest.fixture
def mon(): return Monitor(ref(),'1')

@pytest.fixture
def api(mon):
    app=FastAPI()
    def check(request):
        if request.headers.get('X-API-Key')!='test-only': raise HTTPException(401)
    @app.post('/api/v1/predict')
    async def single(request:Request):
        check(request); r=await request.json()
        if r.get('Area',0)<1: raise HTTPException(422)
        return {'predicted_price':1234.5}
    @app.post('/api/v1/predict/batch')
    async def batch(request:Request):
        check(request); r=await request.json()
        return {'predictions':[{'predicted_price':1234.5} for _ in r['properties']]}
    return TestClient(monitor_app(app,mon))

def test_psi_identical(): assert psi(list(range(100)),list(range(100)),True)==pytest.approx(0)
def test_psi_shift(): assert psi(list(range(100)),[99]*100,True)>.25
def test_psi_category_unseen(): assert psi(['a']*100,['b']*100,False)>.25
def test_psi_constant_finite(): assert np.isfinite(psi([1]*100,[1]*30,True))
def test_initial(mon): assert mon.snapshot()['live']['psi']['Area'] is None
@pytest.mark.parametrize('n',[1,29,30,200,250])
def test_window(mon,n):
    mon.record([row()]*n,[100.]*n)
    s=mon.snapshot()['live']; assert s['samples']==min(n,WINDOW); assert s['ready']==(n>=MIN_SAMPLE)
def test_demo_isolation(mon):
    mon.record([row()]*60,[100.]*60,'demo'); s=mon.snapshot(); assert s['demo']['ready'] and s['live']['samples']==0
    assert mon.properties._value.get()==0
@pytest.mark.parametrize('bad',[{'Area':float('nan')},{'Age':True},{'Location':1}])
def test_invalid_sample(mon,bad):
    with pytest.raises(ValueError): mon.record([{**row(),**bad}],[12])
def test_invalid_price(mon):
    with pytest.raises(ValueError): mon.record([row()],[float('inf')])
def test_single(api,mon):
    assert api.post('/api/v1/predict',json=row(),headers={'X-API-Key':'test-only'}).status_code==200
    assert mon.snapshot()['live']['samples']==1
    assert 'task6_api_requests_total{route="single",status="200"} 1.0' in api.get('/metrics').text

def test_batch(api,mon):
    assert api.post('/api/v1/predict/batch',json={'properties':[row(),row()]},headers={'X-API-Key':'test-only'}).status_code==200
    assert mon.snapshot()['live']['samples']==2
    assert mon.properties._value.get()==2

def test_unauthorized(api,mon):
    assert api.post('/api/v1/predict',json=row()).status_code==401
    assert mon.snapshot()['live']['samples']==0
    assert 'task6_api_requests_total{route="single",status="401"} 1.0' in api.get('/metrics').text

def test_validation(api,mon):
    assert api.post('/api/v1/predict',json={**row(),'Area':0},headers={'X-API-Key':'test-only'}).status_code==422
    assert mon.snapshot()['live']['samples']==0

def test_scrape_not_counted(api,mon):
    a=api.get('/metrics').text; b=api.get('/metrics').text
    assert a==b and 'task6_drift_ready{mode="live"} 0.0' in a

def test_no_raw_payload_or_secret(api):
    api.post('/api/v1/predict',json={**row(),'Location':'private-value'},headers={'X-API-Key':'test-only'})
    text=api.get('/metrics').text+api.get('/monitoring/drift').text
    assert 'private-value' not in text and 'test-only' not in text

def test_alert_configuration():
    import yaml
    conf=yaml.safe_load((ROOT/'monitoring/phase7/alerts.yml').read_text())
    rules=conf['groups'][0]['rules']; assert len(rules)==5
    assert any('mode="demo"' in x['expr'] and x['labels']['severity']=='demo' for x in rules)
    assert any('mode="live"' in x['expr'] for x in rules)

def test_grafana_configuration():
    import yaml
    d=json.loads((ROOT/'monitoring/phase7/grafana/dashboards/task6.json').read_text())
    ds=yaml.safe_load((ROOT/'monitoring/phase7/grafana/provisioning/datasources/phase7.yml').read_text())
    assert all(p['datasource']['uid']==ds['datasources'][0]['uid'] for p in d['panels'])
    assert len({p['id'] for p in d['panels']})==len(d['panels'])
    assert any('DEMO' in p['title'] for p in d['panels'])


def test_original_phase5_contract(mon):
    """Real Phase 5 router/service with a deterministic stand-in, not the registered MLflow model."""
    import pandas as pd
    from backend.phase5_app import create_app
    from backend.services.phase5 import PredictionService
    class Predictor:
        def predict(self, frame): return frame['Area'].to_numpy()*100.
    service=PredictionService(Predictor(),pd.DataFrame([{**row(i),'Price':i*1000.} for i in range(100)]),'1','Fixture','fixture-hash')
    key='local-test-fixture-key-12345678'
    with TestClient(monitor_app(create_app(service,key,ROOT),mon)) as c:
        result=c.post('/api/v1/predict',json=row(10),headers={'X-API-Key':key})
        assert result.status_code==200 and result.json()['predicted_price']==110000
        result=c.post('/api/v1/predict/batch',json={'properties':[row(1),row(2)]},headers={'X-API-Key':key})
        assert result.status_code==200 and result.json()['count']==2
        assert c.post('/api/v1/predict',json=row()).status_code==401
        assert c.get('/monitoring/drift').json()['live']['samples']==3
        assert key not in c.get('/metrics').text
