"""Single local launcher. Run with the project's Python 3.12 interpreter."""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
FRONT = ROOT / 'frontend'
API_PORT, WEB_PORT = 8006, 5176


def run(cmd, cwd=ROOT):
    subprocess.run(cmd, cwd=cwd, check=True)


def tools():
    if sys.version_info[:2] != (3, 12):
        raise SystemExit('Use Python 3.12: activate .venv first (see README).')
    node, npm = shutil.which('node'), shutil.which('npm')
    if not node or not npm:
        raise SystemExit('Node.js 22 LTS and npm are required. See README.')
    major = int(subprocess.check_output([node, '--version'], text=True).strip().lstrip('v').split('.')[0])
    if major != 22:
        raise SystemExit('Use Node.js 22 LTS for this starter project.')
    return npm


def check():
    from backend.services.datasets import dataset_status
    statuses = dataset_status()
    print(json.dumps(statuses, indent=2))
    if any(s['status'] != 'verified' for s in statuses):
        raise SystemExit('Dataset missing or changed. Restore the supplied original CSVs.')
    run([sys.executable, '-m', 'pytest', '-q'])


def ports_free():
    for port in (API_PORT, WEB_PORT):
        with socket.socket() as s:
            try:
                s.bind(('127.0.0.1', port))
            except OSError:
                raise SystemExit(f'Port {port} is busy. Stop the specific Task 6 process; do not kill unrelated apps.')


def stop(children):
    for child in children:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for child in children:
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()


def serve(npm):
    ports_free()
    if not (FRONT / 'node_modules' / '.bin' / 'vite').exists():
        raise SystemExit('Frontend dependencies missing. Run python run.py --setup first.')
    children = []
    try:
        children.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', str(API_PORT)], cwd=ROOT, start_new_session=True))
        children.append(subprocess.Popen([npm, 'run', 'dev'], cwd=FRONT, start_new_session=True))
        for url in (f'http://127.0.0.1:{API_PORT}/api/v1/health', f'http://127.0.0.1:{WEB_PORT}'):
            for _ in range(60):
                if any(c.poll() is not None for c in children):
                    raise SystemExit('A service exited. Read the terminal logs.')
                try:
                    with urllib.request.urlopen(url, timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(0.5)
            else:
                raise SystemExit(f'Service did not become ready: {url}')
        print(f'\nDashboard: http://127.0.0.1:{WEB_PORT}\nAPI docs: http://127.0.0.1:{API_PORT}/docs\nPress Ctrl+C to stop both services.', flush=True)
        while all(c.poll() is None for c in children):
            time.sleep(0.5)
        raise SystemExit('A service stopped. See logs.')
    except KeyboardInterrupt:
        print('Stopping Task 6 services.')
    finally:
        stop(children)


def main():
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--setup', action='store_true')
    modes.add_argument('--check', action='store_true')
    args = parser.parse_args()
    npm = tools()
    if args.setup:
        run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
        run([npm, 'ci' if (FRONT / 'package-lock.json').exists() else 'install'], FRONT)
        run([npm, 'run', 'build'], FRONT)
        check()
    elif args.check:
        check()
    else:
        serve(npm)


if __name__ == '__main__':
    main()
