import secrets

import pytest

from app import create_app
from app.cli import seed_rbac
from app.config import TestConfig
from app.extensions import db
from app.models import CaptchaChallenge, Company, Role, User, UserRole, utcnow
from app.security import hash_password, sha256
from datetime import timedelta

PW = "Str0ng!Passw0rd"


@pytest.fixture()
def app():
    a = create_app(TestConfig)
    with a.app_context():
        db.create_all()
        seed_rbac()
        yield a
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def captcha(answer="abcde"):
    cid = secrets.token_hex(16)
    db.session.add(CaptchaChallenge(id=cid, answer_hash=sha256(answer + cid), expires_at=utcnow() + timedelta(minutes=5)))
    db.session.commit()
    return {"id": cid, "answer": answer}


def make_user(email, role, dept=None, company=None, status="active", must_change=False, password=PW):
    from app.models import Department
    u = User(email=email, full_name=email.split("@")[0].title(), password_hash=hash_password(password), status=status,
             must_change_password=must_change, department_id=Department.query.filter_by(code=dept).one().id if dept else None,
             company_id=company.id if company else None)
    u.assignment = UserRole(role=Role.query.filter_by(name=role).one())
    db.session.add(u)
    db.session.commit()
    return u


class Api:
    def __init__(self, client):
        self.c = client
        self.csrf = None

    def login(self, email, role, password=PW, **kw):
        r = self.c.post("/api/auth/login", json={"identifier": email, "password": password, "portalRole": role,
                                                 "captcha": captcha(), **kw})
        if r.status_code == 200:
            self.csrf = next((c.value for c in self.c._cookies.values() if c.key == "ph_csrf"), None) \
                if hasattr(self.c, "_cookies") else self.c.get_cookie("ph_csrf").value
        return r

    def _h(self):
        return {"X-CSRF-Token": self.csrf} if self.csrf else {}

    def get(self, url, **kw):
        return self.c.get(url, **kw)

    def post(self, url, json=None, **kw):
        return self.c.post(url, json=json, headers=self._h(), **kw)

    def put(self, url, json=None):
        return self.c.put(url, json=json, headers=self._h())

    def delete(self, url):
        return self.c.delete(url, headers=self._h())


@pytest.fixture()
def world(app):
    """Users for each role + two departments' worth of data, two companies."""
    from app.models import Department, Student, Vacancy
    co_a, co_b = Company(name="Acme Ltd"), Company(name="Beta Corp")
    db.session.add_all([co_a, co_b])
    db.session.commit()
    w = {"co_a": co_a, "co_b": co_b,
         "sa": make_user("sa@x.edu", "super_admin"), "dir": make_user("dir@x.edu", "placement_director"),
         "tpo_fin": make_user("tpo.fin@x.edu", "department_tpo", dept="FIN"),
         "tpo_mkt": make_user("tpo.mkt@x.edu", "department_tpo", dept="MKT"),
         "rec_a": make_user("rec@acme.com", "corporate_recruiter", company=co_a),
         "rec_b": make_user("rec@beta.com", "corporate_recruiter", company=co_b),
         "coord": make_user("coord@x.edu", "student_coordinator", dept="FIN")}
    fin, mkt = Department.query.filter_by(code="FIN").one(), Department.query.filter_by(code="MKT").one()
    w["s_fin"] = Student(roll_no="F1", name="Fin One", email="f1@s.edu", department_id=fin.id, batch="2024-26", cgpa=8, coordinator_id=w["coord"].id)
    w["s_mkt"] = Student(roll_no="M1", name="Mkt One", email="m1@s.edu", department_id=mkt.id, batch="2024-26", cgpa=8)
    db.session.add_all([w["s_fin"], w["s_mkt"]])
    w["v_a"] = Vacancy(title="A role", company_id=co_a.id, status="Active", eligible_departments=["FIN"], min_cgpa=6)
    w["v_b"] = Vacancy(title="B role", company_id=co_b.id, status="Active", eligible_departments=["MKT"], min_cgpa=6)
    db.session.add_all([w["v_a"], w["v_b"]])
    db.session.commit()
    return w
