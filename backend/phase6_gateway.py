"""Loopback-only dashboard gateway. Never sends the Phase 5 key to browsers."""
import csv
import json
import math
from pathlib import Path
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

ROUTES = {'health': ('GET','/api/v1/health'), 'model': ('GET','/api/v1/model/info'),
          'market': ('GET','/api/v1/analytics/market'), 'predict': ('POST','/api/v1/predict'),
          'batch': ('POST','/api/v1/predict/batch')}
CHARTS = {k: f'phase3_{k}.png' for k in ('model_performance','neural_network_training','prediction_evaluation')}
METRICS = ('r2','mae','rmse','mape_pct')

def read_reports(root):
    root=Path(root)
    summary=json.loads((root/'reports/phase3_model_summary.json').read_text())
    with (root/'reports/phase3_model_comparison.csv').open(newline='') as f:
        rows=[{'model':r['model'],'split':r['split'], **{k:float(r[k]) for k in METRICS}} for r in csv.DictReader(f)]
    if not rows or any(r['split'] not in ('test','validation') or not all(math.isfinite(r[k]) for k in METRICS) for r in rows):
        raise ValueError('Invalid Phase 3 metrics')
    return {'summary':{k:summary[k] for k in ('selected_model','selection','training_rows','validation_rows','test_rows','source_sha256','model_sha256','units')},'rows':rows}

def create_gateway(root, key, port=5176, transport=None):
    root=Path(root)
    if not key: raise ValueError('API key missing')
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    allowed_hosts={f'127.0.0.1:{port}',f'localhost:{port}'}
    allowed_origins={f'http://{h}' for h in allowed_hosts}
    @app.middleware('http')
    async def guard(request:Request, call_next):
        if request.headers.get('host') not in allowed_hosts:
            return JSONResponse({'detail':'Invalid local host'},403)
        if request.headers.get('origin') and request.headers['origin'] not in allowed_origins:
            return JSONResponse({'detail':'Cross-origin access denied'},403)
        if request.url.path.startswith('/dashboard-api/') and request.headers.get('X-Dashboard-Request')!='1':
            return JSONResponse({'detail':'Dashboard request header required'},403)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'"
        return response
    @app.get('/dashboard-api/reports')
    def reports():
        try: return read_reports(root)
        except (OSError,ValueError,KeyError): raise HTTPException(503,'Phase 3 reports unavailable or invalid') from None
    @app.get('/charts/{name}')
    def charts(name:str):
        path=root/'visualizations'/CHARTS.get(name,'__missing__')
        if name not in CHARTS or not path.is_file(): raise HTTPException(404,'Chart unavailable')
        return FileResponse(path,media_type='image/png')
    @app.api_route('/dashboard-api/{name}',methods=['GET','POST'])
    async def proxy(name:str, request:Request):
        if name not in ROUTES: raise HTTPException(404,'Unknown dashboard endpoint')
        method,path=ROUTES[name]
        if request.method!=method: raise HTTPException(405,'Method not allowed')
        body=None
        if method=='POST':
            chunks=[]; size=0
            async for chunk in request.stream():
                size+=len(chunk)
                if size>256_000: raise HTTPException(413,'Request too large')
                chunks.append(chunk)
            try: body=json.loads(b''.join(chunks))
            except (ValueError,UnicodeError): raise HTTPException(400,'Invalid JSON') from None
        try:
            async with httpx.AsyncClient(base_url='http://127.0.0.1:8006',timeout=30,trust_env=False,transport=transport) as client:
                res=await client.request(method,path,json=body,headers={'X-API-Key':key})
            if res.status_code==401: raise HTTPException(503,'Backend key mismatch. Restart Phase 5 with the current key.')
            if res.status_code>=500: raise HTTPException(503,'Prediction backend unavailable')
            payload=res.json()
            return JSONResponse(payload,status_code=res.status_code)
        except (httpx.HTTPError,ValueError): raise HTTPException(503,'Cannot reach Phase 5 API') from None
    dist=root/'frontend/phase6/dist'
    if (dist/'assets').is_dir(): app.mount('/assets',StaticFiles(directory=dist/'assets'),name='assets')
    @app.get('/')
    def index():
        if not (dist/'index.html').exists(): raise HTTPException(503,'Build the React dashboard first')
        return FileResponse(dist/'index.html')
    return app
