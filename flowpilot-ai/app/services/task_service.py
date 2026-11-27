from datetime import date, datetime
from typing import Any, Optional
from sqlalchemy import or_
from app.extensions import db
from app.models.task import Task
from app.services.activity_service import log_activity

VALID_CATEGORIES = (
    "Operations",
    "Finance",
    "Sales",
    "Customer Support",
    "HR",
    "IT",
    "General",
)
VALID_PRIORITIES = ("Low", "Medium", "High", "Critical")
VALID_STATUSES = ("Pending", "In Progress", "Completed", "Cancelled")


class TaskValidationError(ValueError):
    """Raised when task input fails backend validation."""


def parse_due_date(raw_date: Optional[str]) -> Optional[date]:
    """Parse YYYY-MM-DD string into a date object, or return None if empty."""
    if raw_date is None or str(raw_date).strip() == "":
        return None
    try:
        return datetime.strptime(str(raw_date).strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise TaskValidationError(
            "Invalid due date format. Expected YYYY-MM-DD."
        ) from exc


def validate_task_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize task fields from form or JSON input."""
    title = (data.get("title") or "").strip()
    if not title:
        raise TaskValidationError("Task title is required.")
    if len(title) > 200:
        raise TaskValidationError("Task title must be 200 characters or fewer.")

    description = (data.get("description") or "").strip()
    category = (data.get("category") or "General").strip()
    if category not in VALID_CATEGORIES:
        raise TaskValidationError(f"Invalid category: {category}")

    priority = (data.get("priority") or "Medium").strip()
    if priority not in VALID_PRIORITIES:
        raise TaskValidationError(f"Invalid priority: {priority}")

    status = (data.get("status") or "Pending").strip()
    if status not in VALID_STATUSES:
        raise TaskValidationError(f"Invalid status: {status}")

    due_date = parse_due_date(data.get("due_date"))
    assigned_to = (data.get("assigned_to") or "").strip() or None

    raw_items = data.get("action_items")
    if isinstance(raw_items, str):
        action_items = [line.strip() for line in raw_items.splitlines() if line.strip()]
    elif isinstance(raw_items, list):
        action_items = [str(item).strip() for item in raw_items if str(item).strip()]
    else:
        action_items = []

    return {
        "title": title,
        "description": description,
        "category": category,
        "priority": priority,
        "status": status,
        "due_date": due_date,
        "assigned_to": assigned_to,
        "action_items": action_items,
    }


def create_task(
    data: dict[str, Any],
    original_request: Optional[str] = None,
    confidence: Optional[float] = None,
    event_type: str = "Task created",
) -> Task:
    """Validate and persist a new Task, recording an activity log entry."""
    cleaned = validate_task_payload(data)
    task = Task(
        title=cleaned["title"],
        description=cleaned["description"],
        category=cleaned["category"],
        priority=cleaned["priority"],
        status=cleaned["status"],
        due_date=cleaned["due_date"],
        assigned_to=cleaned["assigned_to"],
        original_request=original_request,
        confidence=confidence,
    )
    task.action_items = cleaned["action_items"]
    db.session.add(task)
    db.session.flush()

    log_activity(event_type, task_id=task.id, details=f"{event_type}: {task.title}")
    db.session.commit()
    return task


def update_task(task: Task, data: dict[str, Any]) -> Task:
    """Validate and update an existing Task, recording an activity log entry."""
    cleaned = validate_task_payload(data)
    task.title = cleaned["title"]
    task.description = cleaned["description"]
    task.category = cleaned["category"]
    task.priority = cleaned["priority"]
    task.status = cleaned["status"]
    task.due_date = cleaned["due_date"]
    task.assigned_to = cleaned["assigned_to"]
    task.action_items = cleaned["action_items"]

    log_activity("Task edited", task_id=task.id, details=f"Edited task: {task.title}")
    db.session.commit()
    return task


def update_task_status(task: Task, new_status: str) -> Task:
    """Transition a Task's status and log the change."""
    if new_status not in VALID_STATUSES:
        raise TaskValidationError(f"Invalid status: {new_status}")
    old_status = task.status
    task.status = new_status
    log_activity(
        "Status changed",
        task_id=task.id,
        details=f"Status changed from {old_status} to {new_status} for '{task.title}'",
    )
    db.session.commit()
    return task


def delete_task(task: Task) -> None:
    """Delete a Task while preserving its historical ActivityLog entries."""
    title = task.title
    task_id = task.id
    log_activity(
        "Task deleted",
        task_id=task_id,
        details=f"Deleted task #{task_id}: {title}",
    )
    db.session.flush()
    db.session.delete(task)
    db.session.commit()


def query_tasks(
    search: str = "",
    status: str = "",
    priority: str = "",
    category: str = "",
    sort_by: str = "created_desc",
) -> list[Task]:
    """Search, filter, and sort tasks."""
    q = Task.query
    if search:
        pattern = f"%{search}%"
        q = q.filter(or_(Task.title.ilike(pattern), Task.description.ilike(pattern)))
    if status and status in VALID_STATUSES:
        q = q.filter(Task.status == status)
    if priority and priority in VALID_PRIORITIES:
        q = q.filter(Task.priority == priority)
    if category and category in VALID_CATEGORIES:
        q = q.filter(Task.category == category)

    if sort_by == "created_asc":
        q = q.order_by(Task.created_at.asc())
    elif sort_by == "due_asc":
        q = q.order_by(Task.due_date.is_(None), Task.due_date.asc())
    elif sort_by == "due_desc":
        q = q.order_by(Task.due_date.is_(None), Task.due_date.desc())
    else:
        q = q.order_by(Task.created_at.desc())

    return q.all()
