"""Import verified Phase 3 experiments and manage a local MLflow model registry."""
from pathlib import Path
import hashlib
import json
import sys
import math
from datetime import datetime, timezone
from importlib.metadata import version
import joblib
import numpy as np
import pandas as pd
from phase4_inference import RAW, predict_bundle

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = 'Task 6 - Real Estate Model Comparison'
MODEL = 'RealEstatePricePredictor'
EXPECTED = {'Linear Regression','Random Forest','Gradient Boosting','Extra Trees','XGBoost','Neural Network'}
METRICS = ['r2','mae','rmse','mape_pct']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    tmp.replace(path)


def validate_comparison(frame, meta, tuning):
    needed = {'model','split','fit_seconds',*METRICS,'test_batch_seconds'}
    if not needed.issubset(frame.columns) or len(frame)!=12 or set(frame.model)!=EXPECTED or set(frame.split)!={'validation','test'} or frame.duplicated(['model','split']).any():
        raise ValueError('Expected six models, each with one validation and one test record')
    if set(tuning)!=EXPECTED:
        raise ValueError('Missing tuning records')
    if not np.isfinite(frame[METRICS+['fit_seconds']].to_numpy(dtype=float)).all():
        raise ValueError('Nonfinite metrics')
    if (frame[['mae','rmse','mape_pct','fit_seconds']] < 0).any().any():
        raise ValueError('Invalid negative error or duration')
    test = frame[frame.split=='test']
    if not np.isfinite(test.test_batch_seconds).all() or (test.test_batch_seconds<0).any():
        raise ValueError('Invalid test timing')
    winner = frame[frame.split=='validation'].sort_values(['rmse','model']).iloc[0].model
    if winner != meta['selected_model']:
        raise ValueError('Winner must be selected by validation RMSE')
    selected = test[test.model==winner].iloc[0]
    for key in METRICS:
        if not math.isclose(float(selected[key]), float(meta['test_metrics'][key]), rel_tol=1e-8, abs_tol=1e-8):
            raise ValueError('Selected model metadata disagrees with test report: '+key)
    return winner


def snapshot(root=ROOT):
    root=Path(root).resolve()
    required=['ml-pipeline/preprocessing/phase2.py','ml-pipeline/training/phase3.py','data/manifest.json','data/processed/split_manifest.json','models/phase3_metadata.json','models/phase3_best_model.joblib','reports/phase3_model_comparison.csv','reports/phase3_tuning.json','reports/phase3_model_comparison.md','reports/phase3_neural_history.csv','visualizations/phase3_model_performance.png','visualizations/phase3_neural_network_training.png','visualizations/phase3_prediction_evaluation.png']
    missing=[x for x in required if not (root/x).is_file()]
    if missing:
        raise FileNotFoundError('Restore/run Phases 2 and 3 first. Missing: '+', '.join(missing))
    for folder in [root,root/'ml-pipeline/training',root/'ml-pipeline/preprocessing']:
        if str(folder) not in sys.path: sys.path.insert(0,str(folder))
    from phase3 import load_partitions, predict, metrics
    from backend.services.datasets import dataset_status
    parts,source=load_partitions(root)
    meta=read(root/'models/phase3_metadata.json')
    model_path=root/'models/phase3_best_model.joblib'
    if source!=meta['source_sha256'] or sha(model_path)!=meta['model_sha256'] or meta['raw_features']!=RAW:
        raise ValueError('Model metadata/source/hash mismatch; rerun Phase 3 locally')
    for name in parts:
        if len(parts[name])!=meta[('training' if name=='train' else name)+'_rows']:
            raise ValueError('Partition counts differ from model metadata')
    df=pd.read_csv(root/'reports/phase3_model_comparison.csv')
    tuning=read(root/'reports/phase3_tuning.json')
    winner=validate_comparison(df,meta,tuning)
    # Trusted local artifact only. Verify inference parity, not model selection.
    bundle=joblib.load(model_path)
    for split in ['validation','test']:
        frame=parts[split]; raw=frame[RAW]
        actual=predict_bundle(bundle,raw)
        np.testing.assert_allclose(actual,predict(bundle,frame),rtol=1e-10,atol=1e-6)
        score=metrics(frame.Price,actual)
        logged=df[(df.model==winner)&(df.split==split)].iloc[0]
        for key in METRICS:
            if not math.isclose(score[key],float(logged[key]),rel_tol=1e-7,abs_tol=1e-7):
                raise ValueError('Saved model does not reproduce recorded '+split+' '+key)
    checks={x:sha(root/x) for x in required}
    # Stable import ID across restarts; different reports/model or code create another version.
    import_id=hashlib.sha256(json.dumps(checks,sort_keys=True).encode()).hexdigest()
    data_manifest={'schema_version':1,'dataset_version':'sha256:'+source,'primary_dataset':'house_prices.csv','source_sha256':source,'datasets':[{k:s[k] for k in ['name','rows','columns','role','status']}|{'sha256':sha(root/'data/raw'/s['name'])} for s in dataset_status(root)],'split_manifest':read(root/'data/processed/split_manifest.json'),'model_sha256':meta['model_sha256'],'import_id':import_id,'input_checksums':checks,'privacy':'Raw and derived records remain local. Other datasets are inventory only.'}
    # Example uses training rows only and is not logged as input data.
    sample=parts['train'][RAW].head(3).copy()
    return {'root':root,'meta':meta,'df':df,'tuning':tuning,'winner':winner,'import_id':import_id,'manifest':data_manifest,'sample':sample,'sample_predictions':predict_bundle(bundle,sample),'model_path':model_path}


