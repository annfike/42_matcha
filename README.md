# Matcha

A dating website built with Flask and SQLite. Users register, verify email, complete their profile, browse suggestions, like profiles, chat in real time, and receive notifications.

**Full setup from scratch:** [docs/getting-started.md](docs/getting-started.md)  
**OAuth (Google, GitHub, 42 Intra):** [docs/oauth-setup.md](docs/oauth-setup.md)

<details>
<summary><strong>Demo</strong> — walkthrough with two test accounts (screenshots and video)</summary>

<br>

Walkthrough with **two accounts**, top to bottom:

- **User 1** — register, verify email, log in, fill profile, add photos via CLI.
- **User 2** — register, verify email, log in, complete profile, then browse and use chat, notifications, events, and video.

<h3 align="center">User 1 — register, log in, complete profile</h3>

<p align="center"><strong>Register — empty form</strong> — fields before the first account is created.</p>

<p align="center"><img src="screenshots/register_empty.png" alt="Register — empty form" width="720"></p>

<p align="center"><strong>Register — user 1</strong> — filled sign-up form ready to submit.</p>

<p align="center"><img src="screenshots/register_user1.png" alt="Register — user 1" width="720"></p>

<p align="center"><strong>After sign-up</strong> — redirect to the login page.</p>

<p align="center"><img src="screenshots/redirect_to_login_after_register.png" alt="Redirect to login" width="720"></p>

<p align="center"><strong>Verify email (user 1)</strong> — open the link from the inbox to activate the account.</p>

<p align="center"><img src="screenshots/verification_email_user1.png" alt="Verification email user 1" width="720"></p>

<p align="center"><strong>Log in (user 1)</strong> — sign in after the email is verified.</p>

<p align="center"><img src="screenshots/login.png" alt="Login user 1" width="720"></p>

<p align="center"><strong>Edit profile — details</strong> — name, bio, gender, preferences, and tags.</p>

<p align="center"><img src="screenshots/edit_profile_after_first_login.png" alt="Edit profile details" width="720"></p>

<p align="center"><strong>Edit profile — location and stats</strong> — geolocation or city, fame rating, and profile completion.</p>

<p align="center"><img src="screenshots/edit_profile_after_first_login_2.png" alt="Edit profile location" width="720"></p>

<p align="center"><strong>Generate photos (CLI)</strong> — for local demos, download portrait images for user 1 from the project root (network required). Replace <code>USERNAME</code> and <code>male|female</code> with your values; full options in <a href="#profile-photos-for-one-user">Profile photos for one user</a>.</p>

<p align="center"><code>python scripts/generate_user_photos.py --username USERNAME --gender male --count 3 --set-main</code></p>

<p align="center"><strong>Edit profile — photos (user 1)</strong> — gallery after the script uploads images and sets the main picture.</p>

<p align="center"><img src="screenshots/edit_profile_after_genaration_fotos1.png" alt="User 1 profile with photos" width="720"></p>

<h3 align="center">User 2 — register, profile, then the rest of the app</h3>

<p align="center"><strong>Register — user 2</strong> — second account while user 1 is already in the database.</p>

<p align="center"><img src="screenshots/register_user2.png" alt="Register user 2" width="720"></p>

<p align="center"><strong>Verify email (user 2)</strong> — confirmation message for the second account.</p>

<p align="center"><img src="screenshots/verification_email_user2.png" alt="Verification email user 2" width="720"></p>

<p align="center"><strong>Log in (user 2)</strong> — same login page, second username.</p>

<p align="center"><img src="screenshots/login.png" alt="Login user 2" width="720"></p>

<p align="center"><strong>Edit profile — photos (user 2)</strong> — second user finishes profile setup (required before suggestions unlock).</p>

<p align="center"><img src="screenshots/edit_profile_after_genaration_fotos2.png" alt="User 2 edit profile with photos" width="720"></p>

<p align="center"><strong>Suggestions</strong> — personalized cards, filters, and likes.</p>

<p align="center"><img src="screenshots/suggestions.png" alt="Suggestions" width="720"></p>

<p align="center"><strong>Search</strong> — advanced filters and tag-based discovery.</p>

<p align="center"><img src="screenshots/search.png" alt="Search" width="720"></p>

<p align="center"><strong>Map</strong> — nearby users on an interactive map.</p>

<p align="center"><img src="screenshots/map.png" alt="Map" width="720"></p>

<p align="center"><strong>Events</strong> — schedule and manage date invitations with matches.</p>

<p align="center"><img src="screenshots/events_empty.png" alt="Events" width="720"></p>

<p align="center"><strong>Who liked you</strong> — list of users who liked your profile (from profile stats).</p>

<p align="center"><img src="screenshots/who_liked_you_empty.png" alt="Who liked you" width="720"></p>

<p align="center"><strong>Who viewed your profile</strong> — recent profile visitors.</p>

<p align="center"><img src="screenshots/who_viewed_your_profile_empty.png" alt="Who viewed your profile" width="720"></p>

<p align="center"><strong>Chat</strong> — real-time messaging with mutual matches (SocketIO).</p>

<p align="center"><img src="screenshots/chat.png" alt="Chat" width="720"></p>

<p align="center"><strong>Notifications</strong> — likes, views, messages, and matches in one feed.</p>

<p align="center"><img src="screenshots/notifications.png" alt="Notifications" width="720"></p>

**App demo (video)** — screen recording while logged in as user 2: browsing **Suggestions**, **Search**, **Map**, **Events**, **Chat**, **Notifications**, **Who liked you** / **Who viewed your profile**, and a **video call** between the two test accounts. Not only chat — the clip walks through the main pages of the app in use.

**[▶ Watch app demo (MP4)](screenshots/video_demo_chat.mp4)** — on GitHub, open this link to play in the browser (~2.5 min). README cannot embed video inline; use the link or the preview below.

<p align="center"><a href="screenshots/video_demo_chat.mp4"><img src="screenshots/video_demo_poster.png" alt="App demo — click to play video" width="720"></a></p>

<p align="center"><em>Click the preview to play the video.</em></p>

</details>

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

**Open and query the database:** [docs/database-sqlite.md](docs/database-sqlite.md) (`sqlite3 matcha.db`, GUI tools, seed checks).

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
│   ├── seed_data.py
│   └── generate_user_photos.py
├── screenshots/              # README demo section (PNG + MP4)
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

After seeding, the script downloads **real portrait photos** (randomuser.me) for users with `@example.com` emails. Users without a successful download keep colored initial avatars.

| Flag | Purpose |
|------|---------|
| `--real-photos` | Only assign/replace real photos for existing seeded users |
| `--images-only` | Only create placeholder avatars for users missing images |

### Profile photos for one user

Use when you need photos for your own account (or any user) without re-seeding:

```bash
python scripts/generate_user_photos.py --username YOUR_USERNAME --gender female --count 3 --set-main
```

| Option | Description |
|--------|-------------|
| `--user-id` / `--username` | Target user (one required) |
| `--gender male\|female` | Portrait set to download |
| `--count` | Number of photos (default 3, max 5 per profile) |
| `--replace` | Remove existing photos first |
| `--set-main` | Set the first new photo as profile picture |
| `--force` | Allow more than 5 images (not recommended) |

Requires network access. Files are saved under `UPLOAD_FOLDER` (default `app/uploads`).

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
