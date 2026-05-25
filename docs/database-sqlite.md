# SQLite database access

Matcha stores all application data in a **single SQLite file**. There is no PostgreSQL, MySQL, or separate database server process. This guide explains where the file lives, how to open it, and useful commands for development and evaluation.

---

## Database file location

| Setting | Default |
|---------|---------|
| Environment variable | `DATABASE_URL` |
| Typical value | `sqlite:///matcha.db` |
| File on disk | `matcha.db` in the **project root** (next to `run.py`) |

The path is resolved in `app/database.py`: relative paths in `DATABASE_URL` are joined to the project root. Absolute paths are used as-is, for example:

```env
DATABASE_URL=sqlite:////home/user/data/matcha.db
```

**Create the database** (tables from `migrations/schema.sql`):

```bash
export FLASK_APP=run.py
flask init-db
```

Expected output: `Database tables created.`

---

## Command-line access (`sqlite3`)

The `sqlite3` program ships with macOS and most Linux distributions. On Windows, install [SQLite tools](https://www.sqlite.org/download.html) or use a GUI (below).

From the project directory:

```bash
cd matcha
sqlite3 matcha.db
```

Inside the interactive shell:

```sql
-- List tables
.tables

-- Show CREATE statement for a table
.schema users

-- Row counts (evaluation: at least 500 users after seed)
SELECT COUNT(*) FROM users;

-- Exit
.quit
```

### One-liners (no interactive shell)

```bash
sqlite3 matcha.db "SELECT COUNT(*) FROM users;"
sqlite3 matcha.db "SELECT username, email, email_verified FROM users LIMIT 10;"
sqlite3 matcha.db "SELECT password_hash FROM users LIMIT 3;"
```

Passwords must appear as **bcrypt** hashes (`$2b$...`), never plain text.

### Useful output modes

```bash
sqlite3 -header -column matcha.db "SELECT id, username, fame_rating FROM users ORDER BY fame_rating DESC LIMIT 5;"
```

In the interactive shell:

```sql
.headers on
.mode column
SELECT id, username, is_online, last_seen FROM users LIMIT 5;
```

---

## GUI tools

| Tool | Notes |
|------|--------|
| [DB Browser for SQLite](https://sqlitebrowser.org/) | Open `matcha.db`, browse tables, run SQL |
| VS Code / Cursor | Extensions such as **SQLite Viewer** or **SQLite** — open the file path |

Always open the same file path as in your `.env` `DATABASE_URL`.

---

## Schema overview

Full definitions: `migrations/schema.sql`. Applied once via `flask init-db` (not Flask-Migrate).

| Table | Purpose |
|-------|---------|
| `users` | Accounts, profile fields, location, fame, auth tokens |
| `user_images` | Photo filenames and order |
| `tags` / `user_tags` | Reusable interest tags |
| `likes` | Profile likes (mutual likes = match) |
| `profile_views` | Who viewed whom |
| `blocks` | Blocked users |
| `reports` | Fake-account reports |
| `messages` | Chat messages |
| `notifications` | like, view, message, match, unlike, event |
| `events` | Date invitations between matches |

---

## Test database (separate file)

Automated tests use **`matcha_test.db`**, not `matcha.db`. Do not confuse them when inspecting data after `pytest`.

```bash
sqlite3 matcha_test.db ".tables"
```

See [tests/TESTING.md](../tests/TESTING.md).

---

## Seed data

Populate 500+ demo profiles (required for project evaluation):

```bash
python scripts/seed_data.py
```

All seeded users use password: `Test1234!`

Verify:

```bash
sqlite3 matcha.db "SELECT COUNT(*) FROM users;"
```

---

## Local testing without SMTP

If email delivery is not configured, you can mark a user verified manually:

```bash
sqlite3 matcha.db "UPDATE users SET email_verified = 1 WHERE email = 'you@example.com';"
```

Or read the verification token from the database and use the link from the app (`/auth/verify/<token>`).

---

## Safety notes

- **Stop the app** or avoid heavy writes while copying `matcha.db` for backups; SQLite allows concurrent reads but copying a live file under write load can be inconsistent.
- **Do not commit** `matcha.db` to Git if it contains real user data (check `.gitignore`).
- **Destructive commands** (`DROP TABLE`, `DELETE` without `WHERE`) affect the only copy of your data — prefer a copy first:

  ```bash
  cp matcha.db matcha.db.backup
  ```

- Matcha uses **parameterized queries** in application code (`app/database.py`). When running ad-hoc SQL in `sqlite3`, you are responsible for your own statements.

---

## What this project does *not* use

| Not used | Use instead |
|----------|-------------|
| `psql`, `createdb` | `sqlite3 matcha.db` |
| Flask-SQLAlchemy / ORM | Raw SQL in routes and `app/database.py` |
| `flask db migrate` | `flask init-db` + `migrations/schema.sql` |

---

## Related documentation

| Document | Topic |
|----------|--------|
| [getting-started.md](getting-started.md) | Install, `flask init-db`, first run |
| [architecture.md](architecture.md) | How the app talks to SQLite per request |
| [authentication.md](authentication.md) | Users, passwords, verification |
