"""Generic, permission-checked, department/company/assignment-scoped CRUD for domain resources."""
import csv
import io
import re
from datetime import date, datetime

from flask import Blueprint, g, jsonify, request
from sqlalchemy import Boolean, Date, Float, Integer, false
from sqlalchemy.exc import IntegrityError

from .auth import can, require_auth
from .errors import ApiError
from .extensions import db
from .models import (Application, Company, Department, Internship, Notification, Outreach, PlacementOffer,
                     RecruitmentDrive, Student, User, Vacancy, VacancyVerification, camel, snake, utcnow)
from .permissions import COORDINATOR, DIRECTOR, RECRUITER, SUPER_ADMIN, TPO
from .services import audit

bp = Blueprint("resources", __name__, url_prefix="/api")
FULL_ACCESS = (SUPER_ADMIN, DIRECTOR)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ------------------------------------------------------------------ scoping (department / company / assignment)
def _vacancy_ids_for_dept(code):
    return [v.id for v in Vacancy.query.all() if not v.eligible_departments or code in v.eligible_departments]


def students_scope(q, u):
    r = u.role_name
    if r in FULL_ACCESS:
        return q
    if r in (TPO, "department_faculty"):
        return q.filter(Student.department_id == u.department_id) if u.department_id else q.filter(false())
    if r == COORDINATOR:
        return q.filter(Student.coordinator_id == u.id)
    if r == "student":
        return q.filter((Student.user_id == u.id) | (Student.email == u.email))
    if r == RECRUITER and u.company_id:
        sub = db.session.query(Application.student_id).join(Vacancy, Vacancy.id == Application.vacancy_id) \
            .filter(Vacancy.company_id == u.company_id)
        return q.filter(Student.id.in_(sub))
    return q.filter(false())


def _through_student(model):
    def scope(q, u):
        if u.role_name in FULL_ACCESS:
            return q
        if u.role_name == RECRUITER:
            return q.filter(false()) if model is not Application else \
                q.filter(Application.vacancy_id.in_(db.session.query(Vacancy.id).filter(Vacancy.company_id == u.company_id)))
        ids = students_scope(db.session.query(Student.id), u)
        return q.filter(model.student_id.in_(ids))
    return scope


def companies_scope(q, u):
    if u.role_name in FULL_ACCESS:
        return q
    if u.role_name == RECRUITER and u.company_id:
        return q.filter(Company.id == u.company_id)
    return q.filter(false())


def vacancies_scope(q, u):
    r = u.role_name
    if r in FULL_ACCESS:
        return q
    if r == RECRUITER and u.company_id:
        return q.filter(Vacancy.company_id == u.company_id)
    live = Vacancy.status.in_(["Approved", "Active", "Closed"])
    if r in (TPO, "department_faculty") and u.department and u.department.code:
        return q.filter(live, Vacancy.id.in_(_vacancy_ids_for_dept(u.department.code) or [-1]))
    if r == COORDINATOR:
        return q.filter(live)
    if r == "student":
        stud = Student.query.filter((Student.user_id == u.id) | (Student.email == u.email)).first()
        dept_code = stud.department.code if (stud and stud.department) else ""
        if dept_code:
            v_ids = _vacancy_ids_for_dept(dept_code) or [-1]
            return q.filter(Vacancy.status.in_(["Approved", "Active"]), Vacancy.id.in_(v_ids))
        return q.filter(Vacancy.status.in_(["Approved", "Active"]))
    return q.filter(false())


def drives_scope(q, u):
    r = u.role_name
    if r in FULL_ACCESS or r == COORDINATOR:
        return q
    if r == RECRUITER and u.company_id:
        return q.filter(RecruitmentDrive.company_id == u.company_id)
    dept = u.department
    if r == "student":
        stud = Student.query.filter((Student.user_id == u.id) | (Student.email == u.email)).first()
        dept = stud.department if stud else None
    if r in (TPO, "department_faculty", "student") and dept:
        ids = _vacancy_ids_for_dept(dept.code) or [-1]
        return q.filter((RecruitmentDrive.vacancy_id.is_(None)) | RecruitmentDrive.vacancy_id.in_(ids))
    return q.filter(false())


def open_scope(q, u):  # director / admin only resources (permission already enforced)
    return q if u.role_name in FULL_ACCESS else q.filter(false())


def departments_scope(q, u):
    if u.role_name in FULL_ACCESS:
        return q
    if u.role_name in (TPO, "department_faculty"):
        return q.filter(Department.id == u.department_id) if u.department_id else q.filter(false())
    return q


# ------------------------------------------------------------------ resource description
class Res:
    def __init__(self, key, model, fields, required=(), choices=None, ranges=None, search=(), filters=(),
                 scope=open_scope, extra=None, order=None, validate=None, writable=None, redact=None,
                 after_save=None, before_delete=None, create_ok=None):
        self.key, self.model, self.fields = key, model, list(fields)
        self.required, self.choices, self.ranges = set(required), choices or {}, ranges or {}
        self.search, self.filters, self.scope = search, filters, scope
        self.extra, self.order, self.validate = extra, order, validate
        self._writable, self.redact, self.after_save = writable, redact, after_save
        self.before_delete, self.create_ok = before_delete, create_ok

    def writable(self, user, creating):
        return self._writable(user, creating) if self._writable else self.fields

    def dump(self, obj, user):
        d = obj.to_dict()
        if self.extra:
            d.update(self.extra(obj))
        if self.redact:
            d = self.redact(d, user)
        return d


def coerce(col, v):
    if v is None or (isinstance(v, str) and v.strip() == ""):
        if col.nullable:
            return None
        if isinstance(col.type, (Integer, Float)) or col.type.__class__.__name__ == "Boolean":
            raise ValueError
        return ""
    t = col.type
    if isinstance(t, Boolean):
        if isinstance(v, bool):
            return v
        raise ValueError
    if isinstance(t, Integer):
        return int(v)
    if isinstance(t, Float):
        return float(v)
    if isinstance(t, Date):
        return date.fromisoformat(str(v)[:10])
    if t.__class__.__name__ == "JSON":
        if isinstance(v, str):
            v = [x.strip() for x in v.split(",") if x.strip()]
        if not isinstance(v, (list, dict)):
            raise ValueError
        return v
    s = str(v).strip()
    if getattr(t, "length", None):
        s = s[: t.length]
    return s


def write_fields(res, obj, data, user, creating):
    errors = {}
    cols = res.model.__table__.columns
    for f in res.writable(user, creating):
        k = camel(f)
        if k not in data:
            if creating and f in res.required and getattr(obj, f) in (None, ""):
                errors[k] = "Required"
            continue
        try:
            v = coerce(cols[f], data[k])
        except (ValueError, TypeError):
            errors[k] = "Invalid value"
            continue
        if f in res.required and v in (None, ""):
            errors[k] = "Required"
            continue
        if f in res.choices and v not in res.choices[f] and v is not None:
            errors[k] = "Choose one of: " + ", ".join(res.choices[f])
            continue
        if f in res.ranges and v is not None and not (res.ranges[f][0] <= v <= res.ranges[f][1]):
            errors[k] = f"Must be between {res.ranges[f][0]} and {res.ranges[f][1]}"
            continue
        setattr(obj, f, v)
    if errors:
        raise ApiError("Please correct the highlighted fields.", 422, errors)
    if res.validate:
        res.validate(obj, g.user, creating)


