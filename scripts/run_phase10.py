"""Phase 10: read existing evidence, generate documentation, and check readiness.
No training, Git writes, deployment, uploads, or edits to Phases 1–9.
"""
from __future__ import annotations
import argparse, csv, json, math, re, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
TITLE = 'RealEstate AI — Property Intelligence Platform'
SHOTS = '''01_project_structure 02_environment_setup 03_foundation_dashboard 04_foundation_api 05_foundation_tests 06_dataset_validation 07_data_preprocessing 08_exploratory_data_analysis 09_property_price_analysis 10_feature_correlation 11_model_training 12_model_comparison 13_model_performance 14_neural_network_training 15_prediction_evaluation 16_mlflow_experiments 17_model_registry 18_data_versioning 19_complete_api_documentation 20_api_price_prediction 21_api_batch_prediction 22_api_security_validation 23_final_dashboard 24_property_price_prediction 25_batch_prediction 26_market_analytics 27_explainable_ai 28_reports_dashboard 29_prometheus_metrics 30_grafana_dashboard 31_model_drift_monitoring 32_monitoring_alerts 33_automated_tests 34_test_coverage 35_performance_benchmarks 36_docker_deployment 37_docker_containers 38_github_actions 39_live_cloud_application 40_task6_submission_confirmation'''.split()
ALIASES = {13:'13_phase3_model_performance',14:'14_phase3_neural_network_training',15:'15_phase3_prediction_evaluation'}

def read(root, rel):
    try:
        v=json.loads((root/rel).read_text()); return v if isinstance(v,dict) else {}
    except (OSError, ValueError): return {}

def number(v, digits=2):
    if isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v): return f'{v:,.{digits}f}'
    return 'Not available'

def percent(v):
    n=number(v); return n+'%' if n!='Not available' else n

def git_read(root, *args):
    try:
        p=subprocess.run(['git',*args],cwd=root, capture_output=True,text=True,timeout=15)
        return p.stdout.strip() if p.returncode==0 else None
    except (OSError,subprocess.TimeoutExpired): return None

def private_path(p):
    return bool(re.match(r'^(?:\.phase9-|\.venv/|venv/|\.env(?:$|\.)|data/(?:raw|processed)/|models/|mlruns/|mlartifacts/|screenshots/|reports/|visualizations/|\.terraform/)',p) or re.search(r'\.(?:joblib|pkl|pem|key|sqlite\d*|db|tfstate(?:\.backup)?|tfvars|tfplan)$',p,re.I)) and not p.endswith(('/.gitkeep','/README.md')) and p!='.env.example'

