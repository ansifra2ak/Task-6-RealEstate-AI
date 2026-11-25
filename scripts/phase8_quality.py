"""Local HTTP integration checks, benchmark aggregation and evidence reports."""
import html
import json
import math
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import httpx

API='http://127.0.0.1:8006'
UI='http://127.0.0.1:5176'

def require(condition, message):
    if not condition: raise RuntimeError(message)

def get_row(info):
    return {**{k:int(v['min']) for k,v in info['training_ranges'].items()}, **{k:v[0] for k,v in info['categories'].items()}}

def prediction_ok(p, version):
    return isinstance(p,dict) and p.get('model_version')==version and isinstance(p.get('predicted_price'),(int,float)) and math.isfinite(p['predicted_price']) and p['predicted_price']>=0

def integration(key, dashboard=False, monitoring=False):
    results=[]
    def check(label, condition):
        results.append({'check':label,'passed':bool(condition)})
    with httpx.Client(base_url=API,timeout=30,trust_env=False) as c:
        h={'X-API-Key':key}
        r=c.get('/api/v1/health'); check('API health and version',r.status_code==200 and r.json().get('version')=='0.5.0')
        r=c.get('/api/v1/model/info',headers=h); require(r.status_code==200,'Model info unavailable or API key mismatch'); info=r.json()
        check('Champion model loaded',info.get('loaded_from_alias')=='champion'); row=get_row(info); version=info['model_version']
        r=c.post('/api/v1/predict',json=row,headers=h); one=r.json(); check('Authorized single prediction',r.status_code==200 and prediction_ok(one,version))
        r=c.post('/api/v1/predict/batch',json={'properties':[row,row]},headers=h); b=r.json(); preds=b.get('predictions',[]); check('Batch count and parity',r.status_code==200 and b.get('count')==2 and len(preds)==2 and all(prediction_ok(p,version) and p['predicted_price']==one.get('predicted_price') for p in preds))
        for path in ('/api/v1/model/info','/api/v1/analytics/market','/api/v1/datasets'):
            check('Missing key rejected: '+path,c.get(path).status_code==401)
        for path,body in (('/api/v1/predict',row),('/api/v1/predict/batch',{'properties':[row]})):
            check('Missing key rejected: '+path,c.post(path,json=body).status_code==401)
            check('Wrong key rejected: '+path,c.post(path,json=body,headers={'X-API-Key':'invalid-test-key'}).status_code==401)
        for patch in ({'Area':-1},{'Area':row['Area']+0.5},{'Bedrooms':True},{'Location':'__invalid__'},{'Price':1}):
            check('Invalid input rejected: '+next(iter(patch)),c.post('/api/v1/predict',json=row|patch,headers=h).status_code==422)
        for count in (0,101): check(f'Invalid batch size {count}',c.post('/api/v1/predict/batch',json={'properties':[row]*count},headers=h).status_code==422)
        r=c.get('/api/v1/analytics/market',headers=h); check('Market analytics uses training sample',r.status_code==200 and r.json().get('sample_size')==info['training_rows'])
        if monitoring:
            r=c.get('/metrics'); check('Prometheus metrics exposed',r.status_code==200 and 'task6_api_requests_total' in r.text)
            r=c.get('/monitoring/drift'); check('Drift status available',r.status_code==200 and 'live' in r.json() and 'demo' in r.json())
    if dashboard:
        with httpx.Client(base_url=UI,timeout=30,trust_env=False) as c:
            h={'X-Dashboard-Request':'1'}
            check('React page served',c.get('/').status_code==200)
            check('Gateway rejects missing guard',c.get('/dashboard-api/model').status_code==403)
            check('Gateway rejects foreign origin',c.get('/dashboard-api/model',headers=h|{'Origin':'https://invalid.example'}).status_code==403)
            r=c.post('/dashboard-api/predict',json=row,headers=h); check('Gateway single prediction',r.status_code==200 and prediction_ok(r.json(),version))
            r=c.post('/dashboard-api/batch',json={'properties':[row,row]},headers=h); check('Gateway batch prediction',r.status_code==200 and r.json().get('count')==2)
            for path in ('model','market','reports'): check('Gateway '+path,c.get('/dashboard-api/'+path,headers=h).status_code==200)
    return results,info,row

def percentile(values,p):
    if not values: return None
    v=sorted(values); i=(len(v)-1)*p; lo=int(i); return v[lo]+(v[min(lo+1,len(v)-1)]-v[lo])*(i-lo)

def summarize(samples, elapsed, batch_size, workers):
    ok=[x['ms'] for x in samples if x['ok']]; n=len(samples)
    return {'requests':n,'successful':len(ok),'failed':n-len(ok),'concurrency':workers,'batch_size':batch_size,'elapsed_seconds':elapsed,'success_pct':100*len(ok)/n if n else 0,'requests_per_second':n/elapsed,'successful_properties_per_second':len(ok)*batch_size/elapsed,'mean_ms':statistics.mean(ok) if ok else None,'p50_ms':percentile(ok,.5),'p95_ms':percentile(ok,.95),'p99_ms':percentile(ok,.99),'max_ms':max(ok) if ok else None,'statuses':{s:sum(x['status']==s for x in samples) for s in sorted({x['status'] for x in samples})}}

