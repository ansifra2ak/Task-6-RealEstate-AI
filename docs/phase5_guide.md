# Task 6 Phase 5 — Prediction API

## Safe setup (macOS, VS Code)
From the existing Task 6 root, with `.venv` active:

```bash
unzip -n ~/Downloads/Task_6_Phase_5_FastAPI_Upgrade.zip -d .
ls scripts/run_phase5.py backend/phase5_app.py tests/test_phase5.py
python scripts/run_phase5.py --setup
```

Do not replace directories. Stop the old foundation backend if it occupies port 8006; leave MLflow running if desired (the API uses the same local SQLite registry directly and does not require port 5006). Phase 4 must have registered a READY champion. If missing, run `python scripts/run_phase4.py prepare` first, then run Phase 5. `python scripts/run_phase5.py` runs the tests and starts the API on subsequent launches. `python scripts/run_phase5.py test` runs Phase 5 tests only; `python scripts/run_phase5.py serve` skips unit tests but still checks the real registry and HTTP smoke tests. Phase 1 launchers stay untouched. The upgraded frontend is not part of Phase 5.

The API pins the version resolved from the champion alias at startup; restart after model promotion or rollback. No fallback to a different model. The registry is trusted local content only; do not load models from unknown sources. Startup checks dataset and training partition hashes, champion status and dataset provenance, and live predictions. Only aggregate training-sample analytics are returned; no raw property records. This is a local demonstration, not a production-ready or externally hosted service. No TLS, distributed rate limiting, user identity management or production secrets service is configured. Source units (price and area) are unspecified. Input categories and numeric ranges come from the verified training partition; values outside those ranges are rejected. Market statistics are sample summaries, not current market prices. Phase 5 adds no dataset copies and does not modify prior code or screenshots.

## Swagger and screenshots
Open http://127.0.0.1:8006/docs in Chrome after `PHASE 5 READY`. Keep the launcher running.

19: Collapse endpoint panels, capture the complete Swagger route list and save `screenshots/19_complete_api_documentation.png`.

Authorization: The launcher generates a random key in `.env.phase5` (ignored by the original `.gitignore`). On a Mac, `open -e .env.phase5` in a second terminal opens it. Copy only the value after `TASK6_API_KEY=` into Swagger **Authorize** > Value. Close the key file and authorization popup before capturing any screenshots. Do not publish or screenshot the key, curl command, request headers or any panel displaying it. If using a user-supplied environment override, use that value instead.

20: Expand POST `/api/v1/predict`, click Try it out, use the following illustrative valid input and Execute. Capture only the endpoint name and HTTP 200 response body, not credentials or curl commands. Save `screenshots/20_api_price_prediction.png`.

```json
{"Area":2500,"Bedrooms":3,"Bathrooms":2,"Age":15,"Location":"Suburb","Property_Type":"House"}
```

21: Expand POST `/api/v1/predict/batch`, click Try it out, paste the following and Execute. Capture HTTP 200, count 2 and both predictions. Save `screenshots/21_api_batch_prediction.png`.

```json
{"properties":[{"Area":2500,"Bedrooms":3,"Bathrooms":2,"Age":15,"Location":"Suburb","Property_Type":"House"},{"Area":3500,"Bedrooms":4,"Bathrooms":3,"Age":10,"Location":"City Center","Property_Type":"Villa"}]}
```

22: Click Authorize then Logout, close the dialog, execute the valid single prediction again. Capture HTTP 401 and `Missing or invalid API key` (no key shown). Save `screenshots/22_api_security_validation.png`. Optionally reauthorize and test invalid Area=-1 to see HTTP 422. No public key should be included in evidence.

Other endpoints: public GET `/api/v1/health`; protected GET `/api/v1/datasets`, `/api/v1/model/info`, `/api/v1/analytics/market`. Model info returns the actual version and supported categories and ranges. The test report is `reports/phase5_test_results.txt`. Use the actual generated response values, not sample numbers from guides.

## Verification
The 27 Phase 5 tests include strict schema validation, security, error handling, batch limits and ordering, aggregate analytics and saved-model prediction parity. The launcher additionally performs real MLflow champion single/batch HTTP checks and unauthorized request rejection. The build environment had no MLflow installed, so live registry startup must pass locally before claiming Phase 5 complete. No foundation test expectations are changed.