def collect(root, reference=False, live=False):
    root=Path(root).resolve()
    summary=read(root,'reports/phase3_model_summary.json'); prep=read(root,'reports/preprocessing_report.json'); quality=read(root,'reports/data_quality.json'); tests=read(root,'reports/phase8/test_summary.json'); integ=read(root,'reports/phase8/integration.json'); bench=read(root,'reports/phase8/benchmark.json')
    metrics=summary.get('test_metrics',{}); selected=summary.get('selected_model','Not available'); split=prep.get('split_counts',{})
    models=[]
    try:
        with (root/'reports/phase3_model_comparison.csv').open(newline='') as f:
            for row in csv.DictReader(f):
                if row['split'] not in ('validation','test'): continue
                models.append({'model':row['model'],'split':row['split'],**{k:float(row[k]) for k in ('r2','mae','rmse','mape_pct')}})
    except (OSError,KeyError,ValueError): models=[]
    screenshots=[]
    for i,stem in enumerate(SHOTS,1):
        names=[stem]+([ALIASES[i]] if i in ALIASES else [])
        found=None
        for name in names:
            p=root/'screenshots'/f'{name}.png'
            try:
                with p.open('rb') as f:
                    if f.read(8)==b'\x89PNG\r\n\x1a\n': found=p.name; break
            except OSError: pass
        screenshots.append({'number':i,'expected':stem+'.png','found':found})
    matches=bool(summary and prep and summary.get('source_sha256') and summary.get('source_sha256')==prep.get('source_sha256'))
    coverage=tests.get('coverage',{}); gate=all(isinstance(coverage.get(k,{}).get('percent'),(int,float)) and coverage[k]['percent']>=80 for k in ('backend','backend_and_ml_pipeline'))
    python=tests.get('python',{}); test_ok=bool(python.get('passed',0)>0 and tests.get('pytest_exit')==0 and tests.get('javascript_exit')==0 and all(python.get(k)==0 for k in ('failure','error','skipped')) and gate)
    checks=integ.get('checks',[]); results=bench.get('results',[])
    integration_ok=bool(checks and all(c.get('passed') is True for c in checks) and integ.get('dashboard_tested') and integ.get('monitoring_tested'))
    benchmark_ok=bool(len(results)==3 and all(r.get('requests',0)>0 and r.get('failed')==0 and r.get('successful')==r.get('requests') for r in results))
    top=git_read(root,'rev-parse','--show-toplevel') if not reference else None
    independent=bool(top and Path(top).resolve()==root)
    tracked=git_read(root,'ls-files') if independent else None
    history=git_read(root,'log','--all','--name-only','--format=') if independent else None
    blocked=sorted(set(p for p in ((tracked or '')+'\n'+(history or '')).splitlines() if private_path(p)))
    head=git_read(root,'rev-parse','HEAD') if independent else None
    upstream=git_read(root,'rev-parse','@{upstream}') if independent else None
    smoke='NOT RUN (use --live to run Phase 9 smoke test)'
    if live and not reference:
        try:
            p=subprocess.run([sys.executable,'scripts/run_phase9.py','smoke'],cwd=root,capture_output=True,text=True,timeout=120)
            smoke='PASS' if p.returncode==0 else 'FAIL (run Phase 9 smoke directly to diagnose)'
        except (OSError,subprocess.TimeoutExpired): smoke='FAIL (could not complete smoke test)'
    validations=[('Phase 3 summary, preprocessing hash and six test comparisons',matches and len([r for r in models if r['split']=='test'])==6 and all(number(metrics.get(k))!='Not available' for k in ('r2','mae','rmse','mape_pct'))),('Phase 8 tests and both 80% coverage gates; no skips',test_ok),('Phase 8 live checks including gateway and monitoring',integration_ok),('Three benchmark scenarios with all requests successful',benchmark_ok),('Independent Git repository and no obvious private paths in index/history',independent and tracked is not None and history is not None and not blocked),('Local HEAD matches cached upstream tracking ref (not remote verification)',bool(head and upstream==head)),('Local Docker live smoke test',smoke=='PASS'),('Screenshots 01–38 present (PNG signature only)',all(x['found'] for x in screenshots[:38]))]
    return dict(reference=reference, generated_utc=datetime.now(timezone.utc).isoformat(),selected=selected,metrics=metrics,split=split,quality=quality.get('datasets',{}).get('house_prices.csv',{}),feature_count=prep.get('transformed_feature_count'),models=models,tests=tests,coverage=coverage,checks=checks,results=results,bench_context={k:bench.get('context',{}).get(k) for k in ('platform','python','model','model_version','timestamp_utc')},screenshots=screenshots,validations=[{'check':k,'passed':bool(v)} for k,v in validations],smoke=smoke,git_private_path_count=len(blocked))

def model_rows(d):
    vals={x['model']:x['rmse'] for x in d['models'] if x['split']=='validation'}
    return [[r['model'],number(vals.get(r['model']),0),number(r['r2'],4),number(r['mae'],0),number(r['rmse'],0),percent(r['mape_pct'])] for r in d['models'] if r['split']=='test']

def bench_rows(d):
    return [[str(r.get('scenario','Unknown')),str(r.get('requests','?')),percent(r.get('success_pct')),number(r.get('p95_ms')),number(r.get('requests_per_second')),number(r.get('successful_properties_per_second'))] for r in d['results']]

def test_lines(d):
    t=d['tests']; p=t.get('python',{}); c=d['coverage'];
    return [f"Python: {p.get('passed','Not available')} passed; {p.get('failure','?')} failures; {p.get('error','?')} errors; {p.get('skipped','?')} skipped" if p else 'Python test summary not available.',f"JavaScript: {('PASS' if t['javascript_exit']==0 else 'FAIL / not run') if 'javascript_exit' in t else 'Not available'}",f"Backend line coverage: {percent(c.get('backend',{}).get('percent'))}",f"Backend + ML pipeline line coverage: {percent(c.get('backend_and_ml_pipeline',{}).get('percent'))}",f"Recorded HTTP integration: {sum(x.get('passed') is True for x in d['checks'])}/{len(d['checks'])} passed" if d['checks'] else 'Recorded HTTP integration: Not available.']

