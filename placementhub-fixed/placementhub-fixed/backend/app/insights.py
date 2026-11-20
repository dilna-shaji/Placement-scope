"""Dashboards, analytics and exports. Every figure is computed from scoped database rows."""
import csv
import io
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from flask import Blueprint, Response, g, jsonify, request
from openpyxl import Workbook

from .auth import can, require_auth
from .errors import ApiError
from .extensions import db
from .models import (Application, AccountRequest, AuditLog, Company, Department, Internship, LoginAttempt,
                     LoginSession, PlacementOffer, RecruitmentDrive, Student, User, Vacancy, utcnow)
from .permissions import COORDINATOR, DIRECTOR, RECRUITER, SUPER_ADMIN, TPO
from .resources import (RESOURCES, _through_student, drives_scope, students_scope, vacancies_scope)
from .services import audit

bp = Blueprint("insights", __name__, url_prefix="/api")
STAGES = ["Applied", "Shortlisted", "Aptitude", "Technical", "HR", "Selected"]


def _kpi(label, value, hint="", tone="indigo", suffix=""):
    return {"label": label, "value": value, "hint": hint, "tone": tone, "suffix": suffix}


def _count(pairs):
    return [{"name": k, "value": v} for k, v in pairs]


def _offers(u, filters=None):
    q = _through_student(PlacementOffer)(PlacementOffer.query, u).filter(PlacementOffer.offer_accepted.is_(True))
    offers = q.all()
    if filters:
        if filters.get("department"):
            offers = [o for o in offers if o.student.department.code == filters["department"]]
        if filters.get("batch"):
            offers = [o for o in offers if o.student.batch == filters["batch"]]
    return offers


def _students(u, filters=None):
    studs = students_scope(Student.query, u).all()
    if filters:
        if filters.get("department"):
            studs = [s for s in studs if s.department.code == filters["department"]]
        if filters.get("batch"):
            studs = [s for s in studs if s.batch == filters["batch"]]
    return studs


def _upcoming_drives(u, n=5):
    rows = drives_scope(RecruitmentDrive.query, u).filter(RecruitmentDrive.status.in_(["Upcoming", "Live Today"])) \
        .order_by(RecruitmentDrive.date).limit(n).all()
    return [{"title": d.title, "subtitle": d.company.name, "meta": d.date.isoformat(), "badge": d.status} for d in rows]


def _stage_counts(apps):
    c = Counter(a.stage for a in apps)
    return _count([(s, c.get(s, 0)) for s in STAGES + ["Rejected"]])


def _pct(a, b):
    return round(100 * a / b, 1) if b else 0


