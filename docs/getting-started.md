# Getting Started from Scratch

This guide walks you through preparing your machine, configuring the project, and running Matcha locally for the first time.

## What you need

| Requirement | Version / notes |
|-------------|-----------------|
| **Python** | 3.8 or newer |
| **PostgreSQL** | Running server with permission to create databases |
| **Git** | To clone the repository |
| **SMTP** (optional) | For email verification and password reset (e.g. Gmail with an app password) |

Optional later:

- OAuth credentials (Google, GitHub, 42 Intra) for social login
- Test database `matcha_test` if you want to run the pytest suite

---

## 1. Install system dependencies

### Python

Check your version:

```bash
python3 --version
```

If Python is missing or too old, install it from [python.org](https://www.python.org/downloads/) or your OS package manager.

### PostgreSQL

**macOS (Homebrew):**

```bash
brew install postgresql@16
brew services start postgresql@16
```

**Debian / Ubuntu:**

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

**Windows:** Install from [postgresql.org](https://www.postgresql.org/download/windows/) and ensure the service is running.

Confirm `psql` works:

```bash
psql --version
```

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
| `DATABASE_URL` | PostgreSQL connection string |
| `FLASK_APP` | Must be `run.py` (already in `.env.example`) |
| `FLASK_ENV` | Use `development` locally |

**Example `DATABASE_URL`:**

```env
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/matcha_db
```

Replace `postgres`, `yourpassword`, host, and port with your PostgreSQL user and settings.

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

## 5. PostgreSQL database

### Create the application database

**Using `createdb`:**

```bash
createdb matcha_db
```

**Or in `psql`:**

```bash
psql -U postgres
```

```sql
CREATE DATABASE matcha_db;
\q
```

### Connect to verify

```bash
psql "postgresql://postgres:yourpassword@localhost/matcha_db"
```

Inside `psql`: `\dt` lists tables (empty until migrations), `\q` quits.

---

## 6. Initialize the schema

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

If you see connection errors, check that PostgreSQL is running and that `DATABASE_URL` in `.env` matches your user, password, host, and database name.

### Upload directory

Ensure the uploads folder exists (created automatically on first upload in some setups, but creating it upfront avoids permission surprises):

```bash
mkdir -p app/uploads
```

---

## 7. Run the application

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

## 8. First use in the browser

1. Open `http://127.0.0.1:5001` (or the port you set).
2. **Register** a new account at `/auth/register`.
3. **Verify email** via the link sent to your inbox (requires working SMTP).
4. **Log in** at `/auth/login`.
5. **Complete your profile** (photos, bio, tags, location) — many features require a complete profile.
6. Browse **suggestions** and **search**, like profiles, and use **chat** when matched.

---

## 9. Optional: seed test data

To populate the database with 500+ fake profiles (Swiss cities, tags, likes):

```bash
python scripts/seed_data.py
```

All seeded users share the password: `Test1234!`

Run this only on a development database, not production.

---

## 10. Optional: run tests

Tests use a separate database `matcha_test`. See [tests/TESTING.md](../tests/TESTING.md) for full details.

Quick setup:

```bash
psql -U postgres -h localhost -c "CREATE DATABASE matcha_test;"
pytest
```

---

## Environment variables reference

| Variable | Required | Description |
|----------|----------|-------------|
| `FLASK_APP` | Yes | `run.py` |
| `FLASK_ENV` | No | `development` or `production` |
| `SECRET_KEY` | Yes (prod) | Flask secret key |
| `DATABASE_URL` | Yes | PostgreSQL URL |
| `MAIL_*` | For email | SMTP settings |
| `UPLOAD_FOLDER` | No | Image storage path |
| `MAX_CONTENT_LENGTH` | No | Max upload size in bytes (default 5MB) |
| `PORT` | No | Port when using `python run.py` (default `5001`) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | No | Google OAuth |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | No | GitHub OAuth |
| `INTRA42_CLIENT_ID` / `INTRA42_CLIENT_SECRET` | No | 42 Intra OAuth |

---

## Troubleshooting

### `flask init-db` — connection refused or authentication failed

- Confirm PostgreSQL is running: `brew services list` (macOS) or `sudo systemctl status postgresql` (Linux).
- Match `DATABASE_URL` to a real role and password: `psql -U <user> -d postgres -c '\du'`.
- Ensure `matcha_db` exists: `psql -l | grep matcha`.

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
createdb matcha_db
export FLASK_APP=run.py
flask init-db
mkdir -p app/uploads

# Every development session
source venv/bin/activate
python run.py
```
