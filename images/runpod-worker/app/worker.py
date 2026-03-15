import json
import time
from datetime import datetime, timezone

import pika

from common.config import settings
from common.db import get_db_session, init_db
from common.job_events import add_job_event
from common.mlflow_client import end_job_run, log_job_params, log_job_status, start_job_run
from common.models import Job
from common.runpod_client import RunpodClient
from common.storage import ensure_bucket, write_output_json

TERMINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"}


def _connection() -> pika.BlockingConnection:
    credentials = pika.PlainCredentials(settings.rabbitmq_user, settings.rabbitmq_password)
    parameters = pika.ConnectionParameters(
        host=settings.rabbitmq_host,
        port=settings.rabbitmq_port,
        credentials=credentials,
        heartbeat=30,
    )
    return pika.BlockingConnection(parameters)


def _runpod_status_to_internal(status: str) -> str:
    mapping = {
        "IN_QUEUE": "queued",
        "IN_PROGRESS": "running",
        "COMPLETED": "succeeded",
        "FAILED": "failed",
        "CANCELLED": "cancelled",
        "TIMED_OUT": "failed",
    }
    return mapping.get(status, "running")


def _build_runpod_input(job: Job) -> dict:
    payload = {
        "jobId": job.id,
        "requestId": job.request_id,
        "taskType": job.task_type,
        "params": job.params or {},
    }
    if job.input_uri:
        payload["inputUri"] = job.input_uri
    if job.input_payload is not None:
        payload["input"] = job.input_payload
    return payload


def _handle_message(body: bytes, runpod_client: RunpodClient) -> None:
    data = json.loads(body.decode("utf-8"))
    job_id = data["job_id"]
    mlflow_run_started = False

    with get_db_session() as session:
        job = session.query(Job).filter(Job.id == job_id).one_or_none()
        if job is None:
            return
        if job.status in {"succeeded", "failed", "cancelled"}:
            return
        run_id = start_job_run(job.id, job.request_id, job.task_type)
        log_job_params(job.params or {})
        mlflow_run_started = bool(run_id)
        if run_id:
            job.mlflow_run_id = run_id
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        job.updated_at = datetime.now(timezone.utc)
        add_job_event(
            session=session,
            job_id=job.id,
            event_type="running",
            message="Worker started processing job",
            details={"mlflowRunId": run_id},
        )

    with get_db_session() as session:
        job = session.query(Job).filter(Job.id == job_id).one()
        submit_response = runpod_client.submit(_build_runpod_input(job))
        provider_job_id = submit_response.get("id")
        if not provider_job_id:
            raise RuntimeError("Runpod response missing job id")
        job.provider_job_id = provider_job_id
        job.updated_at = datetime.now(timezone.utc)
        add_job_event(
            session=session,
            job_id=job.id,
            event_type="submitted_to_runpod",
            message="Job submitted to Runpod endpoint",
            details={"providerJobId": provider_job_id},
        )

    deadline = time.time() + settings.runpod_status_timeout_seconds
    last_status_payload = None
    while time.time() < deadline:
        with get_db_session() as session:
            job = session.query(Job).filter(Job.id == job_id).one()
            status_payload = runpod_client.get_status(job.provider_job_id)
            runpod_status = status_payload.get("status", "IN_PROGRESS")
            internal_status = _runpod_status_to_internal(runpod_status)
            job.status = internal_status
            job.updated_at = datetime.now(timezone.utc)
            last_status_payload = status_payload

            if runpod_status in TERMINAL_STATUSES:
                output_payload = status_payload.get("output")
                if output_payload is not None:
                    job.output_payload = output_payload
                    job.output_uri = write_output_json(job.id, output_payload)
                if runpod_status != "COMPLETED":
                    job.error_message = status_payload.get("error", f"Runpod status: {runpod_status}")
                job.completed_at = datetime.now(timezone.utc)
                add_job_event(
                    session=session,
                    job_id=job.id,
                    event_type=job.status,
                    message="Runpod returned terminal state",
                    details={"runpodStatus": runpod_status, "outputUri": job.output_uri},
                )
                log_job_status(job.status, job.provider_job_id, job.output_uri)
                if mlflow_run_started:
                    end_job_run()
                return

        time.sleep(settings.runpod_status_poll_interval_seconds)

    with get_db_session() as session:
        job = session.query(Job).filter(Job.id == job_id).one()
        job.status = "failed"
        job.error_message = f"Timed out waiting for Runpod status. Last payload: {last_status_payload}"
        job.updated_at = datetime.now(timezone.utc)
        job.completed_at = datetime.now(timezone.utc)
        add_job_event(
            session=session,
            job_id=job.id,
            event_type="failed",
            message="Worker timed out while waiting for Runpod terminal state",
            details={"lastStatusPayload": last_status_payload},
        )
        log_job_status(job.status, job.provider_job_id, job.output_uri)
    if mlflow_run_started:
        end_job_run()


def main() -> None:
    init_db()
    ensure_bucket()
    runpod_client = RunpodClient()

    connection = _connection()
    channel = connection.channel()
    channel.queue_declare(queue=settings.rabbitmq_queue, durable=True)
    channel.basic_qos(prefetch_count=1)

    def on_message(ch, method, _properties, body):
        try:
            _handle_message(body, runpod_client)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as error:
            try:
                payload = json.loads(body.decode("utf-8"))
                failed_job_id = payload.get("job_id")
                if failed_job_id:
                    with get_db_session() as session:
                        job = session.query(Job).filter(Job.id == failed_job_id).one_or_none()
                        if job is not None:
                            job.retry_count = (job.retry_count or 0) + 1
                            job.error_message = str(error)
                            job.updated_at = datetime.now(timezone.utc)
                            add_job_event(
                                session=session,
                                job_id=job.id,
                                event_type="worker_error",
                                message="Worker failed to process message and requeued it",
                                details={"error": str(error), "retryCount": job.retry_count},
                            )
            except Exception:
                pass
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            time.sleep(2)

    channel.basic_consume(queue=settings.rabbitmq_queue, on_message_callback=on_message)
    channel.start_consuming()


if __name__ == "__main__":
    main()

