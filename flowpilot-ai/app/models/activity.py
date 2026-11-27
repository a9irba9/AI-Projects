from datetime import datetime, timezone
from app.extensions import db


class ActivityLog(db.Model):
    """Audit log recording workflow events. Preserves history even if a task is deleted."""

    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(64), nullable=False, index=True)
    task_id = db.Column(
        db.Integer,
        db.ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    details = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
