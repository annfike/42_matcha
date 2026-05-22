import os
from flask import Flask
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_mail import Mail
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect
from flask_caching import Cache
from dotenv import load_dotenv
from werkzeug.exceptions import RequestEntityTooLarge

load_dotenv()

bcrypt = Bcrypt()
login_manager = LoginManager()
mail = Mail()
socketio = SocketIO()
csrf = CSRFProtect()
cache = Cache()


def create_app(config_class=None):
    app = Flask(__name__)
    if config_class is None:
        app.config.from_object("app.config.Config")
    else:
        app.config.from_object(config_class)

    from app.database import init_db
    init_db(app)

    bcrypt.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    mail.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")
    csrf.init_app(app)
    cache.init_app(app, config={
        "CACHE_TYPE": app.config.get("CACHE_TYPE", "SimpleCache"),
        "CACHE_DEFAULT_TIMEOUT": app.config.get("CACHE_DEFAULT_TIMEOUT", 300),
    })

    from app import models as _models  # noqa: F401

    from app.utils.logger import setup_logger
    if not app.config.get("TESTING"):
        setup_logger(app)

    upload_folder = app.config.get("UPLOAD_FOLDER", "./app/uploads")
    if not os.path.isabs(upload_folder):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        upload_folder = os.path.abspath(os.path.join(project_root, upload_folder))
    app.config["UPLOAD_FOLDER"] = upload_folder
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    from app.routes.auth import auth_bp
    from app.routes.profile import profile_bp
    from app.routes.browse import browse_bp
    from app.routes.chat import chat_bp
    from app.routes.notifications import notifications_bp
    from app.routes.map import map_bp
    from app.routes.oauth import oauth_bp, init_oauth
    from app.routes.events import events_bp
    from app.routes.videochat import videochat_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(profile_bp, url_prefix="/profile")
    app.register_blueprint(browse_bp, url_prefix="/browse")
    app.register_blueprint(chat_bp, url_prefix="/chat")
    app.register_blueprint(notifications_bp, url_prefix="/notifications")
    app.register_blueprint(map_bp, url_prefix="/map")
    app.register_blueprint(oauth_bp, url_prefix="/oauth")
    app.register_blueprint(events_bp, url_prefix="/events")
    app.register_blueprint(videochat_bp, url_prefix="/videochat")

    if (
        app.config.get("GOOGLE_CLIENT_ID")
        or app.config.get("GITHUB_CLIENT_ID")
        or app.config.get("INTRA42_CLIENT_ID")
    ):
        init_oauth(app)

    from app.utils.tags import tags_display_form_value

    @app.template_filter("tags_form_value")
    def _tags_form_value_filter(tags):
        return tags_display_form_value(tags)

    @app.before_request
    def check_profile_complete():
        from flask_login import current_user
        from flask import request, redirect, url_for, flash
        from app.utils.profile_completion import get_profile_completion_status

        if not current_user.is_authenticated:
            return
        allowed_prefixes = (
            "/auth/", "/profile/", "/oauth/", "/static/", "/uploads/",
            "/notifications/count", "/chat/unread-count", "/socket.io/",
        )
        if any(request.path.startswith(p) for p in allowed_prefixes):
            return
        if request.path == "/":
            return
        status = get_profile_completion_status(current_user.id)
        if not status["ok"]:
            need = ", ".join(status["missing"])
            flash(
                "Complete your profile before using this part of the site. "
                f"Still needed: {need}.",
                "error",
            )
            return redirect(url_for("profile.edit"))

    @app.route("/")
    def index():
        from flask import redirect, url_for
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for("browse.suggestions"))
        return redirect(url_for("auth.login"))

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        from flask import send_from_directory
        return send_from_directory(app.config.get("UPLOAD_FOLDER", "./app/uploads"), filename)

    @app.errorhandler(RequestEntityTooLarge)
    def handle_file_too_large(e):
        # When MAX_CONTENT_LENGTH is exceeded, Flask rejects the request before our route runs.
        # Redirect back with a clear message instead of showing a generic 413 page.
        from flask import flash, redirect, url_for
        limit = app.config.get("MAX_CONTENT_LENGTH")
        if isinstance(limit, int) and limit > 0:
            mb = limit / (1024 * 1024)
            flash(f"File too large. Maximum upload size is {mb:.1f}MB.", "error")
        else:
            flash("File too large.", "error")
        return redirect(url_for("profile.edit"))

    import click

    @app.cli.command("init-db")
    def init_db_command():
        from app.database import get_db, commit, apply_schema

        apply_schema(get_db())
        commit()
        click.echo("Database tables created.")

    return app
