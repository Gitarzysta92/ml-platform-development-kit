from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, func

from .db import Base


class Job(Base):
    __tablename__ = "gpu_jobs"

    id = Column(String(64), primary_key=True, index=True)
    request_id = Column(String(128), unique=True, nullable=False, index=True)
    task_type = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False, index=True)
    provider_job_id = Column(String(128), nullable=True, index=True)
    mlflow_run_id = Column(String(128), nullable=True, index=True)
    retry_count = Column(Integer, nullable=False, default=0)

    input_uri = Column(String(1024), nullable=True)
    input_payload = Column(JSON, nullable=True)
    params = Column(JSON, nullable=True)

    output_uri = Column(String(1024), nullable=True)
    output_payload = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class JobEvent(Base):
    __tablename__ = "gpu_job_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    message = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

