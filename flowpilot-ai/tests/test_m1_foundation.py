from datetime import date
from app.extensions import db
from app.models.task import Task
from app.models.activity import ActivityLog


def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json()["service"] == "FlowPilot AI"


def test_dashboard_renders(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"FlowPilot AI" in res.data
    assert b"Total Tasks" in res.data


def test_task_and_activity_persistence(app):
    with app.app_context():
        task = Task(
            title="Follow up with ABC supplier",
            description="Check delayed shipment",
            category="Operations",
            priority="High",
            due_date=date(2026, 11, 27),
            assigned_to="Operations Team",
            status="Pending",
        )
        task.action_items = ["Call supplier", "Confirm ETA"]
        db.session.add(task)
        db.session.flush()

        log = ActivityLog(
            event_type="Task approved",
            task_id=task.id,
            details="Approved task: Follow up with ABC supplier",
        )
        db.session.add(log)
        db.session.commit()

        assert Task.query.count() == 1
        assert ActivityLog.query.count() == 1
        assert Task.query.first().action_items == ["Call supplier", "Confirm ETA"]

        # Deleting task preserves activity log with task_id set to None
        db.session.delete(task)
        db.session.commit()
        assert Task.query.count() == 0
        assert ActivityLog.query.count() == 1
