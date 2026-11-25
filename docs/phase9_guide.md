# Task 6 — Phase 9 deployment guide

This additive upgrade retains every earlier file. It reuses the Phase 5 API, Phase 6 React gateway and Phase 7 monitoring. It exports the exact verified MLflow champion version into a private portable bundle, rather than copying the SQLite registry with absolute machine-specific paths. This is a frozen deployment snapshot: refresh deliberately after a champion promotion. The model, data and aggregate reports never enter the Docker build context or the source-only Git staging operation. Only the primary house dataset and required training partition are copied; the churn and supermarket datasets are not transferred. No model retraining is necessary. Local predictions retain unspecified source units.

## A. Local Docker on macOS

1. From your existing Task 6 project root, `unzip -n ~/Downloads/Task_6_Phase_9_Deployment_Upgrade.zip -d .`. Do not replace folders. Keep the Phase 5 schema correction `Area: Annotated[int, Field(gt=0)]` in `backend/schemas/phase5.py`.
2. Run `open -a Docker` and `docker info`. Stop Phase 7/6/5 with Ctrl+C in their original terminal(s); use `python scripts/run_phase7.py stop` if its containers remain. Do not kill unrelated processes. Ports 5176, 8006, 9090 and 3000 must be available.
3. Activate `.venv`: `source .venv/bin/activate`.
4. Run `python scripts/run_phase9.py --setup`. The launcher checks Docker, runs new source/security tests, stages a source-only build context, exports the registered champion, verifies model parity, generates separate deployment secrets, builds the image and runs the stack. It verifies live single/batch prediction parity, unauthorized rejection, integer validation, dashboard integration, reports, Prometheus scraping and Grafana dashboard availability. It exits only after its checks or an error; containers remain running in detached mode.
5. Open `http://127.0.0.1:5176` in Chrome. The Docker API is at `http://127.0.0.1:8006/docs`, Prometheus at `http://127.0.0.1:9090` and Grafana at `http://127.0.0.1:3000/d/task6-phase7`. The API key is a new Docker-only secret, not the old `.env.phase5`. The React gateway handles it automatically. Do not expose the secret or monitoring ports publicly.
6. `python scripts/run_phase9.py status` lists containers; `python scripts/run_phase9.py smoke` repeats live tests. `python scripts/run_phase9.py stop` stops the named stack (does not delete original data). For startup diagnostics: `docker compose -p task6phase9 logs` requires the compose file/env; use `docker ps -a --filter name=task6phase9` then `docker logs <container-name>` for a specific failed service. Do not send secrets.
7. Capture `36_docker_deployment.png` from terminal showing the actual `PHASE 9 READY`, live verification and Compose container table. Capture `37_docker_containers.png` in Docker Desktop > Containers > task6phase9, expanded to show app, prometheus and grafana running. Save under `screenshots/`.

Generated directories `.phase9-build` (source-only), `.phase9-private` (private champion snapshot), `.phase9-secrets` (deployment secrets) are separate from earlier work. Do not commit any of them. The private and secret parent directories have mode 0700; individual files are readable by the non-root containers through their explicit mounts. `prepare --refresh` replaces only the generated private snapshot; never use it while the stack is serving that snapshot. Stop, refresh, then restart. The runtime verifies SHA-256 tree hashes and parity, not a cryptographic signature; only load artifacts you created and trust. A new snapshot may need a new compatible image. Exact core package versions are constrained from your Mac for local Docker; Linux wheels must exist. If not, stop and resolve compatibility, do not silently downgrade. The source-only CI image uses dependency ranges and is not guaranteed to load your private trained model.

## B. Independent GitHub repository and CI/CD

Before any publication, review file contents and history for keys, personal information, data rights and confidential reports. Never use `git add .`, particularly in the parent project. `python scripts/run_phase9.py git-stage` initializes a separate repository if necessary and stages only approved source/config paths. It excludes original private data, model artifacts, reports, charts, notebooks, screenshots, generated runtime and secrets. It also excludes the old foundation workflow on a fresh repository: that workflow expects private data and runs an unscoped test suite. If an existing Task 6 repository already tracks nonallowlisted files, the launcher stops rather than silently removing them. A source allowlist cannot detect secrets written directly inside source; review manually. If any private material has ever been committed, do not push that history.

