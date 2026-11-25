"""Task 6 Phase 4: setup, validate, register, serve, and manage models."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ml-pipeline/registry'))
os.environ['MLFLOW_ENABLE_TELEMETRY'] = 'false'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', default='run', choices=['run','prepare','serve','test','status','promote','rollback'])
    parser.add_argument('--setup', action='store_true', help='Install Phase 4 requirements first')
    parser.add_argument('--version', help='Explicit registry version for promote/rollback')
    args = parser.parse_args()
    if args.action == 'rollback' and not args.version:
        parser.error('rollback requires --version N')
    if args.version and args.action not in ('promote','rollback'):
        parser.error('--version applies only to promote or rollback')
    if args.setup:
        subprocess.run([sys.executable,'-m','pip','install','-r',str(ROOT/'requirements-phase4.txt')], cwd=ROOT, check=True)
    from phase4 import snapshot, register_snapshot, configure, change_alias, read
    import json
    if args.action in ('run','prepare'):
        print('PHASE 4 — MLOPS: verifying local Phase 3 artifacts', flush=True)
        status = register_snapshot(snapshot(ROOT), ROOT)
        print(json.dumps(status,indent=2),flush=True)
        run_tests()
        print('PHASE 4 COMPLETE — registry prediction parity verified',flush=True)
    if args.action == 'test':
        run_tests()
    if args.action == 'status':
        print(json.dumps(read(ROOT/'reports/phase4_registry_status.json'),indent=2))
    if args.action in ('promote','rollback'):
        print(json.dumps(change_alias(ROOT,args.version,args.action),indent=2))
    if args.action in ('run','serve'):
        _,_,uri,artifacts=configure(ROOT)
        print('MLflow dashboard: http://127.0.0.1:5006 (Ctrl+C to stop)',flush=True)
        cli=Path(sys.executable).with_name('mlflow')
        try:
            subprocess.run([str(cli),'server','--backend-store-uri',uri,'--default-artifact-root',artifacts.as_uri(),'--no-serve-artifacts','--host','127.0.0.1','--port','5006','--workers','1'],cwd=ROOT,check=True)
        except KeyboardInterrupt:
            print('\nMLflow stopped; local experiments retained.')


def run_tests():
    import mlflow  # Required for the full registry integration test.
    p=subprocess.run([sys.executable,'-m','pytest','-q'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    (ROOT/'reports').mkdir(exist_ok=True)
    (ROOT/'reports/phase4_test_results.txt').write_text(p.stdout,encoding='utf-8')
    print(p.stdout,flush=True)
    if p.returncode:
        raise SystemExit(p.returncode)


if __name__=='__main__':
    try:
        main()
    except (FileNotFoundError, ValueError, ImportError, subprocess.CalledProcessError) as e:
        print(f'Phase 4 stopped: {e}',file=sys.stderr)
        sys.exit(1)
