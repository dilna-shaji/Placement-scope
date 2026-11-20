"""Database models. Every table has a primary key, explicit foreign keys and constraints."""
from datetime import date, datetime, timezone

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def camel(s: str) -> str:
    p = s.split("_")
    return p[0] + "".join(x.title() for x in p[1:])


def snake(s: str) -> str:
    out = ""
    for ch in s:
        out += ("_" + ch.lower()) if ch.isupper() else ch
    return out


class Serial:
    hidden: set = set()

    def to_dict(self):
        out = {}
        for c in self.__table__.columns:
            if c.name in self.hidden:
                continue
            # Use the mapped attribute key (it can differ from the DB column name, e.g. AggregationRun.search_query -> "query")
            v = getattr(self, self.__mapper__.get_property_by_column(c).key)
            if isinstance(v, (datetime, date)):
                v = v.isoformat()
            out[camel(c.name)] = v
        return out


# ---------------------------------------------------------------- RBAC
role_permissions = db.Table(
    "role_permissions",
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Role(db.Model, Serial):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False)
    label = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(255), default="")
    permissions = db.relationship("Permission", secondary=role_permissions, lazy="joined")


class Permission(db.Model, Serial):
    __tablename__ = "permissions"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(60), unique=True, nullable=False)
    description = db.Column(db.String(160), default="")


class Department(db.Model, Serial):
    """A department is a MBA specialisation (Marketing, Finance, HR, Operations, Business Analytics)."""
    __tablename__ = "departments"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)
    name = db.Column(db.String(80), unique=True, nullable=False)
    hod_name = db.Column(db.String(120), default="")
    intake = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)


class User(db.Model, Serial):
    __tablename__ = "users"
    hidden = {"password_hash"}
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(190), unique=True, nullable=False)
    employee_id = db.Column(db.String(60), unique=True)
    full_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active")  # active | disabled
    must_change_password = db.Column(db.Boolean, default=True, nullable=False)
    failed_attempts = db.Column(db.Integer, default=0, nullable=False)
    lock_count = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id", ondelete="SET NULL"))
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id", ondelete="SET NULL"))
    designation = db.Column(db.String(120), default="")
    phone = db.Column(db.String(30), default="")
    last_login_at = db.Column(db.DateTime)
    password_changed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    department = db.relationship("Department", lazy="joined")
    company = db.relationship("Company", lazy="joined")
    assignment = db.relationship("UserRole", foreign_keys="UserRole.user_id", uselist=False, lazy="joined",
                                 cascade="all, delete-orphan")

    @property
    def role(self):
        return self.assignment.role if self.assignment else None

    @property
    def role_name(self):
        return self.role.name if self.role else None

    def public(self):
        d = self.to_dict()
        d["role"] = self.role_name
        d["roleLabel"] = self.role.label if self.role else None
        d["departmentName"] = self.department.name if self.department else None
        d["departmentCode"] = self.department.code if self.department else None
        d["companyName"] = self.company.name if self.company else None
        d["lockedNow"] = bool(self.locked_until and self.locked_until > utcnow())
        return d


class UserRole(db.Model, Serial):
    """The single authoritative role assignment for a user (set only by an administrator)."""
    __tablename__ = "user_roles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    assigned_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    assigned_at = db.Column(db.DateTime, default=utcnow)
    role = db.relationship("Role", lazy="joined")


class AccountRequest(db.Model, Serial):
    __tablename__ = "account_requests"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(190), nullable=False, index=True)
    employee_id = db.Column(db.String(60))
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id", ondelete="SET NULL"))
    designation = db.Column(db.String(120), default="")
    requested_role = db.Column(db.String(40), nullable=False)
    phone = db.Column(db.String(30), default="")
    reason = db.Column(db.Text, default="")
    company_name = db.Column(db.String(160))
    company_email = db.Column(db.String(190))
    company_phone = db.Column(db.String(30))
    student_id_no = db.Column(db.String(60))
    academic_year = db.Column(db.String(20))
    faculty_supervisor = db.Column(db.String(120))
    status = db.Column(db.String(24), nullable=False, default="Pending Approval")
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at = db.Column(db.DateTime)
    review_note = db.Column(db.String(500), default="")
    created_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    ip_address = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=utcnow)
    department = db.relationship("Department", lazy="joined")


