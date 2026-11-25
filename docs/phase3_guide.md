# Phase 3 — Advanced model development

Apply this additive ZIP inside the existing Task 6 root, without overwriting foundation, Phase 2 or screenshots. Use Python 3.12 in the existing `.venv`.

1. `source .venv/bin/activate`
2. `python -m pip install -r requirements-phase3.txt`
3. If Phase 2 was not run locally, `python scripts/run_phase2.py`.
4. `python scripts/run_phase3.py`

If XGBoost reports a missing `libomp.dylib` on macOS, install the OpenMP runtime with `brew install libomp` and retry. Do not install it unless needed. Phase 3 verifies original dataset and split hashes before training. It does not modify Phase 1 or Phase 2 source files. It generates new phase3-prefixed outputs; rerunning replaces those outputs. Do not use the held-out test set to tune or select models.

Five classical regressors use five-fold training-only cross-validation, with preprocessing fitted within each fold. Neural Network is a scikit-learn MLPRegressor with 64 and 32 hidden units, train-only feature and target scaling and validation-based early stopping. Lowest validation RMSE determines the selected candidate before test predictions are calculated. No post-test refit. No TensorFlow is required for this phase. Price and area units are not confirmed; results describe this small supplied dataset, not a verified current real-estate market.

Generated locally: `models/phase3_best_model.joblib`, `models/phase3_metadata.json`, `data/processed/phase3_test_predictions.csv`, and the reports/charts below. The archive includes build-environment reports and charts for reference; use fresh local outputs for evidence. Model artifact and individual predictions are deliberately not bundled. Only load trusted local joblib artifacts. Keep raw/derived data and model artifacts private unless redistribution is permitted.

## Screenshot evidence after local execution

| Name | Capture |
|---|---|
| 11_model_training.png | Terminal showing six trained candidates and selected model |
| 12_model_comparison.png | reports/phase3_model_comparison.md (Markdown preview) |
| 13_model_performance.png | visualizations/phase3_model_performance.png |
| 14_neural_network_training.png | visualizations/phase3_neural_network_training.png (training/validation RMSE curves) |
| 15_prediction_evaluation.png | visualizations/phase3_prediction_evaluation.png |

Save in the existing screenshots folder. Phase 4 MLflow, prediction API, frontend updates and deployment are not part of this upgrade.
