import sys,json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest,joblib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'ml-pipeline/training'))
from phase3 import load_partitions,metrics,select_model,predict,RAW,ID

def test_split_integrity():
    p,_=load_partitions(ROOT)
    assert [len(p[k]) for k in ['train','validation','test']]==[210,45,45]
    assert not set(p['train'][ID])&set(p['test'][ID])
    assert not set(p['train'][ID])&set(p['validation'][ID])
    assert not set(p['validation'][ID])&set(p['test'][ID])

def test_metrics_perfect():
    assert metrics([1,2,3],[1,2,3])=={'r2':1.,'mae':0.,'rmse':0.,'mape_pct':0.}

def test_selection_ignores_test():
    assert select_model([{'model':'A','split':'validation','rmse':3},{'model':'B','split':'validation','rmse':4},{'model':'B','split':'test','rmse':0}])=='A'

def test_nonfinite_rejected():
    with pytest.raises(ValueError): metrics([1,2],[1,np.nan])

def test_saved_artifact():
    path=ROOT/'models/phase3_best_model.joblib'; assert path.exists(), 'Run scripts/run_phase3.py first'
    parts,_=load_partitions(ROOT); y=predict(joblib.load(path),parts['test'][RAW].head(3))
    assert y.shape==(3,) and np.isfinite(y).all() and (y>=0).all()

def test_comparison_frozen():
    table=pd.read_csv(ROOT/'reports/phase3_model_comparison.csv'); assert len(table)==12 and table.model.nunique()==6
    assert set(table.split)=={'validation','test'}
    meta=json.loads((ROOT/'models/phase3_metadata.json').read_text())
    assert select_model(table.to_dict('records'))==meta['selected_model']