# ------------------------------------------------------------------ per-resource rules
def _name(u):
    return u.full_name if u else None


def students_extra(s):
    c = db.session.get(User, s.coordinator_id) if s.coordinator_id else None
    return {"departmentName": s.department.name, "departmentCode": s.department.code, "coordinatorName": _name(c)}


def students_redact(d, u):
    if u.role_name != RECRUITER:
        return d
    keep = ("id", "rollNo", "name", "departmentName", "departmentCode", "batch", "cgpa", "activeBacklogs",
            "historyBacklogs", "skills", "preferredDomain")
    return {k: d[k] for k in keep if k in d}


def students_validate(s, u, creating):
    errs = {}
    if s.email and not EMAIL_RE.match(s.email):
        errs["email"] = "Invalid e-mail"
    if not db.session.get(Department, s.department_id or 0):
        errs["departmentId"] = "Unknown department"
    if u.role_name == TPO and s.department_id != u.department_id:
        raise ApiError("You can only manage students of your own department.", 403, code="forbidden")
    if s.coordinator_id:
        c = db.session.get(User, s.coordinator_id)
        if not c or c.role_name != COORDINATOR or c.status != "active":
            errs["coordinatorId"] = "Select an active student coordinator"
    if errs:
        raise ApiError("Please correct the highlighted fields.", 422, errs)


def companies_writable(u, creating):
    if u.role_name == RECRUITER:
        return ["industry", "location", "contact_name", "contact_designation", "contact_email", "contact_phone",
                "website", "about"]
    return list(COMPANY_FIELDS)


def companies_create_ok(u):
    return u.role_name != RECRUITER


def vacancies_extra(v):
    n = Application.query.filter_by(vacancy_id=v.id).count()
    sl = Application.query.filter(Application.vacancy_id == v.id,
                                  Application.stage.in_(["Shortlisted", "Aptitude", "Technical", "HR", "Selected"])).count()
    extra = {
        "companyName": v.company.name if v.company else "",
        "applicationsCount": n,
        "shortlistedCount": sl,
        "sourceUrl": v.source_url or "",
        "riskLevel": v.risk_level or "Low Risk",
        "riskScore": v.risk_score or 0,
        "riskFlags": v.risk_flags or [],
        "duration": v.duration or "",
        "workMode": v.work_mode or "On-site",
    }
    u = getattr(g, "user", None)
    if u and u.role_name == "student":
        stud = Student.query.filter((Student.user_id == u.id) | (Student.email == u.email)).first()
        if stud:
            dept_code = stud.department.code if stud.department else ""
            cgpa = stud.cgpa or 0.0
            backlogs = stud.active_backlogs or 0
            dept_match = not v.eligible_departments or (dept_code in v.eligible_departments)
            cgpa_match = cgpa >= (v.min_cgpa or 0.0)
            backlog_match = backlogs <= (v.max_backlogs or 0)
            extra["isEligible"] = dept_match and cgpa_match and backlog_match
            extra["hasApplied"] = Application.query.filter_by(student_id=stud.id, vacancy_id=v.id).first() is not None
        else:
            extra["isEligible"] = False
            extra["hasApplied"] = False
    return extra


def vacancies_writable(u, creating):
    f = list(VACANCY_FIELDS)
    if u.role_name == RECRUITER:
        f.remove("source")
        if creating:
            f.append("company_id")
    else:
        f.append("company_id")
    return f


def vacancies_validate(v, u, creating):
    v.status = v.status or "Draft"
    if u.role_name == RECRUITER:
        if not u.company_id:
            raise ApiError("Your account is not linked to a company.", 403, code="forbidden")
        v.company_id = u.company_id
        if not creating and getattr(v, "_was_live", False):
            v.status = "Pending Verification"  # any edit to a live vacancy requires re-verification
        elif v.status not in ("Draft", "Pending Verification"):
            raise ApiError("Recruiters can only save Draft or Pending Verification vacancies.", 403, code="forbidden")
        v.submitted_by_id = u.id
    elif v.status in ("Approved", "Active") and not can(u, "vacancies:verify"):
        raise ApiError("You may not approve vacancies.", 403, code="forbidden")
    if not db.session.get(Company, v.company_id or 0):
        raise ApiError("Please correct the highlighted fields.", 422, {"companyId": "Unknown company"})
    bad = [c for c in (v.eligible_departments or []) if not Department.query.filter_by(code=c).first()]
    if bad:
        raise ApiError("Please correct the highlighted fields.", 422, {"eligibleDepartments": "Unknown department code: " + ", ".join(bad)})


def drives_extra(d):
    return {"companyName": d.company.name}


def drives_validate(d, u, creating):
    if not db.session.get(Company, d.company_id or 0):
        raise ApiError("Please correct the highlighted fields.", 422, {"companyId": "Unknown company"})
    if d.vacancy_id:
        v = db.session.get(Vacancy, d.vacancy_id)
        if not v or v.company_id != d.company_id:
            raise ApiError("Please correct the highlighted fields.", 422, {"vacancyId": "Vacancy must belong to the selected company"})


def apps_extra(a):
    return {"studentName": a.student.name, "rollNo": a.student.roll_no, "departmentCode": a.student.department.code,
            "cgpa": a.student.cgpa, "vacancyTitle": a.vacancy.title, "companyName": a.vacancy.company.name}


def apps_redact(d, u):
    if u.role_name == RECRUITER:
        d = {k: v for k, v in d.items() if k not in ("updatedById",)}
    return d


def apps_writable(u, creating):
    if u.role_name == "student":
        # A student must never be able to promote their own application; they apply / withdraw via /student/*.
        return ["student_id", "vacancy_id"] if creating else []
    if creating:
        return ["student_id", "vacancy_id", "stage", "score", "remarks"]
    return ["stage", "score", "remarks"]


def apps_create_ok(u):
    return u.role_name != RECRUITER


def apps_validate(a, u, creating):
    if creating:
        s = students_scope(Student.query, u).filter(Student.id == a.student_id).first()
        v = vacancies_scope(Vacancy.query, u).filter(Vacancy.id == a.vacancy_id).first()
        if not s:
            raise ApiError("Student not found in your scope.", 404)
        if not v:
            raise ApiError("Vacancy not found in your scope.", 404)
        if v.status not in ("Approved", "Active"):
            raise ApiError("Applications can only be created for approved vacancies.", 422, {"vacancyId": "Vacancy is not open"})
        why = []
        if (s.cgpa or 0) < (v.min_cgpa or 0):
            why.append(f"CGPA below minimum {v.min_cgpa}")
        if (s.active_backlogs or 0) > (v.max_backlogs or 0):
            why.append("too many active backlogs")
        if s.department.code not in (v.eligible_departments or []):
            why.append("department not eligible")
        if why:
            raise ApiError("Student is not eligible: " + "; ".join(why) + ".", 422, {"studentId": "Not eligible"})
    a.updated_by_id = u.id


