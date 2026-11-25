import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from phase8_quality import percentile,summarize,coverage_totals,prediction_ok,get_row,page,table,report

@pytest.mark.parametrize('p,expected',[(0,10),(.5,20),(.95,29),(1,30)])
def test_percentile(p,expected): assert percentile([30,10,20],p)==pytest.approx(expected)
def test_empty_percentile(): assert percentile([],.95) is None

def test_summary():
    s=summarize([{'ok':True,'ms':10,'status':'200'},{'ok':False,'ms':100,'status':'503'}],2,10,4)
    assert s['success_pct']==50 and s['requests_per_second']==1 and s['successful_properties_per_second']==5 and s['p95_ms']==10 and s['failed']==1

def test_no_success():
    s=summarize([{'ok':False,'ms':50,'status':'transport_error'}],1,1,1)
    assert s['mean_ms'] is None and s['success_pct']==0

@pytest.mark.parametrize('v',[-1,float('nan'),float('inf'),'123',None])
def test_invalid_predictions(v): assert not prediction_ok({'model_version':'1','predicted_price':v},'1')
def test_version(): assert not prediction_ok({'model_version':'2','predicted_price':100},'1')
def test_valid_prediction(): assert prediction_ok({'model_version':'1','predicted_price':100},'1')

def test_coverage_scope():
    data={'files':{'backend/main.py':{'summary':{'num_statements':100,'covered_lines':80}},'ml-pipeline/training/phase3.py':{'summary':{'num_statements':100,'covered_lines':10}}}}
    r=coverage_totals(data); assert r['backend']['percent']==80 and r['backend_and_ml_pipeline']['percent']==45

def test_escape_html(): assert '&lt;script&gt;' in page('x',table(['header'],[['<script>']]))
def test_row_integer(): assert get_row({'training_ranges':{'Area':{'min':1000.0}},'categories':{'Location':['Rural']}})=={'Area':1000,'Location':'Rural'}

def test_report(tmp_path):
    result={'scenario':'Test',**summarize([{'ok':True,'ms':12,'status':'200'}],.1,1,1)}
    report(tmp_path,[result],{'model':'fixture'}); assert all((tmp_path/f).stat().st_size>0 for f in ['benchmark.json','benchmark.html','latency.png','throughput.png'])

def test_isolated_data_and_training_roundtrip(tmp_path):
    """Exercise full pipeline in temporary storage, never replace active artifacts."""
    import shutil, json, joblib, numpy as np
    from threadpoolctl import threadpool_limits
    sys.path.insert(0,str(ROOT/'ml-pipeline/training'))
    sys.path.insert(0,str(ROOT/'ml-pipeline/preprocessing'))
    from phase2 import prepare
    from phase3 import train,load_partitions,predict,RAW
    shutil.copytree(ROOT/'data/raw',tmp_path/'data/raw')
    shutil.copy2(ROOT/'data/manifest.json',tmp_path/'data/manifest.json')
    result=prepare(tmp_path); assert result['splits']=={'train':210,'validation':45,'test':45}
    with threadpool_limits(limits=1): meta=train(tmp_path)
    parts,source=load_partitions(tmp_path)
    assert meta['source_sha256']==source and meta['test_rows']==45
    output=predict(joblib.load(tmp_path/'models/phase3_best_model.joblib'),parts['test'][RAW])
    assert output.shape==(45,) and np.isfinite(output).all()
    assert (tmp_path/'visualizations/phase3_prediction_evaluation.png').is_file()
    assert json.loads((tmp_path/'reports/phase3_model_summary.json').read_text())['selected_model']==meta['selected_model']
