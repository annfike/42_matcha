# Matcha — project architecture

A full guide to how the Matcha dating site is built: what each part of the application does, how data flows between the browser, the server, and the database, and how the main features fit together.

---

## Project structure

```
matcha/
├── run.py                    # Starts the web server with real-time support
├── requirements.txt          # Python dependencies
├── .env                      # Secrets and settings (not in git)
├── .env.example              # Template for environment variables
├── matcha.db                 # SQLite database file (created after init-db)
│
├── migrations/
│   └── schema.sql            # All table definitions (applied via flask init-db)
│
├── scripts/
│   └── seed_data.py          # Optional: hundreds of test profiles for demos
│
├── tests/                    # Automated tests (separate test database)
│
├── docs/                     # Documentation (this file and topic guides)
│
└── app/                      # Application code
    ├── __init__.py           # App factory: wires routes, extensions, middleware
    ├── config.py             # Settings loaded from environment
    ├── database.py           # SQLite access layer (no ORM)
    ├── models.py             # User object for login sessions
    │
    ├── routes/               # URL handlers grouped by feature
    │   ├── auth.py           # Register, login, email verify, password reset
    │   ├── profile.py        # Edit profile, photos, location, view others
    │   ├── browse.py         # Suggestions, search, like, block, report
    │   ├── chat.py           # Messaging + WebSocket presence
    │   ├── notifications.py  # Notification list and read state
    │   ├── map.py            # Map page and user markers API
    │   ├── oauth.py          # Sign in with Google / GitHub / 42 (optional)
    │   ├── events.py         # Date invitations between matches
    │   └── videochat.py      # Video call page + call signaling
    │
    ├── utils/                # Shared logic (matching, images, email, …)
    ├── templates/            # HTML pages and email layouts (Jinja2)
    ├── static/               # CSS and JavaScript served to the browser
    └── uploads/              # User photos stored on disk
```

**How to read this tree:** `run.py` is what you execute. Everything under `app/` is imported when the app starts. Routes answer HTTP requests; utilities hold business rules; templates render HTML. The database file lives at the project root unless you change the path in settings.

---

## Related documentation

| Document | Topic |
|----------|--------|
| [getting-started.md](getting-started.md) | Install, configure, first run |
| [authentication.md](authentication.md) | Accounts, sessions, passwords |
| [oauth-setup.md](oauth-setup.md) | Social login providers |
| [email-smtp.md](email-smtp.md) | Verification and reset emails |
| [file-uploads.md](file-uploads.md) | Photo upload and gallery |
| [geolocation.md](geolocation.md) | GPS and manual city |
| [map-leaflet.md](map-leaflet.md) | User map |
| [realtime-socketio.md](realtime-socketio.md) | Live chat and notifications |
| [videochat-webrtc.md](videochat-webrtc.md) | Video calls |
| [caching.md](caching.md) | Tag list cache |

---

## What Matcha is

Matcha is a **dating website** for the 42 school project. Users create an account, confirm their email, build a profile with photos and interests, discover other people through recommendations or search, like profiles, and when both sides like each other they become a **match** and can chat, schedule a date, or start a video call.

The application is a **single Flask monolith**: one Python process serves normal web pages and WebSocket connections. Data is stored in **SQLite** on disk. There is no separate API server, message queue, or microservices layer—simplicity is intentional.

---

## Technology stack

| Layer | Choice | Role in Matcha |
|-------|--------|----------------|
| Server | Flask 3 | HTTP routes, templates, JSON APIs |
| Database | SQLite | Users, likes, messages, notifications, events |
| Pages | Jinja2 + HTML/CSS | Server-rendered UI |
| Interactivity | Vanilla JavaScript | Chat, map, video, profile editor |
| Real-time | Flask-SocketIO | Push new messages, badges, call signaling |
| Email | Flask-Mail + SMTP | Verify account, reset password |
| Auth | Flask-Login + bcrypt | Sessions and password hashing |
| OAuth | Authlib (optional) | Google, GitHub, 42 Intra |
| Images | Pillow | Validate, resize, edit photos |
| Location | Browser geolocation + geopy | Coordinates and city names |
| Map | Leaflet + OpenStreetMap tiles | See users on a map |
| Video | WebRTC in the browser | Peer-to-peer audio/video |
| Cache | Flask-Caching (in-memory) | Speed up tag list on search page |

