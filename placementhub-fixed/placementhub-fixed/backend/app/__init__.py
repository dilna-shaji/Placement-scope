import os

from flask import Flask, jsonify

from .config import Config
from .errors import ApiError
from .extensions import db, migrate


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(config or Config)
    cfg = app.config
    if cfg["APP_ENV"] != "testing":
        if len(cfg["SECRET_KEY"]) < 32 or cfg["SECRET_KEY"].startswith("change-me"):
            raise RuntimeError("Set SECRET_KEY in backend/.env to a random string of at least 32 characters.")
        if not cfg["SQLALCHEMY_DATABASE_URI"]:
            raise RuntimeError("Set DATABASE_URL in backend/.env (see .env.example).")
    if cfg["APP_ENV"] == "production" and cfg["CAPTCHA_PROVIDER"] != "turnstile":
        raise RuntimeError("Production requires CAPTCHA_PROVIDER=turnstile with TURNSTILE_* keys.")

    db.init_app(app)
    migrate.init_app(app, db)

    from . import admin, auth, files, insights, resources
    from .cli import register_cli
    for m in (auth, resources, admin, insights, files):
        app.register_blueprint(m.bp)
    register_cli(app)

    @app.errorhandler(ApiError)
    def api_error(e):
        db.session.rollback()
        body = {"error": e.message}
        if e.fields:
            body["fields"] = e.fields
        if e.code:
            body["code"] = e.code
        return jsonify(body), e.status

    @app.errorhandler(404)
    def nf(_):
        return jsonify({"error": "Not found."}), 404

    @app.errorhandler(405)
    def na(_):
        return jsonify({"error": "Method not allowed."}), 405

    @app.errorhandler(413)
    def big(_):
        return jsonify({"error": "Upload too large."}), 413

    @app.errorhandler(Exception)
    def unexpected(e):  # secure error handling: never leak internals to the client
        db.session.rollback()
        app.logger.exception("Unhandled error")
        return jsonify({"error": "Unexpected server error."}), 500

    @app.after_request
    def headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    os.makedirs(cfg["UPLOAD_DIR"], exist_ok=True)
    return app
