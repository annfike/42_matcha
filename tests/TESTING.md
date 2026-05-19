# Testing Documentation

## Overview

The test suite uses **pytest** with Flask’s built-in test client (`app.test_client()`). Tests exercise HTTP routes and SQL against a **real PostgreSQL database** named `matcha_test`, not SQLite.

The app talks to the database through **psycopg2** and `app/database.py` (`query_one`, `execute`, `execute_returning`). There is no SQLAlchemy ORM in this project.

`pytest-flask` is listed in `requirements.txt`; fixtures are defined manually in `tests/conftest.py` via `create_app(TestConfig)`.

**Seed data is separate:** `python scripts/seed_data.py` fills `matcha_db` for manual demos. Tests never use the seeder; they create minimal rows in fixtures.

## Prerequisites

1. **PostgreSQL** running locally (same server as development).
2. **`.env`** with a working `DATABASE_URL` for your dev DB, for example:
   ```
   DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/matcha_db
   ```
3. **Test database** `matcha_test` on that server. Tests derive the URL automatically: same host/user/password as `DATABASE_URL`, database name `matcha_test` (see `conftest.py` → `_test_db_url()`).

### Create `matcha_test`

Use the same PostgreSQL user as in `DATABASE_URL` (not necessarily your Windows login).

**psql (recommended on Windows):**

```bash
# Example — adjust user, host, port to match .env
psql -U postgres -h localhost -p 5432 -c "CREATE DATABASE matcha_test;"
```

**Or inside psql:**

```sql
CREATE DATABASE matcha_test;
```

If `createdb` fails with “password authentication failed”, your shell user does not match the PostgreSQL role — use `psql -U ...` with credentials from `.env` instead.

## Setup

From the project root, with the virtual environment activated:

```bash
pip install -r requirements.txt
```

## Running Tests

Run all tests:

```bash
pytest
```

Verbose output:

```bash
pytest -v
```

Single file, class, or test:

```bash
pytest tests/test_auth.py
pytest tests/test_auth.py::TestRegister
pytest tests/test_auth.py::TestRegister::test_register_success
```

Coverage (optional):

```bash
pip install pytest-cov
pytest --cov=app --cov-report=html
```

## How a test run works

1. **`app` fixture** — `create_app(TestConfig)` with `TESTING=True`, `DATABASE_URL` pointing at `matcha_test`.
2. **Schema** — `migrations/schema.sql` is executed on a fresh connection (all tables created).
3. **Test** — uses `client` / `logged_in_client` and optional `user` / `user2` fixtures.
4. **Teardown** — related tables are `DROP`ped so the next test starts clean.

Each test function that uses `app` gets this cycle. Fixtures `user` / `user2` insert verified users with profile picture, tags, birth date, and GPS coordinates (Geneva area) so browse/like tests can run.

## Test structure

```
tests/
├── conftest.py        # TestConfig, app/client fixtures, test users
├── test_auth.py       # Register, login, logout, resend verification
├── test_browse.py     # Suggestions, search, like, unlike, block
├── test_models.py     # DB constraints and inserts (raw SQL)
├── test_utils.py      # Validators, matching math, tags, place labels
└── TESTING.md         # This file
```

## Fixtures (`conftest.py`)

| Fixture | Description |
|---------|-------------|
| `app` | Flask app on `matcha_test`; applies `schema.sql`, drops tables after test |
| `client` | Unauthenticated Flask test client |
| `runner` | Flask CLI test runner |
| `user` | Verified user `testuser` / `test@example.com`, password `Test1234!`, profile photo, tag `music`, location set |
| `user2` | Second user `testuser2` / `test2@example.com`, tag `travel` |
| `logged_in_client` | `client` after `POST /auth/login` as `testuser` |

## Test files

### `test_auth.py`

Authentication flows (no real email is sent).

