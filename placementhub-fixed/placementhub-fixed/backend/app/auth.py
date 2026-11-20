"""Authentication: sessions, decorators, /api/auth/* endpoints."""
import functools
from datetime import timedelta

from flask import Blueprint, current_app, g, jsonify, make_response, request

from .extensions import db
from .models import AccountRequest, Department, LoginSession, PasswordReset, User, utcnow
from .permissions import (ALL_PERMISSIONS, LOGIN_PORTAL_ROLES, ROLE_LABELS, SELF_REGISTERABLE)
from .security import (CaptchaError, captcha_public_config, client_ip, create_local_challenge, hash_password,
                       new_token, password_problems, recent_failures, record_attempt, send_mail, sha256,
                       verify_captcha, verify_password)
from .services import audit, get_setting

bp = Blueprint("auth", __name__, url_prefix="/api/auth")
COOKIE = "ph_session"
CSRF_COOKIE = "ph_csrf"
SAFE = {"GET", "HEAD", "OPTIONS"}


def err(msg, status=400, **extra):
    return jsonify({"error": msg, **extra}), status


# ------------------------------------------------------------ permission lookup
def user_permissions(user) -> set:
    if not user or not user.role:
        return set()
    return {p.code for p in user.role.permissions}


def can(user, perm: str) -> bool:
    return perm in user_permissions(user)


# ------------------------------------------------------------ session handling
def _idle_delta() -> timedelta:
    """Idle timeout from the settings table, falling back to the env default. Never raises on bad data."""
    for raw in (get_setting("session_idle_minutes"), current_app.config.get("SESSION_IDLE_MINUTES")):
        try:
            minutes = float(raw)
        except (TypeError, ValueError):
            continue
        if minutes > 0:
            return timedelta(minutes=minutes)
    return timedelta(minutes=30)


def load_session():
    """Resolve the cookie to a live session. Idle + absolute expiry are enforced on every request."""
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    s = LoginSession.query.filter_by(token_hash=sha256(token)).first()
    if not s or s.revoked:
        return None
    now = utcnow()
    if s.expires_at < now or (s.last_seen_at or s.created_at or now) + _idle_delta() < now:
        s.revoked = True
        db.session.commit()
        return None
    u = s.user
    if not u or u.status != "active" or not u.role:
        return None
    # Reject and revoke any pre-existing session for the retired Student portal.
    if u.role_name not in LOGIN_PORTAL_ROLES:
        s.revoked = True
        db.session.commit()
        return None
    if not s.last_seen_at or (now - s.last_seen_at).total_seconds() > 30:
        s.last_seen_at = now
        db.session.commit()
    return s


def authenticate():
    s = load_session()
    if not s:
        return None
    g.session, g.user = s, s.user
    return s


def _csrf_ok(s) -> bool:
    import hmac
    sent = request.headers.get("X-CSRF-Token", "")
    return bool(sent) and hmac.compare_digest(sent, s.csrf_token)


