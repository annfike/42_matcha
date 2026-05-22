import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-production"
    DATABASE_URL = os.environ.get("DATABASE_URL") or "sqlite:///matcha.db"
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER") or os.path.join(os.path.dirname(__file__), "uploads")
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 5242880))

    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_USERNAME")

    # Demo / evaluation mode: do not require real SMTP.
    # If true, registration will show a verification link instead of sending email.
    # SHOW_VERIFICATION_LINK = os.environ.get("SHOW_VERIFICATION_LINK", "false").lower() == "true"

    VERIFICATION_TOKEN_EXPIRY_HOURS = 24
    RESET_TOKEN_EXPIRY_HOURS = 1

    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
    GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID")
    GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET")
    INTRA42_CLIENT_ID = os.environ.get("INTRA42_CLIENT_ID")
    INTRA42_CLIENT_SECRET = os.environ.get("INTRA42_CLIENT_SECRET")
