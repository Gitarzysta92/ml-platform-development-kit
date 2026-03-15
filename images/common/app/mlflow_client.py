from typing import Any

import mlflow

from .config import settings


def mlflow_enabled() -> bool:
    return bool(settings.mlflow_tracking_uri)


def configure_mlflow() -> None:
    if not mlflow_enabled():
        return
    try:
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        mlflow.set_experiment(settings.mlflow_experiment_name)
    except Exception:
        return


def start_job_run(job_id: str, request_id: str, task_type: str) -> str | None:
    if not mlflow_enabled():
        return None
    try:
        configure_mlflow()
        run = mlflow.start_run(
            run_name=f"runpod-job-{job_id}",
            tags={
                "job_id": job_id,
                "request_id": request_id,
                "task_type": task_type,
                "provider": "runpod",
            },
        )
        return run.info.run_id
    except Exception:
        return None


def log_job_params(params: dict[str, Any]) -> None:
    if not mlflow_enabled():
        return
    try:
        for key, value in params.items():
            mlflow.log_param(str(key), str(value))
    except Exception:
        return


def log_job_status(status: str, provider_job_id: str | None, output_uri: str | None) -> None:
    if not mlflow_enabled():
        return
    try:
        mlflow.set_tag("status", status)
        if provider_job_id:
            mlflow.set_tag("provider_job_id", provider_job_id)
        if output_uri:
            mlflow.set_tag("output_uri", output_uri)
        mlflow.log_metric("job_terminal_state", 1.0 if status == "succeeded" else 0.0)
    except Exception:
        return


def end_job_run() -> None:
    if not mlflow_enabled():
        return
    try:
        mlflow.end_run()
    except Exception:
        return

