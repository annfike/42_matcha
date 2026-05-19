# Matcha

A dating website built with Flask and PostgreSQL. Users register, verify email, complete their profile, browse suggestions, like profiles, chat in real time, and receive notifications.

## Tech stack

| Layer | Technology |
|-------|------------|
| Backend | Flask (Python) |
| Database | PostgreSQL |
| Frontend | HTML, CSS, JavaScript |
| Real-time | Flask-SocketIO (chat, notifications) |
| Email | Flask-Mail |
| Auth | Flask-Login, Flask-Bcrypt |
| File upload | Werkzeug (images) |
| Location | JavaScript Geolocation API + fallback |
| Maps | Leaflet.js (interactive user map) |
| OAuth | Authlib (Google OAuth) |

## Prerequisites

- Python 3.8+
- PostgreSQL
- (Optional) SMTP server for email (e.g. Gmail) for verification and password reset

## Installation

1. Clone the repo and go to the project directory:

```bash
cd matcha
```

2. Create a virtual environment and activate it:

```bash
python3 -m venv venv
source venv/bin/activate   # Linux/macOS
# or: venv\Scripts\activate   # Windows
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Copy environment template and set your values:

```bash
cp .env.example .env
```

Edit `.env`: set `SECRET_KEY`, `DATABASE_URL`, and optionally `MAIL_*` for email.
If you don't want to configure SMTP for evaluation, set `SHOW_VERIFICATION_LINK=True` to display the verification link on screen after registration.

5. Create the PostgreSQL database:

```bash
createdb matcha_db
```

Or in `psql`: `CREATE DATABASE matcha_db;`

To open the database:

From the shell:

```bash
psql matcha_db
```

With an explicit user (enter the password when prompted):

```bash
psql -U user -d matcha_db
```

Using the same URL as in `.env`:

```bash
psql "postgresql://user:password@localhost/matcha_db"
```

If you are already in `psql` (connected to `postgres` or another database), switch to `matcha_db`:

```sql
\c matcha_db
```

Or:

```sql
\connect matcha_db
```

Useful commands inside `psql`: list tables `\dt`, quit `\q`.

6. Run migrations:

```bash
export FLASK_APP=run.py
flask init-db
```

Windows (PowerShell):

```powershell
$env:FLASK_APP="run.py"
flask init-db
```

Note: this project uses `migrations/schema.sql` applied by the custom `flask init-db` command (not Flask-Migrate).

7. (Optional) Create `app/uploads` for user images:

```bash
mkdir -p app/uploads
```

## Environment variables

| Variable | Description | Example |
|----------|-------------|---------|
| `FLASK_APP` | Entry point | `run.py` |
| `FLASK_ENV` | Environment | `development` or `production` |
| `SECRET_KEY` | Session/CSRF secret | Strong random string |
| `DATABASE_URL` | PostgreSQL connection | `postgresql://user:password@localhost/matcha_db` |
| `MAIL_SERVER` | SMTP host | `smtp.gmail.com` |
| `MAIL_PORT` | SMTP port | `587` |
| `MAIL_USE_TLS` | Use TLS | `True` |
| `MAIL_USERNAME` | SMTP login | Your email |
| `MAIL_PASSWORD` | SMTP password / app password | Your password |
| `UPLOAD_FOLDER` | Path for uploads | `./app/uploads` |
| `MAX_CONTENT_LENGTH` | Max upload size (bytes) | `5242880` (5MB) |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID (optional) | From Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret (optional) | From Google Cloud Console |


## Run the app

```bash
export FLASK_APP=run.py
flask run
```

Or:

```bash
python run.py
```

By default the app listens on `http://127.0.0.1:5000`. With `run.py` it binds to `0.0.0.0` and port 5000 (or `PORT` env var).

## Project structure

