# RealEstate AI | Task 6 capstone

AI-powered property price prediction and intelligence platform built for The Developers Arena Data Science internship. This is a local demonstration, not an appraisal, lending or live market valuation service. Source currency and area units are unspecified.

## Capabilities

- Data validation, reproducible train/validation/test split, leakage-aware preprocessing and six regression candidates.
- MLflow experiment tracking, checksum data versioning and candidate/champion aliases.
- FastAPI authenticated single and batch predictions, training-sample analytics and strict input validation.
- React dashboard with CSV batch upload, model sensitivity and model evaluation reports; API key stays in a server-side gateway.
- Prometheus metrics, Grafana dashboard, rolling PSI distribution drift and separate simulation alerts.
- Automated Python and JavaScript tests, scoped coverage gates, local concurrent HTTP benchmarks.
- Docker Compose, source-only GitHub Actions build, Kubernetes and AWS Terraform deployment configurations.

## Architecture

React dashboard (5176) → local gateway → FastAPI (8006) → verified MLflow champion snapshot. Prometheus (9090) scrapes API metrics; Grafana (3000) displays monitoring. Docker Compose provides the local runtime. Cloud templates require separate authorization and deployment; GitHub Actions does not prove cloud hosting.

## Local setup

Prerequisites: Python 3.12, compatible ML dependencies, Node.js/npm, Docker Desktop. This source repository deliberately omits private datasets, trained model and registry, generated reports and credentials. An authorized local copy with the original data and saved model is required for full inference.

```bash
source .venv/bin/activate
open -a Docker
python scripts/run_phase9.py --setup
python scripts/run_phase9.py smoke
```

Open http://127.0.0.1:5176. Stop using `python scripts/run_phase9.py stop`. For earlier training use the phase guides in `docs/` and corresponding launchers. The source-only CI tests are not the same scope as the full local Phase 8 tests.

## Evaluation and documentation

Run `python scripts/run_phase10.py --setup --live` from the existing project root to generate the local technical report, model card, evidence checklist and presentation from Phase 3 and 8 reports. Missing metrics are marked unavailable; the launcher never retrains. Review `reports/phase10/verification.md` and the generated presentation. The original root README remains preserved.

## Responsible use

Only house_prices.csv is modeled; the other supplied datasets are references. Small test set, no verified real-world representativeness, currency, area units or confidence intervals. Model sensitivity is not causal analysis. Drift is not accuracy degradation. Never publish supplied data, artifacts, registry database, secrets, screenshots or private reports without authorization. No production security or accuracy certification. See the Phase 9 cloud guide for prerequisites and costs; verify actual hosted URL and evaluator access before claiming cloud deployment.
