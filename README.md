# RealEstate AI — Task 6 Capstone
AI-Powered Real Estate Price Prediction & Intelligence Platform | The Developers Arena | Phase 1 foundation, v0.1.0.

The starter has a working local API and React foundation screen. No trained model or production deployment is claimed. See [roadmap](docs/roadmap.md), [architecture](docs/architecture.md) and [data handling](docs/data.md).

## macOS (Apple Silicon) setup
Open only this folder in VS Code. Python 3.12 and Node.js 22 LTS are required. Check `python3.12 --version`, `node -v`, `npm -v`. If Node is missing, install Node 22 from nodejs.org or your existing version manager. If using Homebrew: `brew install node@22` and `export PATH="$(brew --prefix node@22)/bin:$PATH"`. Restart VS Code or configure your shell PATH if necessary.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python run.py --setup
python run.py
```

Setup installs only foundation dependencies, builds the frontend, checks dataset hashes and runs tests. Internet is required for pip/npm. On success, open http://127.0.0.1:5176 (dashboard), http://127.0.0.1:8006/docs (Swagger), http://127.0.0.1:8006/api/v1/health. Ctrl+C stops both services. `python run.py --check` repeats local data/tests. After initial install, retain `frontend/package-lock.json` for reproducibility.

## VS Code
Install Python and Python Debugger extensions. Select `.venv/bin/python` using Python: Select Interpreter. Run and Debug → Task 6 — Start API + React → F5. Use Ctrl+C in terminal to stop the launcher before switching to debug or Docker. No earlier task folder needs modification.

## Git and privacy
Initialize independent Git only from this folder when ready: `git init -b main`. Raw and processed data, secrets and model binaries are excluded by default. The manifest records original data hashes and schema but not records. Do not publish supplied data without authorization. Keep local project ZIP private. License choice for original code is pending; no third-party data license is asserted.

## Docker
The included Compose file is an API-only foundation scaffold; final multi-service deployment is a later phase. Stop local API before `docker compose up --build` if experimenting. Use `docker compose down` afterward. This starter Docker build has not been executed in the authoring environment.

## Evidence
Save actual screenshots in `screenshots/`: 01_project_structure.png, 02_environment_setup.png, 03_foundation_dashboard.png, 04_foundation_api.png, 05_foundation_tests.png. Do not create fake results. The rest of the folder hierarchy is reserved for later phases.
