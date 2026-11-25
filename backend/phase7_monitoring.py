"""Bounded, in-memory aggregate monitoring for the Phase 5 ASGI application."""
import json
import math
import time
from collections import deque
from threading import RLock
import numpy as np
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response, JSONResponse

RAW = ('Area','Bedrooms','Bathrooms','Age','Location','Property_Type')
NUMERIC = RAW[:4] + ('predicted_price',)
FEATURES = RAW + ('predicted_price',)
MIN_SAMPLE = 30
WINDOW = 200
THRESHOLD = .25
ROUTES = {'/api/v1/predict':'single','/api/v1/predict/batch':'batch','/api/v1/health':'health','/api/v1/model/info':'model','/api/v1/analytics/market':'market','/api/v1/datasets':'datasets'}


def distribution(reference, values, numeric):
    if numeric:
        ref = np.asarray(reference,dtype=float); obs = np.asarray(values,dtype=float)
        cuts = np.unique(np.quantile(ref, [.2,.4,.6,.8]))
        edges = np.r_[-np.inf,cuts,np.inf]
        return np.histogram(ref,edges)[0],np.histogram(obs,edges)[0]
    cats = sorted(set(reference)|set(values))
    return np.array([reference.count(c) for c in cats]),np.array([values.count(c) for c in cats])


def psi(reference, values, numeric):
    a,b=distribution(list(reference),list(values),numeric)
    # Half-count smoothing avoids zero-bin infinities; heuristic, not a significance test.
    p=(a+.5)/(a.sum()+.5*len(a)); q=(b+.5)/(b.sum()+.5*len(b))
    return float(np.sum((q-p)*np.log(q/p)))


class Monitor:
    def __init__(self, reference, model_version):
        self.ref={k:list(reference[k]) for k in FEATURES}
        if len(self.ref['Area'])<MIN_SAMPLE or len({len(v) for v in self.ref.values()})!=1:
            raise ValueError('Insufficient or inconsistent reference data')
        self.version=str(model_version); self.lock=RLock()
        self.windows={m:deque(maxlen=WINDOW) for m in ('live','demo')}
        self.registry=CollectorRegistry()
        self.requests=Counter('task6_api_requests_total','Observed API requests', ['route','status'], registry=self.registry)
        self.latency=Histogram('task6_api_request_duration_seconds','Observed request duration', ['route'],buckets=(.005,.01,.025,.05,.1,.25,.5,1,2,5,10,30),registry=self.registry)
        self.properties=Counter('task6_predicted_properties_total','Properties in observed successful responses',registry=self.registry)
        self.skipped=Counter('task6_monitor_skipped_total','Successful predictions unavailable for monitoring',registry=self.registry)
        self.samples=Gauge('task6_drift_samples','Properties in rolling drift window',['mode'],registry=self.registry)
        self.ready=Gauge('task6_drift_ready','One when minimum sample count reached',['mode'],registry=self.registry)
        self.scores=Gauge('task6_drift_psi','Population stability index against training reference',['mode','feature'],registry=self.registry)
        self.price=Gauge('task6_prediction_window_mean','Mean model output in unspecified source units',['mode'],registry=self.registry)
        self.reference=Gauge('task6_reference_rows','Training reference rows',registry=self.registry)
        self.reference.set(len(self.ref['Area']))
        self.threshold=Gauge('task6_drift_threshold','Configured PSI warning threshold',registry=self.registry); self.threshold.set(THRESHOLD)
        for m in self.windows: self.refresh(m)
        for route in ROUTES.values():
            self.latency.labels(route)
            for status in ('200','401','422','503'): self.requests.labels(route,status)
    def refresh(self,mode):
        rows=list(self.windows[mode]); n=len(rows)
        self.samples.labels(mode).set(n); self.ready.labels(mode).set(int(n>=MIN_SAMPLE))
        self.price.labels(mode).set(float(np.mean([r['predicted_price'] for r in rows])) if rows else float('nan'))
        scores={}
        for f in FEATURES:
            score=psi(self.ref[f],[r[f] for r in rows],f in NUMERIC) if n>=MIN_SAMPLE else None
            self.scores.labels(mode,f).set(score if score is not None else float('nan')); scores[f]=score
        return {'mode':mode,'samples':n,'ready':n>=MIN_SAMPLE,'psi':scores,'threshold':THRESHOLD}
    def record(self, rows, prices, mode='live'):
        if mode not in self.windows or not rows or len(rows)!=len(prices): raise ValueError('Invalid monitoring sample')
        clean=[]
        for r,p in zip(rows,prices):
            item={k:r[k] for k in RAW}
            if not all(isinstance(item[k],(int,float)) and not isinstance(item[k],bool) and math.isfinite(item[k]) for k in RAW[:4]): raise ValueError('Invalid numeric feature')
            if not all(isinstance(item[k],str) for k in RAW[4:]) or not math.isfinite(float(p)): raise ValueError('Invalid sample')
            item['predicted_price']=float(p); clean.append(item)
        with self.lock:
            self.windows[mode].extend(clean)
            if mode=='live': self.properties.inc(len(clean))
            return self.refresh(mode)
    def snapshot(self):
        with self.lock:
            return {'model_version':self.version,'reference_rows':len(self.ref['Area']),'window_limit':WINDOW,'minimum_samples':MIN_SAMPLE,'units':'unspecified source units','note':'Input/output distribution drift only; no observed sale outcomes or accuracy drift. Demo is synthetic, separate from observed API traffic.', 'live':self.refresh('live'),'demo':self.refresh('demo')}