def internships_extra(i):
    return {"studentName": i.student.name, "rollNo": i.student.roll_no, "departmentCode": i.student.department.code}


def student_link_validate(model_label):
    def v(obj, u, creating):
        if not students_scope(Student.query, u).filter(Student.id == obj.student_id).first():
            raise ApiError("Student not found in your scope.", 404)
    return v


def internship_after(i, creating, user):
    s = i.student
    mapping = {"Ongoing": "Ongoing", "Completed": "Completed", "PPO Converted": "PPO Converted"}
    if i.status in mapping:
        s.internship_status = mapping[i.status]


def placements_extra(p):
    return {"studentName": p.student.name, "rollNo": p.student.roll_no, "departmentCode": p.student.department.code,
            "companyName": p.company.name, "tier": p.company.tier}


def placements_validate(p, u, creating):
    if not db.session.get(Student, p.student_id or 0):
        raise ApiError("Please correct the highlighted fields.", 422, {"studentId": "Unknown student"})
    if not db.session.get(Company, p.company_id or 0):
        raise ApiError("Please correct the highlighted fields.", 422, {"companyId": "Unknown company"})


def placements_after(p, creating, user):
    if creating and not p.offer_ref:
        p.offer_ref = f"OFR-{utcnow().year}-{p.id:05d}"
    if p.offer_accepted:
        p.student.status = "Placed"
    elif p.student.status != "Placed":
        p.student.status = "In Process"
    c = p.company
    if p.signed_date and (not c.last_drive_date or p.signed_date > c.last_drive_date):
        c.last_drive_date = p.signed_date


def placements_before_delete(p):
    others = PlacementOffer.query.filter(PlacementOffer.student_id == p.student_id, PlacementOffer.id != p.id,
                                         PlacementOffer.offer_accepted.is_(True)).count()
    if not others:
        p.student.status = "Unplaced"


def outreach_extra(o):
    return {"companyName": o.company.name}


def departments_validate(d, u, creating):
    d.code = (d.code or "").upper()


STUDENT_FIELDS = ["roll_no", "name", "email", "phone", "department_id", "batch", "cgpa", "active_backlogs",
                  "history_backlogs", "skills", "status", "internship_status", "preferred_domain", "coordinator_id"]
COMPANY_FIELDS = ["name", "industry", "tier", "location", "contact_name", "contact_designation", "contact_email",
                  "contact_phone", "mou_status", "website", "about", "last_drive_date"]
VACANCY_FIELDS = ["title", "job_type", "ctc_lpa", "stipend_per_month", "locations", "eligible_departments",
                  "min_cgpa", "max_backlogs", "application_deadline", "drive_date", "status", "openings",
                  "description", "source", "source_url", "risk_level", "risk_score", "risk_flags", "duration", "work_mode"]
APP_STAGES = ["Applied", "Shortlisted", "Aptitude", "Technical", "HR", "Selected", "Rejected", "Withdrawn"]

RESOURCES = {
    "students": Res("students", Student, STUDENT_FIELDS, required={"roll_no", "name", "email", "department_id", "batch"},
                    choices={"status": ["Placed", "In Process", "Unplaced", "Opted Out"],
                             "internship_status": ["None", "Ongoing", "Completed", "PPO Converted"]},
                    ranges={"cgpa": (0, 10), "active_backlogs": (0, 50), "history_backlogs": (0, 50)},
                    search=("name", "roll_no", "email"), filters=("department_id", "status", "batch"),
                    scope=students_scope, extra=students_extra, redact=students_redact, validate=students_validate,
                    order=Student.name),
    "companies": Res("companies", Company, COMPANY_FIELDS, required={"name"},
                     choices={"tier": ["Super Dream (>20 LPA)", "Dream (12-20 LPA)", "Core Corporate", "Mass Recruiter"],
                              "mou_status": ["Signed", "In Discussion", "Pending Renewal", "None"]},
                     search=("name", "industry", "location"), filters=("tier", "mou_status"), scope=companies_scope,
                     writable=companies_writable, create_ok=companies_create_ok, order=Company.name),
    "vacancies": Res("vacancies", Vacancy, VACANCY_FIELDS, required={"title", "company_id"},
                     choices={"job_type": ["Full-Time", "Internship + PPO", "Internship Only"],
                              "status": ["Draft", "Pending Verification", "Approved", "Active", "Closed", "Archived"]},
                     ranges={"ctc_lpa": (0, 500), "min_cgpa": (0, 10), "max_backlogs": (0, 50), "openings": (1, 10000)},
                     search=("title",), filters=("status", "company_id", "job_type"), scope=vacancies_scope,
                     extra=vacancies_extra, writable=vacancies_writable, validate=vacancies_validate,
                     order=Vacancy.created_at.desc()),
    "outreach": Res("outreach", Outreach, ["company_id", "channel", "subject", "message", "status", "next_followup_date"],
                    required={"company_id", "subject"},
                    choices={"channel": ["Email", "Call", "Meeting", "LinkedIn"],
                             "status": ["Draft", "Sent", "Replied", "Follow-up", "Closed"]},
                    search=("subject",), filters=("status", "company_id", "channel"), extra=outreach_extra,
                    order=Outreach.created_at.desc()),
    "drives": Res("drives", RecruitmentDrive, ["title", "company_id", "vacancy_id", "date", "mode", "venue", "stage",
                                               "status", "registered_count", "shortlisted_count", "selected_count", "notes"],
                  required={"title", "company_id", "date"},
                  choices={"mode": ["On-Campus", "Virtual", "Hybrid"],
                           "stage": ["Pre-Placement Talk", "Online Aptitude Test", "Technical Round 1", "Technical Round 2",
                                     "Group Discussion", "HR Interview", "Final Offers"],
                           "status": ["Upcoming", "Live Today", "Completed", "Postponed"]},
                  search=("title", "venue"), filters=("status", "company_id", "mode"), scope=drives_scope,
                  extra=drives_extra, validate=drives_validate, order=RecruitmentDrive.date.desc()),
    "applications": Res("applications", Application, ["student_id", "vacancy_id", "stage", "score", "remarks"],
                        required={"student_id", "vacancy_id"}, choices={"stage": APP_STAGES},
                        ranges={"score": (0, 100)}, filters=("stage", "vacancy_id", "student_id"),
                        scope=_through_student(Application), extra=apps_extra, redact=apps_redact,
                        writable=apps_writable, validate=apps_validate, create_ok=apps_create_ok,
                        order=Application.updated_at.desc()),
    "internships": Res("internships", Internship,
                       ["student_id", "company_name", "stipend_per_month", "duration_months", "start_date", "end_date",
                        "mentor_name", "mentor_email", "progress_percent", "ppo_offered", "ppo_ctc_lpa",
                        "evaluation_grade", "status"],
                       required={"student_id", "company_name"},
                       choices={"status": ["Ongoing", "PPO Converted", "Completed", "Terminated"]},
                       ranges={"progress_percent": (0, 100), "duration_months": (1, 24)}, filters=("status", "student_id"),
                       search=("company_name",), scope=_through_student(Internship), extra=internships_extra,
                       validate=student_link_validate("internship"), after_save=internship_after,
                       order=Internship.created_at.desc()),
    "placements": Res("placements", PlacementOffer,
                      ["student_id", "company_id", "designation", "ctc_lpa", "base_lpa", "joining_date", "location",
                       "offer_accepted", "verified", "signed_date"],
                      required={"student_id", "company_id", "designation", "ctc_lpa"}, ranges={"ctc_lpa": (0, 500), "base_lpa": (0, 500)},
                      search=("designation", "offer_ref", "location"), filters=("company_id", "student_id", "offer_accepted"),
                      scope=_through_student(PlacementOffer), extra=placements_extra, validate=placements_validate,
                      after_save=placements_after, before_delete=placements_before_delete,
                      order=PlacementOffer.created_at.desc()),
    "departments": Res("departments", Department, ["code", "name", "hod_name", "intake"], required={"code", "name"},
                       ranges={"intake": (0, 5000)}, search=("name", "code"), scope=departments_scope,
                       validate=departments_validate, order=Department.name),
}


