# Task 6 — Phase 6 | RealEstate AI dashboard

This additive upgrade uses the existing Phase 5 API (8006) and serves a separate React application through a loopback-only FastAPI gateway (5176). It does not change the original frontend, saved models, datasets, registry or earlier source files. Use your existing `.venv`, Node.js 22 and npm. The earlier Phase 5 `Area: Annotated[int, Field(gt=0)]` fix must remain in place; the champion alias must point to the selected ready registered model. MLflow's web UI does not need to be running because Phase 5 loads the local registry directly.

## Install from the Task 6 root

```sh
unzip -n ~/Downloads/Task_6_Phase_6_React_Dashboard_Upgrade.zip -d .
source .venv/bin/activate
python scripts/run_phase6.py --setup
```

Use the actual download path if different. Do not replace entire folders. Stop the old foundation frontend if port 5176 is occupied. An existing Phase 5 API on 8006 is reused only if its version, model readiness and key check pass. Otherwise stop your own old backend first. No arbitrary processes are killed. With no API on 8006 the launcher starts Phase 5 itself and stops that child when exiting. The launcher runs the new tests, builds React, checks the live registry-backed API through the gateway, and serves the dashboard. The first npm install needs internet access. Open http://127.0.0.1:5176 in Chrome after the server is ready. Do not close the terminal. Normal launch: `python scripts/run_phase6.py`. Tests only: `python scripts/run_phase6.py test` (tests don't need a running model or npm dependencies). Results: `reports/phase6_test_results.txt`.

## Capture screenshots (Command + Shift + 4)

Save in the existing `screenshots/` directory. Capture actual results; no API key, raw private data or mock result screens.

| File | Page and action |
|---|---|
| 23_final_dashboard.png | Overview, wait until Champion connected; show model and historical sample cards. |
| 24_property_price_prediction.png | Price prediction; leave the example property or choose valid inputs, click Calculate estimate, show actual result. |
| 25_batch_prediction.png | Batch prediction; click Load example CSV then Predict all properties; show both estimates. Test file upload by downloading template, choosing it, then predicting. |
| 26_market_analytics.png | Market analytics; show training sample statistics and category charts. |
| 27_explainable_ai.png | Explainable AI; click Run sensitivity analysis, show baseline and actual signed changes. |
| 28_reports_dashboard.png | Model reports; choose Test, show six models and RMSE chart (scroll/zoom as needed). |

## Security and interpretation

The browser sends relative same-origin requests to the gateway. The gateway reads the current key using Phase 5's existing `get_key()` function; it forwards `X-API-Key` to the API only on the server side. It does not embed or send the key to React. It checks Host, Origin (if present), and a custom request header and only proxies a fixed route allowlist. These are local-demo safeguards, not user authentication: anyone with access to the local machine can use the dashboard. Do not expose either port publicly. The key and raw/processed files must remain excluded from Git; check the prior `.gitignore`. The app does not save CSV input or prediction results on the gateway. Export is initiated locally by the user. Existing reports/charts may contain derived data; confirm redistribution permission before publishing. Prediction units are unspecified. The analytics represent training-only historical data. The explanation is one-at-a-time input sensitivity using actual model predictions, not SHAP or causal attribution. Phase 3 metrics describe that historical evaluation snapshot; the dashboard checks the dataset hash and selected model name but not exact model binary identity.

## Verification limits

The gateway's 15 tests use a mock HTTP upstream and temporary reports. The JavaScript logic has 12 tests. JSX syntax and transpilation were checked with TypeScript. npm registry access and MLflow are unavailable in the package build environment, so no actual Vite bundle or live registry/browser integration was verified there. Run the launcher on your Mac to verify these; the live smoke checks fail closed if the model, predictions, analytics or reports are unavailable. No data, key, model or generated result is shipped in this ZIP.