def status_note(d):
    return 'Reference edition — archived Phase 3 build results, not the latest Mac run.' if d['reference'] else 'Local edition — values read from existing local reports; not a new training run.'

def sections(d):
    q=d['quality']; s=d['split']; m=d['metrics']
    return [
      ('Executive summary',['Task 6 capstone integrates regression, data engineering, MLOps, an authenticated API, React dashboard, observability and deployment. It estimates prices in unspecified source units; it is a learning demonstration, not an appraisal service.']),
      ('Data and methodology',[f"Primary dataset: house_prices.csv; {q.get('rows','Not available')} rows, {q.get('missing_cells','?')} missing cells and {q.get('duplicate_rows','?')} duplicate rows in the recorded quality audit.",f"Split (seed 42): {s.get('train','?')} train, {s.get('validation','?')} validation, {s.get('test','?')} test. Other supplied datasets (churn, supermarket sales) are inventory/reference only.",f"Six raw predictors: Area, Bedrooms, Bathrooms, Age, Location, Property_Type. Two ratios, one-hot categories and standardized numeric inputs; {d['feature_count'] or '?'} transformed features. Property_ID and Price excluded from predictors. Fit on training only and refit preprocessing within CV folds."]),
      ('Model selection and evaluation',[f"Validation-selected model: {d['selected']}. Five classical candidates use training-only 5-fold CV; the MLP uses validation early stopping. Winner chosen by lowest validation RMSE; the held-out test is not used for tuning.",f"Held-out R² {number(m.get('r2'),4)}; MAE {number(m.get('mae'),0)}; RMSE {number(m.get('rmse'),0)}; MAPE {percent(m.get('mape_pct'))}. R² is not percentage accuracy. Error magnitudes use unspecified source units."]),
      ('MLOps and application',['MLflow records six experiment runs; only the winning model is serialized. SHA-256 tracks data/splits and model lineage; SQLite registry uses candidate/champion aliases. FastAPI supports authenticated single and batch predictions (up to 100), validation and training-sample analytics. React uses a server-side gateway, CSV batch upload, local model sensitivity and reports. Area is an integer to match the registry signature.']),
      ('Monitoring and security',['Prometheus captures HTTP status, request volume and latency; Grafana displays metrics. Rolling PSI uses 200 recent successful property predictions, at least 30 observations, with 0.25 a heuristic alert threshold. Synthetic drift demonstrations remain separate. Drift is not evidence of accuracy degradation. API key stays server-side; incorrect or missing keys are rejected. No public production security audit.']),
      ('Testing and benchmarks',test_lines(d)+['Coverage is Python line coverage for backend and backend + ML pipeline; frontend tests are separate. Benchmarks use repeated demo requests on the local host; not production capacity. Latency is for successful requests.', ('Benchmark context: '+', '.join(f'{k}={v}' for k,v in d['bench_context'].items() if v is not None)) if d['results'] else 'Benchmark context unavailable.']),
      ('Deployment and reproducibility',['Docker Compose runs application, Prometheus and Grafana. The source-only image mounts a private verified champion snapshot; GitHub Actions builds and tests source without private data. Kubernetes and AWS Terraform configurations are included as alternatives; cloud infrastructure is not asserted to be provisioned.','Launch from the existing project root: python scripts/run_phase9.py; check with python scripts/run_phase9.py smoke. Phase guides document earlier launchers.']),
      ('Limitations and responsible use',['Small held-out test, unknown currency and area units, no verified time/geographic representativeness, no uncertainty intervals or external market validation. Sensitivity changes individual inputs and is not causal or SHAP. No live market feed. Keep data, model, registry, private reports and credentials local until authorized.','Manual verification still required: remote repository contents and Actions outcome; authorized real HTTPS hosting if required; evaluator access and portal submission. Screenshot presence is not proof of content.'])]