# ------------------------------------------------------------------ endpoint factories
def _scoped_get(res, rid):
    obj = res.scope(res.model.query, g.user).filter(res.model.id == rid).first()
    if not obj:
        raise ApiError("Record not found.", 404)
    return obj


def _page_args(default_size, max_size):
    try:
        page = max(int(request.args.get("page", 1) or 1), 1)
        size = min(max(int(request.args.get("pageSize", default_size) or default_size), 1), max_size)
    except (TypeError, ValueError):
        raise ApiError("page and pageSize must be whole numbers.", 400)
    return page, size


def _commit_or_conflict():
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError("A record with the same unique value already exists, or a linked record is missing.", 409)


def register(res: Res):
    k = res.key

    @bp.get(f"/{k}", endpoint=f"{k}_list")
    @require_auth(f"{k}:read")
    def list_():
        q = res.scope(res.model.query, g.user)
        s = request.args.get("q", "").strip()
        if s and res.search:
            like = f"%{s}%"
            from sqlalchemy import or_
            q = q.filter(or_(*[getattr(res.model, c).ilike(like) for c in res.search]))
        if res.key == "vacancies" and request.args.get("eligible") == "true" and g.user.role_name == "student":
            student = Student.query.filter((Student.user_id == g.user.id) | (Student.email == g.user.email)).first()
            if student:
                q = q.filter(db.func.coalesce(Vacancy.min_cgpa, 0) <= (student.cgpa or 0),
                             db.func.coalesce(Vacancy.max_backlogs, 0) >= (student.active_backlogs or 0))
            else:
                q = q.filter(false())
        for f in res.filters:
            val = request.args.get(camel(f))
            if val not in (None, ""):
                col = getattr(res.model, f)
                if val.startswith("!"):
                    q = q.filter(col != val[1:])
                    continue
                values = [item for item in val.split(",") if item != ""]
                if not values:
                    raise ApiError(f"{camel(f)} filter must not be empty.", 400)
                if isinstance(col.type, Boolean):
                    values = [item == "true" for item in values]
                elif isinstance(col.type, Integer):
                    try:
                        values = [int(item) for item in values]
                    except ValueError:
                        raise ApiError(f"{camel(f)} filter must contain whole numbers.", 400)
                elif isinstance(col.type, Float):
                    try:
                        values = [float(item) for item in values]
                    except ValueError:
                        raise ApiError(f"{camel(f)} filter must contain numbers.", 400)
                q = q.filter(col.in_(values) if len(values) > 1 else col == values[0])

        sort = request.args.get("sort", "").strip()
        direction = request.args.get("sortDir", "asc").lower()
        if sort and direction not in ("asc", "desc"):
            raise ApiError("sortDir must be 'asc' or 'desc'.", 400)
        if sort:
            column_name = snake(sort)
            if column_name not in res.model.__table__.columns:
                raise ApiError("The requested sort field is not supported.", 400)
            column = getattr(res.model, column_name)
            q = q.order_by(column.desc() if direction == "desc" else column.asc())
        elif res.order is not None:
            q = q.order_by(res.order)
        page, size = _page_args(100, 100)
        total = q.count()
        items = q.offset((page - 1) * size).limit(size).all()
        return jsonify({"items": [res.dump(o, g.user) for o in items], "total": total, "page": page, "pageSize": size})

    @bp.get(f"/{k}/<int:rid>", endpoint=f"{k}_get")
    @require_auth(f"{k}:read")
    def get_(rid):
        return jsonify(res.dump(_scoped_get(res, rid), g.user))

    @bp.post(f"/{k}", endpoint=f"{k}_create")
    @require_auth(f"{k}:write")
    def create_():
        if res.create_ok and not res.create_ok(g.user):
            raise ApiError("Your role cannot create this record type.", 403, code="forbidden")
        data = request.get_json(silent=True) or {}
        obj = res.model()
        if k == "vacancies" and g.user.role_name == RECRUITER:
            obj.company_id = g.user.company_id  # recruiters always post for their own company
        write_fields(res, obj, data, g.user, True)
        db.session.add(obj)
        try:
            db.session.flush()
            if res.after_save:
                res.after_save(obj, True, g.user)
        except IntegrityError:
            db.session.rollback()
            raise ApiError("A record with the same unique value already exists.", 409)
        _commit_or_conflict()
        audit(f"Created {k}", k, obj.id, str(getattr(obj, "name", None) or getattr(obj, "title", "") or ""))
        return jsonify(res.dump(obj, g.user)), 201

    @bp.put(f"/{k}/<int:rid>", endpoint=f"{k}_update")
    @require_auth(f"{k}:write")
    def update_(rid):
        obj = _scoped_get(res, rid)
        if k == "vacancies":
            obj._was_live = obj.status in ("Approved", "Active")
        data = request.get_json(silent=True) or {}
        write_fields(res, obj, data, g.user, False)
        if res.after_save:
            res.after_save(obj, False, g.user)
        _commit_or_conflict()
        audit(f"Updated {k}", k, obj.id, ", ".join(sorted(data.keys()))[:200])
        return jsonify(res.dump(obj, g.user))

    @bp.delete(f"/{k}/<int:rid>", endpoint=f"{k}_delete")
    @require_auth(f"{k}:delete")
    def delete_(rid):
        obj = _scoped_get(res, rid)
        if res.before_delete:
            res.before_delete(obj)
        label = str(getattr(obj, "name", None) or getattr(obj, "title", "") or obj.id)
        db.session.delete(obj)
        _commit_or_conflict()
        audit(f"Deleted {k}", k, rid, label)
        return jsonify({"ok": True})


for _r in RESOURCES.values():
    register(_r)


