from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text

from common.db import get_db_session, init_db
from common.job_events import add_job_event
from common.models import Job, JobEvent
from common.queue_client import ensure_queue, publish_job

app = FastAPI(title="Runpod Connector", version="0.1.0")


class CreateJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requestId: str | None = Field(default=None, min_length=8, max_length=128)
    taskType: str = Field(min_length=2, max_length=128)
    inputUri: str | None = Field(default=None, max_length=1024)
    input: dict | None = None
    params: dict | None = None

    @model_validator(mode="after")
    def validate_payload(self):
        if self.inputUri is None and self.input is None:
            raise ValueError("Either inputUri or input must be provided")
        return self


@app.on_event("startup")
def startup() -> None:
    init_db()
    ensure_queue()


@app.get("/healthz")
def healthz():
    with get_db_session() as session:
        session.execute(text("SELECT 1"))
    return {"ok": True}


@app.post("/v1/gpu-jobs")
def create_job(payload: CreateJobRequest):
    job_id = str(uuid4())
    request_id = payload.requestId or job_id

    with get_db_session() as session:
        existing = session.query(Job).filter(Job.request_id == request_id).one_or_none()
        if existing:
            return {
                "jobId": existing.id,
                "requestId": existing.request_id,
                "status": existing.status,
                "providerJobId": existing.provider_job_id,
                "mlflowRunId": existing.mlflow_run_id,
                "idempotentHit": True,
            }

        job = Job(
            id=job_id,
            request_id=request_id,
            task_type=payload.taskType,
            status="queued",
            input_uri=payload.inputUri,
            input_payload=payload.input,
            params=payload.params or {},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(job)
        add_job_event(
            session=session,
            job_id=job_id,
            event_type="queued",
            message="Job accepted and queued for processing",
            details={"taskType": payload.taskType},
        )

    publish_job(job_id)
    return {"jobId": job_id, "requestId": request_id, "status": "queued", "idempotentHit": False}


@app.get("/v1/gpu-jobs/{job_id}")
def get_job(job_id: str):
    with get_db_session() as session:
        job = session.query(Job).filter(Job.id == job_id).one_or_none()
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")

        return {
            "jobId": job.id,
            "requestId": job.request_id,
            "taskType": job.task_type,
            "status": job.status,
            "providerJobId": job.provider_job_id,
            "mlflowRunId": job.mlflow_run_id,
            "outputUri": job.output_uri,
            "error": job.error_message,
            "retryCount": job.retry_count,
            "createdAt": job.created_at,
            "startedAt": job.started_at,
            "completedAt": job.completed_at,
            "updatedAt": job.updated_at,
        }


@app.get("/v1/gpu-jobs/{job_id}/events")
def get_job_events(job_id: str):
    with get_db_session() as session:
        job = session.query(Job).filter(Job.id == job_id).one_or_none()
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")

        events = (
            session.query(JobEvent)
            .filter(JobEvent.job_id == job_id)
            .order_by(JobEvent.created_at.asc(), JobEvent.id.asc())
            .all()
        )
        return {
            "jobId": job_id,
            "events": [
                {
                    "type": event.event_type,
                    "message": event.message,
                    "details": event.details,
                    "createdAt": event.created_at,
                }
                for event in events
            ],
        }

