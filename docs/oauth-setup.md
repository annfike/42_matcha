# Authentication setup (email/password and OAuth)

Matcha supports two sign-in paths:

1. **Email and password** — always available; requires **SMTP** for verification and password-reset links before the first login.
2. **OAuth** (optional) — Google, GitHub, or 42 Intra when client credentials are set in `.env`.

Implementation: `app/routes/auth.py` (local accounts), `app/routes/oauth.py` (social login).

---

## Email and password

Use this flow when you register with the form on **Register** (`/auth/register`) instead of **Continue with Google / GitHub / 42 Intra**. No OAuth app registration is required — only `.env` mail settings (or a local workaround below).

### Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/auth/register` | GET, POST | Create account |
| `/auth/verify/<token>` | GET | Confirm email after registration |
| `/auth/resend-verification` | GET, POST | Request a new verification link |
| `/auth/login` | GET, POST | Sign in with **username** + password |
| `/auth/logout` | GET | End session |
| `/auth/reset-password` | GET, POST | Request password-reset email |
| `/auth/reset-password/<token>` | GET, POST | Set a new password from email link |

### Registration (`POST /auth/register`)

1. Form fields: email, username, first_name, last_name, password, password_confirm.
2. Validation: email/username/name rules, passwords match, `is_password_strong` (min 8 chars, upper, lower, digit).
3. Uniqueness checks on email and username.
4. `verification_token = secrets.token_urlsafe(32)`; password stored as **bcrypt** hash.
5. `INSERT` into `users` with `email_verified = false` (column default).
6. `commit()` — account exists in SQLite.
7. `send_verification_email()` via SMTP (see [email-smtp.md](email-smtp.md)).
8. Redirect to **Login** — **no session** is created yet.

If SMTP fails, registration is **not** rolled back; the user row remains unverified. Configure `MAIL_*` and use **Resend verification**, or verify manually during local testing (see below).

### Email verification (`GET /auth/verify/<token>`)

This is the link in the registration email (`auth.verify_email`).

| Step | Action |
|------|--------|
| 1 | `SELECT id FROM users WHERE verification_token = ?` |
| 2 | If no row → flash *Invalid or expired verification link* → redirect to login |
| 3 | `UPDATE users SET email_verified = true, verification_token = NULL` |
| 4 | `commit()` → flash success → redirect to login |

The verification token in the email body is documented as **24 hours** in the template text; expiry is not enforced in SQL — only the current token value matters (a new resend replaces the old token).

### Login (`POST /auth/login`)

1. Lookup by **username** (not email), with profile picture join.
2. `bcrypt.check_password_hash` — on failure: *Invalid username or password*.
3. **`email_verified` must be true** — otherwise login is blocked with a message pointing to resend verification.
4. `login_user()` → Flask-Login session cookie.
5. `UPDATE is_online = true`, `last_seen = now` → `commit()`.
6. Redirect to `?next=` or `/browse/suggestions`.

OAuth-only accounts use placeholder password hashes (`oauth_google`, etc.) and are meant to sign in via the provider, not this form.

### Password reset

**Request** (`POST /auth/reset-password`):

1. Lookup by email (same success flash whether or not the account exists — no email enumeration).
2. `reset_token` + `reset_token_expiry` (default **1 hour**, `RESET_TOKEN_EXPIRY_HOURS` in `app/config.py`).
3. Email with link to `/auth/reset-password/<token>`.

**Confirm** (`POST /auth/reset-password/<token>`):

1. Token must exist and `reset_token_expiry >= now` (UTC).
2. New password must pass `is_password_strong`.
3. Update `password_hash`, clear reset fields → redirect to login.

### Resend verification (`POST /auth/resend-verification`)

For accounts with `email_verified = false`: new `verification_token`, `UPDATE`, email sent. Response is always generic: *If an unverified account exists with that email, a verification link has been sent.*

### Configure SMTP (required for real email/password use)

In `.env` (see [.env.example](../.env.example)):

