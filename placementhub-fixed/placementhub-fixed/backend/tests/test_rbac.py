from app.extensions import db
from app.models import AccountRequest, Student, User
from .conftest import Api, captcha


def login(client, email, role):
    a = Api(client)
    assert a.login(email, role).status_code == 200
    return a


def test_faculty_cannot_use_super_admin_apis(client, world):
    a = login(client, "tpo.fin@x.edu", "department_tpo")
    for url in ("/api/users", "/api/account-requests", "/api/roles", "/api/settings", "/api/audit", "/api/security/overview"):
        assert a.get(url).status_code == 403, url
    assert a.post("/api/users", {"fullName": "X Y Z", "email": "z@x.edu", "role": "super_admin"}).status_code == 403
    assert a.put("/api/settings", {"max_failed_logins": 99}).status_code == 403


def test_faculty_sees_only_own_department(client, world):
    a = login(client, "tpo.fin@x.edu", "department_tpo")
    names = [s["name"] for s in a.get("/api/students").get_json()["items"]]
    assert names == ["Fin One"]
    assert a.get(f"/api/students/{world['s_mkt'].id}").status_code == 404
    assert a.put(f"/api/students/{world['s_mkt'].id}", {"name": "Hacked"}).status_code == 404
    r = a.post("/api/students", {"rollNo": "X9", "name": "Cross Dept", "email": "x9@s.edu",
                                 "departmentId": world["s_mkt"].department_id, "batch": "2024-26"})
    assert r.status_code == 403
    vac = [v["title"] for v in a.get("/api/vacancies").get_json()["items"]]
    assert vac == ["A role"]


def test_recruiter_isolated_to_own_company(client, world):
    a = login(client, "rec@acme.com", "corporate_recruiter")
    assert [v["title"] for v in a.get("/api/vacancies").get_json()["items"]] == ["A role"]
    assert a.get(f"/api/vacancies/{world['v_b'].id}").status_code == 404
    assert a.put(f"/api/vacancies/{world['v_b'].id}", {"title": "x"}).status_code == 404
    assert [c["name"] for c in a.get("/api/companies").get_json()["items"]] == ["Acme Ltd"]
    assert a.get("/api/students").get_json()["items"] == []  # no applicants shared yet
    for url in ("/api/placements", "/api/audit", "/api/users", "/api/reports/export?dataset=students&format=csv"):
        assert a.get(url).status_code == 403, url
    # tries to create a vacancy for another company and to self-approve
    r = a.post("/api/vacancies", {"title": "Sneaky", "companyId": world["co_b"].id, "status": "Approved"})
    assert r.status_code == 403
    r = a.post("/api/vacancies", {"title": "Mine", "companyId": world["co_b"].id, "status": "Draft"})
    assert r.status_code == 201 and r.get_json()["companyId"] == world["co_a"].id  # forced to own company


def test_recruiter_sees_only_limited_applicant_fields(client, world, app):
    from app.models import Application
    db.session.add(Application(student_id=world["s_fin"].id, vacancy_id=world["v_a"].id))
    db.session.commit()
    a = login(client, "rec@acme.com", "corporate_recruiter")
    s = a.get("/api/students").get_json()["items"]
    assert len(s) == 1 and "email" not in s[0] and "phone" not in s[0]
    b = login(client, "rec@beta.com", "corporate_recruiter")
    assert b.get("/api/students").get_json()["items"] == []


def test_coordinator_limited(client, world):
    a = login(client, "coord@x.edu", "student_coordinator")
    assert [s["name"] for s in a.get("/api/students").get_json()["items"]] == ["Fin One"]
    assert a.put("/api/settings", {"lockout_minutes": 1}).status_code == 403
    assert a.post("/api/roles/1/permissions", {}).status_code in (403, 405)
    assert a.put("/api/roles/1/permissions", {"permissions": []}).status_code == 403
    assert a.post("/api/companies", {"name": "Nope"}).status_code == 403
    assert a.delete(f"/api/students/{world['s_fin'].id}").status_code == 403


def test_only_super_admin_approves_requests(client, world):
    r = client.post("/api/auth/request-account", json={
        "fullName": "New Faculty", "email": "nf@x.edu", "requestedRole": "department_tpo", "departmentId": world["tpo_fin"].department_id,
        "reason": "Need access for placement coordination", "captcha": captcha()})
    assert r.status_code == 201
    rid = AccountRequest.query.one().id
    assert AccountRequest.query.one().status == "Pending Approval" and User.query.filter_by(email="nf@x.edu").count() == 0
    d = login(client, "dir@x.edu", "placement_director")
    assert d.post(f"/api/account-requests/{rid}/approve", {"role": "department_tpo"}).status_code == 403
    assert login(client, "tpo.fin@x.edu", "department_tpo").post(f"/api/account-requests/{rid}/approve", {"role": "department_tpo"}).status_code == 403
    s = login(client, "sa@x.edu", "super_admin")
    r = s.post(f"/api/account-requests/{rid}/approve", {"role": "department_tpo", "departmentId": world["tpo_fin"].department_id})
    assert r.status_code == 200
    cred = r.get_json()["credentials"]
    assert cred["temporaryPassword"] and cred["loginId"] == "nf@x.edu"
    u = User.query.filter_by(email="nf@x.edu").one()
    assert u.must_change_password and cred["temporaryPassword"] not in u.password_hash
    assert s.post(f"/api/account-requests/{rid}/approve", {"role": "department_tpo"}).status_code == 409


