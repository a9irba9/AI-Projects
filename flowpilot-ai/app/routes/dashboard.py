from datetime import date
from flask import Blueprint, jsonify, render_template
from app.models.activity import ActivityLog
from app.models.task import Task

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    """Render the main FlowPilot AI dashboard."""
    today = date.today()
    total_tasks = Task.query.count()
    pending_tasks = Task.query.filter_by(status="Pending").count()
    in_progress_tasks = Task.query.filter_by(status="In Progress").count()
    completed_tasks = Task.query.filter_by(status="Completed").count()
    overdue_tasks = Task.query.filter(
        Task.due_date.isnot(None),
        Task.due_date < today,
        Task.status.notin_(["Completed", "Cancelled"]),
    ).count()
    high_priority_tasks = Task.query.filter(
        Task.priority.in_(["High", "Critical"]),
        Task.status.notin_(["Completed", "Cancelled"]),
    ).count()

    recent_tasks = Task.query.order_by(Task.created_at.desc()).limit(5).all()
    recent_activity = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(5).all()

    stats = {
        "total": total_tasks,
        "pending": pending_tasks,
        "in_progress": in_progress_tasks,
        "completed": completed_tasks,
        "overdue": overdue_tasks,
        "high_priority": high_priority_tasks,
    }
    return render_template(
        "dashboard.html",
        stats=stats,
        recent_tasks=recent_tasks,
        recent_activity=recent_activity,
    )


@dashboard_bp.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "FlowPilot AI"})
