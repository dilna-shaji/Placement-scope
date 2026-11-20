import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
load_dotenv()


class Config:
    APP_ENV = os.getenv("APP_ENV", "development")
    SECRET_KEY = os.getenv("SECRET_KEY", "")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "")
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
    CAPTCHA_PROVIDER = os.getenv("CAPTCHA_PROVIDER", "local")
    TURNSTILE_SITE_KEY = os.getenv("TURNSTILE_SITE_KEY", "")
    TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY", "")
    SESSION_COOKIE_SECURE_FLAG = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    SESSION_IDLE_MINUTES = int(os.getenv("SESSION_IDLE_MINUTES", "30"))
    REMEMBER_ME_DAYS = int(os.getenv("REMEMBER_ME_DAYS", "14"))
    MAIL_MODE = os.getenv("MAIL_MODE", "console")
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    MAIL_FROM = os.getenv("MAIL_FROM", "placementhub@example.edu")
    PUBLIC_APP_URL = os.getenv("PUBLIC_APP_URL", "http://localhost:3000")
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
    if not os.path.isabs(UPLOAD_DIR):  # same folder no matter where the server / flask CLI is started from
        UPLOAD_DIR = str(Path(__file__).resolve().parent.parent / UPLOAD_DIR)
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "5"))
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024


class TestConfig(Config):
    APP_ENV = "testing"
    TESTING = True
    SECRET_KEY = "test-secret-key-not-for-production-0123456789"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    CAPTCHA_PROVIDER = "local"
    MAIL_MODE = "console"
    SMTP_HOST = ""
    SMTP_USER = ""
    SMTP_PASSWORD = ""
    UPLOAD_DIR = "/tmp/placementhub_test_uploads"
