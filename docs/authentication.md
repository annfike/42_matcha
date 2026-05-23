# Authentication (Flask-Login + Flask-Bcrypt)

Matcha uses **cookie-based sessions**: the browser stores a signed session ID; the server loads the user from SQLite on each request. Passwords are never stored in plain text — only **bcrypt** hashes.

---

## Architecture overview

```
HTTP request
    │
    ▼
Flask reads session cookie (signed with SECRET_KEY)
    │
    ▼
login_manager.user_loader(user_id)  →  SELECT users + profile picture
    │
    ▼
current_user available in routes and SocketIO handlers
    │
    ▼
@login_required  →  redirect to /auth/login if anonymous
```

OAuth uses the **same** session mechanism after `login_user()` — it is not JWT or API keys.

---

## Stack

| Library | Role |
|---------|------|
| `Flask-Login` | Session user, `@login_required`, `login_user` / `logout_user` |
| `Flask-Bcrypt` | Password hashing (cost factor handled by extension) |
| `Flask-WTF` / `CSRFProtect` | CSRF on form POSTs |
| `Authlib` | OAuth 2.0 (optional) — [oauth-setup.md](oauth-setup.md) |

Globals in `app/__init__.py`:

```python
bcrypt = Bcrypt()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."
```

---

## User model (`app/models.py`)

```python
class User(UserMixin):
    def get_id(self):
        return str(self.id)  # Flask-Login requires string ID
```

### `make_user(row)`

Converts a DB dict into a `User` instance:

- Copies all columns onto `self.__dict__`
- Pops `pp_filename` / `pp_id` from JOIN
- Sets `user.profile_picture = SimpleNamespace(id=..., filename=...)` if avatar exists

### `load_user(user_id)` — called every authenticated request

```sql
SELECT u.*, ui.filename AS pp_filename, ui.id AS pp_id
FROM users u
LEFT JOIN user_images ui ON u.profile_picture_id = ui.id
WHERE u.id = %s
```

Returns `None` if user deleted → Flask-Login treats as logged out.

**Implication:** profile picture changes appear on next request without re-login.

---

## Registration — step by step

**Route:** `POST /auth/register` (`app/routes/auth.py`)

| Step | Action |
|------|--------|
| 1 | Redirect if already logged in |
| 2 | `sanitize_string` on text fields (strip HTML tags, max length) |
| 3 | Validate email (`validators.is_valid_email`), username (`^[a-zA-Z0-9_]{3,30}$`), names |
| 4 | `is_password_strong` — length, case, digit, no common words from `common_words.txt` |
| 5 | Check duplicate email/username |
| 6 | `bcrypt.generate_password_hash(password).decode("utf-8")` |
| 7 | `secrets.token_urlsafe(32)` → `verification_token` |
| 8 | `INSERT INTO users (...)` via `execute_returning` |
| 9 | `commit()` |
| 10 | `send_verification_email` (see [email-smtp.md](email-smtp.md)) |
| 11 | Redirect to login with flash |

**DB state after register:** `email_verified=0`, `verification_token` set, no profile fields required yet.

---

## Email verification

**Route:** `GET /auth/verify/<token>`

- Lookup by token only (not by user id)
- `UPDATE email_verified=true, verification_token=NULL`
- No automatic login — user must enter password on login page

---

## Login — step by step

**Route:** `POST /auth/login`

| Step | Action |
|------|--------|
| 1 | Load row by **username** (not email) |
| 2 | `bcrypt.check_password_hash(stored_hash, password)` — constant-time compare inside bcrypt |
| 3 | If fail → `log_auth("login", username, success=False)`, flash error |
| 4 | If `not email_verified` → reject with message to resend verification |
| 5 | `make_user(row)` → `login_user(user)` — sets session `_user_id` |
| 6 | `UPDATE is_online=true, last_seen=now` |
| 7 | Redirect to `request.args.get("next")` or `browse.suggestions` |

Session cookie properties depend on Flask defaults (HttpOnly via Flask session interface; `SECRET_KEY` must be strong in production).

