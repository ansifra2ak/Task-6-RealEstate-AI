"""Phase 5 API contracts and local-model parity; registry smoke is in launcher."""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from backend.phase5_app import create_app
from backend.services.phase5 import PredictionService, ROOT, RAW, training_data, sha, load_service

KEY='unit-test-key-not-a-real-secret-12345'
ROW={'Area':2500,'Bedrooms':3,'Bathrooms':2,'Age':15,'Location':'Suburb','Property_Type':'House'}
HEAD={'X-API-Key':KEY}

class Fake:
    def predict(self, frame):
        return frame.Area.to_numpy()*9000

@pytest.fixture
def service():
    rows=[dict(ROW,Area=1000+i*500,Price=1000000+i*100000) for i in range(7)]
    return PredictionService(Fake(),pd.DataFrame(rows),'1','Fixture','fixture-hash')

@pytest.fixture
def client(service):
    with TestClient(create_app(service,KEY)) as c: yield c


def test_health(client):
    assert client.get('/api/v1/health').json()['model_ready'] is True


def test_openapi(client):
    doc=client.get('/openapi.json').json()
    assert doc['components']['securitySchemes']['APIKeyHeader']['name']=='X-API-Key'
    assert '/api/v1/predict/batch' in doc['paths']
    assert doc['paths']['/api/v1/predict']['post']['security']

@pytest.mark.parametrize('path',['/api/v1/model/info','/api/v1/analytics/market','/api/v1/datasets'])
def test_protected_get(client,path):
    assert client.get(path).status_code==401
    assert client.get(path,headers={'X-API-Key':'bad'}).status_code==401

@pytest.mark.parametrize('path,body',[('/api/v1/predict',ROW),('/api/v1/predict/batch',{'properties':[ROW]})])
def test_protected_post(client,path,body):
    assert client.post(path,json=body).status_code==401
    assert client.post(path,json=body,headers={'X-API-Key':'bad'}).status_code==401


def test_single(client):
    r=client.post('/api/v1/predict',json=ROW,headers=HEAD)
    assert r.status_code==200,r.text
    assert r.json()['predicted_price']==22500000
    assert r.json()['model_version']=='1'
    assert r.json()['units']=='unspecified source units'


def test_batch_order(client):
    r=client.post('/api/v1/predict/batch',json={'properties':[ROW,dict(ROW,Area=3000)]},headers=HEAD)
    assert r.status_code==200,r.text
    assert [v['predicted_price'] for v in r.json()['predictions']]==[22500000,27000000]

@pytest.mark.parametrize('patch',[{'Area':-1},{'Area':9999},{'Age':-1},{'Bedrooms':2.5},{'Bedrooms':True},{'Location':'Unknown'},{'Property_Type':' '},{'Price':99},{'Area':'2500'},{'Bathrooms':0}])
def test_invalid(client,patch):
    assert client.post('/api/v1/predict',json=ROW|patch,headers=HEAD).status_code==422

@pytest.mark.parametrize('rows',[[],[ROW]*101,[ROW,ROW|{'Location':'Unknown'}]])
def test_invalid_batch(client,rows):
    assert client.post('/api/v1/predict/batch',json={'properties':rows},headers=HEAD).status_code==422


def test_market(client):
    r=client.get('/api/v1/analytics/market',headers=HEAD).json()
    assert r['sample_size']==7 and r['by_location'][0]['count']==7
    assert r['median_price']==1300000 and 'training' in r['scope']
    assert 'Property_ID' not in json.dumps(r)


def test_info(client):
    r=client.get('/api/v1/model/info',headers=HEAD).json()
    assert r['raw_features']==RAW and r['model_version']=='1'


def test_unavailable_model(client,service):
    service.predictor.predict=lambda _: np.array([np.nan])
    r=client.post('/api/v1/predict',json=ROW,headers=HEAD)
    assert r.status_code==503 and r.json()['detail']=='Prediction unavailable'


def test_missing_registry(tmp_path):
    with pytest.raises(FileNotFoundError,match='Phase 4 registry missing'):
        load_service(tmp_path)


def test_local_saved_model_parity():
    model=ROOT/'models/phase3_best_model.joblib'
    if not model.exists(): pytest.skip('Local private model not included in public checkout')
    import joblib
    frame,source=training_data(ROOT)
    meta=json.loads((ROOT/'models/phase3_metadata.json').read_text())
    assert sha(model)==meta['model_sha256'] and source==meta['source_sha256']
    sys.path.insert(0,str(ROOT/'ml-pipeline/registry'))
    from phase4_inference import predict_bundle
    bundle=joblib.load(model)
    class Local:
        def predict(self,x): return predict_bundle(bundle,x)
    service=PredictionService(Local(),frame,'local-test',meta['selected_model'],source)
    raw=frame[RAW].head(2)
    with TestClient(create_app(service,KEY)) as c:
        result=c.post('/api/v1/predict/batch',json={'properties':raw.to_dict('records')},headers=HEAD)
    assert result.status_code==200,result.text
    np.testing.assert_allclose([r['predicted_price'] for r in result.json()['predictions']],Local().predict(raw),rtol=0,atol=.0051)