# ------------------------------------------------------------------ lookups
@bp.get("/lookups")
@require_auth()
def lookups():
    u = g.user
    out = {"departments": [{"id": d.id, "code": d.code, "label": d.name} for d in Department.query.order_by(Department.name)]}
    if can(u, "companies:read") or can(u, "vacancies:read") or can(u, "placements:write") or can(u, "outreach:read") or can(u, "drives:write"):
        qc = Company.query.order_by(Company.name)
        qc = qc if u.role_name != RECRUITER else companies_scope(qc, u)
        if u.role_name != TPO and u.role_name != COORDINATOR:
            out["companies"] = [{"id": c.id, "label": c.name} for c in qc]
    if can(u, "students:read"):
        out["students"] = [{"id": s.id, "label": f"{s.name} ({s.roll_no})", "departmentId": s.department_id}
                           for s in students_scope(Student.query, u).order_by(Student.name).limit(2000)]
    if can(u, "vacancies:read"):
        out["vacancies"] = [{"id": v.id, "label": f"{v.title} – {v.company.name}", "companyId": v.company_id, "status": v.status}
                            for v in vacancies_scope(Vacancy.query, u).order_by(Vacancy.title).limit(2000)]
    if can(u, "students:write"):
        out["coordinators"] = [{"id": c.id, "label": c.full_name} for c in User.query.all()
                               if c.role_name == COORDINATOR and c.status == "active"]
    return jsonify(out)


# ------------------------------------------------------------------ vacancy workflow
@bp.post("/vacancies/<int:vid>/submit")
@require_auth("vacancies:write")
def submit_vacancy(vid):
    v = _scoped_get(RESOURCES["vacancies"], vid)
    if v.status != "Draft":
        raise ApiError("Only Draft vacancies can be submitted for verification.", 409)
    v.status = "Pending Verification"
    db.session.commit()
    audit("Submitted vacancy for verification", "vacancies", v.id, v.title)
    return jsonify(RESOURCES["vacancies"].dump(v, g.user))


@bp.post("/vacancies/<int:vid>/review")
@require_auth("vacancies:verify")
def review_vacancy(vid):
    v = _scoped_get(RESOURCES["vacancies"], vid)
    d = request.get_json(silent=True) or {}
    decision = d.get("decision")
    note = str(d.get("note", ""))[:500]
    if v.status != "Pending Verification":
        raise ApiError("This vacancy is not awaiting verification.", 409)
    if decision not in ("approve", "return"):
        raise ApiError("Decision must be approve or return.", 400)
    if decision == "return" and len(note) < 5:
        raise ApiError("Give the company a reason when returning a vacancy.", 422, {"note": "Required"})
    v.status = "Approved" if decision == "approve" else "Draft"
    db.session.add(VacancyVerification(vacancy_id=v.id, decision="Approved" if decision == "approve" else "Returned",
                                       note=note, reviewer_id=g.user.id, reviewer_name=g.user.full_name))
    # notify the submitter
    if v.submitted_by_id:
        db.session.add(Notification(user_id=v.submitted_by_id, type="approval", sender_id=g.user.id,
                                    title=f"Vacancy {'approved' if decision == 'approve' else 'returned'}: {v.title}",
                                    message=note or ("Your vacancy has been verified." if decision == "approve" else "")))
    db.session.commit()
    audit(f"Vacancy {decision}", "vacancies", v.id, v.title + (f" – {note}" if note else ""))
    return jsonify(RESOURCES["vacancies"].dump(v, g.user))


@bp.get("/vacancy-verifications")
@require_auth("vacancies:verify")
def verification_history():
    rows = VacancyVerification.query.order_by(VacancyVerification.created_at.desc()).limit(200).all()
    out = []
    for r in rows:
        v = db.session.get(Vacancy, r.vacancy_id)
        d = r.to_dict()
        d["vacancyTitle"] = v.title if v else "(deleted)"
        d["companyName"] = v.company.name if v else ""
        out.append(d)
    return jsonify({"items": out})


@bp.post("/vacancies/import")
@require_auth("vacancies:import")
def import_vacancies():
    """CSV import. dry_run=true validates only; otherwise valid rows are created as Draft (source=Import)."""
    f = request.files.get("file")
    if not f or not (f.filename or "").lower().endswith(".csv"):
        raise ApiError("Upload a .csv file.", 400)
    raw = f.read(2_000_000)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ApiError("File must be UTF-8 encoded.", 400)
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise ApiError("The file has no data rows.", 400)
    if len(rows) > 500:
        raise ApiError("Maximum 500 rows per import.", 400)
    dry = request.form.get("dryRun", "true") == "true"
    companies = {c.name.lower(): c for c in Company.query.all()}
    codes = {d.code for d in Department.query.all()}
    result, created = [], 0
    for i, r in enumerate(rows, start=2):
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
        errs = []
        co = companies.get(r.get("company", "").lower())
        if not r.get("title"):
            errs.append("title missing")
        if not co:
            errs.append(f"company '{r.get('company', '')}' not found")
        try:
            ctc = float(r.get("ctc_lpa") or 0)
            cg = float(r.get("min_cgpa") or 0)
            ob = int(r.get("openings") or 1)
        except ValueError:
            errs.append("numeric field invalid")
            ctc = cg = 0
            ob = 1
        depts = [x.strip().upper() for x in (r.get("departments", "")).replace(";", ",").split(",") if x.strip()]
        if set(depts) - codes:
            errs.append("unknown department code(s): " + ", ".join(sorted(set(depts) - codes)))
        dl = None
        if r.get("deadline"):
            try:
                dl = date.fromisoformat(r["deadline"])
            except ValueError:
                errs.append("deadline must be YYYY-MM-DD")
        jt = r.get("job_type") or "Full-Time"
        if jt not in ("Full-Time", "Internship + PPO", "Internship Only"):
            errs.append("invalid job_type")
        result.append({"row": i, "title": r.get("title"), "company": r.get("company"), "errors": errs})
        if not errs and not dry:
            db.session.add(Vacancy(title=r["title"][:160], company_id=co.id, job_type=jt, ctc_lpa=ctc, min_cgpa=cg,
                                   openings=ob, eligible_departments=depts, application_deadline=dl,
                                   locations=[x.strip() for x in r.get("locations", "").split(";") if x.strip()],
                                   description=r.get("description", "")[:4000], status="Draft", source="Import",
                                   submitted_by_id=g.user.id))
            created += 1
    if not dry:
        db.session.commit()
        audit("Imported vacancies", "vacancies", "", f"{created} created of {len(rows)} rows")
    return jsonify({"dryRun": dry, "total": len(rows), "valid": sum(1 for x in result if not x["errors"]),
                    "created": created, "rows": result})


# ------------------------------------------------------------------ department statistics
@bp.get("/departments-stats")
@require_auth("departments:read")
def department_stats():
    out = []
    for d in departments_scope(Department.query, g.user).order_by(Department.name):
        studs = Student.query.filter_by(department_id=d.id).all()
        offers = PlacementOffer.query.join(Student).filter(Student.department_id == d.id, PlacementOffer.offer_accepted.is_(True)).all()
        placed_ids = {o.student_id for o in offers}
        out.append({**d.to_dict(), "totalStudents": len(studs), "placedStudents": len(placed_ids),
                    "placementRate": round(100 * len(placed_ids) / len(studs), 1) if studs else 0,
                    "avgCtcLpa": round(sum(o.ctc_lpa for o in offers) / len(offers), 2) if offers else 0,
                    "highestCtcLpa": max((o.ctc_lpa for o in offers), default=0)})
    return jsonify({"items": out})


