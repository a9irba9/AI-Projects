import secrets
from flask import Flask, abort, request, session
from config import Config
from app.extensions import db


def _get_csrf_token() -> str:
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(16)
    return session["_csrf_token"]


def create_app(config_class=Config) -> Flask:
    """Create and configure the FlowPilot AI Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    app.jinja_env.globals["csrf_token"] = _get_csrf_token

    @app.before_request
    def csrf_protect():
        if request.method == "POST" and app.config.get("WTF_CSRF_ENABLED", True):
            token = session.get("_csrf_token")
            submitted = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
            if not token or token != submitted:
                abort(400, description="CSRF token missing or invalid.")

    with app.app_context():
        from app import models  # noqa: F401
        db.create_all()

    from app.routes.dashboard import dashboard_bp
    from app.routes.tasks import tasks_bp
    from app.routes.ai_processing import ai_bp
    from app.routes.exports import exports_bp
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(exports_bp)

    return app