# ------------------------------------------------------------------ dashboards (role-specific payloads)
@bp.get("/dashboard")
@require_auth("dashboard:view")
def dashboard():
    u, r = g.user, g.user.role_name
    now = utcnow()
    if r == SUPER_ADMIN:
        users = User.query.all()
        pending = AccountRequest.query.filter_by(status="Pending Approval").count()
        failed24 = LoginAttempt.query.filter(LoginAttempt.kind == "login", LoginAttempt.success.is_(False),
                                             LoginAttempt.created_at > now - timedelta(hours=24)).count()
        sessions = LoginSession.query.filter(LoginSession.revoked.is_(False), LoginSession.expires_at > now).count()
        by_role = Counter(x.role.label for x in users if x.status == "active" and x.role)
        by_dept = Counter(x.department.name for x in users if x.department)
        return jsonify({"role": r, "title": "System control centre", "kpis": [
            _kpi("Active accounts", sum(1 for x in users if x.status == "active"), "approved & enabled", "indigo"),
            _kpi("Pending approvals", pending, "account requests waiting", "coral"),
            _kpi("Failed logins (24h)", failed24, "security signal", "violet"),
            _kpi("Live sessions", sessions, "signed in right now", "aqua")],
            "widgets": [
                {"type": "bar", "title": "Active users by role", "data": _count(by_role.items())},
                {"type": "pie", "title": "Users by department", "data": _count(by_dept.items())},
                {"type": "list", "title": "Recent security events", "data": [
                    {"title": a.action, "subtitle": f"{a.actor_name} · {a.ip_address}", "meta": a.created_at.strftime("%d %b %H:%M"),
                     "badge": a.status} for a in AuditLog.query.filter(AuditLog.status != "Success").order_by(AuditLog.created_at.desc()).limit(6)]},
                {"type": "list", "title": "Recent activity", "data": [
                    {"title": a.action, "subtitle": f"{a.actor_name} ({a.actor_role or '—'})", "meta": a.created_at.strftime("%d %b %H:%M"),
                     "badge": a.status} for a in AuditLog.query.order_by(AuditLog.created_at.desc()).limit(6)]}]})
    if r == DIRECTOR:
        studs, offers = _students(u), _offers(u)
        placed = len({o.student_id for o in offers})
        monthly = Counter(o.signed_date.strftime("%Y-%m") for o in offers if o.signed_date)
        pend_v = Vacancy.query.filter_by(status="Pending Verification").count()
        return jsonify({"role": r, "title": "Placement command centre", "kpis": [
            _kpi("Placement rate", _pct(placed, len(studs)), f"{placed} of {len(studs)} students", "indigo", "%"),
            _kpi("Hiring companies", Company.query.count(), "in the directory", "aqua"),
            _kpi("Open vacancies", Vacancy.query.filter(Vacancy.status.in_(["Approved", "Active"])).count(), f"{pend_v} awaiting verification", "coral"),
            _kpi("Average package", round(sum(o.ctc_lpa for o in offers) / len(offers), 2) if offers else 0, "LPA, accepted offers", "violet")],
            "widgets": [
                {"type": "line", "title": "Offers by month", "data": _count(sorted(monthly.items()))},
                {"type": "bar", "title": "Placement % by department", "data": [
                    {"name": d.code, "value": _pct(len({o.student_id for o in offers if o.student.department_id == d.id}),
                                                   sum(1 for s in studs if s.department_id == d.id))} for d in Department.query.order_by(Department.code)]},
                {"type": "list", "title": "Upcoming drives", "data": _upcoming_drives(u)},
                {"type": "list", "title": "Needs verification", "data": [
                    {"title": v.title, "subtitle": v.company.name, "meta": f"{v.ctc_lpa} LPA", "badge": "Pending"}
                    for v in Vacancy.query.filter_by(status="Pending Verification").limit(6)]}]})
    if r == TPO:
        dept = u.department
        studs = _students(u)
        offers = _offers(u)
        placed = len({o.student_id for o in offers})
        vacs = vacancies_scope(Vacancy.query, u).filter(Vacancy.status.in_(["Approved", "Active"])).all()
        apps = _through_student(Application)(Application.query, u).all()
        eligible = [s for s in studs if s.status != "Placed"]
        return jsonify({"role": r, "title": f"{dept.name if dept else 'Department'} department workspace", "kpis": [
            _kpi("Department students", len(studs), dept.name if dept else "", "indigo"),
            _kpi("Placement progress", _pct(placed, len(studs)), f"{placed} placed", "aqua", "%"),
            _kpi("Eligible / unplaced", len(eligible), "still searching", "coral"),
            _kpi("Department vacancies", len(vacs), "open to your students", "violet")],
            "widgets": [
                {"type": "bar", "title": "Applications by stage", "data": _stage_counts(apps)},
                {"type": "pie", "title": "Student status", "data": _count(Counter(s.status for s in studs).items())},
                {"type": "list", "title": "Open vacancies", "data": [
                    {"title": v.title, "subtitle": v.company.name, "meta": f"{v.ctc_lpa} LPA", "badge": v.status} for v in vacs[:6]]},
                {"type": "list", "title": "Internship tracking", "data": [
                    {"title": i.student.name, "subtitle": i.company_name, "meta": f"{i.progress_percent}%", "badge": i.status}
                    for i in _through_student(Internship)(Internship.query, u).limit(6)]}]})
    if r == RECRUITER:
        co = u.company
        vacs = vacancies_scope(Vacancy.query, u).all()
        apps = _through_student(Application)(Application.query, u).all()
        sel = sum(1 for a in apps if a.stage == "Selected")
        return jsonify({"role": r, "title": f"{co.name if co else 'Company'} recruiter workspace", "profile": co.to_dict() if co else None,
                        "kpis": [
            _kpi("Active job postings", sum(1 for v in vacs if v.status in ("Approved", "Active")), f"{len(vacs)} total", "indigo"),
            _kpi("Applications received", len(apps), "shared with your company", "aqua"),
            _kpi("Candidates selected", sel, "final stage", "coral"),
            _kpi("Awaiting verification", sum(1 for v in vacs if v.status == "Pending Verification"), "with placement cell", "violet")],
            "widgets": [
                {"type": "bar", "title": "Recruitment pipeline", "data": _stage_counts(apps)},
                {"type": "list", "title": "Upcoming drives", "data": _upcoming_drives(u)},
                {"type": "list", "title": "Your vacancies", "data": [
                    {"title": v.title, "subtitle": v.job_type, "meta": f"{v.ctc_lpa} LPA", "badge": v.status} for v in vacs[:6]]}]})
    if r == "student":
        stud = Student.query.filter((Student.user_id == u.id) | (Student.email == u.email)).first()
        dept_code = stud.department.code if (stud and stud.department) else ""
        cgpa = (stud.cgpa or 0.0) if stud else 0.0
        backlogs = (stud.active_backlogs or 0) if stud else 0
        vacs = Vacancy.query.filter(Vacancy.status.in_(["Approved", "Active"])).all()
        eligible = [v for v in vacs if (not v.eligible_departments or dept_code in v.eligible_departments) and cgpa >= (v.min_cgpa or 0) and backlogs <= (v.max_backlogs or 0)]
        apps = Application.query.filter_by(student_id=stud.id).all() if stud else []
        return jsonify({
            "role": r,
            "title": f"Student Career Portal — {stud.name if stud else u.full_name}",
            "kpis": [
                _kpi("Eligible vacancies", len(eligible), "open for application", "indigo"),
                _kpi("Applications submitted", len(apps), "active tracking", "aqua"),
                _kpi("Interviews & shortlists", sum(1 for a in apps if a.stage in ("Shortlisted", "Aptitude", "Technical", "HR")), "in progress", "violet"),
                _kpi("Placement status", 1 if (stud and stud.status == "Placed") else 0, (stud.status if stud else "Unplaced"), "coral", " Placed" if (stud and stud.status == "Placed") else "")
            ],
            "widgets": [
                {"type": "list", "title": "Your active applications", "data": [
                    {"title": a.vacancy.title, "subtitle": a.vacancy.company.name if a.vacancy and a.vacancy.company else "", "meta": a.updated_at.strftime("%d %b") if a.updated_at else "", "badge": a.stage}
                    for a in sorted(apps, key=lambda x: x.updated_at or x.created_at, reverse=True)[:6]
                ]},
                {"type": "list", "title": "Recommended eligible opportunities", "data": [
                    {"title": v.title, "subtitle": f"{v.company.name} · {v.job_type}", "meta": f"{v.ctc_lpa} LPA", "badge": "Eligible"}
                    for v in eligible[:6]
                ]},
                {"type": "list", "title": "Upcoming recruitment drives", "data": _upcoming_drives(u, 6)},
            ]
        })
    if r == "department_faculty":
        dept = u.department
        studs = _students(u)
        offers = _offers(u)
        placed = len({o.student_id for o in offers})
        vacs = vacancies_scope(Vacancy.query, u).filter(Vacancy.status.in_(["Approved", "Active"])).all()
        apps = _through_student(Application)(Application.query, u).all()
        return jsonify({
            "role": r,
            "title": f"{dept.name if dept else 'Department'} faculty overview",
            "kpis": [
                _kpi("Total students", len(studs), dept.name if dept else "", "indigo"),
                _kpi("Placement rate", _pct(placed, len(studs)), f"{placed} placed", "aqua", "%"),
                _kpi("Active applications", len(apps), "department pipeline", "violet"),
                _kpi("Eligible vacancies", len(vacs), "open for your batch", "coral")
            ],
            "widgets": [
                {"type": "bar", "title": "Applications by stage", "data": _stage_counts(apps)},
                {"type": "pie", "title": "Student placement status", "data": _count(Counter(s.status for s in studs).items())},
                {"type": "list", "title": "Active department vacancies", "data": [
                    {"title": v.title, "subtitle": v.company.name, "meta": f"{v.ctc_lpa} LPA", "badge": v.status} for v in vacs[:6]
                ]}
            ]
        })
    # student coordinator
    studs = _students(u)
    apps = _through_student(Application)(Application.query, u).all()
    inprog = [a for a in apps if a.stage not in ("Selected", "Rejected", "Withdrawn")]
    ints = _through_student(Internship)(Internship.query, u).all()
    return jsonify({"role": r, "title": "Coordination workspace", "kpis": [
        _kpi("Assigned students", len(studs), "under your coordination", "indigo"),
        _kpi("Pending application tasks", len(inprog), "still in progress", "coral"),
        _kpi("Ongoing internships", sum(1 for i in ints if i.status == "Ongoing"), "follow-ups due", "aqua"),
        _kpi("Upcoming drives", len(_upcoming_drives(u, 50)), "scheduled", "violet")],
        "widgets": [
            {"type": "bar", "title": "Application stages", "data": _stage_counts(apps)},
            {"type": "list", "title": "Recruitment schedule", "data": _upcoming_drives(u, 6)},
            {"type": "list", "title": "Application updates", "data": [
                {"title": a.student.name, "subtitle": f"{a.vacancy.title} · {a.vacancy.company.name}", "meta": (a.updated_at or a.created_at).strftime("%d %b"), "badge": a.stage}
                for a in sorted(apps, key=lambda x: x.updated_at or x.created_at, reverse=True)[:6]]}]})


