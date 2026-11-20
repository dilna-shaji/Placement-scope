from datetime import timedelta

import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import LoginSession, PasswordReset, User, utcnow
from app.security import sha256
from .conftest import PW, Api, captcha, make_user


def test_correct_login_returns_db_role_and_no_hash(client, world):
    r = Api(client).login("sa@x.edu", "super_admin")
    assert r.status_code == 200
    u = r.get_json()["user"]
    assert u["role"] == "super_admin" and "passwordHash" not in u and "users:manage" in u["permissions"]


def test_incorrect_password(client, world):
    assert Api(client).login("sa@x.edu", "super_admin", password="Wrong!Pass123").status_code == 401


def test_unknown_user_gets_same_error(client, world):
    r = Api(client).login("nobody@x.edu", "super_admin")
    assert r.status_code == 401 and r.get_json()["error"] == "Invalid credentials."


def test_incorrect_role_selection_rejected(client, world):
    r = Api(client).login("tpo.fin@x.edu", "super_admin")  # faculty picks Super Admin portal
    assert r.status_code == 403 and r.get_json()["code"] == "role_mismatch"
    assert client.get("/api/auth/me").status_code == 401  # no session was created


def test_disabled_and_pending_accounts_cannot_login(client, world):
    make_user("off@x.edu", "department_tpo", dept="FIN", status="disabled")
    assert Api(client).login("off@x.edu", "department_tpo").status_code == 403


def test_captcha_failure_and_reuse(client, world):
    r = client.post("/api/auth/login", json={"identifier": "sa@x.edu", "password": PW, "portalRole": "super_admin",
                                              "captcha": {"id": "nope", "answer": "x"}})
    assert r.status_code == 400 and r.get_json()["code"] == "captcha"
    c = captcha()
    body = {"identifier": "sa@x.edu", "password": PW, "portalRole": "super_admin", "captcha": c}
    assert client.post("/api/auth/login", json=body).status_code == 200
    assert client.post("/api/auth/login", json=body).status_code == 400  # one-time use
    bad = captcha()
    bad["answer"] = "wrong"
    assert client.post("/api/auth/login", json={**body, "captcha": bad}).status_code == 400


def test_lockout_after_repeated_failures(client, world):
    for _ in range(5):
        Api(client).login("dir@x.edu", "placement_director", password="Bad!Passw0rd1")
    r = Api(client).login("dir@x.edu", "placement_director")  # correct password, but locked
    assert r.status_code == 423


def test_logout_and_expired_session(client, world):
    a = Api(client)
    a.login("sa@x.edu", "super_admin")
    assert a.get("/api/auth/me").status_code == 200
    s = LoginSession.query.one()
    s.last_seen_at = utcnow() - timedelta(hours=2)  # idle timeout
    db.session.commit()
    assert a.get("/api/auth/me").status_code == 401
    a.login("sa@x.edu", "super_admin")
    assert a.post("/api/auth/logout").status_code == 200
    assert a.get("/api/auth/me").status_code == 401


def test_csrf_required_for_writes(client, world):
    a = Api(client)
    a.login("dir@x.edu", "placement_director")
    r = client.post("/api/companies", json={"name": "NoCsrf"})
    assert r.status_code == 403 and r.get_json()["code"] == "csrf"


def test_temp_password_forces_change(client, world):
    make_user("new@x.edu", "department_tpo", dept="FIN", must_change=True, password="Temp!Passw0rd9")
    a = Api(client)
    assert a.login("new@x.edu", "department_tpo", password="Temp!Passw0rd9").status_code == 200
    assert a.get("/api/students").status_code == 403
    assert a.get("/api/students").get_json()["code"] == "password_change_required"
    assert a.post("/api/auth/change-password", {"currentPassword": "Temp!Passw0rd9", "newPassword": "weak"}).status_code == 400
    assert a.post("/api/auth/change-password", {"currentPassword": "Temp!Passw0rd9", "newPassword": "Brand#New-Passw0rd"}).status_code == 200
    assert a.get("/api/students").status_code == 200


def test_password_reset_flow(client, world, monkeypatch, caplog):
    sent = {}

    def capture_mail(to, subject, body):
        sent.update(to=to, subject=subject, body=body)
        return True

    monkeypatch.setattr("app.auth.send_mail", capture_mail)
    r = client.post("/api/auth/forgot", json={"email": "dir@x.edu", "captcha": captcha()})
    assert r.status_code == 200
    r2 = client.post("/api/auth/forgot", json={"email": "ghost@x.edu", "captcha": captcha()})
    assert r.get_json() == r2.get_json()  # no account enumeration
    token = sent["body"].split("reset_token=")[1].split()[0]
    assert token not in caplog.text
    assert PasswordReset.query.count() == 1
    assert client.post("/api/auth/reset", json={"token": token, "newPassword": "short"}).status_code == 400
    assert client.post("/api/auth/reset", json={"token": token, "newPassword": "Fresh#Passw0rd1"}).status_code == 200
    assert client.post("/api/auth/reset", json={"token": token, "newPassword": "Fresh#Passw0rd2"}).status_code == 400  # single use
    assert Api(client).login("dir@x.edu", "placement_director", password="Fresh#Passw0rd1").status_code == 200


def test_console_mail_does_not_log_or_retain_reset_token(client, world, caplog):
    response = client.post("/api/auth/forgot", json={"email": "dir@x.edu", "captcha": captcha()})
    assert response.status_code == 200
    assert "reset_token=" not in caplog.text
    assert PasswordReset.query.count() == 0


def test_mail_test_endpoint_is_admin_only_and_uses_test_sink(client, world, monkeypatch):
    monkeypatch.setattr("app.admin.send_mail", lambda *_args: True)
    admin = Api(client)
    admin.login("sa@x.edu", "super_admin")
    assert admin.post("/api/mail/test", {"email": "sink@example.edu"}).status_code == 200
    assert admin.post("/api/mail/test", {"email": "not-an-address"}).status_code == 422
    anonymous = client.application.test_client()
    assert anonymous.post("/api/mail/test", json={"email": "sink@example.edu"}).status_code == 401


def test_smtp_uses_encrypted_transport_with_mock_sink(app, monkeypatch):
    import app.security as security

    calls = []

    class MailSink:
        def __init__(self, host, port, **kwargs):
            calls.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def ehlo(self):
            calls.append(("ehlo",))

        def starttls(self, **kwargs):
            calls.append(("starttls", bool(kwargs.get("context"))))

        def login(self, username, password):
            calls.append(("login", username, password))

        def send_message(self, message):
            calls.append(("send", message["To"], message.get_content()))

    monkeypatch.setattr(security.smtplib, "SMTP", MailSink)
    app.config.update(MAIL_MODE="smtp", SMTP_HOST="mail.invalid", SMTP_PORT=587,
                      SMTP_USER="sink-user", SMTP_PASSWORD="sink-password")
    with app.app_context():
        assert security.send_mail("sink@example.edu", "Test", "No external delivery")
    assert ("starttls", True) in calls
    assert ("login", "sink-user", "sink-password") in calls


def test_passwords_are_hashed_with_argon2(world):
    h = User.query.filter_by(email="sa@x.edu").one().password_hash
    assert h.startswith("$argon2id$") and PW not in h


def test_production_requires_secure_session_cookies():
    class InsecureProductionConfig(TestConfig):
        APP_ENV = "production"
        CAPTCHA_PROVIDER = "turnstile"
        SESSION_COOKIE_SECURE_FLAG = False

    with pytest.raises(RuntimeError, match="SESSION_COOKIE_SECURE=true"):
        create_app(InsecureProductionConfig)