```env
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

Full provider notes, Gmail app passwords, and Mailhog: [email-smtp.md](email-smtp.md).

Restart the app after changing `.env`.

### Local testing without SMTP

| Approach | When to use |
|----------|-------------|
| [email-smtp.md](email-smtp.md) — Mailhog / Mailpit | Catch messages on localhost |
| `/auth/resend-verification` | After fixing `MAIL_*` for an existing unverified user |
| SQLite: `UPDATE users SET email_verified = 1 WHERE email = '...'` | Quick manual unlock on your machine only |
| `SHOW_VERIFICATION_LINK` in `app/config.py` | Commented demo mode: flash the verify URL on screen instead of sending mail (uncomment in `config.py` and the matching block in `auth.py`) |

### Email/password vs OAuth

| | Email/password | OAuth |
|---|----------------|-------|
| Setup | `MAIL_*` in `.env` | Provider client ID/secret |
| `email_verified` after sign-up | `false` until link clicked | `true` immediately |
| Login identifier | Username + password | Provider button |
| Session | Flask-Login cookie | Same cookie after OAuth callback |

More on sessions and bcrypt: [authentication.md](authentication.md).

---

## OAuth (Google, GitHub, 42 Intra)

Optional social login via [Authlib](https://docs.authlib.org/). Each provider is enabled independently by setting client credentials in `.env`. Buttons appear on **Login** and **Register** only when the corresponding `*_CLIENT_ID` is set.

### How OAuth works in this app

| Route | Purpose |
|-------|---------|
| `/oauth/google` | Start Google sign-in |
| `/oauth/google/callback` | Google redirect target |
| `/oauth/github` | Start GitHub sign-in |
| `/oauth/github/callback` | GitHub redirect target |
| `/oauth/intra42` | Start 42 Intra sign-in |
| `/oauth/intra42/callback` | 42 Intra redirect target |

**Behaviour:**

- If a user with the same **email** already exists → they are logged in.
- If not → a new account is created with `email_verified = true` (no verification email).
- New OAuth users are redirected to **profile edit** to complete mandatory fields.
- OAuth accounts use a placeholder password hash in the database (`oauth_google`, `oauth_github`, `oauth_intra42`); sign-in is via the provider only.

Implementation: `app/routes/oauth.py`.

### Before you start (OAuth providers)

1. Complete basic setup ([getting-started.md](getting-started.md)): app runs locally, `.env` exists.
2. Decide your **base URL** — the exact origin you use in the browser, including port.

Examples for local development with `python run.py` (default port **5001**):

| Base URL | Google callback |
|----------|-----------------|
| `http://127.0.0.1:5001` | `http://127.0.0.1:5001/oauth/google/callback` |
| `http://localhost:5001` | `http://localhost:5001/oauth/google/callback` |

**Important:** Provider consoles treat `127.0.0.1` and `localhost` as different hosts. Register the callback URL that matches how you open the site. Use the same host for GitHub and 42 Intra.

For production, use `https://your-domain.com/oauth/...` and serve the app over HTTPS.

3. Add credentials to `.env` (see [.env.example](../.env.example)):

```env
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...

INTRA42_CLIENT_ID=...
INTRA42_CLIENT_SECRET=...
```

4. Restart the application after changing `.env`.

---

## Google

### 1. Create a Google Cloud project

1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project (or select an existing one).
3. Go to **APIs & Services** → **OAuth consent screen**.
4. Choose **External** (or **Internal** if using a Workspace org).
5. Fill required fields (app name, support email, developer contact).
6. Add scopes if prompted: `email` and `profile` (the app requests `email profile`).

### 2. Create OAuth client credentials

1. **APIs & Services** → **Credentials** → **Create credentials** → **OAuth client ID**.
2. Application type: **Web application**.
3. **Authorized JavaScript origins** (optional for this server-side flow, but useful for local testing):
   - `http://127.0.0.1:5001`
   - `http://localhost:5001`
4. **Authorized redirect URIs** — add exactly:
   - `http://127.0.0.1:5001/oauth/google/callback`
   - (and/or `http://localhost:5001/oauth/google/callback` if you use `localhost`)

5. Copy **Client ID** and **Client secret** into `.env`:

```env
GOOGLE_CLIENT_ID=123456789-xxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxx
```

### 3. Test

1. Run `python run.py`.
2. Open `http://127.0.0.1:5001/auth/login`.
3. Click **Continue with Google** and complete the flow.

### Google troubleshooting