def configure(store_root):
    import mlflow
    from mlflow import MlflowClient
    root=Path(store_root).resolve(); db=root/'mlruns/phase4.sqlite'; artifacts=root/'mlartifacts/phase4'
    db.parent.mkdir(parents=True,exist_ok=True); artifacts.mkdir(parents=True,exist_ok=True)
    uri='sqlite:///'+str(db)
    mlflow.set_tracking_uri(uri); mlflow.set_registry_uri(uri)
    return mlflow,MlflowClient(tracking_uri=uri,registry_uri=uri),uri,artifacts


def get_alias(client, alias):
    from mlflow.exceptions import MlflowException

    try:
        model = client.get_registered_model(MODEL)
    except MlflowException as e:
        if e.error_code in ('RESOURCE_DOES_NOT_EXIST', 'NOT_FOUND'):
            return None
        raise

    version = model.aliases.get(alias)
    return str(version) if version is not None else None


def register_snapshot(s, store_root=ROOT):
    from mlflow.models import infer_signature
    from phase4_model import PropertyPredictor
    mlflow,client,uri,artifacts=configure(store_root)
    exp=client.get_experiment_by_name(EXPERIMENT)
    eid=exp.experiment_id if exp else client.create_experiment(EXPERIMENT,artifact_location=artifacts.as_uri())
    iid=s['import_id']; root=s['root']; winner=s['winner']
    manifest_path=Path(store_root)/'reports/phase4_data_version.json'
    write(manifest_path,s['manifest'])
    runs={}
    for name in sorted(EXPECTED):
        old=client.search_runs([eid],filter_string=f"tags.phase4_import_id = '{iid}' AND tags.phase3_model = '{name}' AND attributes.status = 'FINISHED'",max_results=10)
        if old:
            runs[name]=old[0].info.run_id
            continue
        with mlflow.start_run(experiment_id=eid,run_name=name,tags={'phase4_import_id':iid,'phase3_model':name,'source_sha256':s['meta']['source_sha256'],'record_origin':'imported from local Phase 3 reports','validation_selected':str(name==winner).lower()}) as run:
            for key,value in s['tuning'][name].items():
                if key=='cv_rmse': mlflow.log_metric('training_cv_rmse',float(value))
                elif key=='best_params':
                    for k,v in value.items(): mlflow.log_param(k,str(v))
                else: mlflow.log_param(key,json.dumps(value) if isinstance(value,(dict,list)) else str(value))
            for split in ['validation','test']:
                row=s['df'][(s['df'].model==name)&(s['df'].split==split)].iloc[0]
                mlflow.log_metrics({f'{split}_{key}':float(row[key]) for key in METRICS})
                if split=='test': mlflow.log_metric('test_batch_seconds',float(row.test_batch_seconds))
            mlflow.log_metric('fit_seconds',float(row.fit_seconds))
            if name=='Neural Network':
                history=pd.read_csv(root/'reports/phase3_neural_history.csv')
                for h in history.itertuples(index=False):
                    mlflow.log_metrics({'epoch_train_rmse':float(h.train_rmse),'epoch_validation_rmse':float(h.validation_rmse)},step=int(h.epoch))
            for key in ['training_rows','validation_rows','test_rows']: mlflow.log_param(key,s['meta'][key])
            mlflow.log_artifact(str(manifest_path),artifact_path='provenance')
            mlflow.log_artifact(str(root/'reports/phase3_model_comparison.csv'),artifact_path='evaluation')
            mlflow.log_artifact(str(root/'reports/phase3_tuning.json'),artifact_path='evaluation')
            if name==winner:
                mlflow.log_artifact(str(root/'reports/phase3_model_comparison.md'),artifact_path='evaluation')
                for path in sorted((root/'visualizations').glob('phase3_*.png')): mlflow.log_artifact(str(path),artifact_path='charts')
                mlflow.log_artifact(str(root/'reports/phase3_neural_history.csv'),artifact_path='evaluation')
                # Portable PythonModel with exact runtime requirements and verified hash.
                reqs=[f'{pkg}=={version(pkg)}' for pkg in ['mlflow','cloudpickle','numpy','pandas','scikit-learn','joblib','xgboost']]
                info=mlflow.pyfunc.log_model(name='property_predictor',python_model=PropertyPredictor(s['meta']['model_sha256']),artifacts={'bundle':str(s['model_path'])},code_paths=[str(Path(__file__).with_name('phase4_model.py')),str(Path(__file__).with_name('phase4_inference.py'))],signature=infer_signature(s['sample'],s['sample_predictions']),pip_requirements=reqs)
                mlflow.set_tag('phase4_model_uri',info.model_uri)
            runs[name]=run.info.run_id
        print('Tracked:',name,flush=True)
    selected=client.get_run(runs[winner]); model_uri=selected.data.tags['phase4_model_uri']
    versions=client.search_model_versions(f"name = '{MODEL}'")
    matches=[v for v in versions if v.tags.get('phase4_import_id')==iid]
    if matches:
        mv=matches[0]
    else:
        mv=mlflow.register_model(model_uri,MODEL,tags={'phase4_import_id':iid,'source_sha256':s['meta']['source_sha256'],'model_sha256':s['meta']['model_sha256'],'selected_model':winner})
    # A real registry round trip is required before alias changes.
    loaded=mlflow.pyfunc.load_model(f'models:/{MODEL}/{mv.version}')
    np.testing.assert_allclose(loaded.predict(s['sample']),s['sample_predictions'],rtol=1e-8,atol=1e-5)
    client.set_registered_model_alias(MODEL,'candidate',mv.version)
    if get_alias(client,'champion') is None:
        client.set_registered_model_alias(MODEL,'champion',mv.version)
    status={'experiment':EXPERIMENT,'experiment_id':eid,'import_id':iid,'runs':runs,'registered_model':MODEL,'registered_version':str(mv.version),'candidate':get_alias(client,'candidate'),'champion':get_alias(client,'champion'),'selected_model':winner,'registry_prediction_parity':'passed','scope':'local demonstration, no production deployment','model_artifacts':'Only validation-selected model is registered; other runs contain recorded metrics.'}
    write(Path(store_root)/'reports/phase4_registry_status.json',status)
    return status


