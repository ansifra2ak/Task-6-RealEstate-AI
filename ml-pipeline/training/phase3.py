"""Train six regressors; tune on training, select on validation, evaluate frozen models."""
from pathlib import Path
import sys, json, time, copy, platform
import numpy as np
import pandas as pd
import joblib
import sklearn, xgboost
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GridSearchCV, KFold
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, ExtraTreesRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, mean_absolute_percentage_error
from xgboost import XGBRegressor
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'ml-pipeline/preprocessing'))
from phase2 import RAW,TARGET,ID,SEED,features,make_preprocessor,sha,validate_properties,split_properties,write_json
from backend.services.datasets import dataset_status

def load_partitions(root):
    root=Path(root); p=root/'data/processed'; raw=root/'data/raw/house_prices.csv'
    if not (p/'split_manifest.json').exists(): raise ValueError('Run python scripts/run_phase2.py first')
    manifest=json.loads((p/'split_manifest.json').read_text()); source=sha(raw)
    if any(s['status']!='verified' for s in dataset_status(root)) or manifest['source_sha256']!=source or manifest['seed']!=SEED: raise ValueError('Dataset or split integrity failure')
    expected=split_properties(validate_properties(pd.read_csv(raw))); parts={}
    for name in ('train','validation','test'):
        f=p/f'{name}.csv'
        if sha(f)!=manifest['partitions'][name]['sha256']: raise ValueError('Split hash mismatch: '+name)
        df=validate_properties(pd.read_csv(f))
        if len(df)!=manifest['partitions'][name]['rows'] or not df.equals(expected[name]): raise ValueError('Split contents mismatch: '+name)
        parts[name]=df
    return parts,source

def metrics(y,p):
    y=np.asarray(y); p=np.asarray(p)
    if not np.isfinite(p).all(): raise ValueError('Nonfinite predictions')
    return dict(r2=float(r2_score(y,p)),mae=float(mean_absolute_error(y,p)),rmse=float(np.sqrt(mean_squared_error(y,p))),mape_pct=float(100*mean_absolute_percentage_error(y,p)))

def predict(a,raw):
    x=features(raw)
    if a['kind']=='mlp':
        p=a['estimator'].predict(a['preprocessor'].transform(x)); p=a['target_scaler'].inverse_transform(p.reshape(-1,1)).ravel()
    else: p=a['estimator'].predict(x)
    return np.maximum(np.asarray(p),0)

def select_model(rows):
    return min((r for r in rows if r['split']=='validation'),key=lambda r:(r['rmse'],r['model']))['model']

def neural(tr,va):
    proc=make_preprocessor().fit(features(tr)); x=proc.transform(features(tr)); vx=proc.transform(features(va))
    ys=StandardScaler().fit(tr[[TARGET]]); y=ys.transform(tr[[TARGET]]).ravel()
    net=MLPRegressor(hidden_layer_sizes=(64,32),activation='relu',solver='adam',alpha=.001,learning_rate_init=.003,batch_size=32,random_state=SEED,max_iter=1)
    history=[]; best=None; best_rmse=float('inf'); epoch_best=0
    for ep in range(1,301):
        net.partial_fit(x,y)
        tp=ys.inverse_transform(net.predict(x).reshape(-1,1)).ravel(); vp=ys.inverse_transform(net.predict(vx).reshape(-1,1)).ravel()
        train_rmse=metrics(tr[TARGET],np.maximum(tp,0))['rmse']; val_rmse=metrics(va[TARGET],np.maximum(vp,0))['rmse']
        history.append(dict(epoch=ep,train_rmse=train_rmse,validation_rmse=val_rmse))
        if val_rmse<best_rmse: best_rmse=val_rmse; best=copy.deepcopy(net); epoch_best=ep
        if ep-epoch_best>=35: break
    return dict(kind='mlp',estimator=best,preprocessor=proc,target_scaler=ys),history,epoch_best