| Problem | What to check |
|---------|----------------|
| `redirect_uri_mismatch` | Redirect URI in Google Console must match the callback URL character-for-character (scheme, host, port, path). |
| `Google OAuth is not configured` | `GOOGLE_CLIENT_ID` missing or empty; restart app after editing `.env`. |
| `Could not get email from Google` | OAuth consent screen / scopes; account must grant email access. |
| App in "Testing" mode | Only test users listed in the consent screen can sign in until the app is published. |

---

## GitHub

### 1. Register an OAuth App

1. Open [GitHub → Settings → Developer settings → OAuth Apps](https://github.com/settings/developers).
2. **New OAuth App**.
3. Fill in:
   - **Application name:** e.g. `Matcha (local)`
   - **Homepage URL:** `http://127.0.0.1:5001` (or your production URL)
   - **Authorization callback URL:** `http://127.0.0.1:5001/oauth/github/callback`

4. Create the app, then **Generate a new client secret**.

### 2. Configure `.env`

```env
GITHUB_CLIENT_ID=Ov23lixxxxxxxx
GITHUB_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

The app requests scope `user:email` so GitHub returns a verified primary email when the public profile email is hidden.

### 3. Test

1. Restart the app.
2. On login/register, click **Continue with GitHub**.

### GitHub troubleshooting

| Problem | What to check |
|---------|----------------|
| `redirect_uri` error | Callback URL in GitHub must match `url_for('oauth.github_callback', _external=True)` — same host/port you use in the browser. |
| No email / fallback address | User may hide email on GitHub; app falls back to primary verified email via API, or `github_<id>@oauth.local` if none is available. |
| `OAuth authentication failed` | Wrong client secret, or callback URL mismatch; check server logs. |

---

## 42 Intra

### 1. Create an OAuth application

1. Log in to [profile.intra.42.fr](https://profile.intra.42.fr/).
2. Go to [OAuth applications](https://profile.intra.42.fr/oauth/applications) (or **Settings** → **API** → **OAuth2**).
3. Create a new application.
4. Set **Redirect URI** to:
   - `http://127.0.0.1:5001/oauth/intra42/callback`
   - (production: `https://your-domain.com/oauth/intra42/callback`)
5. Note **UID** (client ID) and **SECRET** (client secret).

The app uses Intra API v2 with scope `public` and loads the current user from `GET /v2/me`.

### 2. Configure `.env`

```env
INTRA42_CLIENT_ID=your_uid
INTRA42_CLIENT_SECRET=your_secret
```

### 3. Test

1. Restart the app.
2. Click **Continue with 42 Intra** on login or register.
3. Authorize with your 42 account.

### 42 Intra troubleshooting

| Problem | What to check |
|---------|----------------|
| Invalid redirect URI | Redirect URI in the Intra app settings must match `/oauth/intra42/callback` on your base URL exactly. |
| `42 Intra OAuth is not configured` | `INTRA42_CLIENT_ID` not set. |
| `OAuth authentication failed` | Wrong secret, expired token, or API unreachable; verify credentials and redirect URI. |

---

## Production checklist

- [ ] Use **HTTPS** for all redirect URIs.
- [ ] Register production callback URLs on each provider (do not rely only on `127.0.0.1`).
- [ ] Store secrets only in `.env` on the server, never in git.
- [ ] Restrict OAuth app ownership to your team; rotate secrets if leaked.
- [ ] For Google: complete OAuth consent screen verification if the app is public.
- [ ] Open the site using the same host name registered with providers (avoid mixing `localhost` and `127.0.0.1`).

---

## Quick reference: callback URLs

Replace `BASE` with your site origin (no trailing slash).

| Provider | Callback URL |
|----------|----------------|
| Google | `BASE/oauth/google/callback` |
| GitHub | `BASE/oauth/github/callback` |
| 42 Intra | `BASE/oauth/intra42/callback` |

**Local default** (`python run.py`, `PORT` unset):

```text
http://127.0.0.1:5001/oauth/google/callback
http://127.0.0.1:5001/oauth/github/callback
http://127.0.0.1:5001/oauth/intra42/callback
```

---

## Related docs

- [email-smtp.md](email-smtp.md) — verification and reset emails (email/password accounts)
- [authentication.md](authentication.md) — Flask-Login, bcrypt, sessions
- [getting-started.md](getting-started.md) — install and run from scratch
- [README.md](../README.md) — project overview
