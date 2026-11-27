from typing import Optional
from app.extensions import db
from app.models.activity import ActivityLog


def log_activity(
    event_type: str, task_id: Optional[int] = None, details: str = ""
) -> ActivityLog:
    """Record an audit event in ActivityLog."""
    entry = ActivityLog(
        event_type=event_type,
        task_id=task_id,
        details=details,
    )
    db.session.add(entry)
    return entry
