# Getting Started from Scratch

This guide walks you through preparing your machine, configuring the project, and running Matcha locally for the first time.

## What you need

| Requirement | Version / notes |
|-------------|-----------------|
| **Python** | 3.8 or newer |
| **SQLite** | Included with Python (no separate server) |
| **Git** | To clone the repository |
| **SMTP** (optional) | For email verification and password reset (e.g. Gmail with an app password) |

Optional later:

- OAuth credentials (Google, GitHub, 42 Intra) for social login
- No extra setup for tests — pytest uses `matcha_test.db` automatically

---

## 1. Install system dependencies

### Python

Check your version:

```bash
python3 --version
```

If Python is missing or too old, install it from [python.org](https://www.python.org/downloads/) or your OS package manager.

### SQLite

SQLite is bundled with Python. The application stores data in a single file (default: `matcha.db` in the project root). No `psql`, `createdb`, or system service is required. To browse or query the database: [database-sqlite.md](database-sqlite.md).

---

## 2. Get the project

Clone the repository and enter the project directory:

```bash
git clone <repository-url> matcha
cd matcha
```

If you already have the folder, `cd` into it and pull the latest changes:

```bash
git pull
```

---

## 3. Python virtual environment

Create and activate a virtual environment inside the project:

**Linux / macOS:**

```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (PowerShell):**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Your shell prompt should show `(venv)`. All following commands assume this environment is active.

Install Python dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 4. Environment configuration

### Copy the template

```bash
cp .env.example .env
```

Never commit `.env` — it is listed in `.gitignore` and holds secrets.

### Edit `.env`

Open `.env` in your editor and set at least:

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Session and CSRF secret — use a long random string in production |
| `DATABASE_URL` | SQLite database file path |
| `FLASK_APP` | Must be `run.py` (already in `.env.example`) |
| `FLASK_ENV` | Use `development` locally |

**Example `DATABASE_URL`:**

```env
DATABASE_URL=sqlite:///matcha.db
```

The file is created in the project root when you run `flask init-db`. Use an absolute path if you prefer another location, e.g. `sqlite:////home/user/data/matcha.db`.

### Email (recommended for real use)

For registration verification and password reset, configure SMTP:

```env
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

For Gmail, create an [App Password](https://support.google.com/accounts/answer/185833) — your normal account password will not work with SMTP.

If email is not configured, registration may still succeed, but verification emails might not arrive. You can resend verification from `/auth/resend-verification` once SMTP works, or verify users manually in the database during local testing.

### Uploads (optional override)

Default upload path is `./app/uploads`. You can override:

```env
UPLOAD_FOLDER=./app/uploads
MAX_CONTENT_LENGTH=5242880
```

### OAuth (optional)

Leave empty to disable social login. Step-by-step provider setup (callback URLs, `.env`, troubleshooting): **[oauth-setup.md](oauth-setup.md)**.

---

## 5. Initialize the schema

The project applies `migrations/schema.sql` via a custom Flask CLI command (not Flask-Migrate).

**Linux / macOS:**

```bash
export FLASK_APP=run.py
flask init-db
```

**Windows (PowerShell):**

```powershell
$env:FLASK_APP="run.py"
flask init-db
```

Expected output:

```text
Database tables created.
```

After success, `matcha.db` appears in the project root (or at the path in `DATABASE_URL`).

### Upload directory

Ensure the uploads folder exists (created automatically on first upload in some setups, but creating it upfront avoids permission surprises):

```bash
mkdir -p app/uploads
```

---

## 6. Run the application

### Recommended: `run.py` (SocketIO + WebSockets)

```bash
python run.py
```

By default the app listens on **all interfaces** at port **5001** (override with `PORT` in the environment):

```text
http://127.0.0.1:5001
```

Chat, notifications, and video call signaling rely on Flask-SocketIO, so use `python run.py` for full functionality.

### Alternative: Flask development server

```bash
export FLASK_APP=run.py
flask run
```

This typically serves on `http://127.0.0.1:5000` and may not support WebSockets the same way. Prefer `python run.py` for local development.

---

## 7. First use in the browser

1. Open `http://127.0.0.1:5001` (or the port you set).
2. **Register** a new account at `/auth/register`.
3. **Verify email** via the link sent to your inbox (requires working SMTP).
4. **Log in** at `/auth/login`.
5. **Complete your profile** (photos, bio, tags, location) — many features require a complete profile.
6. Browse **suggestions** and **search**, like profiles, and use **chat** when matched.

---

## 8. Optional: seed test data

To populate the database with 500+ fake profiles (Swiss cities, tags, likes):

```bash
python scripts/seed_data.py
```

All seeded users share the password: `Test1234!`

Run this only on a development database, not production.

---

## 9. Optional: run tests

Tests use a separate file `matcha_test.db`. See [tests/TESTING.md](../tests/TESTING.md) for full details.

```bash
pytest
```

---

## Environment variables reference

| Variable | Required | Description |
|----------|----------|-------------|
| `FLASK_APP` | Yes | `run.py` |
| `FLASK_ENV` | No | `development` or `production` |
| `SECRET_KEY` | Yes (prod) | Flask secret key |
| `DATABASE_URL` | Yes | SQLite URL (`sqlite:///path/to/file.db`) |
| `MAIL_*` | For email | SMTP settings |
| `UPLOAD_FOLDER` | No | Image storage path |
| `MAX_CONTENT_LENGTH` | No | Max upload size in bytes (default 5MB) |
| `PORT` | No | Port when using `python run.py` (default `5001`) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | No | Google OAuth |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | No | GitHub OAuth |
| `INTRA42_CLIENT_ID` / `INTRA42_CLIENT_SECRET` | No | 42 Intra OAuth |

---

## Troubleshooting

### `flask init-db` — unable to open database file

- Check that the directory in `DATABASE_URL` exists and is writable.
- On 42 workstations, keep the default `sqlite:///matcha.db` in the project folder.

### `flask: command not found` or wrong Flask

- Activate the virtual environment: `source venv/bin/activate`.
- Reinstall: `pip install -r requirements.txt`.

### Port already in use

```bash
PORT=5002 python run.py
```

### Email not received

- Check spam folder.
- Verify `MAIL_USERNAME` / `MAIL_PASSWORD` and that TLS settings match your provider.
- Watch the terminal for SMTP errors when registering.

### Chat or notifications not updating

- Use `python run.py`, not plain `flask run`, so SocketIO is active.
- Use a modern browser with JavaScript enabled.

### Permission denied on `app/uploads`

```bash
chmod 755 app/uploads
```

Ensure `UPLOAD_FOLDER` in `.env` points to a writable path.

---

## Quick command checklist

```bash
# One-time setup
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env
export FLASK_APP=run.py
flask init-db
mkdir -p app/uploads

# Every development session
source venv/bin/activate
python run.py
```
