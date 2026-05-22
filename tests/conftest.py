import os
import pytest
from dotenv import load_dotenv

load_dotenv()

from app import create_app, bcrypt
from app.database import get_db, commit, execute, execute_returning, rollback, query_one, reset_schema


def _test_db_url():
    base = os.environ.get("DATABASE_URL", "sqlite:///matcha.db")
    if base.endswith("matcha.db"):
        return base.replace("matcha.db", "matcha_test.db")
    if base.endswith(".db"):
        return base.rsplit(".", 1)[0] + "_test.db"
    return "sqlite:///matcha_test.db"


class TestConfig:
    TESTING = True
    DATABASE_URL = _test_db_url()
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SECRET_KEY = "test-secret-key"
    WTF_CSRF_ENABLED = False
    UPLOAD_FOLDER = "/tmp/test_uploads"
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024


@pytest.fixture
def app():
    application = create_app(TestConfig)
    with application.app_context():
        reset_schema(get_db())
        commit()
        yield application
        try:
            rollback()
        except Exception:
            pass
        reset_schema(get_db())
        commit()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def user(app):
    with app.app_context():
        password_hash = bcrypt.generate_password_hash("Test1234!").decode("utf-8")
        row = execute_returning(
            "INSERT INTO users (username, email, password_hash, first_name, last_name, birth_date, "
            "latitude, longitude, location_enabled, "
            "email_verified, gender, sexual_preference, biography) "
            "VALUES (%s, %s, %s, %s, %s, '1995-06-15', 46.2044, 6.1432, 1, "
            "1, 'male', 'heterosexual', 'Test biography') RETURNING id",
            ("testuser", "test@example.com", password_hash, "Test", "User"),
        )
        img = execute_returning(
            "INSERT INTO user_images (user_id, filename, is_profile_picture) VALUES (%s, %s, 1) RETURNING id",
            (row["id"], "test.jpg"),
        )
        execute(
            "UPDATE users SET profile_picture_id = %s WHERE id = %s",
            (img["id"], row["id"]),
        )
        tag = query_one("SELECT id FROM tags WHERE name = %s", ("music",))
        if not tag:
            tag = execute_returning("INSERT INTO tags (name) VALUES (%s) RETURNING id", ("music",))
        execute(
            "INSERT INTO user_tags (user_id, tag_id) VALUES (%s, %s)",
            (row["id"], tag["id"]),
        )
        commit()
        return row["id"]


@pytest.fixture
def user2(app):
    with app.app_context():
        password_hash = bcrypt.generate_password_hash("Test1234!").decode("utf-8")
        row = execute_returning(
            "INSERT INTO users (username, email, password_hash, first_name, last_name, birth_date, "
            "latitude, longitude, location_enabled, "
            "email_verified, gender, sexual_preference, biography) "
            "VALUES (%s, %s, %s, %s, %s, '1993-08-20', 46.5197, 6.6323, 1, "
            "1, 'female', 'bisexual', 'Test2 biography') RETURNING id",
            ("testuser2", "test2@example.com", password_hash, "Test2", "User2"),
        )
        img = execute_returning(
            "INSERT INTO user_images (user_id, filename, is_profile_picture) VALUES (%s, %s, 1) RETURNING id",
            (row["id"], "test2.jpg"),
        )
        execute(
            "UPDATE users SET profile_picture_id = %s WHERE id = %s",
            (img["id"], row["id"]),
        )
        tag = query_one("SELECT id FROM tags WHERE name = %s", ("travel",))
        if not tag:
            tag = execute_returning("INSERT INTO tags (name) VALUES (%s) RETURNING id", ("travel",))
        execute(
            "INSERT INTO user_tags (user_id, tag_id) VALUES (%s, %s)",
            (row["id"], tag["id"]),
        )
        commit()
        return row["id"]


@pytest.fixture
def logged_in_client(client, user, app):
    with app.app_context():
        client.post("/auth/login", data={
            "username": "testuser",
            "password": "Test1234!"
        })
    return client
