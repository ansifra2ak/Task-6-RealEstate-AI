# Task 6 — Render deployment add-on (Phase 11)

This add-on does not replace Phase 1–10 files. It serves the existing React dashboard through its existing FastAPI gateway and Phase 9's verified, frozen MLflow champion. The API is called in-process using an ASGI transport, not a separately exposed port. Render terminates HTTPS. Authentication is HTTP Basic with username `viewer` and a fresh random password. Only `/healthz` is public without authentication. Prometheus/Grafana remain in the local Docker stack; no public scrape or registry endpoints are provided. The free service is a restricted demonstration, not a production availability commitment.

## 1. Extract and test

From the Task 6 project root on your Mac:

```sh
unzip -n ~/Downloads/Task_6_Render_Deployment_Upgrade.zip -d .
source .venv/bin/activate
python scripts/run_phase11.py test
python scripts/run_phase9.py smoke
```

Keep Docker Desktop and Phase 9 running for the last check. No new local dependencies are installed by Phase 11. If any test fails, fix it before continuing. The Phase 11 tests use synthetic fixtures only; they do not prove actual hosted predictions. The earlier Phase 8 full suite must also pass before submission.

## 2. Prepare authorized runtime

**Do not continue until the dataset owner/internship permits hosting the supplied data, trained model and derived reports on Render.** Password protection does not confer permission. The private bundle includes the primary house CSV, training partition, evaluation aggregates/charts and exact saved model; it does not include the other two datasets' raw records or existing API keys. A public Git repository is not authorization. If permission cannot be established, stop; an independently labeled synthetic-data hosted demo would need a separate dataset/model and evaluator acceptance. No synthetic replacement is provided by this add-on.

Only after permission:

```sh
python scripts/run_phase11.py prepare --allow-private-cloud
```

This runs the new tests, checks the Phase 9 snapshot hashes, creates and reopens a restricted compressed archive, checks the exported model's requirements against the active Python 3.12 environment, generates `requirements-render-lock.txt` with exact core runtime versions, and writes the private base64 bundle outside the repository under `~/.task6-render/`. No upload occurs. The digest is printed; the archive contents are not. It caps encoded contents at 950,000 bytes, below Render's 1 MB combined secret-file limit. Base64 is not encryption. Do not paste the bundle into chat, GitHub, terminal arguments, logs, or screenshots.

If local dependencies disagree with the saved model, stop instead of changing the trained model or downgrading packages. If the generated lock already exists with different contents, the launcher stops rather than overwriting it. Linux wheels for the exact macOS versions must exist. The archive is loaded only from `/etc/secrets/task6-runtime.b64` at startup and extracted into a fresh private temporary directory. The digest and each Phase 9 artifact tree hash are checked, then the actual model is loaded and parity is checked against three saved predictions by the Phase 9 runtime. This protects integrity, not authenticity against an attacker able to replace both archive and expected digest. Only use your own trusted model: pickle/MLflow PythonModel loading can execute code.

## 3. Publish source only

Verify the independent repository root and current staging state:

```sh
git rev-parse --show-toplevel
git diff --cached --name-only
```

Root must end in `the-developers-arena-task-06`. If other files are already staged, stop and review before committing. Stage only the new deployment source and lock:

```sh
git add -- Dockerfile.render Dockerfile.render.dockerignore requirements-render.txt requirements-render-lock.txt backend/phase11_render.py scripts/run_phase11.py tests/test_phase11.py docs/render_deployment.md
git diff --cached --stat
git diff --cached
git commit -m "Add secure Render deployment for Task 6"
git push origin main
```

Do not run `git add .` or the old Phase 9 `git-stage` after adding these paths, as its allowlist predates this add-on. Never commit the private bundle, `.phase9-*`, `.env*`, raw/processed data, model artifacts, secret files, private reports or screenshots. Review source contents for hardcoded secrets too. The existing CI workflow remains unchanged; its original test selection does not automatically include Phase 11 tests. Run `python scripts/run_phase11.py test` locally. Check the newest GitHub Actions workflow after the push.

## 4. Render Web Service

Return to your existing Render configuration form. Refresh/reselect the repository if necessary to see the new Dockerfile. Select `ansifra2ak/Task-6-RealEstate-AI`, branch `main`, Docker language, Free ($0/month, 512 MB, 0.1 CPU). Name `task6-realestate-ai` if available, Singapore if offered. Root directory blank. Advanced fields:

| Field | Value |
|---|---|
| Docker Build Context Directory | `.` |
| Dockerfile Path | `./Dockerfile.render` |
| Docker Command | blank |
| Health Check Path | `/healthz` |
| Registry Credential | No credential |
| Pre-Deploy Command | blank |
| Auto-Deploy | Off initially |
| Build Filters | blank |

Environment variables (only after authorization):

| Key | Value |
|---|---|
| `TASK6_RENDER_AUTHORIZED` | `YES` |
| `TASK6_RENDER_SHA256` | SHA256 printed by prepare (64 hex chars) |
| `TASK6_RENDER_VIEWER_PASSWORD` | click Render Generate, ensure at least 32 characters, save privately |

Render supplies `PORT` and `RENDER_EXTERNAL_URL`; do not override them unless required for a diagnosed problem. No old API key is required. The backend generates a fresh internal key and never sends it to the browser. Use a strong password manager-generated password if Generate is unavailable. Never put a password in a Docker ARG, GitHub or screenshots.

Advanced → Secret Files → Add Secret File → Filename: `task6-runtime.b64`.

To copy the digest on Mac, run `python scripts/run_phase11.py copy-digest --allow-private-cloud` and paste into the digest environment variable. Do this before copying the bundle. To copy the private bundle to the clipboard, run:

```sh
python scripts/run_phase11.py copy-bundle --allow-private-cloud
```

Paste into the **contents of the Render secret file**, not an environment variable. Save the secret file. Immediately clear the clipboard (`printf '' | pbcopy`) and consider any clipboard manager's history. Do not screenshot the secret editor. Render also makes secret files available at build time; the Dockerfile uses explicit source COPY instructions and a Dockerfile-specific deny-by-default ignore file, with no secret-consuming build steps. The container runs as non-root with Render's supplementary group 1000 for secret-file access.

Confirm the total price is $0/month and the file name/values are correct. Click **Deploy web service**. Watch deployment logs for `Task 6 runtime integrity and champion parity verified; HTTPS gateway ready.` and a live status. Do not ignore model-loading or memory errors. Free Render has an ephemeral filesystem and can sleep after 15 minutes of inactivity, so the service reloads the snapshot on restart. No persistent disk or paid plan is required by this configuration. If the startup is OOM or Linux dependencies fail, troubleshoot with the actual error before using paid compute. Do not expose port 8006, 9090 or 3000.

## 5. Hosted verification and screenshot 39

Copy the actual `https://...onrender.com` URL shown in Render. Open it in a private browser window. Authenticate with username `viewer` and the new password. Test a valid single prediction, CSV batch, market analytics and reports. Do not include the password, secret files, or any confidential source records in screenshots. Share the viewer password only through an authorized private channel to your evaluator; verify that a password-protected internet URL is acceptable. The URL is publicly routable, but dashboard content is not anonymous.

In your local VS Code terminal:

```sh
python scripts/run_phase11.py smoke --url https://YOUR-ACTUAL-SERVICE.onrender.com
```

Replace the example URL with the actual Render URL. Enter the viewer password at the hidden prompt. This verifies HTTPS, authentication, exact-origin rejection, internal API isolation, real single/batch consistency, strict integer schema, market and report endpoints. A passing smoke check does not prove model accuracy on new real-world data or production SLAs. If the service is asleep, open the URL and retry once live. Save the real dashboard and address bar as `screenshots/39_live_cloud_application.png`. Do not use localhost or a login-only page as deployment evidence.

## 6. Limitations and cleanup

The free plan's 512 MB memory and 0.1 CPU may not support every workload or peak concurrent request; your 227 MiB local observation is not a cloud measurement. The service uses one worker, one BLAS/OpenMP thread, bounded gateway concurrency, and the existing bounded batch size. No production load/security audit, durable telemetry, full account management or cloud monitoring deployment is claimed. A shared password is suitable only for a restricted educational demonstration. The free service can restart and lose in-memory metrics. Phase 9 local monitoring and Phase 8 local benchmark results remain separate. No costs, deployment, dataset authorization, real model load, or hosted URL are claimed by this ZIP. When no longer needed, remove the hosted service and its secret files from Render and delete the generated private copy outside Git after confirming the original snapshot remains intact. Rotate the viewer password if exposed.

Sources: https://render.com/docs/docker-secrets ; https://render.com/docs/configure-environment-variables ; https://render.com/docs/web-services ; https://render.com/docs/free ; https://render.com/docs/environment-variables ; https://render.com/docs/health-checks .
