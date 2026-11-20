"""Accounts, account requests, roles, security console, settings, audit, notifications."""
import re
from datetime import timedelta

from flask import Blueprint, g, jsonify, request
from sqlalchemy import or_

from .auth import require_auth
from .errors import ApiError
from .extensions import db
from .models import (AccountRequest, AuditLog, Company, Department, LoginAttempt, LoginSession, Notification,
                     PasswordReset, Permission, Role, SystemSetting, User, UserRole, utcnow)
from .permissions import (ALL_PERMISSIONS, LOCKED_FOR_SUPER_ADMIN, RECRUITER, ROLE_LABELS, ROLES, SUPER_ADMIN,
                          SUPER_ADMIN_ONLY, TPO, COORDINATOR)
from .security import MailDeliveryError, generate_temp_password, hash_password, send_mail
from .services import DEFAULT_SETTINGS, all_settings, audit

bp = Blueprint("admin", __name__, url_prefix="/api")


def _credentials(user, temp):
    return {"loginId": user.email, "temporaryPassword": temp, "role": user.role_name,
            "roleLabel": user.role.label if user.role else "", "department": user.department.name if user.department else None,
            "company": user.company.name if user.company else None, "status": user.status,
            "fullName": user.full_name, "mustChangePassword": True}


def _active_super_admins(exclude_id=None):
    return [u for u in User.query.filter_by(status="active").all()
            if u.role_name == SUPER_ADMIN and u.id != exclude_id]


def _validate_scope(role, dept_id, company_id):
    """Role/scope consistency. Returns (department, company)."""
    if role not in ROLES:
        raise ApiError("Unknown role.", 422, {"role": "Unknown role"})
    dept = db.session.get(Department, int(dept_id)) if dept_id else None
    comp = db.session.get(Company, int(company_id)) if company_id else None
    if role in (TPO, COORDINATOR) and not dept:
        raise ApiError("This role requires a department scope.", 422, {"departmentId": "Required for this role"})
    if role == RECRUITER and not comp:
        raise ApiError("Corporate recruiters must be linked to a company.", 422, {"companyId": "Required for this role"})
    return dept, comp


def _create_user(full_name, email, role, dept, comp, employee_id, designation, phone):
    email = email.strip().lower()
    if User.query.filter(db.func.lower(User.email) == email).first():
        raise ApiError("A user with this e-mail already exists.", 409, {"email": "Already exists"})
    if employee_id and User.query.filter(db.func.lower(User.employee_id) == employee_id.lower()).first():
        raise ApiError("Employee ID is already in use.", 409, {"employeeId": "Already in use"})
    temp = generate_temp_password()
    u = User(full_name=full_name.strip()[:120], email=email, employee_id=(employee_id or None), designation=designation[:120],
             phone=phone[:30], password_hash=hash_password(temp), status="active", must_change_password=True,
             department_id=dept.id if dept else None, company_id=comp.id if comp else None, created_by_id=g.user.id)
    u.assignment = UserRole(role=Role.query.filter_by(name=role).one(), assigned_by_id=g.user.id)
    db.session.add(u)
    db.session.commit()
    return u, temp


# ------------------------------------------------------------------ users
@bp.get("/users")
@require_auth("users:manage")
def list_users():
    q = User.query
    s = request.args.get("q", "").strip()
    if s:
        like = f"%{s}%"
        q = q.filter(or_(User.full_name.ilike(like), User.email.ilike(like), User.employee_id.ilike(like)))
    if request.args.get("status"):
        q = q.filter(User.status == request.args["status"])
    if request.args.get("role"):
        q = q.join(UserRole, UserRole.user_id == User.id).join(Role, Role.id == UserRole.role_id).filter(Role.name == request.args["role"])
    try:
        page = max(int(request.args.get("page", 1) or 1), 1)
        size = min(max(int(request.args.get("pageSize", 12) or 12), 1), 100)
    except (TypeError, ValueError):
        raise ApiError("page and pageSize must be whole numbers.", 400)
    total = q.count()
    users = q.order_by(User.full_name).offset((page - 1) * size).limit(size).all()
    return jsonify({"items": [u.public() for u in users], "total": total, "page": page, "pageSize": size})