# ------------------------------------------------------------------ student excel import & export
@bp.get("/students/template")
@require_auth("students:read")
def student_template():
    """Generates a downloadable Excel (.xlsx) template with sample valid data for bulk import."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Student Template"
    headers = [
        "Roll No*", "Full Name*", "Email*", "Department Code*", "Batch*",
        "CGPA", "Active Backlogs", "History Backlogs", "Phone", "Gender",
        "Passing Year", "Preferred Domain", "Skills (comma-separated)"
    ]
    ws.append(headers)
    ws.append(["STU-2026-001", "Aarav Sharma", "aarav.sharma@example.edu", "BA", "2024-26", 8.45, 0, 0, "+91 9876543210", "Male", 2026, "Analytics", "Python, SQL, Tableau"])
    ws.append(["STU-2026-002", "Priya Nair", "priya.nair@example.edu", "FIN", "2024-26", 7.90, 0, 0, "+91 9876543211", "Female", 2026, "Financial Analysis", "Excel, Corporate Finance"])
    ws.append(["STU-2026-003", "Rohan Mehta", "rohan.mehta@example.edu", "MKT", "2024-26", 8.10, 0, 0, "+91 9876543212", "Male", 2026, "Brand Management", "Digital Marketing, SEO"])

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    from flask import Response
    return Response(
        out.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=student_import_template.xlsx"}
    )


@bp.post("/students/import")
@require_auth("students:write")
def import_students_excel():
    """Excel and CSV bulk student import with row-by-row validation, duplicate checks, and dry-run preview."""
    import openpyxl
    f = request.files.get("file")
    if not f or not (f.filename or "").lower().endswith((".xlsx", ".csv")):
        raise ApiError("Upload an .xlsx or .csv spreadsheet file.", 400)

    dry = request.form.get("dryRun", "true") == "true"
    rows_data = []

    if (f.filename or "").lower().endswith(".xlsx"):
        try:
            wb = openpyxl.load_workbook(f, data_only=True)
            ws = wb.active
            iter_rows = ws.iter_rows(values_only=True)
            header = next(iter_rows, None)
            if not header:
                raise ApiError("The spreadsheet is empty.", 400)
            col_names = [str(c or "").strip().lower().replace("*", "").replace(" ", "_").replace("-", "_") for c in header]
            for r in iter_rows:
                if not any(r):
                    continue
                row_dict = {col_names[idx]: (str(val).strip() if val is not None else "") for idx, val in enumerate(r) if idx < len(col_names)}
                rows_data.append(row_dict)
        except ApiError:
            raise
        except Exception as e:
            raise ApiError(f"Failed to parse Excel file: {str(e)}", 400)
    else:
        try:
            text = f.read().decode("utf-8-sig")
            rows_data = list(csv.DictReader(io.StringIO(text)))
        except Exception:
            raise ApiError("Failed to decode CSV file. Must be UTF-8.", 400)

    if not rows_data:
        raise ApiError("No data rows found in file.", 400)
    if len(rows_data) > 1000:
        raise ApiError("Maximum 1,000 rows per import batch.", 400)

    dept_map = {d.code.upper(): d for d in Department.query.all()}
    existing_rolls = {s.roll_no.lower() for s in Student.query.all()}
    existing_emails = {s.email.lower() for s in Student.query.all()}

    results = []
    created_count = 0
    file_rolls = set()
    file_emails = set()

    for idx, row in enumerate(rows_data, start=2):
        errs = []
        roll = (row.get("roll_no") or row.get("rollno") or row.get("student_id") or "").strip()
        name = (row.get("full_name") or row.get("name") or "").strip()
        email = (row.get("email") or "").strip()
        dept_code = (row.get("department_code") or row.get("department") or row.get("dept") or "").strip().upper()
        batch = (row.get("batch") or "2024-26").strip()

        if not roll:
            errs.append("Roll No is required")
        elif roll.lower() in existing_rolls:
            errs.append(f"Roll No '{roll}' already exists in database")
        elif roll.lower() in file_rolls:
            errs.append(f"Duplicate Roll No '{roll}' in spreadsheet")

        if not name:
            errs.append("Full Name is required")

        if not email:
            errs.append("Email is required")
        elif not EMAIL_RE.match(email):
            errs.append(f"Invalid email: {email}")
        elif email.lower() in existing_emails:
            errs.append(f"Email '{email}' already registered in database")
        elif email.lower() in file_emails:
            errs.append(f"Duplicate email '{email}' in spreadsheet")

        if not dept_code or dept_code not in dept_map:
            valid_codes = ", ".join(sorted(dept_map.keys()))
            errs.append(f"Department code '{dept_code}' unknown (Valid: {valid_codes})")
        elif g.user.role_name == TPO and dept_map[dept_code].id != g.user.department_id:
            errs.append(f"You can only import students of your own department (not '{dept_code}')")

        cgpa = 0.0
        try:
            cgpa = float(row.get("cgpa") or 0.0)
            if not (0.0 <= cgpa <= 10.0):
                errs.append("CGPA must be between 0.0 and 10.0")
        except ValueError:
            errs.append("CGPA must be numeric")

        active_bl = 0
        try:
            active_bl = int(float(row.get("active_backlogs") or 0))
            if active_bl < 0:
                errs.append("Active backlogs cannot be negative")
        except ValueError:
            errs.append("Active backlogs must be an integer")

        hist_bl = 0
        try:
            hist_bl = int(float(row.get("history_backlogs") or 0))
            if hist_bl < 0:
                errs.append("History backlogs cannot be negative")
        except ValueError:
            errs.append("History backlogs must be an integer")

        file_rolls.add(roll.lower())
        file_emails.add(email.lower())

        results.append({
            "row": idx,
            "rollNo": roll,
            "name": name,
            "email": email,
            "department": dept_code,
            "errors": errs,
        })

        if not errs and not dry:
            dept = dept_map[dept_code]
            skills_raw = row.get("skills_(comma_separated)") or row.get("skills") or ""
            skills = [s.strip() for s in skills_raw.replace(";", ",").split(",") if s.strip()]
            pass_yr = None
            try:
                pass_yr = int(float(row.get("passing_year") or 0)) or None
            except Exception:
                pass

            s = Student(
                roll_no=roll,
                name=name,
                email=email,
                phone=row.get("phone", ""),
                gender=row.get("gender", ""),
                passing_year=pass_yr,
                department_id=dept.id,
                batch=batch,
                cgpa=cgpa,
                active_backlogs=active_bl,
                history_backlogs=hist_bl,
                skills=skills,
                status="Unplaced",
                preferred_domain=row.get("preferred_domain", ""),
                is_sample=False,
            )
            db.session.add(s)
            created_count += 1

    if not dry:
        _commit_or_conflict()
        audit("Imported students Excel", "students", "", f"{created_count} imported of {len(rows_data)} rows")

    valid_count = sum(1 for r in results if not r["errors"])
    skipped_count = sum(1 for r in results if any("already exists" in e for e in r["errors"]))
    err_list = [{"row": r["row"], "error": "; ".join(r["errors"])} for r in results if r["errors"]]

    return jsonify({
        "dryRun": dry,
        "total": len(rows_data),
        "totalRows": len(rows_data),
        "valid": valid_count,
        "imported": created_count if not dry else valid_count,
        "skipped": skipped_count,
        "created": created_count,
        "errors": err_list,
        "rows": results,
    })


# ------------------------------------------------------------------ job aggregation pipeline routes
@bp.post("/aggregation/run")
@require_auth("vacancies:import")
def run_aggregation():
    """Triggers the job aggregation pipeline manually with optional source filtering."""
    d = request.get_json(silent=True) or {}
    source = d.get("source", "all")
    query = d.get("query", "")
    from .aggregation import AggregationPipeline
    pipeline = AggregationPipeline(triggered_by=g.user.full_name)
    result = pipeline.run(source_filter=source, custom_query=query)
    audit("Ran job aggregation pipeline", "vacancies", f"run-{result.get('run_id')}",
          f"Created {result['created']} draft vacancies from {source}")
    return jsonify(result)


@bp.get("/aggregation/runs")
@require_auth("vacancies:import")
def get_aggregation_runs():
    """Returns recent aggregation execution history with counts and logs."""
    from .models import AggregationRun
    runs = AggregationRun.query.order_by(AggregationRun.created_at.desc()).limit(50).all()
    return jsonify({"items": [r.to_dict() for r in runs]})


@bp.get("/aggregation/summary")
@require_auth("vacancies:read")
def get_aggregation_summary():
    """Returns summary counters and status for opportunity aggregation."""
    import os
    from .models import AggregationRun
    total_scraped = Vacancy.query.filter(Vacancy.source.like("Scraper%")).count()
    pending = Vacancy.query.filter(Vacancy.source.like("Scraper%"), Vacancy.status == "Pending Verification").count()
    approved = Vacancy.query.filter(Vacancy.source.like("Scraper%"), Vacancy.status.in_(["Approved", "Active"])).count()
    high_risk = Vacancy.query.filter(Vacancy.source.like("Scraper%"), Vacancy.risk_level.in_(["High Risk", "Requires Manual Review"])).count()
    latest_run = AggregationRun.query.order_by(AggregationRun.created_at.desc()).first()
    return jsonify({
        "totalScraped": total_scraped,
        "pendingVerification": pending,
        "approved": approved,
        "highRiskFlagged": high_risk,
        "lastRun": latest_run.to_dict() if latest_run else None,
        "serperConfigured": bool(os.getenv("SERPER_API_KEY")),
    })


# ------------------------------------------------------------------ student portal routes
@bp.get("/student/profile")
@require_auth("dashboard:view")
def get_student_profile():
    """Returns the authenticated student's profile, application history, and documents."""
    u = g.user
    stud = Student.query.filter((Student.user_id == u.id) | (Student.email == u.email)).first()
    if not stud and u.role_name in FULL_ACCESS:
        sid = request.args.get("id")
        if sid:
            stud = db.session.get(Student, int(sid))
    if not stud:
        return jsonify({"profile": None})

    d = stud.to_dict()
    d["departmentName"] = stud.department.name if stud.department else ""
    d["departmentCode"] = stud.department.code if stud.department else ""

    apps = Application.query.filter_by(student_id=stud.id).all()
    d["applicationsCount"] = len(apps)
    d["applications"] = [{
        "id": a.id, "vacancyId": a.vacancy_id, "vacancyTitle": a.vacancy.title,
        "companyName": a.vacancy.company.name if a.vacancy and a.vacancy.company else "",
        "stage": a.stage, "ctcLpa": a.vacancy.ctc_lpa if a.vacancy else 0,
        "jobType": a.vacancy.job_type if a.vacancy else "",
        "updatedAt": a.updated_at.isoformat() if a.updated_at else "",
        "remarks": a.remarks or "",
    } for a in apps]

    offers = PlacementOffer.query.filter_by(student_id=stud.id).all()
    d["offers"] = [{
        "id": o.id, "companyName": o.company.name if o.company else "",
        "designation": o.designation, "ctcLpa": o.ctc_lpa,
        "offerAccepted": o.offer_accepted, "verified": o.verified,
        "joiningDate": o.joining_date.isoformat() if o.joining_date else "",
    } for o in offers]

    from .models import Document
    docs = Document.query.filter_by(student_id=stud.id).all()
    d["documents"] = [doc.to_dict() for doc in docs]
    return jsonify({"profile": d})


