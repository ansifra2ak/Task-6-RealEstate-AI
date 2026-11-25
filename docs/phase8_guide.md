# Task 6 — Phase 8: Quality assurance

## Safe installation (Mac, VS Code)

Open the existing Task 6 root. Download the archive to Downloads and extract without overwriting:

```bash
unzip -n ~/Downloads/Task_6_Phase_8_Testing_Upgrade.zip -d .
source .venv/bin/activate
```

Keep the Phase 5 integer Area correction. Phase 8 requires the existing raw data, Phase 2/3 outputs, and registered MLflow champion. No prior files need replacement. For the fullest live integration run, start Phase 7 in one terminal (Docker Desktop running) with `python scripts/run_phase7.py`, then open a second terminal and activate the virtual environment. Otherwise Phase 8 can start and stop a temporary Phase 5 API if port 8006 is free; dashboard/monitoring checks will be explicitly marked not run. An unrelated or outdated service on port 8006 must be stopped manually. Do not terminate unknown processes.

```bash
python scripts/run_phase8.py --setup
```

The default run executes all existing Python tests, including an isolated retraining exercise in temporary storage, JavaScript tests, coverage, live API security and integration checks, then benchmarks. It uses the Phase 5 key-loading helper and never prints the API key. Live tests and benchmark send demo property requests, which will affect Phase 7 live traffic counters and rolling drift window if that server is running. No real customer traffic or production capacity claims.

## Coverage scope

The 80% line coverage gate applies to all Python files under `backend/` and separately to the combined `backend/` and `ml-pipeline/` scope, including unexecuted source files. The frontend JavaScript test suite is reported separately, not counted as Python coverage. Launchers, tests, infrastructure and notebooks are not in the coverage denominator. Skips are not passes; the launcher returns nonzero if Python/JavaScript tests fail or skip (Python skips), either coverage gate fails, live integration fails or benchmark requests fail. Optional live dashboard/monitoring checks are identified as not run when services are absent; they must be run with Phase 7 for full integration evidence. These are HTTP checks, not browser interaction tests or complete Docker end-to-end validation.

## Evidence

- 33_automated_tests.png: VS Code terminal after Phase 8 displays Python totals, JavaScript status and both coverage percentages. Capture actual output; if failures occur, resolve them first.
- 34_test_coverage.png: in a new terminal run `open reports/phase8/coverage/index.html`; capture the detailed coverage table and total. `open reports/phase8/tests.html` shows the separate backend and combined gates.
- 35_performance_benchmarks.png: run `open reports/phase8/benchmark.html`; capture the actual benchmark table with latency, throughput and success rate (zoom out if necessary). Charts are also in this report. Do not substitute build-environment numbers.

Save screenshots under the existing `screenshots/` folder. Keep private keys and local raw data out of screenshots and GitHub.

## Generated reports

`reports/phase8/`: tests.html, test_summary.json, pytest.txt, pytest.xml, javascript.txt, coverage.json, coverage/index.html, integration.html, integration.json, benchmark.html, benchmark.json, latency.png and throughput.png. The hidden .coverage data file is local. Re-running replaces only Phase 8 report files. A temporary Phase 5 child may write its existing local startup metadata if its own implementation requires it; existing models and screenshots are not modified by Phase 8.

Other commands:

```bash
python scripts/run_phase8.py test
python scripts/run_phase8.py benchmark
python scripts/run_phase8.py benchmark --requests 100
```

Default benchmark: 60 measured requests in each of three scenarios (single sequential, single concurrent with four workers, batch of ten with four workers); three warmups per scenario excluded from measurements. Percentiles use successful requests only, and failed requests remain in the success-rate denominator. Results depend on hardware, system load and model version. A failure/skip or coverage below 80% is a real review item, not a reason to alter the reported numbers.
