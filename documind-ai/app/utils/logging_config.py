import logging
import sys


def configure_logging(app) -> None:
    """Configure structured application logging without exposing secrets."""
    log_level = logging.DEBUG if app.debug else logging.INFO
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    handler.setFormatter(formatter)

    if not app.logger.handlers:
        app.logger.addHandler(handler)
    app.logger.setLevel(log_level)
