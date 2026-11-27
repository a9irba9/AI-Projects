from datetime import datetime, timezone
import json
from app.extensions import db


class Task(db.Model):
    """Represents an approved business workflow task."""

    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    category = db.Column(db.String(64), nullable=False, default="General", index=True)
    priority = db.Column(db.String(32), nullable=False, default="Medium", index=True)
    due_date = db.Column(db.Date, nullable=True, index=True)
    assigned_to = db.Column(db.String(120), nullable=True)
    action_items_json = db.Column(db.Text, nullable=False, default="[]")
    status = db.Column(db.String(32), nullable=False, default="Pending", index=True)
    original_request = db.Column(db.Text, nullable=True)
    confidence = db.Column(db.Float, nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    activities = db.relationship(
        "ActivityLog",
        backref="task",
        lazy=True,
        passive_deletes=True,
    )

    @property
    def action_items(self) -> list[str]:
        try:
            return json.loads(self.action_items_json or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    @action_items.setter
    def action_items(self, items: list[str]) -> None:
        self.action_items_json = json.dumps(items or [], ensure_ascii=False)