def write_md(out, d):
    def table(h, rows): return '\n'.join(['| '+' | '.join(h)+' |','| '+' | '.join(['---']*len(h))+' |']+['| '+' | '.join(r)+' |' for r in rows])
    text='# '+TITLE+'\n\n'+status_note(d)+'\n\n'
    for heading, paras in sections(d):
        text+='## '+heading+'\n\n'+'\n\n'.join(paras)+'\n\n'
        if heading.startswith('Model selection') and model_rows(d): text+=table(['Model','Val RMSE','Test R²','MAE','RMSE','MAPE'],model_rows(d))+'\n\n'
        if heading=='Testing and benchmarks' and bench_rows(d): text+=table(['Scenario','Requests','Success','P95 ms','Req/s','Properties/s'],bench_rows(d))+'\n\n'
    (out/'technical_report.md').write_text(text)
    m=d['metrics']; (out/'model_card.md').write_text(f'''# Model card | RealEstatePricePredictor\n\n{status_note(d)}\n\n**Model:** {d['selected']} (validation-selected). Registry alias: champion (verify current registry before deployment).\n\n**Intended use:** local learning and property price estimation for inputs similar to the supplied dataset. Not for lending, appraisal, financial decisions or live market valuations.\n\n**Inputs:** Area (positive integer), Bedrooms and Bathrooms (positive integers), Age (nonnegative integer), Location and Property_Type (known categories). Price and area units are unspecified.\n\n**Evaluation:** {d['split'].get('test','?')} held-out properties; R² {number(m.get('r2'),4)}, MAE {number(m.get('mae'),0)}, RMSE {number(m.get('rmse'),0)}, MAPE {percent(m.get('mape_pct'))}. Selection by validation RMSE; no test-driven tuning.\n\n**Risks:** small sample, unverified representativeness, no calibrated intervals, possible drift and poor extrapolation. Fairness across groups not established. Sensitivity is not causality.\n\n**Operational controls:** authenticated API, input checks, versioned snapshot, PSI and latency monitoring. Compare predictions against future labeled data before claiming production accuracy. Do not redistribute model or data without permission.\n\n**Sources:** reports/phase3_model_summary.json, reports/phase3_model_comparison.csv, reports/preprocessing_report.json.\n''')
    evidence=['# Final verification','',status_note(d),'','Automated checks are based on existing reports unless stated. A PASS is not approval to submit.','',f"Local Docker smoke: {d['smoke']}",'']
    for v in d['validations']: evidence.append(f"- [{'x' if v['passed'] else ' '}] {v['check']}")
    evidence+=['','## Evidence files (presence only)','']+[f"- [{'x' if x['found'] else ' '}] {x['found'] or x['expected']}" for x in d['screenshots']]+['','## Manual gates (always review)','- [ ] Verify GitHub remote file tree and successful Actions run.','- [ ] Confirm evaluator access and authorization for any shared results.','- [ ] If required, deploy authorized HTTPS application and verify real prediction.','- [ ] Inspect screenshots and redact secrets; do not publish personal data.','- [ ] Confirm official portal requirements and submit; save confirmation privately.','']
    (out/'verification.md').write_text('\n'.join(evidence)); (out/'verification.json').write_text(json.dumps({'checks':d['validations'],'screenshots':d['screenshots'],'smoke':d['smoke'],'private_path_count':d['git_private_path_count'],'manual_review_required':True},indent=2))


def write_docx(out,d):
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    doc=Document(); sec=doc.sections[0]; sec.top_margin=Inches(.7); sec.bottom_margin=Inches(.65); sec.left_margin=sec.right_margin=Inches(.75)
    normal=doc.styles['Normal']; normal.font.name='Calibri'; normal.font.size=Pt(11); normal.paragraph_format.space_after=Pt(7)
    for name in ('Title','Heading 1','Heading 2'):
        doc.styles[name].font.color.rgb=RGBColor.from_string('164B50')
    sec.header.paragraphs[0].text='THE DEVELOPERS ARENA   /   TASK 6'
    sec.footer.paragraphs[0].text='RealEstate AI  |  Technical report  |  Review before distribution'
    doc.add_heading(TITLE,0); doc.add_paragraph('Technical project report • Data Science Capstone',style='Subtitle')
    doc.add_paragraph(status_note(d));
    def add_table(headers,rows):
        t=doc.add_table(rows=1,cols=len(headers)); t.style='Light Shading Accent 1'
        for c,h in zip(t.rows[0].cells,headers): c.text=h
        for row in rows:
            for c,v in zip(t.add_row().cells,row): c.text=v
        for row in t.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for r in p.runs: r.font.size=Pt(9)
    for i,(heading,paras) in enumerate(sections(d)):
        if i in (2,4,6): doc.add_page_break()
        doc.add_heading(heading,1)
        for p in paras: doc.add_paragraph(p)
        if i==2 and model_rows(d): add_table(['Model','Val RMSE','Test R²','MAE','RMSE','MAPE'],model_rows(d))
        if i==5 and bench_rows(d): add_table(['Scenario','N','Success','P95 ms','Req/s','Prop/s'],bench_rows(d))
    doc.add_heading('Evidence sources',1)
    doc.add_paragraph('reports/data_quality.json; reports/preprocessing_report.json; reports/phase3_model_summary.json; reports/phase3_model_comparison.csv; reports/phase8/test_summary.json, integration.json and benchmark.json (when available). See verification.md for evidence checks.')
    doc.save(out/'technical_report.docx')