@bp.post("/users")
@require_auth("users:manage")
def create_user():
    d = request.get_json(silent=True) or {}
    name, email = str(d.get("fullName", "")).strip(), str(d.get("email", "")).strip()
    if len(name) < 3 or "@" not in email:
        raise ApiError("Enter a name and a valid e-mail.", 422, {"fullName": "Required", "email": "Required"})
    role = str(d.get("role", ""))
    dept, comp = _validate_scope(role, d.get("departmentId"), d.get("companyId"))
    u, temp = _create_user(name, email, role, dept, comp, str(d.get("employeeId") or ""), str(d.get("designation") or ""), str(d.get("phone") or ""))
    audit("Created user", "user", u.id, f"{u.email} role={role}")
    return jsonify({"user": u.public(), "credentials": _credentials(u, temp)}), 201


@bp.put("/users/<int:uid>")
@require_auth("users:manage")
def update_user(uid):
    u = db.session.get(User, uid) or (_ for _ in ()).throw(ApiError("User not found.", 404))
    d = request.get_json(silent=True) or {}
    role = str(d.get("role") or u.role_name)
    dept, comp = _validate_scope(role, d.get("departmentId", u.department_id), d.get("companyId", u.company_id))
    if role != u.role_name:
        if u.id == g.user.id:
            raise ApiError("You cannot change your own role.", 403)
        if u.role_name == SUPER_ADMIN and not _active_super_admins(exclude_id=u.id):
            raise ApiError("At least one active Super Admin must remain.", 409)
        old = u.role_name
        u.assignment.role = Role.query.filter_by(name=role).one()
        u.assignment.assigned_by_id = g.user.id
        u.assignment.assigned_at = utcnow()
        LoginSession.query.filter_by(user_id=u.id).update({"revoked": True})  # force re-login with new role
        audit("Changed user role", "user", u.id, f"{u.email}: {old} -> {role}")
    u.department_id, u.company_id = (dept.id if dept else None), (comp.id if comp else None)
    for f, k in (("full_name", "fullName"), ("designation", "designation"), ("phone", "phone")):
        if k in d:
            setattr(u, f, str(d[k])[:120])
    db.session.commit()
    audit("Updated user", "user", u.id, u.email)
    return jsonify({"user": u.public()})


@bp.post("/users/<int:uid>/status")
@require_auth("users:manage")
def set_status(uid):
    u = db.session.get(User, uid) or (_ for _ in ()).throw(ApiError("User not found.", 404))
    status = (request.get_json(silent=True) or {}).get("status")
    if status not in ("active", "disabled"):
        raise ApiError("Status must be active or disabled.", 400)
    if status == "disabled":
        if u.id == g.user.id:
            raise ApiError("You cannot deactivate your own account.", 403)
        if u.role_name == SUPER_ADMIN and not _active_super_admins(exclude_id=u.id):
            raise ApiError("At least one active Super Admin must remain.", 409)
        LoginSession.query.filter_by(user_id=u.id).update({"revoked": True})
    u.status = status
    db.session.commit()
    audit("Activated user" if status == "active" else "Deactivated user", "user", u.id, u.email)
    return jsonify({"user": u.public()})


@bp.post("/users/<int:uid>/reset-credentials")
@require_auth("users:manage")
def reset_credentials(uid):
    u = db.session.get(User, uid) or (_ for _ in ()).throw(ApiError("User not found.", 404))
    temp = generate_temp_password()
    u.password_hash, u.must_change_password = hash_password(temp), True
    u.failed_attempts, u.locked_until, u.lock_count = 0, None, 0
    LoginSession.query.filter_by(user_id=u.id).update({"revoked": True})
    db.session.commit()
    audit("Reset credentials", "user", u.id, u.email)
    return jsonify({"credentials": _credentials(u, temp)})


@bp.post("/users/<int:uid>/unlock")
@require_auth("users:manage")
def unlock(uid):
    u = db.session.get(User, uid) or (_ for _ in ()).throw(ApiError("User not found.", 404))
    u.failed_attempts, u.locked_until, u.lock_count = 0, None, 0
    db.session.commit()
    audit("Unlocked user", "user", u.id, u.email)
    return jsonify({"user": u.public()})


@bp.get("/users/<int:uid>/history")
@require_auth("users:manage")
def user_history(uid):
    rows = AuditLog.query.filter(or_((AuditLog.entity_type == "user") & (AuditLog.entity_id == str(uid)),
                                     AuditLog.actor_id == uid)).order_by(AuditLog.created_at.desc()).limit(100).all()
    return jsonify({"items": [r.to_dict() for r in rows]})


# ------------------------------------------------------------------ account requests
def _req_dict(r):
    d = r.to_dict()
    d["departmentName"] = r.department.name if r.department else None
    d["requestedRoleLabel"] = ROLE_LABELS.get(r.requested_role, r.requested_role)
    return d


