from app.models.activity import ActivityLog
from app.models.task import Task


def test_task_create_and_detail_view(client, app):
    res = client.post(
        "/tasks/new",
        data={
            "title": "Follow up with ABC supplier",
            "description": "Delayed shipment check",
            "category": "Operations",
            "priority": "High",
            "status": "Pending",
            "due_date": "2026-12-01",
            "assigned_to": "Ops Team",
            "action_items": "Call supplier\nUpdate tracker",
        },
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"Follow up with ABC supplier" in res.data
    assert b"Call supplier" in res.data

    with app.app_context():
        assert Task.query.count() == 1
        assert ActivityLog.query.filter_by(event_type="Task created").count() == 1


def test_task_edit_and_status_transitions(client, app):
    client.post(
        "/tasks/new",
        data={"title": "Budget review", "category": "Finance", "priority": "Medium"},
    )
    with app.app_context():
        task_id = Task.query.first().id

    # Edit
    res = client.post(
        f"/tasks/{task_id}/edit",
        data={
            "title": "Q4 Budget review",
            "description": "Updated",
            "category": "Finance",
            "priority": "Critical",
            "status": "Pending",
            "due_date": "",
        },
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"Q4 Budget review" in res.data

    # Every status transition
    for new_status in ("In Progress", "Completed", "Cancelled", "Pending"):
        res = client.post(
            f"/tasks/{task_id}/status",
            data={"status": new_status},
            follow_redirects=True,
        )
        assert res.status_code == 200
        assert new_status.encode() in res.data

    with app.app_context():
        assert ActivityLog.query.filter_by(event_type="Task edited").count() == 1
        assert ActivityLog.query.filter_by(event_type="Status changed").count() == 4


def test_task_delete_preserves_activity_history(client, app):
    client.post("/tasks/new", data={"title": "Temp task"})
    with app.app_context():
        task_id = Task.query.first().id

    # GET confirmation page
    assert client.get(f"/tasks/{task_id}/delete").status_code == 200
    # POST delete
    res = client.post(f"/tasks/{task_id}/delete", follow_redirects=True)
    assert res.status_code == 200
    assert b"Deleted task" in res.data

    with app.app_context():
        assert Task.query.count() == 0
        assert ActivityLog.query.filter_by(event_type="Task deleted").count() == 1
        assert ActivityLog.query.count() == 2  # created + deleted preserved


def test_search_filter_and_sort(client):
    client.post(
        "/tasks/new",
        data={
            "title": "Alpha Ops",
            "category": "Operations",
            "priority": "High",
            "status": "Pending",
            "due_date": "2026-12-10",
        },
        follow_redirects=True,
    )
    client.post(
        "/tasks/new",
        data={
            "title": "Beta Sales",
            "description": "Follow up with client",
            "category": "Sales",
            "priority": "Low",
            "status": "Completed",
            "due_date": "2026-12-01",
        },
        follow_redirects=True,
    )

    # Search
    res = client.get("/tasks/?q=Alpha")
    assert b"Alpha Ops" in res.data
    assert b"Beta Sales" not in res.data

    # Combined filters
    res = client.get("/tasks/?category=Sales&priority=Low&status=Completed")
    assert b"Beta Sales" in res.data
    assert b"Alpha Ops" not in res.data

    # Sort by due_asc
    res = client.get("/tasks/?sort=due_asc")
    body = res.data.decode("utf-8")
    assert body.index("Beta Sales") < body.index("Alpha Ops")


def test_invalid_input_handling(client, app):
    # Missing title
    res = client.post("/tasks/new", data={"title": "   "})
    assert b"Task title is required" in res.data

    # Invalid category
    res = client.post("/tasks/new", data={"title": "Test", "category": "InvalidCat"})
    assert b"Invalid category" in res.data

    # Invalid priority
    res = client.post("/tasks/new", data={"title": "Test", "priority": "Ultra"})
    assert b"Invalid priority" in res.data

    # Invalid due date
    res = client.post("/tasks/new", data={"title": "Test", "due_date": "not-a-date"})
    assert b"Invalid due date format" in res.data

    with app.app_context():
        assert Task.query.count() == 0
