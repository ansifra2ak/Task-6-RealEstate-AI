"""Run complete test suites, coverage, real HTTP checks and local benchmarks."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys
import time
from xml.etree import ElementTree

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from phase8_quality import integration, benchmark, coverage_totals, report, page, table
OUT=ROOT/'reports/phase8'

def run(command,cwd=ROOT,log=None,env=None):
    p=subprocess.run(command,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,env=env)
    print(p.stdout,flush=True)
    if log: (OUT/log).write_text(p.stdout)
    return p.returncode

def tests():
    # Keep coverage artifacts separate; no changes to the existing pytest configuration.
    env={**os.environ,'COVERAGE_FILE':str(OUT/'.coverage'),'MLFLOW_ENABLE_TELEMETRY':'false'}
    cfg=str(ROOT/'scripts/phase8.coveragerc')
    rc=run([sys.executable,'-m','coverage','run','--rcfile='+cfg,'-m','pytest','-ra','--junitxml='+str(OUT/'pytest.xml')],log='pytest.txt',env=env)
    totals=None
    for command in (['report','-m'],['json','-o',str(OUT/'coverage.json')],['html','-d',str(OUT/'coverage')]):
        if run([sys.executable,'-m','coverage',*command,'--rcfile='+cfg],env=env): raise RuntimeError('Coverage report failed')
    totals=coverage_totals(json.loads((OUT/'coverage.json').read_text()))
    suite=ElementTree.parse(OUT/'pytest.xml').getroot(); cases=list(suite.iter('testcase'))
    stats={s:sum(c.find(s) is not None for c in cases) for s in ('failure','error','skipped')}; stats['total']=len(cases); stats['passed']=len(cases)-sum(stats[k] for k in ('failure','error','skipped'))
    npm=shutil.which('npm'); js=run([npm,'test'],cwd=ROOT/'frontend/phase6',log='javascript.txt') if npm else 127
    if not npm: (OUT/'javascript.txt').write_text('npm missing; JavaScript tests not run.')
    gate=totals['backend']['percent']>=80 and totals['backend_and_ml_pipeline']['percent']>=80
    summary={'python':stats,'pytest_exit':rc,'javascript_exit':js,'coverage':totals,'backend_and_ml_pipeline_80_percent_gate':gate,'skips_require_review':stats['skipped']>0}
    (OUT/'test_summary.json').write_text(json.dumps(summary,indent=2))
    body='<section>'+table(['Suite','Result'],[['Python',f"{stats['passed']} passed; {stats['failure']} failed; {stats['error']} errors; {stats['skipped']} skipped"],['JavaScript','PASS' if js==0 else 'FAIL / not run'],['Python application 80% gate','PASS' if gate else 'FAIL']])+'</section><section>'+table(['Scope','Files','Covered lines','Statements','Line coverage'],[[k,v['files'],v['covered'],v['statements'],f"{v['percent']:.2f}%"] for k,v in totals.items()])+'<p>Gate requires at least 80% line coverage for the backend alone and for the backend plus ML pipeline combined. Launchers, tests, frontend and infrastructure are excluded from Python coverage; JavaScript test results are separate. Skips are not passes.</p><a href="coverage/index.html">Open detailed coverage</a> · <a href="pytest.txt">Python log</a> · <a href="javascript.txt">JavaScript log</a></section>'
    (OUT/'tests.html').write_text(page('Automated tests and code coverage',body))
    print(f"\nPYTHON: {stats['passed']} passed, {stats['failure']} failed, {stats['error']} errors, {stats['skipped']} skipped\nJAVASCRIPT: {'PASS' if js==0 else 'FAIL'}\nBACKEND COVERAGE: {totals['backend']['percent']:.2f}%\nBACKEND + ML PIPELINE: {totals['backend_and_ml_pipeline']['percent']:.2f}%\n80% APPLICATION COVERAGE GATE: {'PASS' if gate else 'FAIL'}\nReports: reports/phase8/tests.html",flush=True)
    return rc==0 and js==0 and gate and not stats['skipped']

def occupied(port):
    with socket.socket() as s:
        s.settimeout(.5); return s.connect_ex(('127.0.0.1',port))==0

def get_key():
    spec=importlib.util.spec_from_file_location('phase5_launcher',ROOT/'scripts/run_phase5.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod.get_key()

def live(args):
    import httpx
    key=get_key(); child=None
    try:
        if not occupied(8006):
            child=subprocess.Popen([sys.executable,'scripts/run_phase5.py','serve'],cwd=ROOT,env={**os.environ,'TASK6_API_KEY':key})
            for _ in range(150):
                if child.poll() is not None: raise RuntimeError('Phase 5 startup failed; review terminal output')
                try:
                    if httpx.get('http://127.0.0.1:8006/api/v1/health',timeout=1,trust_env=False).status_code==200: break
                except httpx.HTTPError: pass
                time.sleep(1)
            else: raise RuntimeError('API startup timed out')
        dash=occupied(5176); monitor=False
        try:
            r=httpx.get('http://127.0.0.1:8006/metrics',timeout=3,trust_env=False); monitor=r.status_code==200 and 'task6_api_requests_total' in r.text
        except httpx.HTTPError: pass
        checks,info,row=integration(key,dashboard=dash,monitoring=monitor)
        (OUT/'integration.json').write_text(json.dumps({'checks':checks,'dashboard_tested':dash,'monitoring_tested':monitor},indent=2))
        body='<section>'+table(['Check','Result'],[[x['check'],'PASS' if x['passed'] else 'FAIL'] for x in checks])+'</section><section><p>Dashboard: '+('tested' if dash else 'NOT RUN — start Phase 6 or 7')+'; monitoring: '+('tested' if monitor else 'NOT RUN — start Phase 7')+'. These are HTTP integration checks, not browser interaction or container end-to-end tests.</p></section>'
        (OUT/'integration.html').write_text(page('Live integration and security',body))
        for c in checks: print(('PASS ' if c['passed'] else 'FAIL ')+c['check'],flush=True)
        if not all(c['passed'] for c in checks): raise RuntimeError('Live integration failed; see integration.html')
        print('Dashboard:', 'tested' if dash else 'not running; skipped', '| Monitoring:', 'tested' if monitor else 'not running; skipped')
        print('Benchmarking actual local API with demonstration properties...',flush=True)
        results=benchmark(key,row,info['model_version'],requests=args.requests)
        context={'platform':platform.system()+' '+platform.machine(),'python':platform.python_version(),'model':info['selected_model'],'model_version':info['model_version'],'requests_per_scenario':args.requests,'monitoring_enabled':monitor,'dashboard_running':dash,'timestamp_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}
        report(OUT,results,context)
        for r in results: print(f"{r['scenario']}: {r['successful']}/{r['requests']} successful | p95 {r['p95_ms']} ms | {r['requests_per_second']:.2f} req/s")
        return all(r['failed']==0 for r in results)
    finally:
        if child and child.poll() is None:
            child.terminate()
            try: child.wait(timeout=10)
            except subprocess.TimeoutExpired: child.kill(); child.wait()

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('action',nargs='?',default='run',choices=['run','test','benchmark']); p.add_argument('--setup',action='store_true'); p.add_argument('--requests',type=int,default=60); a=p.parse_args()
    if not 10<=a.requests<=300: p.error('--requests must be 10–300')
    OUT.mkdir(parents=True,exist_ok=True)
    if a.setup: subprocess.run([sys.executable,'-m','pip','install','-r','requirements-phase8.txt'],cwd=ROOT,check=True)
    ok=True
    if a.action in ('run','test'): ok=tests()
    if a.action in ('run','benchmark'): ok=live(a) and ok
    print('\nPHASE 8 '+('CHECKS PASSED' if ok else 'REVIEW REQUIRED — test/coverage/benchmark failure or skipped test')+'\nReports: reports/phase8/',flush=True)
    return 0 if ok else 1
if __name__=='__main__':
    try: sys.exit(main())
    except KeyboardInterrupt: sys.exit(130)
    except Exception as e: print('Phase 8 stopped:',str(e),file=sys.stderr); sys.exit(1)
