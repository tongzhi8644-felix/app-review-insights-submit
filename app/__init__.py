import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

from app.extensions import db
from app.routes.api import api_bp
from app.routes.main import main_bp

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def create_app():
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config.from_object("app.config.Config")

    db.init_app(app)

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    with app.app_context():
        from app import models  # noqa: F401

        try:
            db.create_all()
        except Exception as exc:  # pragma: no cover - startup diagnostics
            app.logger.warning("DB create_all skipped/failed: %s", exc)

    return app
