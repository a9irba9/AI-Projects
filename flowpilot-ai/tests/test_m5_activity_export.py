from datetime import datetime, timezone
from app.extensions import db
from app.models.activity import ActivityLog
from app.models.task import Task


def test_activity_history_rendering_and_filters(client, app):
    with app.app_context():
        t = Task(title="Audit Target", category="Operations", priority="High")
        db.session.add(t)
        db.session.flush()
        db.session.add(
            ActivityLog(
                event_type="Task created",
                task_id=t.id,
                details="Created Audit Target",
                created_at=datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc),
            )
        )
        db.session.add(
            ActivityLog(
                event_type="Status changed",
                task_id=t.id,
                details="Changed to In Progress",
                created_at=datetime(2026, 11, 25, 10, 0, tzinfo=timezone.utc),
            )
        )
        db.session.commit()

    # Full page
    res = client.get("/exports/activity")
    assert res.status_code == 200
    body = res.data.decode("utf-8")
    assert body.index("Changed to In Progress") < body.index("Created Audit Target")  # Newest first

    # Event-type filter
    res_ev = client.get("/exports/activity?event_type=Task+created")
    assert b"Created Audit Target" in res_ev.data
    assert b"Changed to In Progress" not in res_ev.data

    # Date-range filter
    res_dt = client.get("/exports/activity?start_date=2026-11-24&end_date=2026-11-26")
    assert b"Changed to In Progress" in res_dt.data
    assert b"Created Audit Target" not in res_dt.data


def test_deleted_task_activity_display(client, app):
    client.post("/tasks/new", data={"title": "Ephemeral Task"})
    with app.app_context():
        task_id = Task.query.first().id
    client.post(f"/tasks/{task_id}/delete")

    res = client.get("/exports/activity")
    assert res.status_code == 200
    assert b"(Deleted task)" in res.data


def test_csv_export_headers_escaping_unicode_nulls_and_formula_injection(client, app):
    with app.app_context():
        t1 = Task(
            title='=CMD("calc")',
            description='Line with, "quotes" and বাংলা টেক্সট',
            category="Sales",
            priority="High",
            assigned_to=None,
            due_date=None,
            status="Pending",
        )
        t2 = Task(
            title="+SUM(A1:A2)",
            description="Normal description",
            category="Finance",
            priority="Low",
            assigned_to="@admin",
            status="Completed",
        )
        db.session.add_all([t1, t2])
        db.session.commit()

    res = client.get("/exports/csv")
    assert res.status_code == 200
    assert "text/csv" in res.content_type
    assert "flowpilot_tasks_" in res.headers["Content-Disposition"]

    csv_text = res.data.decode("utf-8-sig")
    assert "Task ID,Title,Description,Category,Priority,Assigned person/team,Due date,Status,Created timestamp,Updated timestamp" in csv_text
    assert "'=CMD" in csv_text
    assert "'+SUM" in csv_text
    assert "'@admin" in csv_text
    assert "বাংলা টেক্সট" in csv_text
    assert '"Line with, ""quotes"" and বাংলা টেক্সট"' in csv_text

    # Filtered CSV export
    res_filtered = client.get("/exports/csv?category=Finance")
    filtered_text = res_filtered.data.decode("utf-8-sig")
    assert "'+SUM" in filtered_text
    assert "'=CMD" not in filtered_text
