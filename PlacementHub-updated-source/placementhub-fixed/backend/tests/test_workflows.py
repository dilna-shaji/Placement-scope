import io

from app.extensions import db
from app.models import Notification, Student
from .conftest import Api, captcha


def login(client, email, role):
    a = Api(client)
    assert a.login(email, role).status_code == 200
    return a


def test_student_crud(client, world):
    a = login(client, "dir@x.edu", "placement_director")
    r = a.post("/api/students", {"rollNo": "N1", "name": "New Student", "email": "n1@s.edu", "departmentId": world["s_fin"].department_id,
                                 "batch": "2025-27", "cgpa": 7.5, "skills": ["Excel", "SQL"]})
    assert r.status_code == 201
    sid = r.get_json()["id"]
    assert a.put(f"/api/students/{sid}", {"cgpa": 8.1, "status": "In Process"}).get_json()["cgpa"] == 8.1
    assert a.post("/api/students", {"rollNo": "N1", "name": "Dup", "email": "d@s.edu", "departmentId": 1, "batch": "x"}).status_code == 409
    assert a.post("/api/students", {"rollNo": "N2", "name": "Bad", "email": "bad", "departmentId": 1, "batch": "x", "cgpa": 15}).status_code == 422
    assert a.get("/api/students?q=New").get_json()["total"] == 1
    assert a.delete(f"/api/students/{sid}").status_code == 200


def test_vacancy_verification_workflow(client, world):
    rec = login(client, "rec@acme.com", "corporate_recruiter")
    v = rec.post("/api/vacancies", {"title": "Analyst", "ctcLpa": 9, "eligibleDepartments": ["FIN"], "locations": ["Pune"]}).get_json()
    assert v["status"] == "Draft"
    assert rec.post(f"/api/vacancies/{v['id']}/review", {"decision": "approve"}).status_code == 403
    assert rec.post(f"/api/vacancies/{v['id']}/submit").get_json()["status"] == "Pending Verification"
    d = login(Api(client.application.test_client()).c, "dir@x.edu", "placement_director")
    assert d.post(f"/api/vacancies/{v['id']}/review", {"decision": "return", "note": ""}).status_code == 422
    assert d.post(f"/api/vacancies/{v['id']}/review", {"decision": "approve", "note": "ok"}).get_json()["status"] == "Approved"
    assert Notification.query.filter_by(user_id=world["rec_a"].id).count() == 1
    # editing a live vacancy sends it back to verification
    assert rec.put(f"/api/vacancies/{v['id']}", {"ctcLpa": 10}).get_json()["status"] == "Pending Verification"


def test_company_drive_application_internship_placement(client, world):
    d = login(client, "dir@x.edu", "placement_director")
    c = d.post("/api/companies", {"name": "Gamma Inc", "tier": "Dream (12-20 LPA)", "mouStatus": "Signed"}).get_json()
    assert d.post("/api/companies", {"name": "Gamma Inc"}).status_code == 409
    dr = d.post("/api/drives", {"title": "Gamma Drive", "companyId": c["id"], "date": "2026-12-01", "mode": "Virtual"})
    assert dr.status_code == 201 and dr.get_json()["companyName"] == "Gamma Inc"
    # application: eligible student/vacancy
    tpo = login(Api(client.application.test_client()).c, "tpo.fin@x.edu", "department_tpo")
    app_ = tpo.post("/api/applications", {"studentId": world["s_fin"].id, "vacancyId": world["v_a"].id})
    assert app_.status_code == 201
    aid = app_.get_json()["id"]
    assert tpo.post("/api/applications", {"studentId": world["s_fin"].id, "vacancyId": world["v_a"].id}).status_code == 409
    assert tpo.put(f"/api/applications/{aid}", {"stage": "Technical", "score": 71}).get_json()["stage"] == "Technical"
    assert tpo.put(f"/api/applications/{aid}", {"stage": "Bogus"}).status_code == 422
    # ineligible: marketing vacancy for finance student
    assert d.post("/api/applications", {"studentId": world["s_fin"].id, "vacancyId": world["v_b"].id}).status_code == 422
    # internship
    i = tpo.post("/api/internships", {"studentId": world["s_fin"].id, "companyName": "Gamma Inc", "progressPercent": 20}).get_json()
    assert tpo.put(f"/api/internships/{i['id']}", {"progressPercent": 60, "status": "Completed"}).get_json()["progressPercent"] == 60
    assert tpo.post("/api/internships", {"studentId": world["s_mkt"].id, "companyName": "X"}).status_code == 404  # other department
    # placement flips student status; TPO cannot create placements
    assert tpo.post("/api/placements", {"studentId": world["s_fin"].id, "companyId": c["id"], "designation": "Analyst", "ctcLpa": 12}).status_code == 403
    p = d.post("/api/placements", {"studentId": world["s_fin"].id, "companyId": c["id"], "designation": "Analyst", "ctcLpa": 12,
                                   "offerAccepted": True, "signedDate": "2026-05-01"}).get_json()
    assert p["offerRef"].startswith("OFR-") and db.session.get(Student, world["s_fin"].id).status == "Placed"
    d.delete(f"/api/placements/{p['id']}")
    assert db.session.get(Student, world["s_fin"].id).status == "Unplaced"


