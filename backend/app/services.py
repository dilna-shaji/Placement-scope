from flask import g, request

from .extensions import db
from .models import AuditLog, SystemSetting
from .security import client_ip

DEFAULT_SETTINGS = {
    "institution_name": "Your Institution",
    "academic_year": "2025-26",
    "max_failed_logins": 5,
    "lockout_minutes": 15,
    "session_idle_minutes": 30,
    "password_min_length": 10,
    "min_cgpa_default": 6.0,
    "max_offers_per_student": 2,
    "placement_policy_note": "",
}


def get_setting(key):
    row = db.session.get(SystemSetting, key)
    return row.value if row is not None else DEFAULT_SETTINGS.get(key)


def all_settings():
    out = dict(DEFAULT_SETTINGS)
    for r in SystemSetting.query.all():
        out[r.key] = r.value
    return out


def audit(action, entity_type="", entity_id="", details="", status="Success", actor=None):
    actor = actor or getattr(g, "user", None)
    db.session.add(AuditLog(
        actor_id=actor.id if actor else None,
        actor_name=actor.full_name if actor else "anonymous",
        actor_role=actor.role_name if actor and actor.role_name else "",
        action=action, entity_type=entity_type, entity_id=str(entity_id or ""),
        ip_address=client_ip() if request else "", status=status, details=(details or "")[:500]))
    db.session.commit()