---

## Starting the application

**Recommended:** run `python run.py`. This starts Flask together with the Socket.IO server on port **5001** (or the port set in your environment). Chat delivery, notification badges, and video call signaling depend on this mode.

**Database setup:** once per environment, run `flask init-db` with `FLASK_APP=run.py`. That reads the SQL file under `migrations/` and creates all tables in the SQLite file.

**Not sufficient for full features:** `flask run` alone serves HTTP but does not run the real-time stack the same way; live chat and calls may not work.

Configuration (secret key, database path, mail server, OAuth keys, upload limits) comes from a `.env` file at the project root. See [getting-started.md](getting-started.md).

---

## How the application is assembled at startup

When the server starts, a factory function builds the Flask application:

1. **Configuration** is loaded from environment variables (secret key, database URL, mail settings, upload folder, optional OAuth client IDs).

2. **Extensions** are attached: password hashing, login manager, mail sender, WebSocket layer, CSRF protection, and a small cache for tag names.

3. **Database access** is registered so each incoming HTTP request gets its own SQLite connection, committed or rolled back when the request ends.

4. **Route modules** are registered under URL prefixes (`/auth`, `/profile`, `/browse`, `/chat`, and so on). Each module handles one area of the product.

5. **OAuth providers** are initialized only if at least one client ID is configured.

6. **Global middleware** runs before most pages: if you are logged in but your profile is incomplete, you are redirected to the profile editor with a message listing what is still missing.

7. **Static file serving** for uploaded photos is exposed under `/uploads/…`.

8. A **CLI command** `flask init-db` creates tables from the schema file.

The root URL `/` sends guests to login and logged-in users to the suggestions page.

---

## Request lifecycle (HTTP)

Understanding the order of operations helps when debugging “my change did not save” or “I see stale data.”

1. The browser sends an HTTP request (GET or POST).

2. Flask creates a fresh **request context**. The login system reads the session cookie and loads the current user from the database (including profile picture if set).

3. **Profile gate:** for most URLs, if the user is logged in but mandatory profile fields are missing, the server stops here and redirects to profile edit. Auth pages, profile edit itself, static files, upload URLs, lightweight count APIs, and WebSocket handshake paths are exempt.

4. The **matched route** runs: it reads or writes data through the database layer, may call helpers (matching score, send email, push a WebSocket event), and often calls an explicit **save** so the next step in the same request sees fresh data.

5. The server returns HTML (from a template) or JSON.

6. At the end of the request, the database connection is **committed** if nothing crashed, or **rolled back** if an error occurred, then **closed**. The next request opens a new connection.

WebSocket handlers (connect, disconnect, read messages, video signaling) run in **separate** request contexts with their own database connection—so online status updates inside a socket handler save immediately there too.

---

## Database layer (no ORM)

Matcha talks to SQLite directly with parameterized queries—user input is never pasted into SQL strings as raw text.

**One connection per HTTP request** is stored on Flask’s request-local storage. All reads and writes during that request share the same transaction until the request ends.

**Type conversion:** dates, datetimes, and boolean columns are converted when rows are read so templates and Python code work with normal Python types, not only strings.

**Inserts that need the new row id** use SQLite’s “returning” feature so the app gets the new primary key in one step (for example right after registration).

**Schema** defines users, photos, tags, likes, profile views, blocks, reports, messages, notifications, and events. Foreign keys are enforced. Full table list is in the migrations SQL file.

For deep detail on queries and transactions, the Russian architecture doc’s database section aligns with the same code; behavior is identical.

---

## Data model (conceptual)

**Users** hold account credentials, profile text, gender and preference, location coordinates, popularity score, online status, and a pointer to the main profile photo.

**Photos** are separate rows (up to five per user) with display order; one is marked as the profile picture.

**Tags** are a shared dictionary of interest names; users link to many tags through a join table.

**Likes** are directional (A likes B). A **match** exists when both directions are present.

**Profile views** log who opened whose profile (drives “fame” and “someone viewed you” notifications).

**Blocks** hide users from suggestions and prevent interaction.

**Reports** store moderator-style reports (reason text).

**Messages** are chat lines between two users, with a read flag.

**Notifications** are inbox rows (like, view, message, match, unlike, event) plus real-time pushes.