def test_analytics_scoped_and_computed(client, world):
    d = login(client, "dir@x.edu", "placement_director")
    d.post("/api/placements", {"studentId": world["s_fin"].id, "companyId": world["co_a"].id, "designation": "A", "ctcLpa": 10, "offerAccepted": True, "signedDate": "2026-04-01", "location": "Pune"})
    a = d.get("/api/analytics").get_json()
    assert a["kpis"]["students"] == 2 and a["kpis"]["placed"] == 1 and a["kpis"]["placementRate"] == 50.0 and a["kpis"]["avgCtc"] == 10
    t = login(Api(client.application.test_client()).c, "tpo.mkt@x.edu", "department_tpo")
    b = t.get("/api/analytics?department=FIN").get_json()  # TPO is pinned to own department
    assert b["kpis"]["students"] == 1 and b["kpis"]["placed"] == 0


def test_dashboards_are_role_specific(client, world):
    titles = {}
    for email, role in (("sa@x.edu", "super_admin"), ("dir@x.edu", "placement_director"), ("tpo.fin@x.edu", "department_tpo"),
                        ("rec@acme.com", "corporate_recruiter"), ("coord@x.edu", "student_coordinator")):
        a = login(Api(client.application.test_client()).c, email, role)
        titles[role] = a.get("/api/dashboard").get_json()["title"]
    assert len(set(titles.values())) == 5


def test_export_csv_xlsx_scoped_and_injection_safe(client, world):
    d = login(client, "dir@x.edu", "placement_director")
    d.post("/api/students", {"rollNo": "E1", "name": "=HYPERLINK(\"http://evil\")", "email": "e1@s.edu", "departmentId": world["s_fin"].department_id, "batch": "b"})
    r = d.get("/api/reports/export?dataset=students&format=csv")
    assert r.status_code == 200 and "'=HYPERLINK" in r.get_data(as_text=True)
    assert d.get("/api/reports/export?dataset=students&format=xlsx").data[:2] == b"PK"
    assert d.get("/api/reports/export?dataset=audit&format=csv").status_code == 403  # director lacks audit:view
    t = login(Api(client.application.test_client()).c, "tpo.fin@x.edu", "department_tpo")
    assert "Mkt One" not in t.get("/api/reports/export?dataset=students&format=csv").get_data(as_text=True)


def test_user_creation_shows_credentials_once(client, world):
    s = login(client, "sa@x.edu", "super_admin")
    r = s.post("/api/users", {"fullName": "Ravi Kumar", "email": "ravi@x.edu", "role": "department_tpo", "departmentId": world["s_fin"].department_id})
    cred = r.get_json()["credentials"]
    assert len(cred["temporaryPassword"]) >= 12
    users = s.get("/api/users").get_json()["items"]
    assert all("passwordHash" not in u and "temporaryPassword" not in str(u) for u in users)
    assert s.post("/api/users", {"fullName": "No Dept", "email": "nd@x.edu", "role": "department_tpo"}).status_code == 422
    # reset credentials yields a NEW password and forces change
    r2 = s.post(f"/api/users/{r.get_json()['user']['id']}/reset-credentials").get_json()["credentials"]
    assert r2["temporaryPassword"] != cred["temporaryPassword"]
    a = Api(client.application.test_client())
    assert a.login("ravi@x.edu", "department_tpo", password=r2["temporaryPassword"]).get_json()["user"]["mustChangePassword"] is True


def test_csv_import_and_document_upload_validation(client, world):
    d = login(client, "dir@x.edu", "placement_director")
    csvf = "title,company,ctc_lpa,min_cgpa,departments\nGood Role,Acme Ltd,8,6.5,FIN;MKT\nBad Role,Missing Co,8,6,FIN\n"
    r = d.c.post("/api/vacancies/import", headers=d._h(), data={"dryRun": "true", "file": (io.BytesIO(csvf.encode()), "v.csv")})
    j = r.get_json()
    assert j["valid"] == 1 and j["created"] == 0 and j["rows"][1]["errors"]
    r = d.c.post("/api/vacancies/import", headers=d._h(), data={"dryRun": "false", "file": (io.BytesIO(csvf.encode()), "v.csv")})
    assert r.get_json()["created"] == 1
    bad = d.c.post("/api/documents", headers=d._h(), data={"studentId": str(world["s_fin"].id), "file": (io.BytesIO(b"MZ exe"), "a.pdf")})
    assert bad.status_code == 422
    exe = d.c.post("/api/documents", headers=d._h(), data={"file": (io.BytesIO(b"MZ"), "a.exe")})
    assert exe.status_code == 422
    ok = d.c.post("/api/documents", headers=d._h(), data={"studentId": str(world["s_fin"].id), "docType": "Resume", "file": (io.BytesIO(b"%PDF-1.4 x"), "cv.pdf")})
    assert ok.status_code == 201
    assert d.get(f"/api/documents/{ok.get_json()['id']}/file").data.startswith(b"%PDF")
    t = login(Api(client.application.test_client()).c, "tpo.mkt@x.edu", "department_tpo")
    assert t.get(f"/api/documents/{ok.get_json()['id']}/file").status_code == 404  # other dept


def test_audit_records_role_changes_and_denials(client, world):
    s = login(client, "sa@x.edu", "super_admin")
    s.put(f"/api/users/{world['coord'].id}", {"role": "department_tpo", "departmentId": world["s_fin"].department_id})
    t = login(Api(client.application.test_client()).c, "tpo.fin@x.edu", "department_tpo")
    t.get("/api/users")
    items = s.get("/api/audit?pageSize=200").get_json()["items"]
    acts = [i["action"] for i in items]
    assert "Changed user role" in acts and "Permission denied" in acts and "Login" in acts
