"""Password hashing, tokens, CAPTCHA adapters, rate limiting, e-mail."""
import hashlib
import hmac
import random
import re
import secrets
import smtplib
import string
from datetime import timedelta
from email.message import EmailMessage

import requests
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from flask import current_app, request

from .extensions import db
from .models import CaptchaChallenge, LoginAttempt, utcnow

_ph = PasswordHasher()  # Argon2id by default
_DUMMY_HASH = _ph.hash("dummy-password-for-timing-equalisation")


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(hash_: str | None, pw: str) -> bool:
    try:
        return _ph.verify(hash_ or _DUMMY_HASH, pw) and bool(hash_)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def generate_temp_password() -> str:
    alphabet = string.ascii_letters.replace("l", "").replace("I", "").replace("O", "") + "23456789"
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(12)) + secrets.choice("!@#$%&*?") + secrets.choice("23456789")
        if password_problems(pw) is None:
            return pw


def password_problems(pw: str, min_len: int = 10) -> str | None:
    if len(pw) < min_len:
        return f"Password must be at least {min_len} characters."
    if not re.search(r"[a-z]", pw) or not re.search(r"[A-Z]", pw):
        return "Password must contain upper and lower case letters."
    if not re.search(r"\d", pw):
        return "Password must contain a number."
    if not re.search(r"[^A-Za-z0-9]", pw):
        return "Password must contain a symbol."
    return None


def client_ip() -> str:
    return (request.remote_addr or "unknown")[:64]


# ------------------------------------------------------------ rate limiting
def recent_failures(kind: str, minutes: int, ip: str | None = None, identifier: str | None = None) -> int:
    q = LoginAttempt.query.filter(LoginAttempt.kind == kind, LoginAttempt.success.is_(False),
                                  LoginAttempt.created_at > utcnow() - timedelta(minutes=minutes))
    if ip:
        q = q.filter(LoginAttempt.ip_address == ip)
    if identifier:
        q = q.filter(LoginAttempt.identifier == identifier)
    return q.count()


def record_attempt(kind: str, identifier: str, success: bool, reason: str = ""):
    db.session.add(LoginAttempt(kind=kind, identifier=(identifier or "")[:190], ip_address=client_ip(),
                                success=success, reason=reason[:80]))
    db.session.commit()


# ------------------------------------------------------------ CAPTCHA
class CaptchaError(Exception):
    pass


def captcha_provider() -> str:
    return current_app.config["CAPTCHA_PROVIDER"]


def captcha_public_config() -> dict:
    p = captcha_provider()
    return {"provider": p, "siteKey": current_app.config["TURNSTILE_SITE_KEY"] if p == "turnstile" else None}


def create_local_challenge() -> dict:
    """Local development adapter: server-side one-time challenge rendered as a distorted SVG."""
    rnd = random.SystemRandom()
    text = "".join(rnd.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(5))
    cid = secrets.token_hex(16)
    db.session.add(CaptchaChallenge(id=cid, answer_hash=sha256(text.lower() + cid),
                                    expires_at=utcnow() + timedelta(minutes=15)))
    db.session.commit()
    CaptchaChallenge.query.filter(CaptchaChallenge.expires_at < utcnow() - timedelta(hours=1)).delete()
    db.session.commit()
    glyphs = ""
    for i, ch in enumerate(text):
        x = 18 + i * 26
        y = 34 + rnd.randint(-4, 4)
        rot = rnd.randint(-22, 22)
        glyphs += (f'<text x="{x}" y="{y}" font-size="{rnd.randint(26, 32)}" font-family="monospace" '
                   f'font-weight="700" fill="#{rnd.choice(["17182F", "5146D8", "20756f", "b3402b"])}" '
                   f'transform="rotate({rot} {x} {y})">{ch}</text>')
    lines = "".join(
        f'<line x1="{rnd.randint(0, 30)}" y1="{rnd.randint(0, 50)}" x2="{rnd.randint(120, 160)}" '
        f'y2="{rnd.randint(0, 50)}" stroke="#8768F7" stroke-opacity="0.45" stroke-width="1.4"/>' for _ in range(5))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 50" width="160" height="50">'
           f'<rect width="160" height="50" fill="#F6F5FB"/>{lines}{glyphs}</svg>')
    return {"id": cid, "svg": svg}


def verify_captcha(payload: dict | None) -> None:
    """Raises CaptchaError. Always called server-side before any credential check."""
    provider = captcha_provider()
    payload = payload or {}
    if provider == "turnstile":
        secret = current_app.config["TURNSTILE_SECRET_KEY"]
        token = payload.get("token")
        if not secret or not token:
            raise CaptchaError("CAPTCHA verification is required.")
        try:
            r = requests.post("https://challenges.cloudflare.com/turnstile/v0/siteverify",
                              data={"secret": secret, "response": token, "remoteip": client_ip()}, timeout=8)
            ok = r.json().get("success") is True
        except Exception:
            raise CaptchaError("CAPTCHA service unavailable. Try again.")
        if not ok:
            raise CaptchaError("CAPTCHA verification failed.")
        return
    if provider == "local":
        if current_app.config["APP_ENV"] == "production":
            raise CaptchaError("Local CAPTCHA adapter is disabled in production.")
        cid = str(payload.get("id", "")).strip()
        answer = "".join(str(payload.get("answer", "")).split()).lower()  # tolerate stray spaces / case
        if not answer:
            raise CaptchaError("Enter the characters shown in the security check.")
        ch = db.session.get(CaptchaChallenge, cid) if cid else None
        if not ch or ch.used or ch.expires_at < utcnow():
            raise CaptchaError("The security check timed out. A new one has been loaded — please enter it and try again.")
        ch.used = True  # single use, whether right or wrong
        db.session.commit()
        if not hmac.compare_digest(ch.answer_hash, sha256(answer + cid)):
            raise CaptchaError("CAPTCHA answer is incorrect.")
        return
    raise CaptchaError("CAPTCHA provider is not configured.")


# ------------------------------------------------------------ mail
def send_mail(to: str, subject: str, body: str):
    cfg = current_app.config
    if cfg["MAIL_MODE"] == "smtp" and cfg["SMTP_HOST"]:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = cfg["MAIL_FROM"], to, subject
        msg.set_content(body)
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=15) as s:
            s.starttls()
            if cfg["SMTP_USER"]:
                s.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
            s.send_message(msg)
    else:
        current_app.logger.warning("MAIL (console mode) to=%s subject=%s\n%s", to, subject, body)