---

## Logout

**Route:** `GET /auth/logout` (`@login_required`)

```python
execute("UPDATE users SET is_online = false, last_seen = %s WHERE id = %s", ...)
logout_user()  # clears session
```

---

## Password reset

See [email-smtp.md](email-smtp.md) for mail details.

| Route | Method | Behavior |
|-------|--------|----------|
| `/auth/reset-password` | GET/POST | Request link by email |
| `/auth/reset-password/<token>` | GET | Show new password form if token valid |
| `/auth/reset-password/<token>` | POST | Set new hash, clear tokens |

Expiry: `reset_token_expiry < datetime.now(UTC)` → link rejected.

---

## CSRF protection

`CSRFProtect()` initialized in `create_app`. Forms include hidden CSRF field via Flask-WTF.

For **JSON APIs** (chat, location, image reorder):

```html
<meta name="csrf-token" content="{{ csrf_token() }}">
```

JavaScript sends header:

```javascript
'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
```

SocketIO connections use session cookie only — no separate CSRF on WebSocket events.

---

## OAuth (`app/routes/oauth.py`)

Initialized only if at least one `*_CLIENT_ID` is set in config.

### Flow per provider (Google / GitHub / 42)

1. `GET /oauth/<provider>` → `oauth.<provider>.authorize_redirect(redirect_uri)`
2. User approves at provider
3. `GET /oauth/<provider>/callback` → exchange code, fetch profile
4. `_oauth_login_or_create(email, first_name, last_name, username_hint, ...)`

### `_oauth_login_or_create` logic

**Existing email:**

```python
login_user(user)
UPDATE is_online = true
redirect browse.suggestions
```

**New user:**

```python
INSERT users (username, email, first_name, last_name,
              password_hash='oauth_google', email_verified=true, is_online=true)
login_user(user)
redirect profile.edit  # must complete profile fields
```

Username collision: append `_<provider_id[:6]>` suffix.

OAuth users **skip** email verification but still hit `before_request` profile gate until profile complete.

---

## Profile completion gate (`app/__init__.py`)

After login, most routes require full profile:

```python
@app.before_request
def check_profile_complete():
    if not current_user.is_authenticated: return
    if path starts with allowed_prefixes: return
    status = get_profile_completion_status(current_user.id)
    if not status["ok"]: redirect profile.edit
```

Allowed without full profile: `/auth/`, `/profile/`, `/oauth/`, static, uploads, notification/message count APIs, `/socket.io/`.

---

## Online presence

| Event | `is_online` | `last_seen` |
|-------|-------------|-------------|
| Login | `true` | updated |
| Logout | `false` | updated |
| SocketIO connect | `true` | updated |
| SocketIO disconnect | `false` | updated |

Multiple browser tabs: each tab may open a SocketIO connection; last disconnect sets offline even if another tab is open (known limitation).

---

## Database columns (auth)

| Column | Type | Notes |
|--------|------|-------|
| `username` | UNIQUE | Login identifier |
| `email` | UNIQUE | Verification / reset target |
| `password_hash` | string | Bcrypt; OAuth placeholder `oauth_*` |
| `email_verified` | bool | Login gate |
| `verification_token` | nullable | Cleared after verify |
| `reset_token` | nullable | Cleared after reset |
| `reset_token_expiry` | datetime | Compared on reset POST |

---

## Security summary

| Threat | Mitigation |
|--------|------------|
| Password theft from DB | Bcrypt hashes |
| Weak passwords | `is_password_strong` + common word list |
| Session tampering | Signed cookie with `SECRET_KEY` |
| CSRF on forms | Flask-WTF |
| User enumeration on reset | Generic flash message |
| XSS in names | `sanitize_string` strips tags |

---

## Related files

```
app/__init__.py
app/config.py
app/models.py
app/routes/auth.py
app/routes/oauth.py
app/utils/security.py
app/utils/validators.py
app/utils/profile_completion.py
app/utils/logger.py          # log_auth()
```