**Events** are date invitations between two matched users with status pending, accepted, declined, or cancelled.

---

## Authentication and sessions

**Registration** collects email, username, name, and password. Passwords must meet strength rules (length, mixed case, digit, no common dictionary words). The password is hashed before storage. A random verification token is stored; an email is sent with a link. The user cannot log in until they open that link.

**Login** checks username and password against the hash, requires verified email, then creates a **session** (signed cookie). The server marks the user as online and records last activity time.

**Logout** clears the session and marks the user offline.

**Password reset** emails a short-lived token; submitting a new password clears the token.

**OAuth** (optional) redirects to Google, GitHub, or 42 Intra. If the email already exists, the user is logged in; otherwise a new account is created with email already verified and a placeholder password hash. New OAuth users must still complete the profile form.

See [authentication.md](authentication.md) and [email-smtp.md](email-smtp.md).

---

## Profile completion gate

Before using suggestions, chat, map, or most social features, every logged-in user must have:

- Date of birth (18+), gender, sexual preference, non-empty biography  
- At least one interest tag  
- At least one photo with a valid main profile picture  
- Location: latitude and longitude saved; if they did not use device GPS, they must have typed a city or neighborhood name  

Until this is satisfied, navigation redirects to profile edit with a clear list of missing items. This matches the project subject requirements for a complete profile before browsing.

---

## Profile editing and photos

The profile editor updates name, email, birth date, gender, orientation, biography, and tags. Tags are normalized: hashes and punctuation stripped, lowercased, limited in count, stored in a shared tag table, and fully replaced on each save (not merged incrementally).

**Photos** upload through a form or drag-and-drop. The server checks file type and size, verifies the image with an imaging library, resizes large images, saves under a random filename, and records metadata in the database. The first photo becomes the profile picture automatically. Users can reorder photos (first in order becomes main), delete, or apply rotation/brightness edits on the server.

**Location** can be set by browser GPS (with optional reverse lookup of a place name) or by typing a city and geocoding it to coordinates. GPS mode and manual mode are stored differently so the app knows whether coordinates came from the device or from a declared area.

Viewing someone else’s profile records a view, sends them a notification, refreshes their popularity score, and shows distance if both have coordinates.

See [file-uploads.md](file-uploads.md) and [geolocation.md](geolocation.md).

---

## Recommendations and search

**Suggestions** show people you might like. The server builds a list of eligible users: verified email, not yourself, not blocked, compatible with your gender and preference settings, has location data, and passes optional filters (age, fame score, tags, max distance).

Each candidate gets a **score**: much higher weight for nearby distance (tiers at 10 km, 50 km, 100 km), plus points for shared tags and their fame rating. Results sort by score, age, distance, fame, or shared tags depending on user choice. Twenty profiles per page.

**Search** uses the same engine but only runs the query when the user submits the search form (so an empty search does not load everyone by default). Tag names for filters can come from a cached global list.

**Liking** requires both users to have a profile picture. A like notifies the other person. If they already liked you, both get a **match** notification and can open chat. Liking updates both users’ fame scores.

**Unlike** removes your like; if it broke a mutual match, the other user may get an “unlike” notification.

**Block** stops interaction and removes cross-likes. **Report** stores a reason for admins (no automated action in code).

---

## Fame rating

Popularity is a single integer on each user, recalculated when relevant:

- Ten points per like received  
- One point per profile view  
- Twenty points per mutual match  

It influences sort order and filters but is transparent on the profile stats section.

---

## Chat

Chat is only between **matches** (mutual likes) who have not blocked each other.

The **conversation list** is built from SQL that finds everyone you liked who also liked you, minus blocks. Conversations sort by most recent message. Unread counts come from messages addressed to you that are still marked unread.

Opening a chat marks incoming messages from that person as read.

**Sending a message** uses a normal HTTP POST with JSON: the server validates the relationship, saves the message and a notification row, commits, then pushes the text to the recipient’s browser over WebSocket. The sender’s UI updates from the HTTP response without waiting for the socket. This hybrid design keeps validation and CSRF on familiar HTTP paths while still feeling instant for the other person.

**Online status** updates when users connect or disconnect WebSocket (and on login/logout). The chat sidebar can show “Online” or last seen time.

See [realtime-socketio.md](realtime-socketio.md).

---

## Notifications