def change_alias(root, target, operation, input_root=None):
    mlflow,client,_,_=configure(root)
    previous=get_alias(client,'champion')
    if target is None: target=get_alias(client,'candidate')
    if not target or not str(target).isdigit() or int(target)<1: raise ValueError('Use a positive registered version number')
    mv=client.get_model_version(MODEL,str(target))
    if mv.status!='READY' or not mv.tags.get('phase4_import_id'): raise ValueError('Version is not a ready Phase 4 model')
    # Smoke-test target before changing pointer; no test data used for promotion.
    s=snapshot(input_root or root)
    p=np.asarray(mlflow.pyfunc.load_model(f'models:/{MODEL}/{target}').predict(s['sample']))
    if p.shape!=(len(s['sample']),) or not np.isfinite(p).all() or (p<0).any(): raise ValueError('Target smoke test failed')
    client.set_registered_model_alias(MODEL,'champion',str(target))
    event={'time_utc':datetime.now(timezone.utc).isoformat(),'operation':operation,'previous':previous,'champion':str(target)}
    with (Path(root)/'mlruns/phase4_alias_history.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps(event)+'\n')
    report=Path(root)/'reports/phase4_registry_status.json'
    if report.exists():
        data=read(report); data['champion']=str(target); data['last_alias_change']=event; write(report,data)
    return event