def benchmark(key,row,version,requests=60):
    results=[]
    for name,size,workers in [('Single / sequential',1,1),('Single / concurrent',1,4),('Batch 10 / concurrent',10,4)]:
        path='/api/v1/predict' if size==1 else '/api/v1/predict/batch'; body=row if size==1 else {'properties':[row]*size}
        with httpx.Client(base_url=API,headers={'X-API-Key':key},timeout=30,trust_env=False,limits=httpx.Limits(max_connections=workers,max_keepalive_connections=workers)) as client:
            def request(_):
                start=time.perf_counter(); status='transport_error'; ok=False
                try:
                    r=client.post(path,json=body); status=str(r.status_code)
                    if r.status_code==200:
                        p=r.json(); items=[p] if size==1 else p.get('predictions',[])
                        ok=len(items)==size and all(prediction_ok(x,version) for x in items) and (size==1 or p.get('count')==size)
                except (httpx.HTTPError,ValueError,TypeError,AttributeError): pass
                return {'ms':(time.perf_counter()-start)*1000,'status':status,'ok':ok}
            for _ in range(3): require(request(0)['ok'],'Benchmark warmup failed')
            start=time.perf_counter()
            with ThreadPoolExecutor(max_workers=workers) as pool: samples=list(pool.map(request,range(requests)))
            elapsed=time.perf_counter()-start
        results.append({'scenario':name,**summarize(samples,elapsed,size,workers)})
    return results

def coverage_totals(data):
    files=data['files']; selected={k:v for k,v in files.items() if Path(k).parts[0]=='backend'}
    def calc(group):
        total=sum(v['summary']['num_statements'] for v in group.values()); hit=sum(v['summary']['covered_lines'] for v in group.values()); return {'statements':total,'covered':hit,'percent':100*hit/total if total else 0,'files':len(group)}
    return {'backend':calc(selected),'backend_and_ml_pipeline':calc(files)}

def page(title,body):
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+'</title><style>body{font:16px system-ui;background:#eef4f2;color:#16343d;margin:0}main{max-width:1150px;margin:auto;padding:36px}h1{font-size:32px}section{background:white;border:1px solid #d9e5e1;border-radius:12px;padding:22px;margin:18px 0}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:10px;border-bottom:1px solid #e2e9e6}th{background:#edf5f1}img{max-width:100%}a{color:#146a65}small{color:#526e73}pre{white-space:pre-wrap}</style><main><small>TASK 06 / QUALITY ASSURANCE / PHASE 08</small><h1>'+html.escape(title)+'</h1>'+body+'</main></html>'

def table(headers,rows):
    def cells(tag,row): return ''.join(f'<{tag}>{html.escape(str(x))}</{tag}>' for x in row)
    return '<table><thead><tr>'+cells('th',headers)+'</tr></thead><tbody>'+''.join('<tr>'+cells('td',r)+'</tr>' for r in rows)+'</tbody></table>'

def report(out, results, context):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    (out/'benchmark.json').write_text(json.dumps({'context':context,'results':results},indent=2,allow_nan=False))
    labels=[r['scenario'] for r in results]; fig,ax=plt.subplots(figsize=(10,4.8)); ax.bar(labels,[r['p95_ms'] if r['p95_ms'] is not None else 0 for r in results],color='#267d75'); ax.set_ylabel('Milliseconds'); ax.set_title('P95 successful request latency'); ax.tick_params(axis='x',labelsize=9); fig.tight_layout(); fig.savefig(out/'latency.png',dpi=150); plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4.8)); ax.bar(labels,[r['successful_properties_per_second'] for r in results],color='#3975a3'); ax.set_ylabel('Properties / second'); ax.set_title('Successful prediction throughput'); ax.tick_params(axis='x',labelsize=9); fig.tight_layout(); fig.savefig(out/'throughput.png',dpi=150); plt.close(fig)
    fmt=lambda x: 'N/A' if x is None else f'{x:.2f}'
    body='<section>'+table(['Scenario','Requests','Concurrency','Batch','Success %','Mean ms','P50 ms','P95 ms','P99 ms','Requests/s','Properties/s'],[[r['scenario'],r['requests'],r['concurrency'],r['batch_size'],fmt(r['success_pct']),fmt(r['mean_ms']),fmt(r['p50_ms']),fmt(r['p95_ms']),fmt(r['p99_ms']),fmt(r['requests_per_second']),fmt(r['successful_properties_per_second'])] for r in results])+'</section><section><img src="latency.png" alt="Latency chart"><img src="throughput.png" alt="Throughput chart"></section><section><p>Local HTTP benchmark; three unmeasured warmup requests per scenario. Latency statistics use successful requests only; failures remain in success rate and request throughput. Repeated valid demo property, not customer traffic or production capacity. Zero bar if no successful requests (N/A in table).</p><pre>'+html.escape(json.dumps(context,indent=2))+'</pre></section>'
    (out/'benchmark.html').write_text(page('API performance benchmarks',body))
