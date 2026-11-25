"""Run model development and test suite in the activated environment."""
import sys, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'ml-pipeline/training'))
from phase3 import train

def main():
    print('PHASE 3 — MACHINE LEARNING',flush=True)
    train(ROOT)
    result=subprocess.run([sys.executable,'-m','pytest','-q'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    (ROOT/'reports/phase3_test_results.txt').write_text(result.stdout)
    print(result.stdout,flush=True)
    if result.returncode: raise SystemExit(result.returncode)
    print('PHASE 3 COMPLETE — six trained candidates; selected artifact saved.',flush=True)
if __name__=='__main__': main()