| Test class | Tests | What is checked |
|------------|-------|-----------------|
| `TestRegister` | page load, success, password mismatch, weak password, invalid email/username, duplicate email | HTTP responses and `users` row |
| `TestLogin` | page load, success, wrong password, unknown user | Session / flash messages |
| `TestResendVerification` | page load, token generation | `verification_token` set for unverified user |
| `TestLogout` | logout | Redirect and “logged out” message |

### `test_utils.py`

Pure Python helpers (no HTTP).

| Test class | What is checked |
|------------|-----------------|
| `TestPasswordStrength` | `is_password_strong` rules |
| `TestSanitizeString` | trim, HTML strip, length, `None` |
| `TestValidators` | email, username, name |
| `TestMatching` | `calculate_age`, `haversine_distance` |
| `TestCanonicalTags` | `canonical_tag_name`, `tags_display_form_value`, `split_tags_input` |
| `TestBuildPlaceLabel` | `build_place_label_from_address` (reverse geocode labels) |

### `test_models.py`

Database layer and PostgreSQL constraints via raw SQL (not ORM models).

| Test class | What is checked |
|------------|-----------------|
| `TestUserModel` | insert defaults (`fame_rating`, `email_verified`), unique username/email |
| `TestTagModel` | tag insert |
| `TestLikeModel` | like insert, unique `(liker_id, liked_id)` |
| `TestBlockModel` | block insert |
| `TestMessageModel` | message insert, `is_read` default |
| `TestNotificationModel` | notification insert, `is_read` default |

### `test_browse.py`

Browse routes (requires login except redirect tests).

| Test class | What is checked |
|------------|-----------------|
| `TestSuggestions` | 302 when guest, 200 when logged in |
| `TestSearch` | same |
| `TestLike` | like creates row; self-like does not |
| `TestUnlike` | unlike removes row |
| `TestBlock` | block row; cannot like blocked user |

## Test configuration

Defined in `tests/conftest.py`:

```python
def _test_db_url():
    base = os.environ.get("DATABASE_URL", "postgresql://localhost/matcha_db")
    parts = base.rsplit("/", 1)
    return parts[0] + "/matcha_test"


class TestConfig:
    TESTING = True
    DATABASE_URL = _test_db_url()
    SQLALCHEMY_DATABASE_URI = DATABASE_URL  # legacy key; app uses DATABASE_URL
    SECRET_KEY = "test-secret-key"
    WTF_CSRF_ENABLED = False
    UPLOAD_FOLDER = "/tmp/test_uploads"
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
```

Differences from production:

- Database name `matcha_test` instead of `matcha_db`
- `TESTING = True` (e.g. skips some `before_request` hooks)
- CSRF disabled for simpler form posts in tests
- Temporary upload folder

## What is not covered by automated tests

These are expected to be checked manually (see evaluation checklist):

- WebRTC / video calls and Socket.IO (`python run.py`, not `flask run`)
- Real email delivery
- OAuth providers
- File upload UI and image processing edge cases
- Map (Leaflet) and live geocoding / Nominatim rate limits
- Large suggestion lists (use `scripts/seed_data.py` on `matcha_db` for that)

## Troubleshooting

| Problem | Likely cause |
|---------|----------------|
| `connection refused` / `database "matcha_test" does not exist` | PostgreSQL not running or DB not created |
| `password authentication failed` | Wrong user in `DATABASE_URL` or `createdb` without `-U` |
| `relation "users" does not exist` | `schema.sql` failed; check migrations match code |
| DeprecationWarning from `eventlet` / `distutils` | Harmless when `create_app()` loads Socket.IO; tests still pass |

## Relation to development data

| | Development / demo | Tests |
|--|-------------------|--------|
| Database | `matcha_db` | `matcha_test` |
| Data | `python scripts/seed_data.py` (500 users) | Fixtures in `conftest.py` (1–2 users) |
| Password for seeded users | `Test1234!` | Same for fixture users |

Running `pytest` does not modify `matcha_db`.