```
matcha/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── config.py            # Configuration
│   ├── models.py            # SQLAlchemy models
│   ├── routes/
│   │   ├── auth.py          # Register, login, logout, verify, reset password
│   │   ├── profile.py       # Profile editing, images, location, viewing other profiles
│   │   ├── browse.py        # Suggestions, search, like/unlike, block, report
│   │   ├── chat.py          # Real-time chat with WebSocket (Flask-SocketIO)
│   │   ├── notifications.py # Real-time notifications with WebSocket
│   │   ├── map.py           # Interactive user map (Leaflet.js)
│   │   ├── oauth.py         # Google OAuth authentication
│   │   ├── events.py        # Date/event scheduling for matches
│   │   └── videochat.py     # WebRTC video/audio calls
│   ├── templates/
│   │   ├── base.html
│   │   ├── auth/            # register, login, reset_password
│   │   ├── browse/          # suggestions, search
│   │   ├── profile/         # edit, view, visitors, likes
│   │   ├── chat/            # index (list), conversation
│   │   └── notifications/   # index (list)
│   ├── static/css/style.css
│   ├── utils/
│   │   ├── security.py       # Password validation, sanitization
│   │   ├── validators.py     # Email, username, name validation
│   │   ├── email.py          # Verification and reset emails
│   │   ├── images.py         # Image upload, resize, validation
│   │   ├── fame.py           # Fame rating calculation
│   │   ├── matching.py       # Matching algorithm, search, distance
│   │   ├── notifications.py  # WebSocket notification emit helper
│   │   └── common_words.txt  # For password strength check
│   └── uploads/             # User-uploaded images
├── scripts/
│   └── seed_data.py         # Generate 500+ test profiles
├── tests/
│   ├── conftest.py          # Pytest fixtures
│   ├── test_auth.py         # Auth tests
│   ├── test_browse.py       # Browse/like/block tests
│   ├── test_models.py       # Model tests
│   └── test_utils.py        # Utility function tests
├── migrations/               # Flask-Migrate (created by flask db init)
├── .env.example
├── .gitignore
├── requirements.txt
├── run.py
├── PROJECT_PLAN.md           # Full roadmap and DB schema
└── README.md
```

## Seed data

Generate 500+ test profiles with random data:

```bash
python scripts/seed_data.py
```

This creates users with random names, locations (Swiss cities), tags, likes, and profile views. All test users have password `Test1234!`.

## Testing

Tests use **pytest** against a separate PostgreSQL database **`matcha_test`** (same server/credentials as `DATABASE_URL` in `.env`, different database name). The schema is applied from `migrations/schema.sql` per test; this is independent of seed data on `matcha_db`.

Create the test database once (adjust user/host to match `.env`):

```bash
psql -U postgres -h localhost -c "CREATE DATABASE matcha_test;"
```

Run tests from the project root (virtualenv active, dependencies installed):

```bash
pytest
pytest -v
pytest tests/test_auth.py
```

Optional coverage: `pip install pytest-cov` then `pytest --cov=app --cov-report=html`.

Full setup, fixtures, and troubleshooting: [tests/TESTING.md](tests/TESTING.md).

## Features

- **Pagination**: User lists are paginated (20 per page)
- **HTML Emails**: Beautiful responsive email templates for verification and password reset
- **Logging**: User actions logged to `app.log` (auth, errors)
- **Caching**: Flask-Caching for frequently accessed data (tags list)

## Bonus features

- **Google OAuth**: Sign in/register with Google account
- **Interactive map**: Leaflet.js map showing nearby users with GPS localization
- **Photo gallery**: Drag-and-drop upload, reorder images, basic editing (rotate, flip, brightness, contrast)
- **Video/audio chat**: WebRTC peer-to-peer video calls for matched users
- **Event scheduling**: Create, accept/decline date invitations with matched users

## Security

- **SQL Injection**: SQLAlchemy ORM with parameterized queries
- **XSS**: Jinja2 auto-escaping, input sanitization
- **CSRF**: Flask-WTF CSRF protection on all POST forms
- **Passwords**: bcrypt hashing, strength validation (8+ chars, mixed case, numbers)
- **File uploads**: Extension + MIME validation, PIL image verification, UUID renaming, size limits (5MB)
- **Input validation**: Server-side and client-side (HTML5) validation

## Database schema

- **users** – auth, profile fields, location, fame_rating, email_verified, tokens, is_online, last_seen
- **user_images** – per-user images, profile picture, order
- **tags** / **user_tags** – interest tags (many-to-many)
- **likes** – liker_id, liked_id (unique pair)
- **profile_views** – viewer, viewed, viewed_at
- **blocks** – blocker, blocked (unique pair)
- **reports** – reporter, reported, reason
- **messages** – sender, receiver, content, is_read
- **notifications** – user, type (like, view, message, match, unlike), related_user, is_read
