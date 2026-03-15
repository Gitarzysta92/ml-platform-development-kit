# ml-platform-development-kit

Reusable ML platform building blocks focused on a Runpod Serverless integration pattern.

This repository provides a minimal but production-shaped stack you can consume from a client GitOps repository via remote Kustomize bases.

## Contents

- `cluster/`: Kustomize base for a serverless GPU connector stack.
- `images/`: Docker build contexts for:
  - `runpod-connector` API service
  - `runpod-worker` async worker
  - shared Python runtime code (`images/common`)

## Included stack (`cluster/runpod-serverless-stack`)

- Connector API service (FastAPI):
  - `POST /v1/gpu-jobs`
  - `GET /v1/gpu-jobs/{job_id}`
  - `GET /v1/gpu-jobs/{job_id}/events`
- Worker service:
  - pulls queue messages
  - submits jobs to Runpod Serverless
  - polls Runpod status and updates job state
- MLflow tracking server:
  - stores experiment observability for submitted jobs
- Job state store: MySQL
  - operational source of truth (status, retries, provider IDs, event timeline)
- Queue: RabbitMQ
- Object storage: MinIO (S3-compatible)
- Secrets/config wiring for Runpod API key + storage credentials

## Architecture and reasoning

This kit uses a deliberate Stage 3 split:

- MySQL is the operational source of truth.
- RabbitMQ is the asynchronous execution buffer.
- MLflow is the experiment and run observability system.

Why this split:

- RabbitMQ is built for decoupling API ingress from long-running GPU execution.
- MySQL provides strict idempotency and reliable operational queries.
- MLflow gives run-level visibility (params, tags, outcomes) for ML workflows.

This avoids overloading any single component:

- MLflow does not act as a queue.
- RabbitMQ does not act as persistent job state.
- MySQL does not replace ML observability.

### Component responsibilities

- `runpod-connector`:
  - validates payload
  - enforces idempotency by `request_id`
  - writes initial job row and `queued` event to MySQL
  - publishes `job_id` to RabbitMQ
- `runpod-worker`:
  - consumes queue messages
  - transitions state in MySQL (`running`, `succeeded`, `failed`, `cancelled`)
  - writes immutable job events (`submitted_to_runpod`, `worker_error`, terminal events)
  - tracks MLflow run metadata
  - stores outputs to MinIO/S3
- `MySQL`:
  - source of truth for API read models (`/v1/gpu-jobs/*`)
  - idempotency and retry counters
  - timeline of operational events
- `MLflow`:
  - experiment observability (`runpod-jobs`)
  - tags and params for investigation and model/process analysis

### Request lifecycle

1. Client calls `POST /v1/gpu-jobs`.
2. Connector checks idempotency (`request_id`).
3. Connector stores `queued` state in MySQL and publishes queue message.
4. Worker consumes message and marks job `running`.
5. Worker submits payload to Runpod endpoint.
6. Worker polls Runpod status until terminal state or timeout.
7. Worker stores output in MinIO/S3 and updates MySQL state.
8. Worker logs run metadata in MLflow.
9. Client reads state via:
   - `GET /v1/gpu-jobs/{job_id}`
   - `GET /v1/gpu-jobs/{job_id}/events`

### Operational guarantees

- Idempotency: unique `request_id` in MySQL.
- Async decoupling: queue absorbs spikes and short provider outages.
- Auditable timeline: immutable `gpu_job_events`.
- Retry signal: `retry_count` increments on worker requeue.
- Dual visibility:
  - operational truth in MySQL
  - experiment/run observability in MLflow

### Failure behavior

- Temporary provider/network failure:
  - worker nacks and requeues message
  - retry count and `worker_error` event are persisted
- Runpod terminal failure:
  - job status becomes `failed` or `cancelled`
  - error message and event details are stored
  - MLflow run is closed with terminal status tags
- Status timeout:
  - job is marked `failed`
  - timeout event captures last known payload snapshot

### Evolution path

- Current target: low-to-medium scale with strong correctness.
- Next improvements:
  - dead-letter queue and retry policy tuning
  - multi-worker horizontal scaling
  - managed MySQL/RabbitMQ/object storage
  - callback-based status updates instead of polling

## GitOps consumption

Reference this module as a remote base from your client repository:

```yaml
resources:
  - github.com/Gitarzysta92/ml-platform-development-kit//cluster/runpod-serverless-stack?ref=main
```

### Argo CD application base (platform-development-kit style)

This repository ships an Argo CD `Application` base under:

- `cluster/runpod-serverless-stack/argo-application/application.yaml`

Use it directly or copy/paste into your client repository (`threesixty-platform`) and set:

- `spec.source.targetRevision` to a pinned tag/sha
- optional: update shared-service endpoints in `spec.source.kustomize.patches` (defaults target `platform` namespace service DNS)

### Reuse shared platform services (RabbitMQ, MySQL, MinIO)