@bp.put("/student/profile")
@require_auth("dashboard:view")
def update_student_profile():
    """Allows student to update permitted personal details."""
    u = g.user
    stud = Student.query.filter((Student.user_id == u.id) | (Student.email == u.email)).first()
    if not stud:
        raise ApiError("Student record not linked to this account.", 404)
    data = request.get_json(silent=True) or {}
    if "phone" in data:
        stud.phone = str(data["phone"])[:30]
    if "skills" in data and isinstance(data["skills"], list):
        stud.skills = [str(x)[:40] for x in data["skills"]][:30]
    if "preferredDomain" in data:
        stud.preferred_domain = str(data["preferredDomain"])[:80]
    if "bio" in data:
        stud.bio = str(data["bio"])[:2000]
    if "linkedinUrl" in data:
        stud.linkedin_url = str(data["linkedinUrl"])[:255]
    if "githubUrl" in data:
        stud.github_url = str(data["githubUrl"])[:255]
    db.session.commit()
    audit("Updated student profile", "students", stud.id, stud.name)
    return jsonify({"profile": stud.to_dict()})


@bp.get("/student/eligible-vacancies")
@require_auth("vacancies:read")
def get_student_eligible_vacancies():
    """Returns verified and active vacancies with personalized student eligibility evaluation."""
    u = g.user
    stud = Student.query.filter((Student.user_id == u.id) | (Student.email == u.email)).first()
    dept_code = stud.department.code if (stud and stud.department) else ""
    cgpa = (stud.cgpa or 0.0) if stud else 10.0
    backlogs = (stud.active_backlogs or 0) if stud else 0

    vacs = Vacancy.query.filter(Vacancy.status.in_(["Approved", "Active"])).order_by(Vacancy.created_at.desc()).all()
    applied_vids = {a.vacancy_id for a in Application.query.filter_by(student_id=stud.id).all()} if stud else set()

    items = []
    for v in vacs:
        dept_match = not v.eligible_departments or (dept_code in v.eligible_departments)
        cgpa_match = cgpa >= (v.min_cgpa or 0.0)
        backlog_match = backlogs <= (v.max_backlogs or 0)
        is_eligible = dept_match and cgpa_match and backlog_match

        d = v.to_dict()
        d["companyName"] = v.company.name if v.company else ""
        d["companyWebsite"] = v.company.website if v.company else ""
        d["companyIndustry"] = v.company.industry if v.company else ""
        d["companyLocation"] = v.company.location if v.company else ""
        d["isEligible"] = is_eligible
        d["hasApplied"] = v.id in applied_vids
        reasons = []
        if not dept_match:
            reasons.append(f"Departments: {', '.join(v.eligible_departments)}")
        if not cgpa_match:
            reasons.append(f"Min CGPA {v.min_cgpa} (Yours: {cgpa})")
        if not backlog_match:
            reasons.append(f"Max {v.max_backlogs} backlogs (Yours: {backlogs})")
        d["eligibilityReasons"] = reasons
        items.append(d)

    return jsonify({"items": items})


