"""Phase 4 checks. Integration test runs only with MLflow installed."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'ml-pipeline/registry'))
from phase4 import snapshot, validate_comparison, sha, read, write, EXPECTED
from phase4_inference import predict_bundle, RAW


@pytest.fixture(scope='module')
def verified():
    return snapshot(ROOT)


def test_actual_phase3_snapshot(verified):
    assert set(verified['df'].model)==EXPECTED
    assert len(verified['df'])==12
    assert len(verified['sample_predictions'])==3
    assert np.isfinite(verified['sample_predictions']).all()
    assert verified['manifest']['model_sha256']==sha(verified['model_path'])
    assert all(x['status']=='verified' for x in verified['manifest']['datasets'])


def test_stable_import_id(verified):
    assert snapshot(ROOT)['import_id']==verified['import_id']


def test_missing_comparison_row(verified):
    with pytest.raises(ValueError):
        validate_comparison(verified['df'].iloc[:-1],verified['meta'],verified['tuning'])


def test_wrong_selection(verified):
    meta=verified['meta'].copy()
    meta['selected_model']=next(x for x in EXPECTED if x!=verified['winner'])
    with pytest.raises(ValueError):
        validate_comparison(verified['df'],meta,verified['tuning'])


def test_invalid_metric(verified):
    df=verified['df'].copy(); df.loc[0,'rmse']=float('nan')
    with pytest.raises(ValueError):
        validate_comparison(df,verified['meta'],verified['tuning'])


@pytest.mark.parametrize('column,value',[('Area',-1),('Bedrooms',0),('Age',-1),('Location',''),('Bathrooms',1.5),('Area',np.inf)])
def test_invalid_inference(verified,column,value):
    frame=verified['sample'].copy(); frame[column]=value
    with pytest.raises(ValueError): predict_bundle({},frame)


def test_wrong_columns(verified):
    with pytest.raises(ValueError): predict_bundle({},verified['sample'].drop(columns=['Area']))


def test_manifest_write(tmp_path,verified):
    path=tmp_path/'version.json'; write(path,verified['manifest'])
    assert read(path)==verified['manifest']


def test_mlflow_registry_roundtrip(tmp_path,verified,monkeypatch):
    monkeypatch.setenv('MLFLOW_ENABLE_TELEMETRY','false')
    mlflow=pytest.importorskip('mlflow')
    from phase4 import register_snapshot, configure, MODEL, get_alias, change_alias
    old_tracking=mlflow.get_tracking_uri(); old_registry=mlflow.get_registry_uri()
    try:
        s=register_snapshot(verified,tmp_path)
        t=register_snapshot(verified,tmp_path)
        assert s['runs']==t['runs'] and s['registered_version']==t['registered_version']
        _,client,_,_=configure(tmp_path)
        assert len(client.search_runs([s['experiment_id']]))==6
        assert get_alias(client,'champion')==s['registered_version']
        assert len(client.search_model_versions(f"name = '{MODEL}'"))==1
        loaded=mlflow.pyfunc.load_model(f'models:/{MODEL}@champion')
        np.testing.assert_allclose(loaded.predict(verified['sample']),verified['sample_predictions'],rtol=1e-8,atol=1e-5)
        # Make a second version from the same artifact solely to test alias changes in isolation.
        mv=client.get_model_version(MODEL,s['registered_version'])
        second=client.create_model_version(MODEL,mv.source,run_id=mv.run_id,tags={'phase4_import_id':'test-only'})
        client.set_registered_model_alias(MODEL,'candidate',second.version)
        # Alias switching and backtracking without altering the real project registry.
        promoted=change_alias(tmp_path,second.version,'promote',input_root=ROOT)
        assert promoted['champion']==second.version
        rolled=change_alias(tmp_path,s['registered_version'],'rollback',input_root=ROOT)
        assert rolled['champion']==s['registered_version']
        assert get_alias(client,'champion')==s['registered_version']
    finally:
        mlflow.set_tracking_uri(old_tracking); mlflow.set_registry_uri(old_registry)