```sh
python scripts/run_phase9.py git-stage
git rev-parse --show-toplevel
git diff --cached --stat
git diff --cached
```

Confirm the root is `the-developers-arena-task-06`. Review the diff locally; never screenshot private keys. Create a new empty repository on GitHub (private is preferred until publication permission; do not initialize README). Commit and push only after review:

```sh
git commit -m "Complete real estate intelligence platform source and deployment"
git branch -M main
git remote -v
# If no origin exists, substitute your actual new repository URL:
git remote add origin https://github.com/YOUR_USERNAME/Task-6-RealEstate-AI.git
git push -u origin main
```

GitHub → repository → Actions → Phase 9 source checks and image delivery. The workflow runs source-only Phase 5/6/7/9 fixture tests, JavaScript tests, a Docker build and runtime imports. It deliberately does not run dataset-dependent Phase 2–4/8 tests or claim the local coverage gate in a public checkout. For continuous delivery, manually run the workflow with `publish=true` to publish a source-only image to GHCR tagged with the commit SHA. No private runtime is included, and the workflow does not automatically deploy a VM. Capture `38_github_actions.png` only after the actual workflow is green. Verify remote file tree and URL before sharing. Keep screenshot evidence local or submit separately after review.

## C. Public cloud (optional until explicit dataset/model permission)

Do not transfer data/model or expose dashboard outputs to a cloud provider until you have permission. Even an authenticated site involves storing private material off-device. AWS resources, public IPv4, domain and storage may incur charges. This template is an example AWS EC2 deployment; no account, DNS name, billing authorization or cloud access is assumed. Use AWS credentials locally, not in Git; set a budget. If no permission or domain is available, finish screenshots 36–38 and mark screenshot 39 pending. Do not use a localhost screenshot as public evidence.

Prerequisites: AWS CLI credentials for a permitted account, Terraform, existing EC2 SSH key pair in the region, matching private key file, your public IPv4 CIDR (/32), a DNS domain you control. Terraform creates a VPC, subnet, internet gateway, security group allowing only your IP on SSH plus public HTTP/HTTPS, an encrypted Ubuntu 24.04 EC2 disk and Elastic IP. Default t3.large is a paid example; review sizing/cost. The cloud-init script installs Docker. Do not open ports 5176, 8006, 3000 or 9090 to the internet. Check the plan before applying:

```sh
terraform -chdir=infrastructure/phase9/terraform init
terraform -chdir=infrastructure/phase9/terraform validate
terraform -chdir=infrastructure/phase9/terraform plan -out=phase9.tfplan
terraform -chdir=infrastructure/phase9/terraform apply phase9.tfplan
terraform -chdir=infrastructure/phase9/terraform output -raw public_ip
```

Enter your `key_name` and `ssh_cidr` when prompted. Set an A record for your domain to the actual Elastic IP. Ensure DNS has propagated and no conflicting AAAA record. Verify SSH server fingerprint independently through the provider before accepting it. Set these placeholders to your actual values on your Mac (do not share your private key):

```sh
VM_IP='REPLACE_WITH_ACTUAL_ELASTIC_IP'
SSH_KEY="$HOME/.ssh/REPLACE_WITH_YOUR_KEY.pem"
DOMAIN='REPLACE_WITH_YOUR_ACTUAL_DOMAIN'
ssh -i "$SSH_KEY" ubuntu@"$VM_IP" 'cloud-init status --wait; docker info'
```

If Docker group access is not ready, reconnect after cloud-init completes. Export current private snapshot and generate a private transfer archive **only after permission**:

```sh
python scripts/run_phase9.py prepare
python scripts/run_phase9.py cloud-package --allow-private-cloud
ssh -i "$SSH_KEY" ubuntu@"$VM_IP" 'umask 077; mkdir -p ~/task6'
scp -i "$SSH_KEY" .phase9-transfer.tar.gz ubuntu@"$VM_IP":~/task6/
ssh -i "$SSH_KEY" ubuntu@"$VM_IP"
```

On the VM:

```sh
cd ~/task6
umask 077
tar -xzf .phase9-transfer.tar.gz
chmod 700 .phase9-private
python3 scripts/run_phase9.py up --use-prepared --cloud-domain YOUR_ACTUAL_DOMAIN --allow-private-cloud
```

The image builds natively on the VM from source; the private data/model are mounted separately. Caddy obtains TLS after DNS is correct and publicly routes only the dashboard. PublicGuard requires a separate random viewer password and checks exact host/origin; the API key never goes to the browser. On your Mac, in another terminal, copy the viewer password privately (not to screenshots):

```sh
ssh -i "$SSH_KEY" ubuntu@"$VM_IP" 'cat ~/task6/.phase9-secrets/viewer_password' | pbcopy
```

Open `https://YOUR_ACTUAL_DOMAIN` and authenticate as `viewer` with the copied password. Verify a valid prediction. Capture `39_live_cloud_application.png` with the real HTTPS address bar and working dashboard, no credentials. Keep the password private and share only through an authorized secure channel with the evaluator. An HTTPS endpoint with password is internet-accessible but not anonymous. No external load testing, rate limiting, identity federation or production security review is included. Use this as a limited-access demonstration, not a public anonymous production service. If the evaluator requires anonymous access, first obtain dataset/model rights and redesign the public security controls.

When no longer needed, stop the stack on the VM (`python3 scripts/run_phase9.py stop`) and destroy AWS resources from the Mac using the same Terraform state and variable values: `terraform -chdir=infrastructure/phase9/terraform destroy`. Review the destroy plan first. Remove private transfer copies when safe. Avoid retaining AWS resources unintentionally. Never commit Terraform state or private keys.

## D. Kubernetes alternative (optional)

This is a single-replica private app deployment with a PVC, Secret, resource constraints, probes and ClusterIP service. Monitoring stays available in the Compose deployment; the Kubernetes API metrics are scrapeable inside the cluster, but no Kubernetes Grafana/Prometheus operator or ingress is installed here. Use a trusted local cluster with a default StorageClass, and make the architecture-matched `task6-phase9:local` image available to it (e.g. load into your local cluster). No public ingress is provided. Stop local Compose first to free port 5176.

```sh
kubectl apply -f infrastructure/phase9/kubernetes/app.yaml
kubectl -n task6 scale deployment task6-app --replicas=0
kubectl apply -f infrastructure/phase9/kubernetes/seed.yaml
kubectl -n task6 wait --for=condition=Ready pod/task6-seed --timeout=120s
kubectl -n task6 cp .phase9-private/data task6-seed:/private/data
kubectl -n task6 cp .phase9-private/reports task6-seed:/private/reports
kubectl -n task6 cp .phase9-private/visualizations task6-seed:/private/visualizations
kubectl -n task6 cp .phase9-private/champion task6-seed:/private/champion
kubectl -n task6 delete pod task6-seed
kubectl -n task6 create secret generic task6-runtime --from-file=api_key=.phase9-secrets/api_key
kubectl -n task6 scale deployment task6-app --replicas=1
kubectl -n task6 rollout status deployment/task6-app --timeout=300s
kubectl -n task6 port-forward svc/task6-app 5176:5176
```

Open localhost:5176, not a public address. The seed step is for an empty PVC; do not overwrite existing private volume content without review. Kubernetes Secrets are not automatically encrypted at rest unless the cluster is configured accordingly. Never copy private files to a remote cluster without permission. The deployment uses the locally built image by default; change image reference only to a compatible trusted image. If needed, `kubectl -n task6 get pods` and `kubectl -n task6 logs deployment/task6-app`. No Kubernetes run is required for screenshots 36–39 unless the internship explicitly requires it.

## E. Verification and limitations

Local package tests cover source staging and privacy, bundle checksums, secret handling, exact-host/origin and password protection, preservation of the gateway guard, Compose configuration, Kubernetes configuration and workflow configuration. Docker, Terraform, Kubernetes, live MLflow and hosted deployment must be verified in the actual environment. Do not claim a screenshot, green workflow, public URL or deployment result before it exists. The earlier Phase 8 test suite and coverage results are not replaced by Phase 9 checks.