def monitor_app(app, monitor):
    """Observe final status and only successful prediction payloads; never log keys or bodies."""
    @app.get('/metrics',include_in_schema=False)
    def metrics():
        with monitor.lock: return Response(generate_latest(monitor.registry),headers={'Content-Type':CONTENT_TYPE_LATEST})
    @app.get('/monitoring/drift',include_in_schema=False)
    def drift(): return JSONResponse(monitor.snapshot())
    app.add_middleware(Observe,monitor=monitor)
    return app


class Observe:
    def __init__(self,app,monitor): self.app=app; self.monitor=monitor
    async def __call__(self,scope,receive,send):
        route=ROUTES.get(scope.get('path')) if scope['type']=='http' else None
        if not route: return await self.app(scope,receive,send)
        pred=route in ('single','batch') and scope.get('method')=='POST'
        req=bytearray(); res=bytearray(); limit=512000; overflow=False; status=500; start=time.perf_counter()
        async def read():
            nonlocal overflow
            msg=await receive()
            if pred and msg['type']=='http.request':
                chunk=msg.get('body',b'')
                if len(req)+len(chunk)>limit: overflow=True
                elif not overflow: req.extend(chunk)
            return msg
        async def write(msg):
            nonlocal status,overflow
            if msg['type']=='http.response.start': status=msg['status']
            if pred and status==200 and msg['type']=='http.response.body':
                chunk=msg.get('body',b'')
                if len(res)+len(chunk)>limit: overflow=True
                elif not overflow: res.extend(chunk)
            await send(msg)
        try: await self.app(scope,read,write)
        finally:
            self.monitor.requests.labels(route,str(status)).inc()
            self.monitor.latency.labels(route).observe(time.perf_counter()-start)
            if pred and status==200:
                try:
                    if overflow: raise ValueError('Monitoring capture limit')
                    inp=json.loads(req); out=json.loads(res)
                    rows=[inp] if route=='single' else inp['properties']
                    prices=[out['predicted_price']] if route=='single' else [r['predicted_price'] for r in out['predictions']]
                    self.monitor.record(rows,prices)
                except Exception: self.monitor.skipped.inc()


def create_instrumented(root,key):
    from backend.services.phase5 import load_service
    from backend.phase5_app import create_app
    service=load_service(root)
    frame=service.frame[list(RAW)].copy()
    baseline=np.asarray(service.predictor.predict(frame),dtype=float)
    if baseline.shape!=(len(frame),) or not np.isfinite(baseline).all(): raise ValueError('Invalid reference predictions')
    ref={k:frame[k].tolist() for k in RAW}; ref['predicted_price']=baseline.tolist()
    mon=Monitor(ref,service.version)
    # Repeated valid synthetic scenarios with high area, not user requests or market observations.
    demo=frame.sort_values('Area').tail(max(1,len(frame)//10)).sample(n=60,replace=True,random_state=42)
    values=np.asarray(service.predictor.predict(demo),dtype=float)
    mon.record(demo.to_dict('records'),values.tolist(),'demo')
    return monitor_app(create_app(service,key,root),mon)