The provided Argo CD application base already assumes this model and:

- deletes in-stack `mysql`, `rabbitmq`, and `minio` `StatefulSet`/`Service` resources
- keeps connector/worker/MLflow in `ml-platform`
- points service hosts to shared DNS in `platform` namespace

Expected shared endpoints (patch as needed):

- `MYSQL_HOST=mysql.platform.svc.cluster.local`
- `RABBITMQ_HOST=rabbitmq.platform.svc.cluster.local`
- `S3_ENDPOINT_URL=http://minio.platform.svc.cluster.local:9000`

## GitHub workflows

This repository includes CI workflows aligned with `threesixty-platform` and `solution-development-kit` conventions:

- `.github/workflows/ml-images.workflow.yml`
  - triggers on `push` to `main`/`develop` for `images/**`, `cluster/**`, `.github/**`
  - builds and pushes both images:
    - `ml-platform-development-kit/runpod-connector`
    - `ml-platform-development-kit/runpod-worker`
- `.github/workflows/ml-dev-loop.workflow.yml`
  - manual `workflow_dispatch`
  - supports modes:
    - `connectivity` (registry preflight and login)
    - `build` (docker build only, no push)
    - `build-and-push` (build and publish dev-loop tag)

### Required repository configuration

- Variables:
  - `NEXUS_DOCKER_HOST` (or `NEXUS_HOST`)
  - `NEXUS_DOCKER_REGISTRY`
- Secrets:
  - `NEXUS_USERNAME`
  - `NEXUS_PASSWORD`

### Runner and registry alignment

Workflows intentionally mirror `solution-development-kit` conventions:

- runner: `arc-runner-set-ml-platform-development-kit`
- Docker registry auth: Nexus (`NEXUS_*` variables + credentials)
- build strategy: matrix-based image build/push + manual dev loop

If your `threesixty-platform` environment uses different runner labels or registry hostnames, override these values in workflow files or via repository variables.

### ARC runner GitOps bootstrap (integration claim model)

This repository exposes a single integration-claim entrypoint for the host platform:

- Bootstrap kustomization (contains governance + apps):
  - `argocd/bootstrap/kustomization.yaml`
- AppProject:
  - `argocd/bootstrap/projects/ml-platform-development-kit-project/ml-platform-development-kit-project.yaml`
- ARC runner config `Application`:
  - `argocd/applications/platform-core/arc-runner-set-ml-platform-development-kit/application.yaml`

Onboarding flow:

1. Ensure this repository is connected in Argo CD (`repoURL` access).
2. In `threesixty-platform`, generate and apply integration claim `Application` YAML:

```bash
./scripts/generate-platform-integration-claim.sh https://github.com/Gitarzysta92/ml-platform-development-kit.git main | kubectl apply -f -
```

This creates `ml-platform-development-kit-platform-integration-claim`, which reconciles `argocd/bootstrap` from this repository and creates:

- `AppProject/ml-platform-development-kit`
- `Application/arc-runner-set-ml-platform-development-kit-config`

Then:

3. Run ARC auth bootstrap workflow to create `arc-github-auth-ml-platform-development-kit` secret.
4. Run image workflows (`ml-images` / `ml-dev-loop`) on `arc-runner-set-ml-platform-development-kit`.

## Quick start (local cluster / dev)

1) Apply the module:

```bash
kubectl apply -k cluster/runpod-serverless-stack
```

2) Replace placeholders in:
- `cluster/runpod-serverless-stack/secret.yaml`
- `cluster/runpod-serverless-stack/configmap.yaml` (`RUNPOD_ENDPOINT_ID`)
- if you use shared services, prefer `cluster/runpod-serverless-stack/argo-application/application.yaml`

3) Build and push images used by:
- `cluster/runpod-serverless-stack/connector-deployment.yaml`
- `cluster/runpod-serverless-stack/worker-deployment.yaml`

4) Test:

```bash
kubectl -n ml-platform port-forward svc/runpod-connector 8080:8080
curl -X POST http://127.0.0.1:8080/v1/gpu-jobs \
  -H "Content-Type: application/json" \
  -d '{"taskType":"image-generation","input":{"prompt":"a mountain at sunrise"}}'
```

5) Open MLflow UI:

```bash
kubectl -n ml-platform port-forward svc/mlflow 5000:5000
```

Then open `http://127.0.0.1:5000` and inspect experiment `runpod-jobs`.

6) Inspect operational events:

```bash
curl http://127.0.0.1:8080/v1/gpu-jobs/<job-id>/events
```

## Notes

- This is an MVP stack designed to be easy to understand and extend.
- Architecture follows Stage 3 split: MySQL for operational truth, MLflow for observability.
- For production, consider replacing in-cluster MySQL/RabbitMQ/MinIO with managed services.
- Add quotas, tenant-level limits, and alerting before high-volume traffic.
