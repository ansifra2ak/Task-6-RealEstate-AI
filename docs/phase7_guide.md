# Task 6 — Phase 7: monitoring and observability

## Installation (Mac, VS Code)

Keep every existing Phase 1–6 file. From the Task 6 project root:

```sh
unzip -n ~/Downloads/Task_6_Phase_7_Monitoring_Upgrade.zip -d .
source .venv/bin/activate
```

The previous Phase 5 integer Area fix must remain in `backend/schemas/phase5.py`:
`Area: Annotated[int, Field(gt=0)]`. The registered `champion` must exist and be ready. Do not re-create it if it already works.

Open Docker Desktop and confirm the engine is running (`docker info`). Stop old Task 6 API/dashboard launchers with Ctrl+C in their original terminals. Leave unrelated processes alone. Ports 8006, 5176, 9090 and 3000 must be free. The MLflow web UI on 5006 is optional; the existing local registry remains in use.

```sh
python scripts/run_phase7.py --setup
```

The launcher installs dependencies, runs the new tests, builds the existing Phase 6 frontend through its launcher, starts the instrumented Phase 5 app and starts an isolated Docker Compose project called `task6phase7`. It checks actual registered-model single/batch predictions and key rejection, scrapes and dashboard provisioning before printing PHASE 7 READY. No original Python/React files are changed. Internet access is needed for dependencies/images not cached locally. First Docker image pulls and the React build may take time. Do not interrupt normal startup. Docker/Node dependencies are required.

## Browser pages

- React: http://127.0.0.1:5176
- API metrics: http://127.0.0.1:8006/metrics
- Prometheus: http://127.0.0.1:9090/query (or use the Query page)
- Grafana: http://127.0.0.1:3000/d/task6-phase7 (anonymous local viewer; no login)
- Drift JSON: http://127.0.0.1:8006/monitoring/drift
- Alerts: http://127.0.0.1:9090/alerts

Keep the launcher running. For additional observed test traffic, open a second terminal and use the dashboard to predict, or:

```sh
source .venv/bin/activate
python scripts/run_phase7.py load
```

This sends 40 valid training-sampled test properties through the actual API. It is demonstration traffic, not real customer requests. Existing startup checks are also included in observed traffic counts. The separate synthetic high-area demo does not enter live counters or windows. Wait for at least two scrapes and alert evaluations before taking screenshots; look at the actual status.

## Screenshot evidence

Use Cmd+Shift+4, save into the existing `screenshots/` folder. Do not include secrets.

29 `29_prometheus_metrics.png`: Prometheus Query page; run `sum by (route, status) (task6_api_requests_total)` as a table. Include nonzero single/batch 200 and intentional 401 counts. Alternatively use `up{job="task6-api"}` to diagnose the scrape. It should be 1.

30 `30_grafana_dashboard.png`: Grafana > Dashboards > Task 6 > Task 6 | RealEstate AI Monitoring. Capture the top overview, API scrape health, successful properties, status counts and latency. Use recent 15-minute time range; traffic is local test traffic.

31 `31_model_drift_monitoring.png`: Same Grafana dashboard, scroll to the LIVE and DEMO PSI panels. Use `load` to reach the 30-property minimum if needed. Capture both panels and their labels. The demo is intentionally shifted high-area resampling, not a claim of market drift. Alternative: `/monitoring/drift` aggregate JSON if chart unavailable.

32 `32_monitoring_alerts.png`: Prometheus Alerts page. Expand task6-monitoring. Capture the actual rules/status and the explicitly named Task6DemoDistributionDrift alert. Its firing state is expected once the demo is scraped and the 10s rule hold completes; verify instead of fabricating status. Live alerts should only fire when their conditions hold. No email or external notifications are configured.

## Monitoring details and limitations

- ASGI middleware observes actual HTTP status and request duration for the six fixed Phase 5 routes. It counts valid successful prediction rows only. Failed/unauthorized predictions never enter drift samples. Scrapes are excluded from request counts. No API key or request body is exported or logged by this instrumentation. Up to 200 input/output feature rows are retained in RAM only; counts reset on restart. No customer or property IDs are collected. Underlying API logging remains unchanged.
- PSI compares verified training reference feature distributions and model predictions on that reference against a rolling 200-property window. Numeric bins are based on reference quintiles (duplicates merged, extreme values included); categories use union counts and half-count smoothing. Minimum 30 observed properties; threshold 0.25 is a heuristic, not statistical proof. No outcome labels means no actual accuracy/concept drift measured. Demo uses 60 sampled high-area scenarios and real model predictions, separate from observed traffic. Price and area units are unspecified.
- Alerts: scrape unavailable, server-error ratio above 5% with at least 10 requests in two minutes, p95 prediction latency above 1s with at least 10 prediction requests in two minutes, live PSI and explicitly demo PSI. 401 does not count as a 5xx failure. Rule states are evaluated by Prometheus. Grafana shows firing counts, not independent notification delivery.
- Local only: Docker host ports are loopback-published, Grafana anonymous Viewer, API key server-side. This is not a production security design. Prometheus/Grafana state is session-scoped; capture screenshots before stopping. No new raw datasets, saved models or secret files in ZIP. Do not publish private data or API keys.

## Commands and troubleshooting

`python scripts/run_phase7.py` normal startup; `python scripts/run_phase7.py test` tests only; `python scripts/run_phase7.py load` sample API traffic; Ctrl+C stops launcher-owned processes and Compose containers. If necessary `python scripts/run_phase7.py stop` removes only Phase 7 Compose containers (does not stop standalone Python processes). Existing Phase 6 launcher can still be run by itself after stopping Phase 7.

If ports are busy, use `lsof -nP -iTCP:8006 -sTCP:LISTEN` (replace port as needed), identify the application and stop only your own old server. If Docker target is down, inspect Prometheus > Status > Targets and Docker Desktop host access. The scrape uses `host.docker.internal:8006` (Docker Desktop Mac). If the container cannot reach your loopback API, do not expose API to the LAN as a workaround; report the target error. If Docker daemon is down, start Docker Desktop. If the Area schema mismatch recurs, verify the earlier correction. If an error occurs before PHASE 7 READY, send terminal output without credentials.

## Build verification

24 tests passed in the packaging environment using the original Phase 5 router/service with a deterministic stand-in predictor for the integration test, plus mock ASGI and configuration checks. Real MLflow startup, Docker containers, PromQL rule execution and rendered Grafana panels were not run here; the launcher checks live API and scrape/dashboard availability on your Mac. Rule firing must be checked in the browser. No earlier file was overwritten in the package.