def test_self_registration_as_privileged_role_is_refused(client, world):
    for role in ("super_admin", "placement_director"):
        r = client.post("/api/auth/request-account", json={"fullName": "Mistaken Person", "email": f"{role}@x.edu",
                                                           "requestedRole": role, "reason": "I picked the wrong role", "captcha": captcha()})
        assert r.status_code == 400
    assert AccountRequest.query.count() == 0


def test_admin_assigned_role_is_authoritative(client, world):
    """A faculty request is approved as faculty even if the requester asked for something else."""
    client.post("/api/auth/request-account", json={"fullName": "Some Faculty", "email": "sf@x.edu", "requestedRole": "department_tpo",
                                                   "departmentId": world["tpo_fin"].department_id, "reason": "placement duties here", "captcha": captcha()})
    s = login(client, "sa@x.edu", "super_admin")
    rid = AccountRequest.query.one().id
    s.post(f"/api/account-requests/{rid}/approve", {"role": "student_coordinator", "departmentId": world["tpo_fin"].department_id})
    assert User.query.filter_by(email="sf@x.edu").one().role_name == "student_coordinator"


def test_role_change_revokes_access_and_cannot_self_elevate(client, world):
    s = login(client, "sa@x.edu", "super_admin")
    uid = world["tpo_fin"].id
    t = login(Api(client.application.test_client()).c, "tpo.fin@x.edu", "department_tpo")
    assert t.get("/api/students").status_code == 200
    assert s.put(f"/api/users/{uid}", {"role": "placement_director"}).status_code == 200
    assert t.get("/api/students").status_code == 401  # sessions revoked on role change
    # old portal selection no longer works, new one does
    assert Api(client.application.test_client()).login("tpo.fin@x.edu", "department_tpo").status_code == 403
    assert Api(client.application.test_client()).login("tpo.fin@x.edu", "placement_director").status_code == 200
    assert s.put(f"/api/users/{world['sa'].id}", {"role": "placement_director"}).status_code == 403  # own role
    assert s.post(f"/api/users/{world['sa'].id}/status", {"status": "disabled"}).status_code == 403  # self


def test_revoke_access_blocks_live_session(client, world):
    s = login(client, "sa@x.edu", "super_admin")
    d = login(Api(client.application.test_client()).c, "dir@x.edu", "placement_director")
    assert d.get("/api/companies").status_code == 200
    assert s.post(f"/api/users/{world['dir'].id}/status", {"status": "disabled"}).status_code == 200
    assert d.get("/api/companies").status_code == 401
    assert Api(client.application.test_client()).login("dir@x.edu", "placement_director").status_code == 403


def test_cannot_demote_last_super_admin(client, world):
    s = login(client, "sa@x.edu", "super_admin")
    other = s.post("/api/users", {"fullName": "Second Admin", "email": "sa2@x.edu", "role": "super_admin"}).get_json()["user"]["id"]
    assert s.put(f"/api/users/{other}", {"role": "placement_director"}).status_code == 200  # one SA remains (self)
    assert s.post(f"/api/users/{other}/status", {"status": "disabled"}).status_code == 200


def test_cannot_grant_system_permissions_to_other_roles(client, world):
    from app.models import Role
    s = login(client, "sa@x.edu", "super_admin")
    rid = Role.query.filter_by(name="placement_director").one().id
    assert s.put(f"/api/roles/{rid}/permissions", {"permissions": ["users:manage"]}).status_code == 403
    assert s.put(f"/api/roles/{rid}/permissions", {"permissions": ["students:read", "dashboard:view"]}).status_code == 200
    d = login(Api(client.application.test_client()).c, "dir@x.edu", "placement_director")
    assert d.get("/api/companies").status_code == 403  # permission removal takes effect immediately


def test_forged_role_in_payload_is_ignored(client, world):
    a = Api(client)
    r = a.login("tpo.fin@x.edu", "department_tpo", forgedRole="super_admin", roleName="super_admin")
    assert r.get_json()["user"]["role"] == "department_tpo"
    assert a.get("/api/users").status_code == 403
