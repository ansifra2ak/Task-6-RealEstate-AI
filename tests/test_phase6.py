import asyncio
import json
import httpx
from backend.phase6_gateway import create_gateway,read_reports
KEY='local-test-key-never-in-response'
HEAD={'X-Dashboard-Request':'1'}

def request(root,method,path,headers=HEAD,body=None,upstream=None):
    def handle(req):
        assert req.headers['X-API-Key']==KEY
        assert req.url.host=='127.0.0.1'
        if upstream: return upstream(req)
        return httpx.Response(200,json={'path':req.url.path,'body':json.loads(req.content) if req.content else None})
    app=create_gateway(root,KEY,transport=httpx.MockTransport(handle))
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1:5176') as c:
            return await c.request(method,path,headers=headers,json=body)
    return asyncio.run(run())

def test_proxy_key_not_exposed(tmp_path):
    r=request(tmp_path,'GET','/dashboard-api/model');assert r.status_code==200;assert KEY not in r.text;assert r.json()['path']=='/api/v1/model/info'
def test_single_integer(tmp_path):
    r=request(tmp_path,'POST','/dashboard-api/predict',body={'Area':2500});assert r.json()['body']=={'Area':2500}
def test_batch_forward(tmp_path):
    r=request(tmp_path,'POST','/dashboard-api/batch',body={'properties':[{'Area':2500},{'Area':3500}]});assert r.json()['body']['properties'][1]['Area']==3500
def test_market(tmp_path): assert request(tmp_path,'GET','/dashboard-api/market').json()['path']=='/api/v1/analytics/market'
def test_missing_header(tmp_path): assert request(tmp_path,'GET','/dashboard-api/model',headers={}).status_code==403
def test_origin(tmp_path): assert request(tmp_path,'POST','/dashboard-api/predict',headers={**HEAD,'Origin':'https://example.com'},body={}).status_code==403
def test_host(tmp_path): assert request(tmp_path,'GET','/dashboard-api/model',headers={**HEAD,'Host':'example.com'}).status_code==403
def test_unknown_route(tmp_path): assert request(tmp_path,'GET','/dashboard-api/secret').status_code==404
def test_method(tmp_path): assert request(tmp_path,'GET','/dashboard-api/predict').status_code==405
def test_backend_401(tmp_path):
    r=request(tmp_path,'GET','/dashboard-api/model',upstream=lambda r:httpx.Response(401,json={'detail':KEY}));assert r.status_code==503;assert KEY not in r.text
def test_backend_422(tmp_path): assert request(tmp_path,'POST','/dashboard-api/predict',body={},upstream=lambda r:httpx.Response(422,json={'detail':'bad input'})).status_code==422
def test_size_limit(tmp_path): assert request(tmp_path,'POST','/dashboard-api/batch',body={'x':'x'*260000}).status_code==413
def test_missing_reports(tmp_path): assert request(tmp_path,'GET','/dashboard-api/reports').status_code==503
def test_no_arbitrary_file(tmp_path): assert request(tmp_path,'GET','/charts/secret').status_code==404
def test_report_selection(tmp_path):
    p=tmp_path/'reports';p.mkdir();(p/'phase3_model_summary.json').write_text(json.dumps(dict(selected_model='NN',selection='validation',training_rows=210,validation_rows=45,test_rows=45,source_sha256='a',model_sha256='b',units='source units',private='not returned')));(p/'phase3_model_comparison.csv').write_text('model,split,r2,mae,rmse,mape_pct\nNN,test,0.99,1,2,3\n');r=request(tmp_path,'GET','/dashboard-api/reports');assert r.status_code==200;assert r.json()['rows'][0]['r2']==.99;assert 'private' not in r.json()['summary']
