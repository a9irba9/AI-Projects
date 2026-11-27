import csv
from datetime import date, datetime, time
import io
from flask import Blueprint, Response, render_template, request
from app.models.activity import ActivityLog
from app.services.task_service import query_tasks

exports_bp = Blueprint("exports", __name__, url_prefix="/exports")

EVENT_TYPES = (
    "AI request processed",
    "Task approved",
    "Task rejected",
    "Task created",
    "Task edited",
    "Status changed",
    "Task deleted",
)

DANGEROUS_CSV_PREFIXES = ("=", "+", "-", "@")


def _sanitize_csv_cell(value: object) -> str:
    """Convert value to string and neutralize spreadsheet formula injection."""
    if value is None:
        return ""
    text = str(value)
    if text.startswith(DANGEROUS_CSV_PREFIXES):
        return "'" + text
    return text


@exports_bp.route("/activity")
def activity_history():
    """Render the Activity History audit log with filtering and pagination."""
    event_type = request.args.get("event_type", "").strip()
    start_date_str = request.args.get("start_date", "").strip()
    end_date_str = request.args.get("end_date", "").strip()
    page = request.args.get("page", 1, type=int)

    q = ActivityLog.query
    if event_type and event_type in EVENT_TYPES:
        q = q.filter(ActivityLog.event_type == event_type)

    if start_date_str:
        try:
            start_dt = datetime.combine(
                datetime.strptime(start_date_str, "%Y-%m-%d").date(), time.min
            )
            q = q.filter(ActivityLog.created_at >= start_dt)
        except ValueError:
            start_date_str = ""

    if end_date_str:
        try:
            end_dt = datetime.combine(
                datetime.strptime(end_date_str, "%Y-%m-%d").date(), time.max
            )
            q = q.filter(ActivityLog.created_at <= end_dt)
        except ValueError:
            end_date_str = ""

    pagination = q.order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc()).paginate(
        page=max(1, page), per_page=20, error_out=False
    )

    return render_template(
        "activity.html",
        logs=pagination.items,
        pagination=pagination,
        event_types=EVENT_TYPES,
        event_type=event_type,
        start_date=start_date_str,
        end_date=end_date_str,
    )


@exports_bp.route("/csv")
def export_csv():
    """Export tasks (optionally filtered) as a UTF-8 CSV with formula-injection protection."""
    search = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    priority = request.args.get("priority", "").strip()
    category = request.args.get("category", "").strip()
    sort_by = request.args.get("sort", "created_desc").strip()

    tasks = query_tasks(
        search=search,
        status=status,
        priority=priority,
        category=category,
        sort_by=sort_by,
    )

    output = io.StringIO()
    fieldnames = [
        "Task ID",
        "Title",
        "Description",
        "Category",
        "Priority",
        "Assigned person/team",
        "Due date",
        "Status",
        "Created timestamp",
        "Updated timestamp",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for t in tasks:
        writer.writerow(
            {
                "Task ID": t.id,
                "Title": _sanitize_csv_cell(t.title),
                "Description": _sanitize_csv_cell(t.description),
                "Category": _sanitize_csv_cell(t.category),
                "Priority": _sanitize_csv_cell(t.priority),
                "Assigned person/team": _sanitize_csv_cell(t.assigned_to),
                "Due date": t.due_date.isoformat() if t.due_date else "",
                "Status": _sanitize_csv_cell(t.status),
                "Created timestamp": t.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "Updated timestamp": t.updated_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            }
        )

    csv_bytes = ("\ufeff" + output.getvalue()).encode("utf-8")
    filename = f"flowpilot_tasks_{date.today().isoformat()}.csv"
    return Response(
        csv_bytes,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