def write_pptx(out,d):
    from pptx import Presentation
    from pptx.util import Inches,Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN
    prs=Presentation(); prs.slide_width=Inches(13.333); prs.slide_height=Inches(7.5)
    C={'dark':'15343D','teal':'187E75','muted':'527078','paper':'F1F5F3','white':'FFFFFF','line':'D9E6E1','light':'B6E9D9','ink':'19343D'}
    def color(v): return RGBColor.from_string(C.get(v,v))
    def rect(s,x,y,w,h,fill):
        q=s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h)); q.fill.solid(); q.fill.fore_color.rgb=color(fill); q.line.fill.background(); return q
    def text(s,x,y,w,h,t,size=20,fg='ink',bold=False):
        sh=s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf=sh.text_frame; tf.word_wrap=True; tf.margin_left=tf.margin_right=Inches(0); tf.margin_top=tf.margin_bottom=Inches(0)
        p=tf.paragraphs[0]; p.text=str(t); p.font.name='Calibri'; p.font.size=Pt(size); p.font.bold=bold; p.font.color.rgb=color(fg); return sh
    def slide(k,title,sub=''):
        s=prs.slides.add_slide(prs.slide_layouts[6]); s.background.fill.solid(); s.background.fill.fore_color.rgb=color('paper'); rect(s,0,0,13.333,.13,'teal'); text(s,.55,.32,12,.35,'THE DEVELOPERS ARENA   /   DATA SCIENCE CAPSTONE',12,'teal',True); text(s,.55,.85,12.2,.68,title,32,'ink',True); text(s,.55,1.58,12.2,.45,sub,16,'muted'); rect(s,.55,7.03,12.2,.015,'line'); text(s,.55,7.13,11,.23,'REFERENCE • archived Phase 3 results' if d['reference'] else 'TASK 6 • local report evidence; verify before sharing',10,'muted'); text(s,12.2,7.12,.6,.25,f'{k:02d}',11,'muted',True); return s
    def cards(s,items):
        for i,(head,body) in enumerate(items):
            x=.55+(i%2)*6.19; y=2.1+(i//2)*2.24; rect(s,x,y,6.0,2.05,'white'); rect(s,x,y,.07,2.05,'teal'); text(s,x+.23,y+.20,5.55,.4,head,21,'teal',True); text(s,x+.23,y+.74,5.55,1.17,body,18)
    def gridtable(s,headers,rows,widths,fs=15):
        x=.55; y=2.13; rowh=.54; total=sum(widths)
        for i,row in enumerate([headers]+rows):
            rect(s,x,y+i*rowh,total,rowh-.02,'dark' if i==0 else ('white' if i%2 else 'line')); xx=x
            for v,w in zip(row,widths): text(s,xx+.09,y+i*rowh+.10,w-.17,.39,v,fs,'white' if i==0 else 'ink',i==0); xx+=w
    s=prs.slides.add_slide(prs.slide_layouts[6]); s.background.fill.solid(); s.background.fill.fore_color.rgb=color('dark'); rect(s,.65,.65,.13,5.9,'teal'); text(s,1.02,.7,11.8,.35,'THE DEVELOPERS ARENA   /   TASK 6',16,'light',True); text(s,1.02,1.65,11.5,2.0,'RealEstate AI\nProperty intelligence platform',49,'white',True); text(s,1.04,4.1,10.9,.9,'Regression  ·  MLOps  ·  FastAPI  ·  React  ·  Observability',22,'light'); text(s,1.04,5.7,11,.8,status_note(d),17,'white')
    s=slide(2,'Problem & solution','A reproducible learning platform rather than a commercial valuation service.'); cards(s,[('Problem','Estimate property price from structured property attributes.'),('User workflow','Enter a property or upload a CSV; receive estimates and explanations.'),('Engineering goal','Connect model selection, registry, API, UI, monitoring and deployment.'),('Boundary','No verified currency, live market feed or calibrated uncertainty.')])
    q=d['quality']; a=d['split']; s=slide(3,'Dataset & split','House prices are the only modeling dataset.'); cards(s,[('Primary data',f"{q.get('rows','?')} rows; {q.get('missing_cells','?')} missing cells; {q.get('duplicate_rows','?')} duplicate rows in audit."),('Train / validation / test',f"{a.get('train','?')} / {a.get('validation','?')} / {a.get('test','?')} properties; seed 42."),('Inputs','Area, Bedrooms, Bathrooms, Age, Location, Property_Type.'),('Reference only','Churn and supermarket datasets are not joined to house prices.')])
    s=slide(4,'Leakage-aware feature engineering','Preprocessing is fitted on the training partition and within CV folds.'); cards(s,[('Numerical','Standardized raw numeric features and two ratios.'),('Categorical','One-hot Location and Property_Type.'),('Feature count',f"{d['feature_count'] or '?'} transformed features; target and ID excluded."),('Selection','Validation RMSE decides winner; held-out test used for evaluation only.')])
    s=slide(5,'Six-model comparison','Validation RMSE selects the champion; held-out metrics are reported separately.'); rows=model_rows(d); gridtable(s,['Model','Val RMSE','Test R²','Test MAE','Test RMSE','MAPE'],rows,[2.85,2.0,1.3,2.0,2.0,1.8],14) if rows else text(s,.6,2.3,11,1,'Comparison report not available.',24); text(s,.6,6.25,12,.45,'Price errors use unspecified source units. R² is not accuracy percentage.',16,'muted')
    m=d['metrics']; s=slide(6,'Held-out model evaluation',f"Selected on validation RMSE: {d['selected']}")
    rect(s,.55,2.12,7.65,4.6,'white'); text(s,.77,2.33,7.1,.4,'Test MAPE (%) | lower is better',20,'teal',True)
    rows=sorted([r for r in d['models'] if r['split']=='test' and math.isfinite(r['mape_pct'])],key=lambda r:r['mape_pct']); mx=max([r['mape_pct'] for r in rows]+[1])
    for i,r in enumerate(rows):
        y=2.96+i*.55; text(s,.77,y,2.35,.38,r['model'],15); rect(s,3.12,y+.04,3.75*r['mape_pct']/mx,.24,'teal' if r['model']==d['selected'] else '9DB9B8'); text(s,6.98,y-.02,1.0,.4,percent(r['mape_pct']),14,'ink',r['model']==d['selected'])
    if not rows: text(s,.77,3.1,7,1,'Comparison report unavailable.',20,'muted')
    for i,(h,v) in enumerate([('R²',number(m.get('r2'),4)),('MAE',number(m.get('mae'),0)),('RMSE',number(m.get('rmse'),0))]):
        y=2.12+i*1.55; rect(s,8.38,y,4.37,1.4,'white'); text(s,8.61,y+.15,3.95,.32,h,16,'teal',True); text(s,8.61,y+.55,3.95,.56,v,28,'ink',True)
    text(s,.8,6.35,7.1,.32,f"{a.get('test','?')} held-out rows; MAE/RMSE in unspecified source units.",13,'muted')
    s=slide(7,'MLOps & API','Reproducible artifacts and authenticated inference.'); cards(s,[('MLflow','Six imported runs; only the winner serialized. Candidate/champion aliases.'),('Lineage','SHA-256 dataset, split and model fingerprints.'),('FastAPI','Single and batch predictions (up to 100); strict integer area.'),('Security','API key server-side; input validation and unauthorized rejection.')])
    s=slide(8,'React intelligence dashboard','Six workspace views connect to the existing API.'); cards(s,[('Prediction','Property input form; actual estimate and model version.'),('Batch','CSV validation, upload and prediction export.'),('Analytics','Training-sample location and type comparisons.'),('Explainability','Local sensitivity analysis; not causal or SHAP. Model reports.')])
    s=slide(9,'Monitoring & alerts','Observe request quality and distribution shift.'); cards(s,[('Prometheus','Request counts, HTTP status, prediction latency and scrape health.'),('Grafana','Provisioned dashboard and separate demo metrics.'),('Drift','Rolling 200 properties; minimum 30; PSI threshold 0.25.'),('Limitations','Demonstration traffic is not customer traffic; drift is not accuracy loss.')])
    s=slide(10,'Quality assurance & benchmarks','Local Phase 8 measurements only; missing evidence stays missing.'); lines=test_lines(d); text(s,.65,2.08,12,1.58,'\n'.join(lines),18); br=bench_rows(d); 
    if br:
        # Compact second table below test summary.
        for i,row in enumerate([['Scenario','N','Success','P95 ms','Req/s','Prop/s']]+br):
            y=3.88+i*.56; rect(s,.55,y,12.15,.54,'dark' if i==0 else 'white'); x=.55
            for val,w in zip(row,[3.35,1.1,1.7,1.8,2.0,2.2]): text(s,x+.08,y+.1,w-.15,.33,val,14,'white' if i==0 else 'ink',i==0); x+=w
    else: text(s,.65,4.12,11,1,'Benchmark report unavailable in this edition.',22,'muted',True)
    text(s,.65,6.45,12,.35,'Local demo workload; not a production capacity claim.',14,'muted')
    s=slide(11,'Deployment architecture','Source-only image plus separately mounted private runtime.');
    for i,(h,b) in enumerate([('GitHub Actions','Source tests + image build'),('Docker app','React + FastAPI'),('Private model','Champion snapshot'),('Monitoring','Prometheus + Grafana')]):
        x=.55+i*3.07; rect(s,x,2.5,2.91,2.25,'white'); text(s,x+.18,2.75,2.55,.55,h,20,'teal',True); text(s,x+.18,3.48,2.55,.85,b,18)
    text(s,.65,5.22,12,1.1,'Kubernetes and AWS Terraform are deployment configurations. Actual remote CI, cloud hosting and evaluator access require verification.',21)
    s=slide(12,'Conclusion & demonstration','Show evidence, disclose limitations, and verify before submission.'); cards(s,[('Demonstrate','Single and CSV batch predictions; show model registry and monitoring.'),('Verify','Run Phase 9 smoke test; inspect Phase 8 results and screenshots.'),('Protect','Keep data, model, API keys and private reports out of Git.'),('Next steps','Confirm Actions, authorized cloud deployment if required, and portal submission.')])
    prs.save(out/'realestate_ai_presentation.pptx')

def generate(root,out,deck,reference=False,live=False):
    out.mkdir(parents=True,exist_ok=True); deck.mkdir(parents=True,exist_ok=True)
    d=collect(root,reference,live); write_md(out,d); write_docx(out,d); write_pptx(deck,d)
    return d

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--setup',action='store_true'); p.add_argument('--live',action='store_true',help='Run existing Phase 9 local smoke check'); p.add_argument('--verify-only',action='store_true',help='Read evidence without creating outputs'); a=p.parse_args()
    if a.setup: subprocess.run([sys.executable,'-m','pip','install','-r',str(ROOT/'requirements-phase10.txt')],check=True,cwd=ROOT)
    d=collect(ROOT,live=a.live) if a.verify_only else generate(ROOT,ROOT/'reports/phase10',ROOT/'presentation/phase10',live=a.live)
    for v in d['validations']: print(('PASS  ' if v['passed'] else 'REVIEW  ')+v['check'])
    print(f"PNG evidence present: {sum(bool(x['found']) for x in d['screenshots'])}/40 (presence only)")
    print('PHASE 10 DOCUMENTS GENERATED' if not a.verify_only else 'PHASE 10 VERIFICATION COMPLETE')
    print('Manual review required: GitHub Actions, cloud if required, reviewer access and submission. Never share secrets.')
    return 0 if all(v['passed'] for v in d['validations']) else 1
if __name__=='__main__':
    sys.exit(main())
