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
- Worker service:
  - pulls queue messages
  - submits jobs to Runpod Serverless
  - polls Runpod status and updates job state
- Job state store: PostgreSQL
- Queue: RabbitMQ
- Object storage: MinIO (S3-compatible)
- Secrets/config wiring for Runpod API key + storage credentials

## GitOps consumption

Reference this module as a remote base from your client repository:

```yaml
resources:
  - github.com/Gitarzysta92/ml-platform-development-kit//cluster/runpod-serverless-stack?ref=main
```

## Quick start (local cluster / dev)

1) Apply the module:

```bash
kubectl apply -k cluster/runpod-serverless-stack
```

2) Replace placeholders in:
- `cluster/runpod-serverless-stack/secret.yaml`
- `cluster/runpod-serverless-stack/configmap.yaml` (`RUNPOD_ENDPOINT_ID`)

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

## Notes

- This is an MVP stack designed to be easy to understand and extend.
- For production, consider replacing in-cluster Postgres/RabbitMQ/MinIO with managed services.
- Add quotas, tenant-level limits, and alerting before high-volume traffic.