def charts(df,history,epoch,pred,viz,winner):
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold'})
    t=df[df.split=='test']; colors=['#16877e' if n==winner else '#527ca3' for n in t.model]
    fig,axes=plt.subplots(1,3,figsize=(15,5.4))
    for ax,key,label in zip(axes,['r2','mae','rmse'],['R²','MAE (million units)','RMSE (million units)']):
        vals=t[key] if key=='r2' else t[key]/1e6
        bars=ax.barh(t.model,vals,color=colors); ax.bar_label(bars,fmt='%.3f',padding=3,fontsize=9); ax.set_title(label); ax.margins(x=.22); ax.invert_yaxis()
    fig.suptitle('Held-out test performance | 45 properties',fontsize=16,fontweight='bold'); fig.text(.5,.015,'Teal = validation-selected model. Test scores were not used for selection.',ha='center'); fig.tight_layout(rect=[0,.05,1,.93]); fig.savefig(viz/'phase3_model_performance.png',dpi=150,bbox_inches='tight'); plt.close(fig)
    h=pd.DataFrame(history); fig,ax=plt.subplots(figsize=(9,5.5)); ax.plot(h.epoch,h.train_rmse/1e6,label='Training',color='#527ca3'); ax.plot(h.epoch,h.validation_rmse/1e6,label='Validation',color='#16877e'); ax.axvline(epoch,ls='--',color='#b45309',label=f'Best epoch {epoch}'); ax.set(title='Neural network learning curves',xlabel='Epoch',ylabel='RMSE (million source units)'); ax.legend(); fig.tight_layout(); fig.savefig(viz/'phase3_neural_network_training.png',dpi=150); plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,5.3)); a=pred.actual/1e6; p=pred.predicted/1e6; r=pred.residual/1e6; bounds=[min(a.min(),p.min()),max(a.max(),p.max())]; axes[0].scatter(a,p,color='#16877e',alpha=.75); axes[0].plot(bounds,bounds,'--',color='#64748b'); axes[0].set(title='Actual versus predicted',xlabel='Actual (million units)',ylabel='Predicted (million units)'); axes[1].scatter(p,r,color='#527ca3',alpha=.75); axes[1].axhline(0,ls='--',color='#64748b'); axes[1].set(title='Residuals',xlabel='Predicted (million units)',ylabel='Actual − predicted (million units)'); fig.suptitle(f'{winner} | held-out evaluation (n=45)',fontsize=15,fontweight='bold'); fig.tight_layout(); fig.savefig(viz/'phase3_prediction_evaluation.png',dpi=150); plt.close(fig)

