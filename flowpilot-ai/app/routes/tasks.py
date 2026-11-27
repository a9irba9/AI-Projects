from flask import Blueprint, flash, redirect, render_template, request, url_for
from app.extensions import db
from app.models.task import Task
from app.services.task_service import (
    VALID_CATEGORIES,
    VALID_PRIORITIES,
    VALID_STATUSES,
    TaskValidationError,
    create_task,
    delete_task,
    query_tasks,
    update_task,
    update_task_status,
)

tasks_bp = Blueprint("tasks", __name__, url_prefix="/tasks")


@tasks_bp.route("/")
def list_tasks():
    """List tasks with search, status/priority/category filters, and sorting."""
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
    return render_template(
        "tasks.html",
        tasks=tasks,
        search=search,
        status=status,
        priority=priority,
        category=category,
        sort_by=sort_by,
        categories=VALID_CATEGORIES,
        priorities=VALID_PRIORITIES,
        statuses=VALID_STATUSES,
    )


@tasks_bp.route("/kanban")
def kanban_board():
    """Render a 4-column Kanban board grouped by task status."""
    all_tasks = Task.query.order_by(Task.created_at.desc()).all()
    columns = {s: [t for t in all_tasks if t.status == s] for s in VALID_STATUSES}
    return render_template("kanban.html", columns=columns, statuses=VALID_STATUSES)


@tasks_bp.route("/new", methods=["GET", "POST"])
def new_task():
    """Create a task manually."""
    if request.method == "POST":
        try:
            task = create_task(request.form.to_dict())
            flash(f"Task '{task.title}' created.", "success")
            return redirect(url_for("tasks.task_detail", task_id=task.id))
        except TaskValidationError as exc:
            flash(str(exc), "danger")

    return render_template(
        "task_form.html",
        task=None,
        categories=VALID_CATEGORIES,
        priorities=VALID_PRIORITIES,
        statuses=VALID_STATUSES,
    )


@tasks_bp.route("/<int:task_id>")
def task_detail(task_id: int):
    """Display full details of a single task."""
    task = db.session.get(Task, task_id)
    if not task:
        flash("Task not found.", "danger")
        return redirect(url_for("tasks.list_tasks"))
    return render_template("task_detail.html", task=task, statuses=VALID_STATUSES)


@tasks_bp.route("/<int:task_id>/edit", methods=["GET", "POST"])
def edit_task(task_id: int):
    """Edit an existing task."""
    task = db.session.get(Task, task_id)
    if not task:
        flash("Task not found.", "danger")
        return redirect(url_for("tasks.list_tasks"))

    if request.method == "POST":
        try:
            update_task(task, request.form.to_dict())
            flash(f"Task '{task.title}' updated.", "success")
            return redirect(url_for("tasks.task_detail", task_id=task.id))
        except TaskValidationError as exc:
            flash(str(exc), "danger")

    return render_template(
        "task_form.html",
        task=task,
        categories=VALID_CATEGORIES,
        priorities=VALID_PRIORITIES,
        statuses=VALID_STATUSES,
    )


@tasks_bp.route("/<int:task_id>/status", methods=["POST"])
def change_status(task_id: int):
    """Update a task's status via POST."""
    task = db.session.get(Task, task_id)
    if not task:
        flash("Task not found.", "danger")
        return redirect(url_for("tasks.list_tasks"))

    new_status = (request.form.get("status") or "").strip()
    try:
        update_task_status(task, new_status)
        flash(f"Status updated to '{new_status}'.", "success")
    except TaskValidationError as exc:
        flash(str(exc), "danger")

    return redirect(url_for("tasks.task_detail", task_id=task.id))


@tasks_bp.route("/<int:task_id>/delete", methods=["GET", "POST"])
def remove_task(task_id: int):
    """Show confirmation screen on GET; delete task on POST."""
    task = db.session.get(Task, task_id)
    if not task:
        flash("Task not found.", "danger")
        return redirect(url_for("tasks.list_tasks"))

    if request.method == "POST":
        title = task.title
        delete_task(task)
        flash(f"Deleted task '{title}'.", "info")
        return redirect(url_for("tasks.list_tasks"))

    return render_template("task_delete_confirm.html", task=task)
