# OAuth setup (Google, GitHub, 42 Intra)

Matcha supports optional social login via [Authlib](https://docs.authlib.org/). Each provider is enabled independently by setting client credentials in `.env`. Buttons appear on **Login** and **Register** only when the corresponding `*_CLIENT_ID` is set.

## How it works in this app

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

---

## Before you start

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

- [getting-started.md](getting-started.md) — install and run from scratch
- [README.md](../README.md) — project overview
