"""Synthetic fixture tests; no private data or real model is read."""
import base64
import hashlib
import io
import json
from pathlib import Path
import tarfile
import asyncio
import httpx
import pytest
from fastapi import FastAPI, Header, HTTPException
from backend.phase11_render import EXACT, MAX_ENCODED, CloudGate, create_cloud_gateway, public_origin, unpack
from backend.phase9_runtime import tree_hash
from scripts.run_phase11 import pack, prepare

ORIGIN='https://test-task6.onrender.com'
PASSWORD='p'*40
KEY='k'*40


def fixture(root):
    root.mkdir()
    for name in EXACT - {'champion/deployment.json'}:
        p=root/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text('synthetic fixture')
    p=root/'champion/model/MLmodel'; p.parent.mkdir(parents=True); p.write_text('synthetic fixture')
    meta={'model_version':'test','hashes':{n:tree_hash(root/n) for n in ('data','reports','visualizations','champion/model')}}
    (root/'champion/deployment.json').write_text(json.dumps(meta))
    return root


def archive(name, kind=tarfile.REGTYPE):
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode='w:gz') as t:
        m=tarfile.TarInfo(name); m.type=kind; m.linkname='/etc/passwd'; m.size=0
        t.addfile(m,io.BytesIO())
    raw=buf.getvalue(); return base64.b64encode(raw),hashlib.sha256(raw).hexdigest()


def test_roundtrip(tmp_path):
    root=fixture(tmp_path/'src'); encoded,digest=pack(root)
    dest=tmp_path/'dst'; dest.mkdir()
    assert unpack(encoded,digest,dest)['model_version']=='test'
    assert (dest/'champion/model/MLmodel').read_text()=='synthetic fixture'
    assert (dest/'champion/model/MLmodel').stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('name,kind',[('../escape',tarfile.REGTYPE),('/absolute',tarfile.REGTYPE),('champion/model/link',tarfile.SYMTYPE),('champion/model/link',tarfile.LNKTYPE),('champion/model/device',tarfile.CHRTYPE),('data/raw/customer_churn.csv',tarfile.REGTYPE),('.env.phase5',tarfile.REGTYPE)])
def test_bad_archive(tmp_path,name,kind):
    encoded,digest=archive(name,kind)
    with pytest.raises(ValueError): unpack(encoded,digest,tmp_path)
    assert not (tmp_path.parent/'escape').exists()


def test_checksum_and_size(tmp_path):
    encoded,digest=archive('champion/model/a')
    with pytest.raises(ValueError,match='checksum'): unpack(encoded,'0'*64,tmp_path)
    with pytest.raises(ValueError,match='size'): unpack(b'A'*(MAX_ENCODED+1),digest,tmp_path)


def test_bundle_tampering(tmp_path):
    root=fixture(tmp_path/'src'); (root/'reports/phase3_model_summary.json').write_text('tampered')
    with pytest.raises(ValueError,match='hash mismatch'): pack(root)


def test_private_unexpected_file(tmp_path):
    root=fixture(tmp_path/'src'); (root/'.env').write_text('synthetic secret')
    with pytest.raises(ValueError,match='Unexpected'): pack(root)


def test_no_permission():
    with pytest.raises(ValueError,match='permission'): prepare(False)


@pytest.mark.parametrize('url',['http://example.com','https://example.com/path','https://user:pass@example.com','https://example.com:444','https://example.com?x=1',''])
def test_invalid_origin(url):
    with pytest.raises(ValueError): public_origin(url)


def test_public_origin(): assert public_origin(ORIGIN+'/')==ORIGIN


def test_short_password():
    with pytest.raises(ValueError): CloudGate(FastAPI(),ORIGIN,'short')


def test_gateway_contract(tmp_path):
    api=FastAPI()
    @api.get('/api/v1/model/info')
    def model(x_api_key:str=Header('')):
        if x_api_key!=KEY: raise HTTPException(401)
        return {'model_version':'fixture'}
    @api.post('/api/v1/predict')
    def predict(body:dict,x_api_key:str=Header('')):
        if x_api_key!=KEY: raise HTTPException(401)
        return {'predicted_price':123.0,'model_version':'fixture'}
    app=create_cloud_gateway(tmp_path,api,KEY,ORIGIN,PASSWORD)
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=ORIGIN) as c:
            assert (await c.get('/healthz')).status_code==200
            assert (await c.get('/')).status_code==401
            h={'X-Dashboard-Request':'1'}; auth=('viewer',PASSWORD)
            assert (await c.get('/dashboard-api/model',headers=h)).status_code==401
            assert (await c.get('/dashboard-api/model',auth=auth)).status_code==403
            assert (await c.get('/dashboard-api/model',headers={**h,'Origin':'https://evil.example'},auth=auth)).status_code==403
            assert (await c.get('/dashboard-api/model',headers={**h,'Host':'evil.example'},auth=auth)).status_code==403
            assert (await c.get('/dashboard-api/model',headers=h,auth=('viewer','wrong'))).status_code==401
            r=await c.get('/dashboard-api/model',headers={**h,'Origin':ORIGIN},auth=auth)
            assert r.status_code==200 and r.json()=={'model_version':'fixture'} and KEY not in r.text
            assert (await c.post('/dashboard-api/predict',headers=h,auth=auth,json={'Area':2000})).json()['predicted_price']==123.0
            for p in ('/api/v1/model/info','/metrics','/monitoring/drift','/docs','/openapi.json'):
                assert (await c.get(p,headers=h,auth=auth)).status_code==404
    asyncio.run(run())
