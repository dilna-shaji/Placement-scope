"""Regression tests for bugs fixed in the login/session, applications, notifications and aggregation code."""
from app.extensions import db
from app.models import Application
from .conftest import PW, Api, captcha, make_user


def _login_body(**over):
    body = {"identifier": "sa@x.edu", "password": PW, "portalRole": "super_admin", "captcha": captcha()}
    body.update(over)
    return body


# ---------------------------------------------------------------- login / cookies / captcha
def test_captcha_answer_is_case_and_space_tolerant(client, world):
    c = captcha("abcde")
    c["answer"] = " A B c D e "
    assert client.post("/api/auth/login", json=_login_body(captcha=c)).status_code == 200


def test_missing_captcha_answer_has_clear_message(client, world):
    c = captcha()
    c["answer"] = ""
    r = client.post("/api/auth/login", json=_login_body(captcha=c))
    assert r.status_code == 400 and r.get_json()["code"] == "captcha"


def test_session_cookie_not_secure_over_plain_http_even_if_flag_is_on(app, client, world):
    """A Secure cookie is dropped by browsers on http://localhost, which looked like an instantly expired session."""
    app.config["SESSION_COOKIE_SECURE_FLAG"] = True
    r = client.post("/api/auth/login", json=_login_body())
    assert r.status_code == 200
    cookies = " ".join(r.headers.getlist("Set-Cookie")).lower()
    assert "ph_session=" in cookies and "secure" not in cookies
    assert client.get("/api/auth/me").status_code == 200  # the cookie was kept and is accepted


def test_session_cookie_secure_behind_https_proxy(app, client, world):
    app.config["SESSION_COOKIE_SECURE_FLAG"] = True
    r = client.post("/api/auth/login", json=_login_body(), headers={"X-Forwarded-Proto": "https"})
    assert "secure" in " ".join(r.headers.getlist("Set-Cookie")).lower()


def test_bad_idle_setting_does_not_break_sessions(client, world):
    from app.models import SystemSetting
    db.session.add(SystemSetting(key="session_idle_minutes", value="not-a-number"))
    db.session.commit()
    a = Api(client)
    assert a.login("sa@x.edu", "super_admin").status_code == 200
    assert a.get("/api/auth/me").status_code == 200


# ---------------------------------------------------------------- notifications stream
def test_notification_stream_is_valid_sse(client, world):
    a = Api(client)
    a.login("sa@x.edu", "super_admin")
    r = a.get("/api/notifications/stream")
    assert r.status_code == 200 and r.mimetype == "text/event-stream"
    body = r.get_data(as_text=True)
    assert "data:" in body and '"unread"' in body and "event:" not in body  # unnamed -> EventSource.onmessage fires
    assert "Connection" not in r.headers  # hop-by-hop headers are rejected by waitress


# ---------------------------------------------------------------- applications: privilege checks
def _application(world):
    a = Application(student_id=world["s_fin"].id, vacancy_id=world["v_a"].id, stage="Applied")
    db.session.add(a)
    db.session.commit()
    return a


def test_student_portal_login_is_disabled_and_application_records_remain(client, world):
    app_row = _application(world)
    make_user("f1@s.edu", "student")
    api = Api(client)
    # Existing Student-role accounts may remain in the database, but cannot sign in.
    response = api.login("f1@s.edu", "student")
    assert response.status_code == 400
    assert client.get("/api/auth/me").status_code == 401
    # Student application data is retained; disabling the portal does not delete records.
    assert db.session.get(Application, app_row.id).stage == "Applied"


def test_candidate_list_is_scoped_to_role(client, world):
    fin = _application(world)
    mkt = Application(student_id=world["s_mkt"].id, vacancy_id=world["v_b"].id, stage="Applied")
    db.session.add(mkt)
    db.session.commit()

    tpo = Api(client)
    tpo.login("tpo.fin@x.edu", "department_tpo")
    ids = {c["id"] for c in tpo.get("/api/recruiter/candidates").get_json()["items"]}
    assert ids == {fin.id}

    other = Api(client.application.test_client())
    other.login("rec@acme.com", "corporate_recruiter")
    ids = {c["id"] for c in other.get("/api/recruiter/candidates").get_json()["items"]}
    assert ids == {fin.id}  # Acme's vacancy only; never Beta's applicant


def test_tpo_cannot_move_candidate_outside_department(client, world):
    mkt = Application(student_id=world["s_mkt"].id, vacancy_id=world["v_b"].id, stage="Applied")
    db.session.add(mkt)
    db.session.commit()
    tpo = Api(client)
    tpo.login("tpo.fin@x.edu", "department_tpo")
    assert tpo.put(f"/api/recruiter/candidates/{mkt.id}/stage", {"stage": "Shortlisted"}).status_code == 404


def test_stage_update_validates_score(client, world):
    app_row = _application(world)
    rec = Api(client)
    rec.login("rec@acme.com", "corporate_recruiter")
    assert rec.put(f"/api/recruiter/candidates/{app_row.id}/stage", {"stage": "Shortlisted", "score": "abc"}).status_code == 422
    assert rec.put(f"/api/recruiter/candidates/{app_row.id}/stage", {"stage": "Shortlisted", "score": 140}).status_code == 422
    assert rec.put(f"/api/recruiter/candidates/{app_row.id}/stage", {"stage": "Shortlisted", "score": 80}).status_code == 200


def test_bad_pagination_is_a_400_not_a_500(client, world):
    a = Api(client)
    a.login("sa@x.edu", "super_admin")
    assert a.get("/api/students?page=abc").status_code == 400


# ---------------------------------------------------------------- aggregation pipeline
def test_aggregation_pipeline_runs_offline(client, world):
    """Used to crash with NameError (missing `import re`) as soon as the first job was processed."""
    a = Api(client)
    a.login("sa@x.edu", "super_admin")
    r = a.post("/api/aggregation/run", {"source": "curated-only"})
    assert r.status_code == 200, r.get_data(as_text=True)
    out = r.get_json()
    assert out["created"] >= 1
    from app.models import Vacancy
    assert {v.job_type for v in Vacancy.query.filter(Vacancy.source.like("Scraper%"))} <= {"Full-Time", "Internship + PPO", "Internship Only"}
