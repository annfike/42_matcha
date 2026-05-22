# Testing Documentation

## Overview

The test suite uses **pytest** with Flask’s built-in test client (`app.test_client()`). Tests exercise HTTP routes and SQL against a **real SQLite database** file `matcha_test.db`, separate from the development `matcha.db`.

The app talks to the database through **`sqlite3`** and `app/database.py` (`query_one`, `execute`, `execute_returning`). There is no SQLAlchemy ORM in this project.

`pytest-flask` is listed in `requirements.txt`; fixtures are defined manually in `tests/conftest.py` via `create_app(TestConfig)`.

**Seed data is separate:** `python scripts/seed_data.py` fills `matcha.db` for manual demos. Tests never use the seeder; they create minimal rows in fixtures.

## Prerequisites

1. **Python 3.8+** with the standard library `sqlite3` module.
2. **`.env`** (optional) — if `DATABASE_URL` is set, tests use the same path with `matcha.db` replaced by `matcha_test.db`. Default test URL: `sqlite:///matcha_test.db`.

No database server installation is required.

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

1. **`app` fixture** — `create_app(TestConfig)` with `TESTING=True`, `DATABASE_URL` pointing at `matcha_test.db`.
2. **Schema** — `reset_schema()` drops and recreates all tables from `migrations/schema.sql`.
3. **Test** — uses `client` / `logged_in_client` and optional `user` / `user2` fixtures.
4. **Teardown** — schema is reset again for the next test.

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
| `app` | Flask app on `matcha_test.db`; resets schema before and after each test |
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

### `test_browse.py`

Browse and social actions (requires `logged_in_client` and complete profile fixtures).

| Test class | Tests | What is checked |
|------------|-------|-----------------|
| `TestSuggestions` | page loads | HTTP 200 on `/browse/suggestions` |
| `TestSearch` | page loads | HTTP 200 on `/browse/search` |
| `TestLike` | like user, cannot like self | `likes` table, flash messages |
| `TestUnlike` | unlike after like | row removed from `likes` |
| `TestBlock` | block user, cannot like blocked | `blocks` table |

### `test_models.py`

Database layer and SQLite constraints via raw SQL (not ORM models).

### `test_utils.py`

Pure utility functions (validators, haversine, tag canonicalization).

## Configuration snippet

`TestConfig` in `conftest.py`:

```python
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
```

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| `database is locked` | Another process holds `matcha_test.db` (stop a running Flask app using the same file) |
| `relation "users" does not exist` | `schema.sql` failed; check migrations match code |
| Import errors | Virtualenv not activated or `pip install -r requirements.txt` not run |

Test database files (`*.db`) are listed in `.gitignore` and are not committed.