# ------------------------------------------------------------------ analytics
@bp.get("/analytics")
@require_auth("analytics:view")
def analytics():
    u = g.user
    f = {"department": request.args.get("department") or None, "batch": request.args.get("batch") or None}
    if u.role_name == TPO:
        f["department"] = u.department.code if u.department else "-"  # TPO is always pinned to own department
    studs, offers = _students(u, f), _offers(u, f)
    sids = {s.id for s in studs}
    placed_ids = {o.student_id for o in offers}
    ctcs = [o.ctc_lpa for o in offers]
    brackets = [("< 6", 0, 6), ("6 – 9", 6, 9), ("9 – 12", 9, 12), ("12 – 15", 12, 15), ("15 – 20", 15, 20), ("20+", 20, 1e9)]
    vacs = [v for v in vacancies_scope(Vacancy.query, u).all()
            if not f["department"] or f["department"] in (v.eligible_departments or [])]
    apps = [a for a in _through_student(Application)(Application.query, u).all() if a.student_id in sids]
    ints = [i for i in _through_student(Internship)(Internship.query, u).all() if i.student_id in sids]
    cum = []
    for i, st in enumerate(STAGES):
        cum.append({"name": st, "value": sum(1 for a in apps if a.stage in STAGES[i:] )})
    by_dept = []
    for d in Department.query.order_by(Department.code):
        if f["department"] and d.code != f["department"]:
            continue
        ds = [s for s in studs if s.department_id == d.id]
        do = [o for o in offers if o.student.department_id == d.id]
        by_dept.append({"name": d.name, "code": d.code, "students": len(ds),
                        "placed": len({o.student_id for o in do}), "rate": _pct(len({o.student_id for o in do}), len(ds)),
                        "avgCtc": round(sum(o.ctc_lpa for o in do) / len(do), 2) if do else 0,
                        "highestCtc": max((o.ctc_lpa for o in do), default=0)})
    yoy = []
    for b in sorted({s.batch for s in studs}):
        bs = [s for s in studs if s.batch == b]
        bo = [o for o in offers if o.student.batch == b]
        yoy.append({"name": b, "students": len(bs), "placed": len({o.student_id for o in bo}),
                    "rate": _pct(len({o.student_id for o in bo}), len(bs)),
                    "avgCtc": round(sum(o.ctc_lpa for o in bo) / len(bo), 2) if bo else 0,
                    "highestCtc": max((o.ctc_lpa for o in bo), default=0)})
    comp_act = defaultdict(lambda: {"offers": 0, "vacancies": 0})
    for o in offers:
        comp_act[o.company.name]["offers"] += 1
    for v in vacs:
        comp_act[v.company.name]["vacancies"] += 1
    top = sorted(comp_act.items(), key=lambda kv: (kv[1]["offers"], kv[1]["vacancies"]), reverse=True)[:8]
    return jsonify({
        "filters": {"department": f["department"], "batch": f["batch"], "batches": sorted({s.batch for s in students_scope(Student.query, u).all()})},
        "kpis": {"students": len(studs), "placed": len(placed_ids), "placementRate": _pct(len(placed_ids), len(studs)),
                 "avgCtc": round(sum(ctcs) / len(ctcs), 2) if ctcs else 0, "highestCtc": max(ctcs, default=0),
                 "medianCtc": round(sorted(ctcs)[len(ctcs) // 2], 2) if ctcs else 0, "offers": len(offers),
                 "companies": len({o.company_id for o in offers}), "vacancies": len(vacs)},
        "departmentComparison": by_dept, "yearOverYear": yoy, "funnel": cum,
        "salaryDistribution": [{"name": n, "value": sum(1 for c in ctcs if lo <= c < hi)} for n, lo, hi in brackets],
        "placementTrend": _count(sorted(Counter(o.signed_date.strftime("%Y-%m") for o in offers if o.signed_date).items())),
        "vacancyTrend": _count(sorted(Counter(v.created_at.strftime("%Y-%m") for v in vacs).items())),
        "locationDistribution": _count(Counter(o.location or "Unspecified" for o in offers).most_common(8)),
        "companyActivity": [{"name": k, **v} for k, v in top],
        "internshipPerformance": {"status": _count(Counter(i.status for i in ints).items()),
                                  "avgProgress": round(sum(i.progress_percent for i in ints) / len(ints), 1) if ints else 0,
                                  "ppoConversion": _pct(sum(1 for i in ints if i.ppo_offered), len(ints)),
                                  "total": len(ints)},
        "records": [{"rollNo": o.student.roll_no, "student": o.student.name, "department": o.student.department.code,
                     "company": o.company.name, "designation": o.designation, "ctcLpa": o.ctc_lpa, "location": o.location,
                     "batch": o.student.batch} for o in offers][:500],
    })


# ------------------------------------------------------------------ reports / export
DATASETS = {  # dataset -> (resource key, permission, columns)
    "students": ("students", "students:read", ["rollNo", "name", "email", "phone", "departmentCode", "batch", "cgpa", "activeBacklogs", "status", "internshipStatus"]),
    "companies": ("companies", "companies:read", ["name", "industry", "tier", "location", "contactName", "contactEmail", "mouStatus"]),
    "vacancies": ("vacancies", "vacancies:read", ["title", "companyName", "jobType", "ctcLpa", "minCgpa", "status", "applicationDeadline", "openings", "applicationsCount"]),
    "applications": ("applications", "applications:read", ["rollNo", "studentName", "departmentCode", "vacancyTitle", "companyName", "stage", "score"]),
    "placements": ("placements", "placements:read", ["offerRef", "rollNo", "studentName", "departmentCode", "companyName", "designation", "ctcLpa", "location", "offerAccepted", "verified", "signedDate"]),
    "internships": ("internships", "internships:read", ["rollNo", "studentName", "departmentCode", "companyName", "stipendPerMonth", "durationMonths", "progressPercent", "ppoOffered", "status"]),
    "drives": ("drives", "drives:read", ["title", "companyName", "date", "mode", "venue", "status", "registeredCount", "selectedCount"]),
    "audit": (None, "audit:view", ["createdAt", "actorName", "actorRole", "action", "entityType", "entityId", "ipAddress", "status", "details"]),
}


def _safe_cell(v):
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v  # neutralise CSV/Excel formula injection
    return v


def dataset_rows(name, user):
    key, perm, cols = DATASETS[name]
    if not can(user, perm):
        raise ApiError("You do not have permission to export this dataset.", 403, code="forbidden")
    if name == "audit":
        rows = [r.to_dict() for r in AuditLog.query.order_by(AuditLog.created_at.desc()).limit(5000)]
    else:
        res = RESOURCES[key]
        q = res.scope(res.model.query, user)
        rows = [res.dump(o, user) for o in q.limit(10000)]
    return cols, rows


@bp.get("/reports/datasets")
@require_auth("reports:view")
def report_datasets():
    out = []
    for name, (key, perm, cols) in DATASETS.items():
        if can(g.user, perm):
            try:
                n = len(dataset_rows(name, g.user)[1])
            except ApiError:
                continue
            out.append({"name": name, "columns": cols, "count": n})
    return jsonify({"datasets": out})


@bp.get("/reports/export")
@require_auth("reports:view")
def export():
    name, fmt = request.args.get("dataset", ""), request.args.get("format", "csv")
    if name not in DATASETS or fmt not in ("csv", "xlsx"):
        raise ApiError("Unknown dataset or format.", 400)
    cols, rows = dataset_rows(name, g.user)
    audit("Exported report", "report", name, f"{fmt}, {len(rows)} rows")
    data = [[_safe_cell(r.get(c)) for c in cols] for r in rows]
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(cols)
        w.writerows(data)
        return Response("\ufeff" + buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename={name}_{stamp}.csv"})
    wb = Workbook()
    ws = wb.active
    ws.title = name[:30]
    ws.append(cols)
    for row in data:
        ws.append([str(x) if isinstance(x, (list, dict)) else x for x in row])
    out = io.BytesIO()
    wb.save(out)
    return Response(out.getvalue(), mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename={name}_{stamp}.xlsx"})