@bp.get("/account-requests")
@require_auth("account_requests:manage")
def list_requests():
    q = AccountRequest.query
    if request.args.get("status"):
        q = q.filter_by(status=request.args["status"])
    search = request.args.get("q", "").strip()
    if search:
        like = f"%{search}%"
        q = q.filter(or_(AccountRequest.full_name.ilike(like), AccountRequest.email.ilike(like),
                         AccountRequest.company_name.ilike(like)))
    try:
        page = max(int(request.args.get("page", 1) or 1), 1)
        size = min(max(int(request.args.get("pageSize", 12) or 12), 1), 100)
    except (TypeError, ValueError):
        raise ApiError("page and pageSize must be whole numbers.", 400)
    total = q.count()
    rows = q.order_by(AccountRequest.created_at.desc()).offset((page - 1) * size).limit(size).all()
    return jsonify({"items": [_req_dict(r) for r in rows], "total": total, "page": page, "pageSize": size})


@bp.post("/account-requests/<int:rid>/approve")
@require_auth("account_requests:manage")
def approve_request(rid):
    r = db.session.get(AccountRequest, rid) or (_ for _ in ()).throw(ApiError("Request not found.", 404))
    if r.status != "Pending Approval":
        raise ApiError("This request has already been processed.", 409)
    d = request.get_json(silent=True) or {}
    role = str(d.get("role", ""))  # the administrator's decision is the source of truth, not r.requested_role
    dept_id = d.get("departmentId") or r.department_id
    comp_id = d.get("companyId")
    if role == RECRUITER and not comp_id and d.get("createCompany") and r.company_name:
        comp = Company.query.filter(db.func.lower(Company.name) == r.company_name.lower()).first()
        if not comp:
            comp = Company(name=r.company_name, contact_name=r.full_name, contact_email=r.company_email or r.email,
                           contact_phone=r.company_phone or "", contact_designation=r.designation or "")
            db.session.add(comp)
            db.session.flush()
        comp_id = comp.id
    dept, comp = _validate_scope(role, dept_id, comp_id)
    u, temp = _create_user(r.full_name, r.email, role, dept, comp, r.employee_id or "", r.designation or "", r.phone or "")
    r.status, r.reviewed_by_id, r.reviewed_at = "Approved", g.user.id, utcnow()
    r.review_note, r.created_user_id = str(d.get("note", ""))[:500], u.id
    db.session.commit()
    audit("Approved account request", "account_request", r.id, f"{r.email} requested={r.requested_role} assigned={role}")
    return jsonify({"user": u.public(), "credentials": _credentials(u, temp)})


@bp.post("/account-requests/<int:rid>/reject")
@require_auth("account_requests:manage")
def reject_request(rid):
    r = db.session.get(AccountRequest, rid) or (_ for _ in ()).throw(ApiError("Request not found.", 404))
    if r.status != "Pending Approval":
        raise ApiError("This request has already been processed.", 409)
    r.status, r.reviewed_by_id, r.reviewed_at = "Rejected", g.user.id, utcnow()
    r.review_note = str((request.get_json(silent=True) or {}).get("note", ""))[:500]
    db.session.commit()
    audit("Rejected account request", "account_request", r.id, r.email)
    return jsonify(_req_dict(r))


# ------------------------------------------------------------------ roles & permissions
@bp.get("/roles")
@require_auth("roles:configure")
def list_roles():
    roles = []
    for r in Role.query.all():
        roles.append({"id": r.id, "name": r.name, "label": r.label, "description": r.description,
                      "permissions": sorted(p.code for p in r.permissions),
                      "userCount": UserRole.query.filter_by(role_id=r.id).count()})
    order = {n: i for i, n in enumerate(ROLES)}
    roles.sort(key=lambda x: order.get(x["name"], 99))
    return jsonify({"roles": roles, "catalogue": ALL_PERMISSIONS, "superAdminOnly": sorted(SUPER_ADMIN_ONLY),
                    "lockedForSuperAdmin": sorted(LOCKED_FOR_SUPER_ADMIN)})