# ---------------------------------------------------------------- Security tables
class LoginSession(db.Model, Serial):
    __tablename__ = "login_sessions"
    hidden = {"token_hash", "csrf_token"}
    id = db.Column(db.Integer, primary_key=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    csrf_token = db.Column(db.String(64), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    last_seen_at = db.Column(db.DateTime, default=utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    remember = db.Column(db.Boolean, default=False)
    revoked = db.Column(db.Boolean, default=False)
    ip_address = db.Column(db.String(64))
    user_agent = db.Column(db.String(255))
    user = db.relationship("User", lazy="joined")


class PasswordReset(db.Model, Serial):
    __tablename__ = "password_resets"
    hidden = {"token_hash"}
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    kind = db.Column(db.String(20), default="forgot")  # forgot | admin
    created_at = db.Column(db.DateTime, default=utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)


class LoginAttempt(db.Model, Serial):
    __tablename__ = "login_attempts"
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(20), default="login")  # login | forgot | request
    identifier = db.Column(db.String(190))
    ip_address = db.Column(db.String(64), index=True)
    success = db.Column(db.Boolean, default=False)
    reason = db.Column(db.String(80), default="")
    created_at = db.Column(db.DateTime, default=utcnow, index=True)


class CaptchaChallenge(db.Model):
    __tablename__ = "captcha_challenges"
    id = db.Column(db.String(32), primary_key=True)
    answer_hash = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)


class AuditLog(db.Model, Serial):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=utcnow, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    actor_name = db.Column(db.String(120), default="")
    actor_role = db.Column(db.String(40), default="")
    action = db.Column(db.String(80), nullable=False)
    entity_type = db.Column(db.String(40), default="")
    entity_id = db.Column(db.String(40), default="")
    ip_address = db.Column(db.String(64), default="")
    status = db.Column(db.String(12), default="Success")
    details = db.Column(db.String(500), default="")


class SystemSetting(db.Model):
    __tablename__ = "system_settings"
    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.JSON)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)


# ---------------------------------------------------------------- Placement domain
class Student(db.Model, Serial):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    roll_no = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(190), unique=True, nullable=False)
    phone = db.Column(db.String(30), default="")
    gender = db.Column(db.String(20), default="")
    passing_year = db.Column(db.Integer)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    batch = db.Column(db.String(20), nullable=False)
    cgpa = db.Column(db.Float, default=0)
    active_backlogs = db.Column(db.Integer, default=0)
    history_backlogs = db.Column(db.Integer, default=0)
    skills = db.Column(db.JSON, default=list)
    status = db.Column(db.String(20), default="Unplaced")
    internship_status = db.Column(db.String(20), default="None")
    preferred_domain = db.Column(db.String(80), default="")
    bio = db.Column(db.Text, default="")
    linkedin_url = db.Column(db.String(255), default="")
    github_url = db.Column(db.String(255), default="")
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    resume_doc_id = db.Column(db.Integer, db.ForeignKey("documents.id", ondelete="SET NULL", use_alter=True, name="fk_students_resume_doc"))
    coordinator_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    is_sample = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    department = db.relationship("Department", lazy="joined")
    user = db.relationship("User", foreign_keys=[user_id], lazy="joined")


class Company(db.Model, Serial):
    __tablename__ = "companies"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), unique=True, nullable=False)
    industry = db.Column(db.String(80), default="")
    tier = db.Column(db.String(40), default="Core Corporate")
    location = db.Column(db.String(120), default="")
    contact_name = db.Column(db.String(120), default="")
    contact_designation = db.Column(db.String(120), default="")
    contact_email = db.Column(db.String(190), default="")
    contact_phone = db.Column(db.String(30), default="")
    mou_status = db.Column(db.String(20), default="None")
    website = db.Column(db.String(190), default="")
    about = db.Column(db.Text, default="")
    last_drive_date = db.Column(db.Date)
    is_sample = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)


class Vacancy(db.Model, Serial):
    __tablename__ = "vacancies"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    job_type = db.Column(db.String(30), default="Full-Time")
    ctc_lpa = db.Column(db.Float, default=0)
    stipend_per_month = db.Column(db.Float)
    locations = db.Column(db.JSON, default=list)
    eligible_departments = db.Column(db.JSON, default=list)
    min_cgpa = db.Column(db.Float, default=0)
    max_backlogs = db.Column(db.Integer, default=0)
    application_deadline = db.Column(db.Date)
    drive_date = db.Column(db.Date)
    status = db.Column(db.String(24), default="Draft")
    openings = db.Column(db.Integer, default=1)
    description = db.Column(db.Text, default="")
    source = db.Column(db.String(60), default="Manual")
    source_url = db.Column(db.String(500), default="")
    risk_level = db.Column(db.String(40), default="Low Risk")
    risk_score = db.Column(db.Integer, default=0)
    risk_flags = db.Column(db.JSON, default=list)
    duration = db.Column(db.String(60), default="")
    work_mode = db.Column(db.String(40), default="On-site")
    scraped_at = db.Column(db.DateTime)
    submitted_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    is_sample = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    company = db.relationship("Company", lazy="joined")


class VacancyVerification(db.Model, Serial):
    __tablename__ = "vacancy_verifications"
    id = db.Column(db.Integer, primary_key=True)
    vacancy_id = db.Column(db.Integer, db.ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False)
    decision = db.Column(db.String(12), nullable=False)  # Approved | Returned
    note = db.Column(db.String(500), default="")
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    reviewer_name = db.Column(db.String(120), default="")
    created_at = db.Column(db.DateTime, default=utcnow)