Every social action that should alert someone creates a row in the notifications table: profile view, like, match, unlike, new message, event invitation, event response, cancellation.

In parallel, a small WebSocket message tells an open browser to refresh badge counts in the header. The full history is on the notifications page; counts are fetched with a light HTTP endpoint when the badge needs updating.

Users can mark one notification or all as read.

---

## Map

The map page centers on your saved coordinates (or a default in Switzerland if none). JavaScript loads Leaflet, draws OpenStreetMap tiles, places a marker for you, then fetches up to two hundred other users who have location set, are verified, are not blocked, and plots them. Clicking a marker opens a popup with photo, online state, and a link to their profile.

The map does not filter by dating preference—only privacy (location shared) and blocks apply.

See [map-leaflet.md](map-leaflet.md).

---

## Events (date invitations)

Matched users can propose a meeting: title, description, date and time, optional place text. The invitee sees it in their events list with status **pending** and can accept or decline. The creator can cancel. Each step notifies the other party. Only creator and invitee can view an event’s detail page.

---

## Video calls

From chat, a match can open a video call page. The server checks match and block rules, then renders a page that requests camera and microphone access. **Media never passes through the server**—browsers connect peer-to-peer with WebRTC.

The server only relays **signaling**: which user joined the call room, session descriptions (offer/answer), and network candidates so the two browsers find each other. Incoming calls show a modal on any open page if the callee is connected via WebSocket. Call room names are derived from the two user ids so both sides join the same room without a central call registry.

See [videochat-webrtc.md](videochat-webrtc.md) and [realtime-socketio.md](realtime-socketio.md).

---

## Caching

The only cached data is the alphabetical list of tag names used on the search page, kept in memory for about ten minutes to avoid repeating the same database query. New tags created when someone saves their profile may not appear in search filters until the cache expires. Nothing else is cached—suggestions, profiles, and messages always read fresh data.

See [caching.md](caching.md).

---

## Frontend architecture

**Server-rendered pages** use a common layout: navigation, flash messages, notification and chat badges, and optional incoming-call dialog. Child templates fill in the main content area.

**JavaScript** is loaded per feature: chat page loads chat script; map loads Leaflet and map script; video page loads WebRTC logic. The base layout always opens a WebSocket for badges and incoming calls when logged in.

**Security in the browser:** message text from sockets is escaped before insertion into the DOM; forms use CSRF tokens; templates auto-escape HTML by default.

---

## Security overview

| Concern | Approach |
|---------|----------|
| SQL injection | Parameterized queries only |
| Cross-site scripting | Template escaping + input sanitization on forms |
| CSRF | Tokens on state-changing forms and JSON APIs |
| Password storage | Bcrypt hashes, never plain text |
| File uploads | Type and content checks, size limits, random stored names |
| Sessions | Signed cookies with a server secret |
| Secrets | Environment file excluded from version control |

---

## End-to-end user journey (diagram)

```
Register → verify email → login
    → complete profile (photos, tags, location)
    → browse suggestions / search
    → like → (mutual) match
    → chat ─┬→ schedule event
            └→ video call
```

---

## Architecture diagram

```
┌──────────────┐     HTTP / WebSocket      ┌─────────────────────────┐
│   Browser    │ ◄──────────────────────► │  Flask + Socket.IO       │
│  HTML/JS     │                           │  Routes + utilities     │
└──────────────┘                           └───────────┬─────────────┘
                                                       │
                                                       ▼
                                           ┌───────────────────────┐
                                           │  SQLite (matcha.db)   │
                                           └───────────────────────┘
                                                       │
                                           ┌───────────┴───────────┐
                                           ▼                       ▼
                                    Photo files on disk      SMTP (email)
```

---

## Testing and demo data

Automated tests use pytest with a separate test database file so production data is untouched. See `tests/TESTING.md`.

`scripts/seed_data.py` can populate hundreds of fictional profiles (Swiss cities, tags, likes) with a known test password for demos and evaluation.

---

## Operational notes

- **Single process** is assumed for development; multiple workers need shared Socket.IO configuration for video rooms and broadcasts to reach all users.
- **Email** must be configured for real verification in production; otherwise users stay unverified.
- **HTTPS** is required for camera access on non-localhost deployments.
- **Nominatim** (geocoding) should be used at low volume per OpenStreetMap policy.