@bp.put("/roles/<int:rid>/permissions")
@require_auth("roles:configure")
def set_role_permissions(rid):
    role = db.session.get(Role, rid) or (_ for _ in ()).throw(ApiError("Role not found.", 404))
    wanted = set((request.get_json(silent=True) or {}).get("permissions", []))
    if wanted - set(ALL_PERMISSIONS):
        raise ApiError("Unknown permission in request.", 422)
    if role.name == SUPER_ADMIN:
        if not LOCKED_FOR_SUPER_ADMIN <= wanted:
            raise ApiError("Core Super Admin permissions cannot be removed.", 403)
    elif wanted & SUPER_ADMIN_ONLY:
        raise ApiError("System-level permissions can only belong to the Super Admin role.", 403)
    perms = {p.code: p for p in Permission.query.all()}
    before = {p.code for p in role.permissions}
    role.permissions = [perms[c] for c in wanted]
    db.session.commit()
    audit("Changed role permissions", "role", role.id, f"{role.name}: +{sorted(wanted - before)} -{sorted(before - wanted)}"[:480])
    return jsonify({"ok": True})


# ------------------------------------------------------------------ security console
@bp.get("/security/overview")
@require_auth("security:manage")
def security_overview():
    now = utcnow()
    sessions = LoginSession.query.filter(LoginSession.revoked.is_(False), LoginSession.expires_at > now).order_by(LoginSession.last_seen_at.desc()).limit(100).all()
    idle = timedelta(minutes=int(all_settings()["session_idle_minutes"]))
    sessions = [s for s in sessions if s.last_seen_at + idle > now]
    attempts = LoginAttempt.query.filter(LoginAttempt.kind == "login", LoginAttempt.success.is_(False),
                                         LoginAttempt.created_at > now - timedelta(hours=24)).order_by(LoginAttempt.created_at.desc()).limit(100).all()
    locked = [u.public() for u in User.query.filter(User.locked_until > now).all()]
    resets = PasswordReset.query.order_by(PasswordReset.created_at.desc()).limit(30).all()
    return jsonify({
        "sessions": [{"id": s.id, "userName": s.user.full_name, "role": s.user.role_name, "ip": s.ip_address,
                      "userAgent": s.user_agent, "createdAt": s.created_at.isoformat(), "lastSeenAt": s.last_seen_at.isoformat(),
                      "current": s.id == g.session.id} for s in sessions],
        "failedAttempts": [a.to_dict() for a in attempts],
        "lockedUsers": locked,
        "resets": [{"id": r.id, "userName": db.session.get(User, r.user_id).full_name, "kind": r.kind,
                    "createdAt": r.created_at.isoformat(), "used": bool(r.used_at), "expired": r.expires_at < now} for r in resets],
        "policy": {k: all_settings()[k] for k in ("max_failed_logins", "lockout_minutes", "session_idle_minutes", "password_min_length")},
    })


@bp.post("/security/sessions/<int:sid>/revoke")
@require_auth("security:manage")
def revoke_session(sid):
    s = db.session.get(LoginSession, sid) or (_ for _ in ()).throw(ApiError("Session not found.", 404))
    s.revoked = True
    db.session.commit()
    audit("Revoked session", "session", sid, s.user.email)
    return jsonify({"ok": True})


# ------------------------------------------------------------------ settings
_SETTING_TYPES = {k: type(v) for k, v in DEFAULT_SETTINGS.items()}
_SETTING_RANGES = {"max_failed_logins": (3, 20), "lockout_minutes": (1, 1440), "session_idle_minutes": (5, 480),
                   "password_min_length": (8, 64), "min_cgpa_default": (0, 10), "max_offers_per_student": (1, 10)}


@bp.get("/settings")
@require_auth("settings:manage")
def get_settings():
    return jsonify({"settings": all_settings(), "defaults": DEFAULT_SETTINGS})


@bp.put("/settings")
@require_auth("settings:manage")
def put_settings():
    data = request.get_json(silent=True) or {}
    errs = {}
    for k, v in data.items():
        if k not in DEFAULT_SETTINGS:
            errs[k] = "Unknown setting"
            continue
        t = _SETTING_TYPES[k]
        try:
            v = t(v)
        except (TypeError, ValueError):
            errs[k] = "Invalid value"
            continue
        if k in _SETTING_RANGES and not (_SETTING_RANGES[k][0] <= v <= _SETTING_RANGES[k][1]):
            errs[k] = f"Must be between {_SETTING_RANGES[k][0]} and {_SETTING_RANGES[k][1]}"
            continue
        if t is str:
            v = v.strip()[:200]
        row = db.session.get(SystemSetting, k) or SystemSetting(key=k)
        row.value = v
        db.session.add(row)
    if errs:
        db.session.rollback()
        raise ApiError("Some settings are invalid.", 422, errs)
    db.session.commit()
    audit("Updated settings", "settings", "", ", ".join(sorted(data)))
    return jsonify({"settings": all_settings()})