class Outreach(db.Model, Serial):
    __tablename__ = "outreach"
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    channel = db.Column(db.String(20), default="Email")
    subject = db.Column(db.String(190), nullable=False)
    message = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="Draft")
    next_followup_date = db.Column(db.Date)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, default=utcnow)
    company = db.relationship("Company", lazy="joined")


class RecruitmentDrive(db.Model, Serial):
    __tablename__ = "recruitment_drives"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    vacancy_id = db.Column(db.Integer, db.ForeignKey("vacancies.id", ondelete="SET NULL"))
    date = db.Column(db.Date, nullable=False)
    mode = db.Column(db.String(20), default="On-Campus")
    venue = db.Column(db.String(160), default="")
    stage = db.Column(db.String(40), default="Pre-Placement Talk")
    status = db.Column(db.String(20), default="Upcoming")
    rounds = db.Column(db.JSON, default=list)
    eligible_departments = db.Column(db.JSON, default=list)
    min_cgpa = db.Column(db.Float, default=0)
    registered_count = db.Column(db.Integer, default=0)
    shortlisted_count = db.Column(db.Integer, default=0)
    selected_count = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text, default="")
    is_sample = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    company = db.relationship("Company", lazy="joined")


class AggregationRun(db.Model, Serial):
    __tablename__ = "aggregation_runs"
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(60), default="All Sources")
    # NB: a Python attribute called `query` would shadow Flask-SQLAlchemy's `Model.query`
    # (breaking AggregationRun.query.order_by(...)), so the attribute is renamed while the DB column stays "query".
    search_query = db.Column("query", db.String(190), default="")
    status = db.Column(db.String(20), default="Success")
    discovered_count = db.Column(db.Integer, default=0)
    duplicates_count = db.Column(db.Integer, default=0)
    scam_flagged_count = db.Column(db.Integer, default=0)
    created_count = db.Column(db.Integer, default=0)
    duration_seconds = db.Column(db.Float, default=0.0)
    logs = db.Column(db.JSON, default=list)
    error_message = db.Column(db.Text, default="")
    triggered_by = db.Column(db.String(80), default="Manual")
    created_at = db.Column(db.DateTime, default=utcnow)


class Application(db.Model, Serial):
    __tablename__ = "applications"
    __table_args__ = (db.UniqueConstraint("student_id", "vacancy_id", name="uq_application_student_vacancy"),)
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    vacancy_id = db.Column(db.Integer, db.ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False)
    stage = db.Column(db.String(20), default="Applied")
    score = db.Column(db.Float)
    remarks = db.Column(db.String(500), default="")
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    is_sample = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    student = db.relationship("Student", lazy="joined")
    vacancy = db.relationship("Vacancy", lazy="joined")


class Internship(db.Model, Serial):
    __tablename__ = "internships"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    company_name = db.Column(db.String(160), nullable=False)
    stipend_per_month = db.Column(db.Float, default=0)
    duration_months = db.Column(db.Integer, default=2)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    mentor_name = db.Column(db.String(120), default="")
    mentor_email = db.Column(db.String(190), default="")
    progress_percent = db.Column(db.Integer, default=0)
    ppo_offered = db.Column(db.Boolean, default=False)
    ppo_ctc_lpa = db.Column(db.Float)
    evaluation_grade = db.Column(db.String(4), default="")
    status = db.Column(db.String(20), default="Ongoing")
    is_sample = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    student = db.relationship("Student", lazy="joined")


class PlacementOffer(db.Model, Serial):
    __tablename__ = "placement_offers"
    id = db.Column(db.Integer, primary_key=True)
    offer_ref = db.Column(db.String(40), unique=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    designation = db.Column(db.String(120), nullable=False)
    ctc_lpa = db.Column(db.Float, nullable=False)
    base_lpa = db.Column(db.Float, default=0)
    joining_date = db.Column(db.Date)
    location = db.Column(db.String(120), default="")
    offer_accepted = db.Column(db.Boolean, default=False)
    verified = db.Column(db.Boolean, default=False)
    signed_date = db.Column(db.Date)
    is_sample = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    student = db.relationship("Student", lazy="joined")
    company = db.relationship("Company", lazy="joined")


class Notification(db.Model, Serial):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    message = db.Column(db.Text, default="")
    type = db.Column(db.String(20), default="system")
    read = db.Column(db.Boolean, default=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, default=utcnow)


class Document(db.Model, Serial):
    __tablename__ = "documents"
    hidden = {"stored_name"}
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    doc_type = db.Column(db.String(30), default="Other")
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"))
    stored_name = db.Column(db.String(80), nullable=False)
    original_name = db.Column(db.String(190), default="")
    mime = db.Column(db.String(80), default="")
    size_bytes = db.Column(db.Integer, default=0)
    verified = db.Column(db.Boolean, default=False)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, default=utcnow)
    student = db.relationship("Student", foreign_keys=[student_id], lazy="joined")
