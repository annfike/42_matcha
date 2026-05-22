# Matcha

A dating website built with Flask and SQLite. Users register, verify email, complete their profile, browse suggestions, like profiles, chat in real time, and receive notifications.

**Full setup from scratch:** [docs/getting-started.md](docs/getting-started.md)  
**OAuth (Google, GitHub, 42 Intra):** [docs/oauth-setup.md](docs/oauth-setup.md)

## Tech stack

| Layer | Technology |
|-------|------------|
| Backend | Flask (Python) |
| Database | SQLite (`sqlite3`, parameterized SQL) |
| Frontend | HTML, CSS, JavaScript |
| Real-time | Flask-SocketIO (chat, notifications, call signaling) |
| Email | Flask-Mail |
| Auth | Flask-Login, Flask-Bcrypt |
| OAuth | Authlib (Google, GitHub, 42 Intra — optional) |
| File upload | Werkzeug + Pillow (images) |
| Location | JavaScript Geolocation API + manual city fallback |
| Maps | Leaflet.js (interactive user map) |

## Prerequisites

- Python 3.8+ (includes SQLite)
- SMTP (recommended) for email verification and password reset (e.g. Gmail with an app password)

## Quick start

```bash
git clone <repository-url> matcha && cd matcha
python3 -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                # edit SECRET_KEY, DATABASE_URL, MAIL_*
export FLASK_APP=run.py
flask init-db
mkdir -p app/uploads
python run.py
```

Open **http://127.0.0.1:5001** (default port when using `run.py`). Step-by-step details, troubleshooting, and optional seed/tests: [docs/getting-started.md](docs/getting-started.md).

## Environment variables

| Variable | Description | Example |
|----------|-------------|---------|
| `FLASK_APP` | Entry point | `run.py` |
| `FLASK_ENV` | Environment | `development` or `production` |
| `SECRET_KEY` | Session/CSRF secret | Strong random string |
| `DATABASE_URL` | SQLite database file | `sqlite:///matcha.db` |
| `MAIL_SERVER` | SMTP host | `smtp.gmail.com` |
| `MAIL_PORT` | SMTP port | `587` |
| `MAIL_USE_TLS` | Use TLS | `True` |
| `MAIL_USERNAME` | SMTP login | Your email |
| `MAIL_PASSWORD` | SMTP password / app password | App password |
| `UPLOAD_FOLDER` | Path for uploads | `./app/uploads` |
| `MAX_CONTENT_LENGTH` | Max upload size (bytes) | `5242880` (5MB) |
| `PORT` | Port for `python run.py` | `5001` (default) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth (optional) | See [docs/oauth-setup.md](docs/oauth-setup.md) |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | GitHub OAuth (optional) | See [docs/oauth-setup.md](docs/oauth-setup.md) |
| `INTRA42_CLIENT_ID` / `INTRA42_CLIENT_SECRET` | 42 Intra OAuth (optional) | See [docs/oauth-setup.md](docs/oauth-setup.md) |

## Run the app

**Recommended** (WebSockets for chat, notifications, video calls):

```bash
python run.py
```

Listens on `0.0.0.0` at port **5001** by default, or set `PORT` in the environment.

**Alternative** (basic HTTP only, no SocketIO server):

```bash
export FLASK_APP=run.py
flask run
```

Typically `http://127.0.0.1:5000` — prefer `python run.py` for full functionality.

## Database

Schema is applied from `migrations/schema.sql` via:

```bash
export FLASK_APP=run.py
flask init-db
```

This is a custom Flask CLI command, not Flask-Migrate.

## Project structure

```
matcha/
├── app/
│   ├── __init__.py           # Flask app factory, blueprints, init-db
│   ├── config.py
│   ├── database.py           # SQLite connection, query helpers
│   ├── models.py             # User model (Flask-Login), make_user()
│   ├── routes/
│   │   ├── auth.py           # Register, login, verify, reset password
│   │   ├── profile.py        # Profile, images, location, visitors
│   │   ├── browse.py         # Suggestions, search, like, block, report
│   │   ├── chat.py           # Real-time chat (SocketIO)
│   │   ├── notifications.py  # Real-time notifications (SocketIO)
│   │   ├── map.py            # User map (Leaflet)
│   │   ├── oauth.py          # Google, GitHub, 42 Intra OAuth
│   │   ├── events.py         # Date/event scheduling
│   │   └── videochat.py      # WebRTC calls (SocketIO signaling)
│   ├── templates/            # Jinja2 HTML (+ email templates)
│   ├── static/               # CSS, JS (chat, map, videochat)
│   ├── utils/                # validators, email, images, matching, …
│   └── uploads/              # User-uploaded images
├── docs/
│   ├── getting-started.md
│   └── oauth-setup.md
├── migrations/
│   └── schema.sql
├── scripts/
│   └── seed_data.py
├── tests/
├── .env.example
├── requirements.txt
└── run.py
```

## Seed data

```bash
python scripts/seed_data.py
```

Creates 500+ test profiles (Swiss cities, tags, likes, views). Password for all seeded users: `Test1234!`

## Testing

Uses a separate SQLite file **`matcha_test.db`** (derived from `DATABASE_URL`). See [tests/TESTING.md](tests/TESTING.md).

```bash
pytest
```

## Features

- Email registration with verification and password reset (HTML emails)
- Profile completion gate before browsing
- Suggestions, search, likes, blocks, reports, fame rating
- Real-time chat and notifications (SocketIO)
- Pagination (20 per page)
- Logging to `app.log`
- Flask-Caching for tag lists

## Bonus features

- **OAuth:** Google, GitHub, 42 Intra ([setup guide](docs/oauth-setup.md))
- **Interactive map:** Leaflet.js, nearby users, GPS + manual city
- **Photo gallery:** drag-and-drop, reorder, rotate/flip/brightness/contrast
- **Video/audio chat:** WebRTC for matched users
- **Event scheduling:** create and accept/decline date invitations with matches

## Security

- **SQL injection:** parameterized queries (`sqlite3`) — no string-concatenated SQL
- **XSS:** Jinja2 auto-escaping, input sanitization
- **CSRF:** Flask-WTF on POST forms
- **Passwords:** bcrypt, strength rules (length, mixed case, numbers)
- **Uploads:** extension + MIME checks, PIL verification, UUID filenames, 5MB limit
- **Secrets:** `.env` in `.gitignore`; use `.env.example` as template

## Database schema

- **users** — auth, profile, location, fame_rating, email_verified, tokens, online status
- **user_images** — photos, profile picture, order
- **tags** / **user_tags** — interests (many-to-many)
- **likes**, **profile_views**, **blocks**, **reports**
- **messages**, **notifications**
- **events** — scheduled dates between matched users (pending / accepted / declined / cancelled)