@bp.post("/student/apply")
@require_auth("applications:write")
def student_self_apply():
    """Allows student to apply directly for an eligible vacancy."""
    u = g.user
    stud = Student.query.filter((Student.user_id == u.id) | (Student.email == u.email)).first()
    if not stud:
        raise ApiError("No student record found linked to your account.", 404)
    data = request.get_json(silent=True) or {}
    vid = data.get("vacancyId")
    if not vid:
        raise ApiError("vacancyId is required.", 400)
    v = db.session.get(Vacancy, int(vid))
    if not v or v.status not in ("Approved", "Active"):
        raise ApiError("This vacancy is not accepting applications.", 400)

    existing = Application.query.filter_by(student_id=stud.id, vacancy_id=v.id).first()
    if existing:
        raise ApiError("You have already applied for this opportunity.", 400)

    dept_code = stud.department.code if stud.department else ""
    if v.eligible_departments and dept_code not in v.eligible_departments:
        raise ApiError(f"Your department ({dept_code}) is not eligible.", 400)
    if (stud.cgpa or 0) < (v.min_cgpa or 0.0):
        raise ApiError(f"Minimum CGPA required is {v.min_cgpa}.", 400)
    if (stud.active_backlogs or 0) > (v.max_backlogs or 0):
        raise ApiError("Active backlogs exceed maximum allowed.", 400)

    app_record = Application(
        student_id=stud.id,
        vacancy_id=v.id,
        stage="Applied",
        remarks="Applied through Student Portal",
        updated_by_id=u.id,
        is_sample=False,
    )
    db.session.add(app_record)

    if v.submitted_by_id:
        db.session.add(Notification(
            user_id=v.submitted_by_id,
            type="application",
            sender_id=u.id,
            title=f"New applicant: {stud.name}",
            message=f"{stud.name} ({stud.roll_no}, {dept_code}) applied for {v.title}."
        ))

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ApiError("You have already applied for this opportunity.", 400)
    audit("Student submitted application", "applications", app_record.id, f"{stud.name} -> {v.title}")
    return jsonify({"status": "Applied", "applicationId": app_record.id})


@bp.post("/student/withdraw/<int:aid>")
@require_auth("applications:write")
def student_withdraw_application(aid):
    """Allows student to withdraw their own pending application."""
    u = g.user
    stud = Student.query.filter((Student.user_id == u.id) | (Student.email == u.email)).first()
    if not stud:
        raise ApiError("Student not found.", 404)
    app_record = Application.query.filter_by(id=aid, student_id=stud.id).first()
    if not app_record:
        raise ApiError("Application not found.", 404)
    if app_record.stage in ("Selected", "Rejected", "Withdrawn"):
        raise ApiError(f"Cannot withdraw application in stage '{app_record.stage}'.", 400)
    app_record.stage = "Withdrawn"
    app_record.remarks = "Withdrawn by candidate"
    db.session.commit()
    audit("Student withdrew application", "applications", app_record.id, stud.name)
    return jsonify({"status": "Withdrawn", "applicationId": app_record.id})


# ------------------------------------------------------------------ recruiter candidate management
@bp.get("/recruiter/candidates")
@require_auth("applications:read")
def get_recruiter_candidates():
    """Returns candidate applications for recruiter's company vacancies."""
    u = g.user
    if not u.company_id and u.role_name == RECRUITER:
        return jsonify({"items": []})

    # Same scoping as /api/applications: recruiters -> own company, TPO/faculty -> own department,
    # coordinator -> assigned students, student -> self.
    q = RESOURCES["applications"].scope(Application.query.join(Vacancy), u)

    apps = q.order_by(Application.created_at.desc()).all()
    out = []
    for a in apps:
        s = a.student
        v = a.vacancy
        out.append({
            "id": a.id,
            "studentId": s.id,
            "studentName": s.name,
            "rollNo": s.roll_no,
            "email": s.email,
            "phone": s.phone,
            "departmentCode": s.department.code if s.department else "",
            "cgpa": s.cgpa,
            "skills": s.skills,
            "vacancyId": v.id,
            "vacancyTitle": v.title,
            "stage": a.stage,
            "score": a.score,
            "remarks": a.remarks,
            "appliedAt": a.created_at.isoformat() if a.created_at else "",
            "updatedAt": a.updated_at.isoformat() if a.updated_at else "",
        })
    return jsonify({"items": out})


@bp.put("/recruiter/candidates/<int:aid>/stage")
@require_auth("applications:write")
def update_candidate_stage(aid):
    """Allows recruiter or TPO to advance candidate stage in the hiring pipeline."""
    u = g.user
    if u.role_name == "student":
        raise ApiError("Students cannot change application stages.", 403, code="forbidden")
    a = RESOURCES["applications"].scope(Application.query, u).filter(Application.id == aid).first()
    if not a:
        raise ApiError("Application not found.", 404)

    data = request.get_json(silent=True) or {}
    new_stage = data.get("stage")
    if not new_stage or new_stage not in APP_STAGES:
        raise ApiError(f"Invalid stage. Must be one of: {', '.join(APP_STAGES)}", 400)

    old_stage = a.stage
    a.stage = new_stage
    a.updated_by_id = u.id
    if "remarks" in data:
        a.remarks = str(data["remarks"])[:500]
    if "score" in data:
        try:
            score = float(data["score"]) if data["score"] not in (None, "") else None
        except (TypeError, ValueError):
            raise ApiError("Score must be a number between 0 and 100.", 422, {"score": "Invalid value"})
        if score is not None and not 0 <= score <= 100:
            raise ApiError("Score must be a number between 0 and 100.", 422, {"score": "Must be between 0 and 100"})
        a.score = score

    # Notify student
    if a.student and a.student.user_id:
        db.session.add(Notification(
            user_id=a.student.user_id,
            type="status",
            sender_id=u.id,
            title=f"Application update: {a.vacancy.title}",
            message=f"Your application status for {a.vacancy.title} at {a.vacancy.company.name} has been updated to '{new_stage}'."
        ))

    db.session.commit()
    audit(f"Candidate stage changed ({old_stage} -> {new_stage})", "applications", a.id, f"{a.student.name} for {a.vacancy.title}")
    return jsonify({"status": "Updated", "stage": a.stage, "id": a.id})


# ------------------------------------------------------------------ real-time notification stream (SSE)
@bp.get("/notifications/stream")
@require_auth("notifications:read")
def stream_notifications():
    """Server-Sent Events endpoint. Sends the current unread count, then lets the browser reconnect after `retry` ms.

    The count is computed inside the request context (a lazily-run generator would execute after the context is gone),
    events are unnamed so `EventSource.onmessage` receives them, and no hop-by-hop `Connection` header is set (waitress
    rejects those per PEP 3333).
    """
    import json
    from flask import Response
    unread = Notification.query.filter_by(user_id=g.user.id, read=False).count()

    def event_stream():
        yield "retry: 30000\n"
        yield f"data: {json.dumps({'unread': unread})}\n\n"

    return Response(event_stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
