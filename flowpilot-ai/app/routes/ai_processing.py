import uuid
from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from app.extensions import db
from app.services.activity_service import log_activity
from app.services.task_extraction import (
    ExtractionError,
    extract_multiple_tasks_from_request,
    extract_task_from_request,
)
from app.services.task_service import (
    VALID_CATEGORIES,
    VALID_PRIORITIES,
    TaskValidationError,
    create_task,
)

ai_bp = Blueprint("ai_processing", __name__, url_prefix="/ai")


@ai_bp.route("/create", methods=["GET"])
def create_task_page():
    """Render the natural-language Create Task page."""
    return render_template("create_task.html")


@ai_bp.route("/process", methods=["POST"])
def process_request():
    """Process a natural-language request via Gemini/Demo Mode and stage for human review."""
    user_request = (request.form.get("user_request") or "").strip()
    if not user_request:
        flash("Please enter a business request.", "warning")
        return redirect(url_for("ai_processing.create_task_page"))

    try:
        extracted = extract_task_from_request(user_request)
    except ExtractionError as exc:
        flash(f"AI processing failed: {exc}", "danger")
        return redirect(url_for("ai_processing.create_task_page"))

    log_activity(
        "AI request processed",
        details=f"Processed request ({'Demo Mode' if extracted.get('is_demo') else 'Gemini'}): {user_request[:120]}",
    )
    db.session.commit()

    session["pending_review"] = {
        "review_id": uuid.uuid4().hex,
        "original_request": user_request,
        "extracted": extracted,
    }
    return redirect(url_for("ai_processing.review_task_page"))


@ai_bp.route("/review", methods=["GET"])
def review_task_page():
    """Display the editable human-in-the-loop review screen."""
    pending = session.get("pending_review")
    if not pending:
        flash("No pending task review found or session expired.", "warning")
        return redirect(url_for("ai_processing.create_task_page"))

    return render_template(
        "review_task.html",
        review_id=pending["review_id"],
        original_request=pending["original_request"],
        extracted=pending["extracted"],
        categories=VALID_CATEGORIES,
        priorities=VALID_PRIORITIES,
    )


@ai_bp.route("/approve", methods=["POST"])
def approve_task():
    """Validate edited fields, create the task, and clear the pending review."""
    pending = session.get("pending_review")
    submitted_review_id = request.form.get("review_id", "")

    if not pending or pending.get("review_id") != submitted_review_id:
        flash("Pending review not found or already processed.", "warning")
        return redirect(url_for("ai_processing.create_task_page"))

    extracted = pending["extracted"]
    due_date_val = (request.form.get("due_date") or "").strip()

    if extracted.get("requires_clarification") and not due_date_val:
        flash(
            "Clarification is required before approval. Please provide a valid due date.",
            "warning",
        )
        return redirect(url_for("ai_processing.review_task_page"))

    payload = {
        "title": request.form.get("title", ""),
        "description": request.form.get("description", ""),
        "category": request.form.get("category", "General"),
        "priority": request.form.get("priority", "Medium"),
        "status": "Pending",
        "due_date": due_date_val,
        "assigned_to": request.form.get("assigned_to", ""),
        "action_items": request.form.get("action_items", ""),
    }

    try:
        task = create_task(
            payload,
            original_request=pending["original_request"],
            confidence=extracted.get("confidence"),
            event_type="Task approved",
        )
    except TaskValidationError as exc:
        flash(f"Validation error: {exc}", "danger")
        return redirect(url_for("ai_processing.review_task_page"))

    session.pop("pending_review", None)
    flash(f"Task '{task.title}' approved and saved.", "success")
    return redirect(url_for("tasks.task_detail", task_id=task.id))


@ai_bp.route("/reject", methods=["POST"])
def reject_task():
    """Discard the pending review without creating a task."""
    pending = session.pop("pending_review", None)
    if pending:
        log_activity(
            "Task rejected",
            details=f"Rejected AI suggestion for: {pending['original_request'][:120]}",
        )
        db.session.commit()
        flash("AI task suggestion rejected and discarded.", "info")
    else:
        flash("No pending review to reject.", "warning")
    return redirect(url_for("ai_processing.create_task_page"))


@ai_bp.route("/process-batch", methods=["POST"])
def process_batch_request():
    """Extract multiple tasks from meeting notes or email threads for batch human review."""
    user_request = (request.form.get("user_request") or "").strip()
    if not user_request:
        flash("Please enter meeting notes or a business request.", "warning")
        return redirect(url_for("ai_processing.create_task_page"))

    try:
        tasks_list = extract_multiple_tasks_from_request(user_request)
    except ExtractionError as exc:
        flash(f"Batch AI processing failed: {exc}", "danger")
        return redirect(url_for("ai_processing.create_task_page"))

    log_activity(
        "AI request processed",
        details=f"Batch processed ({len(tasks_list)} proposed tasks): {user_request[:100]}",
    )
    db.session.commit()

    session["pending_batch_review"] = {
        "review_id": uuid.uuid4().hex,
        "original_request": user_request,
        "tasks": tasks_list,
    }
    return redirect(url_for("ai_processing.review_batch_page"))


@ai_bp.route("/review-batch", methods=["GET"])
def review_batch_page():
    """Display batch review screen for multiple AI-proposed tasks."""
    pending = session.get("pending_batch_review")
    if not pending:
        flash("No pending batch review found.", "warning")
        return redirect(url_for("ai_processing.create_task_page"))

    return render_template(
        "review_batch.html",
        review_id=pending["review_id"],
        original_request=pending["original_request"],
        tasks=pending["tasks"],
        categories=VALID_CATEGORIES,
        priorities=VALID_PRIORITIES,
    )


@ai_bp.route("/approve-batch", methods=["POST"])
def approve_batch():
    """Approve selected tasks from a batch extraction."""
    pending = session.get("pending_batch_review")
    submitted_id = request.form.get("review_id", "")
    if not pending or pending.get("review_id") != submitted_id:
        flash("Pending batch review not found or already processed.", "warning")
        return redirect(url_for("ai_processing.create_task_page"))

    created_count = 0
    for idx in range(len(pending["tasks"])):
        if not request.form.get(f"include_{idx}"):
            continue
        payload = {
            "title": request.form.get(f"title_{idx}", ""),
            "description": request.form.get(f"description_{idx}", ""),
            "category": request.form.get(f"category_{idx}", "General"),
            "priority": request.form.get(f"priority_{idx}", "Medium"),
            "status": "Pending",
            "due_date": request.form.get(f"due_date_{idx}", ""),
            "assigned_to": request.form.get(f"assigned_to_{idx}", ""),
            "action_items": [],
        }
        try:
            create_task(
                payload,
                original_request=pending["original_request"],
                confidence=pending["tasks"][idx].get("confidence"),
                event_type="Task approved",
            )
            created_count += 1
        except TaskValidationError as exc:
            flash(f"Skipped task #{idx + 1}: {exc}", "warning")

    session.pop("pending_batch_review", None)
    flash(f"Approved and saved {created_count} task(s).", "success")
    return redirect(url_for("tasks.list_tasks"))
