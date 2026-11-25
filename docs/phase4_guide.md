# Phase 4 — MLflow, data versioning and model registry

## Safe installation on macOS

Open the existing Task 6 root in VS Code, activate `.venv` if needed, and run `unzip -n ~/Downloads/Task_6_Phase_4_MLOps_Upgrade.zip -d .` from the root (not its parent). If downloaded elsewhere, use its actual path. `-n` refuses to replace existing files. No original project files are included in this ZIP. Do not replace folders in Finder. Verify `ls scripts/run_phase4.py requirements-phase4.txt tests/test_phase4.py`.

`python scripts/run_phase4.py --setup` installs the additive requirements in the current virtual environment, verifies original data/splits and the saved model, imports Phase 3 reports, registers the validation-selected model, reloads it and checks prediction parity, executes all available tests, and launches the local dashboard at http://127.0.0.1:5006. Leave the terminal open while viewing the UI. Ctrl+C stops the server. Subsequent launches use `python scripts/run_phase4.py`.

If a required file is missing, restore only that file or rerun Phase 2 then Phase 3 from the existing launchers. Phase 4 does not retrain. The local model must be generated in the same compatible Python/ML environment; if package compatibility breaks, restore the previous versions or rerun Phases 2 and 3 after installation. Do not use untrusted joblib files.

## Data and model lineage

- Experiment: `Task 6 - Real Estate Model Comparison`; six imported runs with validation and test R2, MAE, RMSE and MAPE (percent), recorded tuning parameters, CV RMSE where applicable, timings, and neural epoch metrics. No invented metrics or timings. Only the winner's serialized model was saved by Phase 3; remaining runs are metrics/parameter records, not five additional deployable models.
- Validation RMSE determines selection; the frozen test set is checked for parity with the saved report, not used for promotion or selection. Phase 4 wraps the exact saved Phase 3 joblib bundle in an MLflow PythonModel with six raw predictors and the same feature ratios and transformations. Its runtime package versions are recorded. Source currency is unspecified.
- `reports/phase4_data_version.json`: SHA-256 data version, inventory of all three CSVs, deterministic split checksums, row counts, input hashes and model hash. Only house prices are modeled; other CSVs are inventory. This is hash-based versioning, not a DVC remote or dataset storage service.
- `reports/phase4_registry_status.json`: run IDs, registered model version, aliases and registry parity result. The same input checksum set reuses completed runs and existing version; changed reports/model create a new import. Do not run concurrent import processes or move the project while MLflow is active.
- Model name `RealEstatePricePredictor`; `candidate` points to the current import; first verified version becomes `champion` for this local demo. Later candidates do not automatically replace the champion. This is local model management, not production deployment or approval governance.
- SQLite database in `mlruns/phase4.sqlite`; model and run artifacts in `mlartifacts/phase4/`. Existing `.gitignore` excludes these directories, raw/processed CSVs, model files and environment. Keep those private and do not upload raw data or model bundles without permission. Verify screenshots and reports before public commit. The server binds only to loopback; it is not a public authenticated server. MLflow telemetry disabled by launcher. Do not expose the dashboard to the internet.

## Launcher commands

| Command | Purpose |
|---|---|
| `python scripts/run_phase4.py --setup` | Install, import, test and start dashboard |
| `python scripts/run_phase4.py` | Verify and resume, then start dashboard |
| `python scripts/run_phase4.py prepare` | Import, register and test without server |
| `python scripts/run_phase4.py serve` | Start existing local MLflow UI |
| `python scripts/run_phase4.py test` | Run all available project tests |
| `python scripts/run_phase4.py status` | Show recorded registry status |
| `python scripts/run_phase4.py promote` | Smoke-test candidate and assign champion |
| `python scripts/run_phase4.py promote --version 2` | Promote specified existing version |
| `python scripts/run_phase4.py rollback --version 1` | Restore specified existing version after smoke test |

Use real version numbers from Models UI, not hypothetical ones. Rollback to a different model needs at least two actual registered versions; do not invent versions or retrain merely to manufacture evidence. Alias events are recorded in `mlruns/phase4_alias_history.jsonl`. The integration test uses a temporary database and temporary second version to exercise promotion and rollback without changing the real registry.

## Screenshots 16–18

1. **16_mlflow_experiments.png** — browser, http://127.0.0.1:5006, Experiments → Task 6 - Real Estate Model Comparison. Capture the six model runs; show validation_rmse, test_r2 or test_mape_pct columns if available in the run-table column selector. Select the current six runs if more than one import exists.
2. **17_model_registry.png** — browser, Models (sometimes labeled Registered Models) → RealEstatePricePredictor → registered version. Capture the actual version and `candidate`/`champion` aliases. Do not claim more versions than exist.
3. **18_data_versioning.png** — VS Code, reports → phase4_data_version.json. Show `dataset_version`, primary dataset, verified inventory, and split hashes; zoom out as needed, do not expose raw records. Save these three images into the original `screenshots/` folder. macOS: Cmd+Shift+4.

## Build verification and limitations

The merged original Phase 1–3 build was tested in Linux Python 3.13.5 against its actual saved model and reports: 41 passed and 1 skipped (13 new Phase 4 non-MLflow tests plus the 28 prior tests). MLflow could not be installed in the build environment; registry round-trip, server and alias integration must be confirmed on the user's Mac. No fake registry, dashboard screenshots or generated results are bundled. The launcher runs the MLflow integration test and reports any error before opening the UI.

API reference: https://mlflow.org/docs/latest/api_reference/python_api/mlflow.pyfunc.html ; https://mlflow.org/docs/latest/ml/model-registry/tutorial/ ; https://mlflow.org/docs/latest/api_reference/cli.html
