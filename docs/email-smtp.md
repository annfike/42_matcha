# Email (Flask-Mail / SMTP)

Matcha sends transactional email for **account verification** and **password reset** using [Flask-Mail](https://pythonhosted.org/Flask-Mail/) over SMTP. Email is the only way to activate a password-based account before first login.

---

## How it fits in the app

```
User submits form (register / forgot password)
        │
        ▼
auth.py validates input, writes token to SQLite
        │
        ▼
email.py builds Message (HTML + plain text)
        │
        ▼
Flask-Mail opens SMTP connection (MAIL_* from config)
        │
        ▼
User clicks link → auth route validates token → updates users row
```

Mail is **not** used for chat, likes, or notifications — those use SocketIO and the `notifications` table.

---

## Stack

| Piece | Role |
|-------|------|
| `Flask-Mail` | Extension; `mail.init_app(app)` in `app/__init__.py` |
| `app/config.py` | Reads `MAIL_*` from `.env` into `Config` class |
| `app/utils/email.py` | `send_verification_email`, `send_password_reset_email` |
| `app/templates/email/` | Jinja2 HTML bodies (`base.html`, `verify.html`, `reset_password.html`) |
| `app/routes/auth.py` | Triggers sends after DB writes |

---

## Configuration

Set in `.env` (see `.env.example`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `MAIL_SERVER` | `smtp.gmail.com` | SMTP host |
| `MAIL_PORT` | `587` | Port (STARTTLS) |
| `MAIL_USE_TLS` | `true` | Enable TLS |
| `MAIL_USERNAME` | — | SMTP login |
| `MAIL_PASSWORD` | — | SMTP password or Gmail **app password** |

In `app/config.py`:

```python
MAIL_DEFAULT_SENDER = os.environ.get("MAIL_USERNAME")
VERIFICATION_TOKEN_EXPIRY_HOURS = 24   # documented in email template text
RESET_TOKEN_EXPIRY_HOURS = 1           # enforced in DB on reset confirm
```

Flask-Mail reads `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER` from `app.config` automatically when `mail.init_app(app)` runs.

---

## Registration email — full flow

### Step 1: User submits `POST /auth/register`

Fields: email, username, first_name, last_name, password, password_confirm.

Validation order in `auth.py`:

1. All fields present
2. `is_valid_email`, `is_valid_username`, `is_valid_name`
3. Passwords match; `is_password_strong(password)`
4. Unique email and username (`SELECT id FROM users WHERE ...`)

### Step 2: Token and hash

```python
verification_token = secrets.token_urlsafe(32)  # ~43 chars, URL-safe
password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
```

### Step 3: INSERT user

```sql
INSERT INTO users (email, username, first_name, last_name, password_hash, verification_token)
```

`email_verified` stays **0** (default). User **cannot log in** until verified.

### Step 4: Send email

```python
send_verification_email(user_obj, verification_token)
```

Inside `email.py`:

1. `verify_url = url_for("auth.verify_email", token=token, _external=True)`  
   Example: `http://127.0.0.1:5001/auth/verify/AbCdEf...`
2. Render `email/verify.html` with `user`, `verify_url`
3. Build plain-text body (same link, 24h note)
4. `Message(subject="Verify your Matcha account", recipients=[user.email], ...)`
5. `current_app.extensions["mail"].send(msg)` — blocking SMTP send

### Step 5: User clicks link — `GET /auth/verify/<token>`

```sql
SELECT id FROM users WHERE verification_token = %s
UPDATE users SET email_verified = true, verification_token = NULL WHERE id = %s
```

Invalid token → flash error, redirect login. Success → flash success, redirect login.

### Resend — `POST /auth/resend-verification`

Always returns generic success (no email enumeration). If unverified user exists:

- New `verification_token` written to DB
- `send_verification_email` called again

---

## Password reset email — full flow

### Step 1: `POST /auth/reset-password`

User enters email. Server:

```python
token = secrets.token_urlsafe(32)
expiry = now + timedelta(hours=RESET_TOKEN_EXPIRY_HOURS)  # 1 hour
UPDATE users SET reset_token = %s, reset_token_expiry = %s WHERE id = %s
send_password_reset_email(user_obj, token)
```

Response is always the same flash message whether email exists (anti-enumeration).

### Step 2: Email content

- Subject: `Reset your Matcha password`
- Link: `/auth/reset-password/<token>` (`_external=True`)
- Template: `email/reset_password.html`

### Step 3: `GET /auth/reset-password/<token>`

```python
row = query_one("SELECT id, reset_token_expiry FROM users WHERE reset_token = %s", ...)
if not row or row["reset_token_expiry"] < now:
    # invalid or expired
```

Shows password form if valid.

### Step 4: `POST /auth/reset-password/<token>`

New password validated with `is_password_strong`, bcrypt hash stored:

```sql
UPDATE users SET password_hash = %s, reset_token = NULL, reset_token_expiry = NULL
```

Old sessions are not invalidated explicitly (Flask-Login session remains valid until logout).

---

## HTML templates

`email/base.html` provides shared styling (wrapper, button class `.btn`).

`verify.html` includes:

- Personalized greeting (`user.first_name`)
- CTA button linking to `verify_url`
- Plain URL fallback (for clients that strip buttons)
- 24-hour expiry note

Same pattern for reset password template.

---

## Error handling

`auth.py` wraps every `send_*` in `try/except Exception: pass`:

- Registration **succeeds** even if SMTP fails
- User sees “check your email” but may receive nothing
- No retry queue or dead-letter log

**Local development options:**

- Gmail + [app password](https://support.google.com/accounts/answer/185833)
- [Mailhog](https://github.com/mailhog/Mailhog) / Mailpit — SMTP catcher on localhost
- Commented `SHOW_VERIFICATION_LINK` in `config.py` (demo mode — link in flash instead of email)

---

## Security

| Topic | Implementation |
|-------|----------------|
| Token entropy | `secrets.token_urlsafe(32)` |
| Token storage | Plain in DB (single-use; cleared after use) |
| Reset expiry | Checked server-side against `reset_token_expiry` |
| Verification | Token nulled after success; link cannot be reused |
| Link host | `_external=True` uses request host — set correct public URL in production |
| Credentials | `MAIL_PASSWORD` only in `.env`, never committed |

Verification tokens have no DB expiry column; expiry is stated in email text only (24h policy is informational unless you add a `created_at` check).

---

## Related files

```
app/config.py
app/__init__.py              # mail.init_app
app/utils/email.py
app/routes/auth.py
app/templates/email/base.html
app/templates/email/verify.html
app/templates/email/reset_password.html
```

See also: [authentication.md](authentication.md)
