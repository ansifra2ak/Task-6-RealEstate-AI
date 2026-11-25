"""Run API and its same-container loopback gateway, exiting if either fails."""
import subprocess,sys,time,signal

def main():
    children=[]
    def stop(*_): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,stop)
    try:
        for mode in ('api','gateway'):
            children.append(subprocess.Popen([sys.executable,'-m','backend.phase9_runtime',mode]))
        while all(p.poll() is None for p in children): time.sleep(.5)
        return 1
    except KeyboardInterrupt: return 0
    finally:
        for p in children:
            if p.poll() is None: p.terminate()
        for p in children:
            try: p.wait(timeout=8)
            except subprocess.TimeoutExpired: p.kill(); p.wait()
if __name__=='__main__': raise SystemExit(main())
