"""Portable private champion serving; existing Phase 5/6/7 contracts are reused."""
import base64
import hashlib
import json
import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit


def tree_hash(path):
    path=Path(path)
    digest=hashlib.sha256()
    for f in sorted(path.rglob('*')):
        if f.is_symlink(): raise ValueError('Symlinks are not allowed in private bundle')
        if f.is_file():
            digest.update(f.relative_to(path).as_posix().encode()+b'\0')
            digest.update(hashlib.sha256(f.read_bytes()).digest())
    return digest.hexdigest()


def read_secret(name):
    path=Path(os.environ.get('TASK6_'+name+'_FILE','/run/secrets/'+name.lower()))
    value=path.read_text().strip()
    if len(value)<24: raise ValueError('Secret must be at least 24 characters: '+name)
    return value


def verify_bundle(root):
    root=Path(root)
    meta=json.loads((root/'champion/deployment.json').read_text())
    for name in ('data','reports','visualizations','champion/model'):
        if tree_hash(root/name)!=meta['hashes'][name]: raise ValueError('Private bundle hash mismatch: '+name)
    return meta


def api(root):
    import mlflow
    import numpy as np
    from backend.services.phase5 import PredictionService,training_data,RAW
    from backend.phase5_app import create_app
    from backend.phase7_monitoring import Monitor,monitor_app
    meta=verify_bundle(root)
    frame,source=training_data(root)
    if source!=meta['source_sha256']: raise ValueError('Champion source mismatch')
    predictor=mlflow.pyfunc.load_model(str(root/'champion/model'))
    service=PredictionService(predictor,frame,meta['model_version'],meta['selected_model'],source)
    raw=frame[RAW].copy()
    baseline=np.asarray(predictor.predict(raw),dtype=float)
    if baseline.shape!=(len(raw),) or not np.isfinite(baseline).all(): raise ValueError('Invalid reference predictions')
    np.testing.assert_allclose(baseline[:3],meta['parity_predictions'],rtol=1e-7,atol=0.01)
    ref={k:raw[k].tolist() for k in RAW}; ref['predicted_price']=baseline.tolist()
    monitor=Monitor(ref,service.version)
    demo=raw.sort_values('Area').tail(max(1,len(raw)//10)).sample(n=60,replace=True,random_state=42)
    monitor.record(demo.to_dict('records'),np.asarray(predictor.predict(demo)).tolist(),'demo')
    return monitor_app(create_app(service,read_secret('API_KEY'),root),monitor)


class PublicGuard:
    """Require Basic authentication and exact HTTPS origin before adapting local gateway headers.
    TLS must terminate at the configured reverse proxy. Never expose the raw port publicly.
    """
    def __init__(self, app, origin, password):
        parsed=urlsplit(origin)
        if parsed.scheme!='https' or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password or parsed.port not in (None,443):
            raise ValueError('Public origin must be https://your-domain without a path')
        self.app=app; self.origin=origin; self.host=parsed.netloc; self.password=password
    async def __call__(self,scope,receive,send):
        from starlette.responses import JSONResponse
        if scope['type']!='http': return await self.app(scope,receive,send)
        headers=dict(scope['headers'])
        if headers.get(b'host',b'').decode('latin1')!=self.host or (b'origin' in headers and headers[b'origin'].decode('latin1')!=self.origin):
            return await JSONResponse({'detail':'Host or origin rejected'},403)(scope,receive,send)
        try:
            scheme,token=headers.get(b'authorization',b'').split(b' ',1)
            valid=scheme.lower()==b'basic' and secrets.compare_digest(base64.b64decode(token,validate=True),('viewer:'+self.password).encode())
        except (ValueError,TypeError): valid=False
        if not valid:
            return await JSONResponse({'detail':'Authentication required'},401,headers={'WWW-Authenticate':'Basic realm="Task 6", charset="UTF-8"','Cache-Control':'no-store'})(scope,receive,send)
        filtered=[(k,v) for k,v in scope['headers'] if k not in (b'host',b'origin',b'authorization')]
        filtered.append((b'host',b'localhost:5176'))
        if b'origin' in headers: filtered.append((b'origin',b'http://localhost:5176'))
        return await self.app({**scope,'headers':filtered},receive,send)


def gateway(root):
    from backend.phase6_gateway import create_gateway
    app=create_gateway(root,read_secret('API_KEY'))
    origin=os.environ.get('TASK6_PUBLIC_ORIGIN','')
    return PublicGuard(app,origin,read_secret('VIEWER_PASSWORD')) if origin else app


if __name__=='__main__':
    import sys,uvicorn
    root=Path('/app')
    mode=sys.argv[1]
    if mode=='api': uvicorn.run(api(root),host='0.0.0.0',port=8006,access_log=False)
    elif mode=='gateway': uvicorn.run(gateway(root),host='0.0.0.0',port=5176,access_log=False)
    else: raise SystemExit('Unknown runtime mode')
