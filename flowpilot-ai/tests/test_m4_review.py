from app import create_app
from config import TestConfig
from app.extensions import db
from app.models.activity import ActivityLog
from app.models.task import Task


def test_create_task_page_renders(client):
    res = client.get("/ai/create")
    assert res.status_code == 200
    assert b"Create Task with AI" in res.data


def test_demo_mode_extraction_and_review_display(client, app):
    with app.app_context():
        app.config["GEMINI_API_KEY"] = ""

    res = client.post(
        "/ai/process",
        data={
            "user_request": "The delivery to ABC Manufacturing is delayed. Follow up with the supplier tomorrow and mark it as high priority."
        },
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"Demo Mode" in res.data
    assert b"Follow up with ABC Manufacturing supplier" in res.data
    with app.app_context():
        assert Task.query.count() == 0  # Not saved until approved


def test_review_edit_and_approve_once(client, app):
    with app.app_context():
        app.config["GEMINI_API_KEY"] = ""

    client.post(
        "/ai/process",
        data={"user_request": "Follow up with ABC Manufacturing tomorrow"},
        follow_redirects=True,
    )
    with client.session_transaction() as sess:
        review_id = sess["pending_review"]["review_id"]

    # Approve with edited title & priority
    res = client.post(
        "/ai/approve",
        data={
            "review_id": review_id,
            "title": "Edited Supplier Follow-up",
            "description": "User edited description",
            "category": "Operations",
            "priority": "Critical",
            "due_date": "2026-12-01",
            "assigned_to": "Supply Chain",
            "action_items": "Call vendor\nConfirm ETA",
        },
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"Edited Supplier Follow-up" in res.data

    # Repeated approval must NOT create a second task
    res2 = client.post(
        "/ai/approve",
        data={"review_id": review_id, "title": "Edited Supplier Follow-up"},
        follow_redirects=True,
    )
    assert b"already processed" in res2.data

    with app.app_context():
        assert Task.query.count() == 1
        assert Task.query.first().priority == "Critical"
        assert ActivityLog.query.filter_by(event_type="Task approved").count() == 1


def test_reject_creates_no_task(client, app):
    with app.app_context():
        app.config["GEMINI_API_KEY"] = ""

    client.post(
        "/ai/process",
        data={"user_request": "Follow up with ABC Manufacturing tomorrow"},
        follow_redirects=True,
    )
    res = client.post("/ai/reject", follow_redirects=True)
    assert res.status_code == 200
    assert b"rejected" in res.data

    with app.app_context():
        assert Task.query.count() == 0
        assert ActivityLog.query.filter_by(event_type="Task rejected").count() == 1


def test_invalid_edited_values_rejected(client, app):
    with app.app_context():
        app.config["GEMINI_API_KEY"] = ""

    client.post(
        "/ai/process",
        data={"user_request": "Follow up with ABC Manufacturing tomorrow"},
    )
    with client.session_transaction() as sess:
        review_id = sess["pending_review"]["review_id"]

    res = client.post(
        "/ai/approve",
        data={
            "review_id": review_id,
            "title": "Valid Title",
            "category": "BadCategory",
            "priority": "High",
        },
        follow_redirects=True,
    )
    assert b"Invalid category" in res.data
    with app.app_context():
        assert Task.query.count() == 0


def test_missing_review_session_handled(client):
    res = client.get("/ai/review", follow_redirects=True)
    assert res.status_code == 200
    assert b"No pending task review found" in res.data


def test_clarification_blocks_approval_until_due_date_provided(client, app):
    with app.app_context():
        app.config["GEMINI_API_KEY"] = ""

    # Request without date triggers clarification in Demo Mode
    client.post(
        "/ai/process",
        data={"user_request": "Prepare quarterly budget report"},
    )
    with client.session_transaction() as sess:
        review_id = sess["pending_review"]["review_id"]

    res = client.post(
        "/ai/approve",
        data={
            "review_id": review_id,
            "title": "Prepare quarterly budget report",
            "category": "Finance",
            "priority": "Medium",
            "due_date": "",
        },
        follow_redirects=True,
    )
    assert b"Clarification is required" in res.data
    with app.app_context():
        assert Task.query.count() == 0


def test_csrf_and_post_only_enforcement():
    class CsrfTestConfig(TestConfig):
        WTF_CSRF_ENABLED = True

    app = create_app(CsrfTestConfig)
    with app.app_context():
        db.create_all()
        c = app.test_client()
        assert c.get("/ai/process").status_code == 405
        assert c.post("/ai/process", data={"user_request": "Test"}).status_code == 400