def train(root=ROOT):
    root=Path(root); parts,source=load_partitions(root); tr,va,te=[parts[k] for k in ('train','validation','test')]
    reports=root/'reports'; viz=root/'visualizations'; models=root/'models'; processed=root/'data/processed'
    for p in [reports,viz,models]:p.mkdir(exist_ok=True,parents=True)
    specs=[('Linear Regression',LinearRegression(),{}),('Random Forest',RandomForestRegressor(n_estimators=120,random_state=SEED,n_jobs=1),{'max_depth':[None,8],'min_samples_leaf':[1,3]}),('Gradient Boosting',GradientBoostingRegressor(random_state=SEED),{'n_estimators':[100,200],'max_depth':[2,3]}),('Extra Trees',ExtraTreesRegressor(n_estimators=120,random_state=SEED,n_jobs=1),{'max_depth':[None,8],'min_samples_leaf':[1,3]}),('XGBoost',XGBRegressor(objective='reg:squarederror',random_state=SEED,n_jobs=1,tree_method='hist',verbosity=0),{'n_estimators':[100,200],'max_depth':[2,4]})]
    rows=[]; artifacts={}; tuning={}; times={}; x=features(tr); y=tr[TARGET]; cv=KFold(5,shuffle=True,random_state=SEED)
    for name,est,grid in specs:
        start=time.perf_counter(); pipe=Pipeline([('preprocess',make_preprocessor()),('model',est)])
        search=GridSearchCV(pipe,{'model__'+k:v for k,v in grid.items()},cv=cv,scoring='neg_root_mean_squared_error',n_jobs=1,error_score='raise',refit=True).fit(x,y)
        times[name]=time.perf_counter()-start; artifacts[name]=dict(kind='pipeline',estimator=search.best_estimator_)
        tuning[name]=dict(best_params=search.best_params_,cv_rmse=float(-search.best_score_),candidates=len(search.cv_results_['params']))
        print(f'Trained {name} | CV RMSE {tuning[name]["cv_rmse"]:,.2f}',flush=True)
    name='Neural Network'; start=time.perf_counter(); artifact,history,epoch=neural(tr,va); times[name]=time.perf_counter()-start; artifacts[name]=artifact
    tuning[name]=dict(hidden_layers=[64,32],best_epoch=epoch,epochs_run=len(history),selection='validation RMSE early stopping; no CV score')
    print(f'Trained {name} | best epoch {epoch}',flush=True)
    for name,a in artifacts.items(): rows.append(dict(model=name,split='validation',fit_seconds=times[name],**metrics(va[TARGET],predict(a,va))))
    winner=select_model(rows); print('Selected by validation RMSE:',winner,flush=True)
    predictions={}
    for name,a in artifacts.items():
        start=time.perf_counter(); p=predict(a,te); latency=time.perf_counter()-start; predictions[name]=p
        rows.append(dict(model=name,split='test',fit_seconds=times[name],test_batch_seconds=latency,**metrics(te[TARGET],p)))
    df=pd.DataFrame(rows); df.to_csv(reports/'phase3_model_comparison.csv',index=False); pd.DataFrame(history).to_csv(reports/'phase3_neural_history.csv',index=False); write_json(reports/'phase3_tuning.json',tuning)
    path=models/'phase3_best_model.joblib'; joblib.dump(artifacts[winner],path)
    p=predictions[winner]; pred=pd.DataFrame({ID:te[ID],'actual':te[TARGET],'predicted':p,'residual':te[TARGET]-p}); pred.to_csv(processed/'phase3_test_predictions.csv',index=False)
    meta=dict(version='0.3.0',selected_model=winner,selection='lowest validation RMSE; frozen test evaluation',source_sha256=source,model_sha256=sha(path),training_rows=len(tr),validation_rows=len(va),test_rows=len(te),units='unspecified source units',raw_features=RAW,neural_backend='scikit-learn MLPRegressor (two hidden layers)',versions=dict(python=platform.python_version(),sklearn=sklearn.__version__,xgboost=xgboost.__version__),test_metrics=metrics(te[TARGET],p))
    write_json(models/'phase3_metadata.json',meta); write_json(reports/'phase3_model_summary.json',meta); charts(df,history,epoch,pred,viz,winner)
    table=['# Phase 3 — Model comparison','',f'Selected on validation RMSE: **{winner}**. Training 210, validation 45, test 45. No test-driven selection or final refit.','', '| Model | Validation RMSE | Test R² | Test MAE | Test RMSE | Test MAPE |','|---|---:|---:|---:|---:|---:|']
    for name in artifacts:
        v=df[(df.model==name)&(df.split=='validation')].iloc[0]; t=df[(df.model==name)&(df.split=='test')].iloc[0]
        table.append(f'| {name} | {v.rmse:,.2f} | {t.r2:.4f} | {t.mae:,.2f} | {t.rmse:,.2f} | {t.mape_pct:.2f}% |')
    table+=['','## Method and limitations','Five classical candidates use 5-fold training-only CV with fold-fitted preprocessing. The two-hidden-layer MLP uses train-only feature/target scaling and validation early stopping. Predictions are clipped at zero consistently. All metrics are in source units except R² and MAPE. No verified currency, dates, sampling representativeness, market accuracy or calibrated uncertainty. The 45-row test is small. Do not select or tune models using these test results. Never load untrusted joblib files.']
    (reports/'phase3_model_comparison.md').write_text('\n'.join(table)+'\n'); print(df[['model','split','r2','mae','rmse','mape_pct']].to_string(index=False),flush=True)
    return meta
