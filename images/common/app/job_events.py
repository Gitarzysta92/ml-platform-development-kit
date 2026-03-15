from .models import JobEvent


def add_job_event(session, job_id: str, event_type: str, message: str | None = None, details: dict | None = None) -> None:
    session.add(
        JobEvent(
            job_id=job_id,
            event_type=event_type,
            message=message,
            details=details or {},
        )
    )