def require_auth(perm: str | None = None, allow_pending_password=False):
    """Backend authentication + permission check. Every non-public endpoint uses this."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            s = authenticate()
            if not s:
                return err("Authentication required.", 401, code="unauthenticated")
            if request.method not in SAFE and not _csrf_ok(s):
                return err("CSRF validation failed.", 403, code="csrf")
            if g.user.must_change_password and not allow_pending_password:
                return err("You must change your temporary password first.", 403, code="password_change_required")
            if perm and not can(g.user, perm):
                audit("Permission denied", "endpoint", request.path, f"missing {perm}", "Failed")
                return err("You do not have permission to perform this action.", 403, code="forbidden")
            return fn(*a, **kw)
        return wrapper
    return deco


def user_payload(u: User) -> dict:
    d = u.public()
    d["permissions"] = sorted(user_permissions(u))
    return d


def _cookie_secure() -> bool:
    """`Secure` cookies are silently dropped by browsers on plain http://, which makes a correct login look like an
    instantly-expired session. Only mark the cookie Secure when the request really arrived over HTTPS (directly or
    through a TLS-terminating proxy that sets X-Forwarded-Proto)."""
    if not current_app.config["SESSION_COOKIE_SECURE_FLAG"]:
        return False
    proto = (request.headers.get("X-Forwarded-Proto") or "").split(",")[0].strip().lower()
    return request.is_secure or proto == "https"


def _set_cookies(resp, token, csrf, remember):
    cfg = current_app.config
    max_age = cfg["REMEMBER_ME_DAYS"] * 86400 if remember else None
    secure = _cookie_secure()
    resp.set_cookie(COOKIE, token, httponly=True, samesite="Lax", secure=secure, max_age=max_age, path="/")
    resp.set_cookie(CSRF_COOKIE, csrf, httponly=False, samesite="Lax", secure=secure, max_age=max_age, path="/")
    return resp


def _clear_cookies(resp):
    resp.delete_cookie(COOKIE, path="/")
    resp.delete_cookie(CSRF_COOKIE, path="/")
    return resp


# ------------------------------------------------------------ endpoints
@bp.get("/config")
def config():
    return jsonify({"captcha": captcha_public_config(),
                    "selfRegisterRoles": [{"value": r, "label": ROLE_LABELS[r]} for r in SELF_REGISTERABLE],
                    "portalRoles": [{"value": r, "label": ROLE_LABELS[r]} for r in LOGIN_PORTAL_ROLES],
                    "departments": [d.to_dict() for d in Department.query.order_by(Department.name)]})


@bp.get("/captcha")
def captcha():
    if current_app.config["CAPTCHA_PROVIDER"] != "local" or current_app.config["APP_ENV"] == "production":
        return err("Local CAPTCHA is not enabled.", 404)
    return jsonify(create_local_challenge())


@bp.post("/login")
def login():
    d = request.get_json(silent=True) or {}
    ident = str(d.get("identifier", "")).strip().lower()[:190]
    password = str(d.get("password", ""))
    portal = str(d.get("portalRole", ""))
    ip = client_ip()

    if recent_failures("login", 15, ip=ip) >= 20:
        return err("Too many failed attempts from this network. Try again later.", 429)
    try:
        verify_captcha(d.get("captcha"))
    except CaptchaError as e:
        record_attempt("login", ident, False, "captcha")
        return err(str(e), 400, code="captcha")
    if not ident or not password or portal not in LOGIN_PORTAL_ROLES:
        return err("Enter your login ID, password and portal role.", 400)

    user = User.query.filter((db.func.lower(User.email) == ident) | (db.func.lower(User.employee_id) == ident)).first()
    now = utcnow()
    generic = "Invalid credentials."

    if user and user.locked_until and user.locked_until > now:
        mins = int((user.locked_until - now).total_seconds() // 60) + 1
        record_attempt("login", ident, False, "locked")
        return err(f"Account temporarily locked. Try again in about {mins} minute(s).", 423, code="locked")

    ok = verify_password(user.password_hash if user else None, password)
    if not user or not ok:
        if user:
            user.failed_attempts += 1
            if user.failed_attempts >= int(get_setting("max_failed_logins") or 5):
                user.lock_count += 1
                delay = int(get_setting("lockout_minutes") or 15) * (2 ** min(user.lock_count - 1, 6))  # progressive
                user.locked_until = now + timedelta(minutes=delay)
                user.failed_attempts = 0
                audit("Account locked", "user", user.id, f"{delay} min after repeated failures", "Warning", actor=user)
            db.session.commit()
        record_attempt("login", ident, False, "bad_credentials")
        return err(generic, 401)

    # Password correct. Now enforce account state and role. The portal role is only an *intent* check.
    if user.status != "active":
        record_attempt("login", ident, False, "disabled")
        audit("Login refused (inactive)", "user", user.id, "", "Failed", actor=user)
        return err("This account is disabled or not approved. Contact the administrator.", 403, code="inactive")
    if not user.role or user.role_name != portal:
        record_attempt("login", ident, False, "role_mismatch")
        audit("Login refused (role mismatch)", "user", user.id, f"selected portal={portal}", "Failed", actor=user)
        return err("This account is not authorised for the selected portal role.", 403, code="role_mismatch")

    user.failed_attempts = 0
    user.lock_count = 0
    user.locked_until = None
    user.last_login_at = now
    remember = bool(d.get("remember"))
    token, csrf = new_token(), new_token()
    absolute = timedelta(days=current_app.config["REMEMBER_ME_DAYS"]) if remember else timedelta(hours=12)
    db.session.add(LoginSession(token_hash=sha256(token), csrf_token=csrf, user_id=user.id, remember=remember,
                                expires_at=now + absolute, ip_address=ip,
                                user_agent=(request.headers.get("User-Agent") or "")[:255]))
    db.session.commit()
    record_attempt("login", ident, True)
    audit("Login", "user", user.id, f"portal={portal}", actor=user)
    return _set_cookies(make_response(jsonify({"user": user_payload(user)})), token, csrf, remember)


@bp.get("/me")
def me():
    s = authenticate()
    if not s:
        return err("Not authenticated.", 401, code="unauthenticated")
    return jsonify({"user": user_payload(g.user)})


@bp.post("/logout")
def logout():
    s = authenticate()
    if s:
        if not _csrf_ok(s):
            return err("CSRF validation failed.", 403, code="csrf")
        s.revoked = True
        db.session.commit()
        audit("Logout", "user", g.user.id)
    return _clear_cookies(make_response(jsonify({"ok": True})))


@bp.post("/change-password")
@require_auth(allow_pending_password=True)
def change_password():
    d = request.get_json(silent=True) or {}
    cur, new = str(d.get("currentPassword", "")), str(d.get("newPassword", ""))
    u = g.user
    if not verify_password(u.password_hash, cur):
        return err("Current password is incorrect.", 400)
    if cur == new:
        return err("New password must differ from the current password.", 400)
    prob = password_problems(new, int(get_setting("password_min_length") or 10))
    if prob:
        return err(prob, 400)
    u.password_hash = hash_password(new)
    u.must_change_password = False
    u.password_changed_at = utcnow()
    # revoke every other session of this user
    LoginSession.query.filter(LoginSession.user_id == u.id, LoginSession.id != g.session.id).update({"revoked": True})
    db.session.commit()
    audit("Password changed", "user", u.id)
    return jsonify({"user": user_payload(u)})


@bp.post("/forgot")
def forgot():
    d = request.get_json(silent=True) or {}
    email = str(d.get("email", "")).strip().lower()[:190]
    if recent_failures("forgot", 60, ip=client_ip()) + 0 >= 10:
        return err("Too many requests. Try again later.", 429)
    try:
        verify_captcha(d.get("captcha"))
    except CaptchaError as e:
        return err(str(e), 400, code="captcha")
    record_attempt("forgot", email, False, "requested")  # counted for throttling
    user = User.query.filter(db.func.lower(User.email) == email).first()
    if user and user.status == "active":
        token = new_token()
        db.session.add(PasswordReset(user_id=user.id, token_hash=sha256(token), kind="forgot",
                                     expires_at=utcnow() + timedelta(minutes=30)))
        db.session.commit()
        link = f"{current_app.config['PUBLIC_APP_URL']}/?reset_token={token}"
        send_mail(user.email, "PlacementHub password reset",
                  f"Use this link within 30 minutes to reset your password:\n{link}\n\nIf you did not ask for this, ignore this e-mail.")
        audit("Password reset requested", "user", user.id, actor=user)
    # identical response whether or not the account exists (no account enumeration)
    return jsonify({"message": "If that e-mail belongs to an active account, a reset link has been sent."})


@bp.post("/reset")
def reset():
    d = request.get_json(silent=True) or {}
    token, new = str(d.get("token", "")), str(d.get("newPassword", ""))
    pr = PasswordReset.query.filter_by(token_hash=sha256(token)).first() if token else None
    if not pr or pr.used_at or pr.expires_at < utcnow():
        return err("This reset link is invalid or has expired.", 400)
    prob = password_problems(new, int(get_setting("password_min_length") or 10))
    if prob:
        return err(prob, 400)
    u = db.session.get(User, pr.user_id)
    u.password_hash = hash_password(new)
    u.must_change_password = False
    u.password_changed_at = utcnow()
    u.failed_attempts, u.locked_until, u.lock_count = 0, None, 0
    pr.used_at = utcnow()
    LoginSession.query.filter_by(user_id=u.id).update({"revoked": True})
    db.session.commit()
    audit("Password reset completed", "user", u.id, actor=u)
    return jsonify({"message": "Password updated. You can now sign in."})


@bp.post("/request-account")
def request_account():
    d = request.get_json(silent=True) or {}
    if recent_failures("request", 60, ip=client_ip()) >= 5:
        return err("Too many requests from this network. Try again later.", 429)
    try:
        verify_captcha(d.get("captcha"))
    except CaptchaError as e:
        return err(str(e), 400, code="captcha")
    role = str(d.get("requestedRole", ""))
    if role not in SELF_REGISTERABLE:
        return err("This role cannot be requested through self-service. Ask an administrator to create the account.", 400)
    name, email = str(d.get("fullName", "")).strip(), str(d.get("email", "")).strip().lower()
    if len(name) < 3 or "@" not in email or "." not in email.split("@")[-1]:
        return err("Enter your full name and a valid e-mail address.", 400)
    reason = str(d.get("reason", "")).strip()
    if len(reason) < 10:
        return err("Please explain why you need access (at least 10 characters).", 400)
    if User.query.filter(db.func.lower(User.email) == email).first() or \
            AccountRequest.query.filter(db.func.lower(AccountRequest.email) == email,
                                        AccountRequest.status == "Pending Approval").first():
        record_attempt("request", email, False, "duplicate")
        return err("An account or pending request already exists for this e-mail.", 409)
    dept = db.session.get(Department, int(d["departmentId"])) if str(d.get("departmentId", "")).isdigit() else None
    if role in (SELF_REGISTERABLE[0], SELF_REGISTERABLE[2]) and not dept:
        return err("Select your department.", 400)
    if role == "corporate_recruiter" and not (str(d.get("companyName", "")).strip() and str(d.get("companyEmail", "")).strip()):
        return err("Company name and official company e-mail are required for recruiters.", 400)
    if role == "student_coordinator" and not (str(d.get("studentIdNo", "")).strip() and str(d.get("facultySupervisor", "")).strip()):
        return err("Student ID and faculty supervisor are required for student coordinators.", 400)
    r = AccountRequest(
        full_name=name[:120], email=email, employee_id=(str(d.get("employeeId", "")).strip() or None),
        department_id=dept.id if dept else None, designation=str(d.get("designation", ""))[:120],
        requested_role=role, phone=str(d.get("phone", ""))[:30], reason=reason[:2000],
        company_name=str(d.get("companyName", ""))[:160] or None, company_email=str(d.get("companyEmail", ""))[:190] or None,
        company_phone=str(d.get("companyPhone", ""))[:30] or None, student_id_no=str(d.get("studentIdNo", ""))[:60] or None,
        academic_year=str(d.get("academicYear", ""))[:20] or None,
        faculty_supervisor=str(d.get("facultySupervisor", ""))[:120] or None,
        status="Pending Approval", ip_address=client_ip())
    db.session.add(r)
    db.session.commit()
    record_attempt("request", email, False, "submitted")
    audit("Account requested", "account_request", r.id, f"requested={role}", actor=None)
    return jsonify({"message": "Request submitted. An administrator will review it; you will be contacted once it is approved."}), 201