@bp.post("/mail/test")
@require_auth("settings:manage")
def test_mail():
    email = str((request.get_json(silent=True) or {}).get("email", "")).strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ApiError("Enter a valid test e-mail address.", 422, {"email": "Invalid e-mail"})
    try:
        sent = send_mail(email, "PlacementHub mail configuration test",
                         "This message confirms that the PlacementHub SMTP configuration can deliver e-mail.")
    except MailDeliveryError:
        audit("SMTP configuration test failed", "system_settings", "mail", "Delivery failed", "Warning")
        raise ApiError("Mail delivery failed. Check the protected server logs and SMTP configuration.", 503)
    if not sent:
        raise ApiError("SMTP is not enabled; no test e-mail was sent.", 409)
    audit("SMTP configuration test sent", "system_settings", "mail", "Test message accepted by SMTP")
    return jsonify({"message": "Test message accepted by the configured SMTP server."})


# ------------------------------------------------------------------ audit
@bp.get("/audit")
@require_auth("audit:view")
def audit_list():
    q = AuditLog.query
    s = request.args.get("q", "").strip()
    if s:
        like = f"%{s}%"
        q = q.filter(or_(AuditLog.actor_name.ilike(like), AuditLog.action.ilike(like), AuditLog.details.ilike(like)))
    if request.args.get("status"):
        q = q.filter(AuditLog.status == request.args["status"])
    if request.args.get("entityType"):
        q = q.filter(AuditLog.entity_type == request.args["entityType"])
    total = q.count()
    page, size = max(int(request.args.get("page", 1)), 1), min(int(request.args.get("pageSize", 50)), 500)
    rows = q.order_by(AuditLog.created_at.desc()).offset((page - 1) * size).limit(size).all()
    return jsonify({"items": [r.to_dict() for r in rows], "total": total, "page": page, "pageSize": size})


# ------------------------------------------------------------------ notifications (always limited to own inbox)
@bp.get("/notifications")
@require_auth("notifications:read")
def my_notifications():
    rows = Notification.query.filter_by(user_id=g.user.id).order_by(Notification.created_at.desc()).limit(200).all()
    return jsonify({"items": [n.to_dict() for n in rows], "unread": sum(1 for n in rows if not n.read)})


@bp.post("/notifications/<int:nid>/read")
@require_auth("notifications:read")
def read_notification(nid):
    n = Notification.query.filter_by(id=nid, user_id=g.user.id).first() or (_ for _ in ()).throw(ApiError("Not found.", 404))
    n.read = True
    db.session.commit()
    return jsonify(n.to_dict())


@bp.post("/notifications/read-all")
@require_auth("notifications:read")
def read_all():
    Notification.query.filter_by(user_id=g.user.id, read=False).update({"read": True})
    db.session.commit()
    return jsonify({"ok": True})


@bp.delete("/notifications/<int:nid>")
@require_auth("notifications:read")
def delete_notification(nid):
    n = Notification.query.filter_by(id=nid, user_id=g.user.id).first() or (_ for _ in ()).throw(ApiError("Not found.", 404))
    db.session.delete(n)
    db.session.commit()
    return jsonify({"ok": True})


@bp.post("/notifications")
@require_auth("notifications:send")
def send_notification():
    d = request.get_json(silent=True) or {}
    title, message = str(d.get("title", "")).strip(), str(d.get("message", "")).strip()
    if len(title) < 3:
        raise ApiError("Title is required.", 422, {"title": "Required"})
    audience = str(d.get("audience", ""))  # all | role:<name> | department:<id>
    users = [u for u in User.query.filter_by(status="active").all() if u.id != g.user.id]
    if audience.startswith("role:"):
        users = [u for u in users if u.role_name == audience[5:]]
    elif audience.startswith("department:") and audience[11:].isdigit():
        users = [u for u in users if u.department_id == int(audience[11:])]
    elif audience != "all":
        raise ApiError("Choose an audience.", 422, {"audience": "Required"})
    t = d.get("type") if d.get("type") in ("drive", "approval", "student", "system", "offer") else "system"
    for u in users:
        db.session.add(Notification(user_id=u.id, title=title[:160], message=message[:2000], type=t, sender_id=g.user.id))
    db.session.commit()
    audit("Sent notification", "notification", "", f"{title} -> {audience} ({len(users)} recipients)")
    return jsonify({"recipients": len(users)}), 201
