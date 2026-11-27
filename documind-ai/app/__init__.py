from pathlib import Path
from flask import Flask
from app.config import Config
from app.extensions import db
from app.utils.logging_config import configure_logging


def create_app(config_class=Config) -> Flask:
    """Create and configure the Flask application instance."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    configure_logging(app)

    # Ensure storage directories exist
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["VECTOR_INDEX_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)

    # Import models so SQLAlchemy registers all tables
    with app.app_context():
        from app import models  # noqa: F401
        db.create_all()

    # Register blueprints
    from app.routes.dashboard import dashboard_bp
    from app.routes.documents import documents_bp
    from app.routes.assistant import assistant_bp
    from app.routes.exports import exports_bp
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(assistant_bp)
    app.register_blueprint(exports_bp)

    return app
