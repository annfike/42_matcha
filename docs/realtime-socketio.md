# Real-time layer: Flask-SocketIO

Matcha uses **Flask-SocketIO** for live chat delivery, instant notification badges, online presence, and WebRTC call signaling. This document explains how the pieces connect; video media details are in [videochat-webrtc.md](videochat-webrtc.md).

---

## Design: hybrid HTTP + WebSocket

Matcha deliberately **does not** send chat messages over SocketIO from client to server.

| Action | Channel | Why |
|--------|---------|-----|
| Send message | HTTP `POST /chat/send` | CSRF validation, `login_required`, easy error JSON |
| Deliver message | SocketIO `new_message` | Push to recipient without poll |
| Persist message | SQLite `messages` | Source of truth |
| Badge update | SocketIO `notification` + HTTP count refresh | Instant hint + accurate count |

Benefits:

- Same validation stack as other JSON routes
- Message saved even if recipient offline (they see it on next page load)
- Sender gets immediate HTTP response to render own bubble

Drawback: requires SocketIO server process (`python run.py`).

---

## Process model

```
run.py
  socketio.run(app, host="0.0.0.0", port=5001)
       │
       ├── Werkzeug/Flask HTTP (routes, templates)
       └── python-socketio + eventlet (WebSocket / long-polling)
```

Dependencies:

- `Flask-SocketIO==5.3.6`
- `python-socketio==5.10.0`
- `eventlet==0.33.3`

Client: Socket.IO **4.6.0** from CDN; `var socket = io();` connects to same origin `/socket.io/`.

---

## Server singleton

```python
# app/__init__.py
socketio = SocketIO()

def create_app():
    socketio.init_app(app, cors_allowed_origins="*")
```

Imported everywhere emits happen:

```python
from app import socketio
socketio.emit("new_message", {...}, room=f"user_{receiver_id}")
```

`cors_allowed_origins="*"` — permissive for dev; restrict in production if frontends are split.

---

## Rooms

| Room | Join when | Members | Events |
|------|-----------|---------|--------|
| `user_{id}` | SocketIO `connect` if logged in | That user's browser tabs | `new_message`, `notification`, `incoming_call` |
| `call_{min}_{max}` | `join_call` on video page | Two peers in one call | `offer`, `answer`, `ice_candidate`, … |

Rooms are server-side labels — clients never subscribe by name directly; server `join_room()` on their socket.

---

## Authentication on WebSocket

Flask-Login stores user id in **signed session cookie**. Browser sends cookie on SocketIO handshake.

```python
@socketio.on("connect")
def handle_connect():
    if current_user.is_authenticated:
        join_room(f"user_{current_user.id}")
        execute("UPDATE users SET is_online=true, last_seen=? ...")
```

Anonymous users: connect succeeds but no personal room → no targeted events.

**Same session** as HTTP — logging out invalidates future loads; existing socket may disconnect on next navigation.

---

## 1. Chat

### Match list (`get_matches`)

Chat is only with **mutual likes**:

```sql
SELECT u.id, ...
FROM users u
WHERE u.id IN (
  SELECT l1.liked_id FROM likes l1
  JOIN likes l2 ON l1.liker_id = l2.liked_id AND l1.liked_id = l2.liker_id
  WHERE l1.liker_id = :me
)
AND u.id NOT IN (SELECT blocked_id FROM blocks WHERE blocker_id = :me)
AND u.id NOT IN (SELECT blocker_id FROM blocks WHERE blocked_id = :me)
```

`chat.index` sorts conversations by last message time; shows unread count per match.

### Opening conversation — HTTP

`GET /chat/<user_id>`:

1. Verify match + not blocked
2. `UPDATE messages SET is_read=true WHERE sender_id=other AND receiver_id=me`
3. Render history from `get_conversation` (last 100 messages, chronological)

### Sending — HTTP + emit

`POST /chat/send` body: `{ receiver_id, content }`

| Step | Code |
|------|------|
| Validate match | `is_match(me, receiver)` |
| Validate block | `is_blocked` |
| Truncate | 2000 chars |
| INSERT | `messages` + `notifications` type `message` |
| commit | |
| emit | `new_message` + `notification` → `room=user_{receiver}` |

Emit payload (`new_message`):

```python
{
    "id": msg["id"],
    "sender_id": current_user.id,
    "sender_name": current_user.first_name,
    "content": content,
    "created_at": "2025-01-15 14:30",  # formatted string
}
```

### Receiver client (`chat.js`)

```javascript
socket.on('connect', function() {
    socket.emit('mark_read', {sender_id: receiverId});
});

socket.on('new_message', function(data) {
    if (data.sender_id === receiverId) {
        // append DOM bubble, escapeHtml(content)
        socket.emit('mark_read', {sender_id: receiverId});
    }
});
```

Sender uses `fetch(POST /chat/send)` and appends bubble from JSON response — does not wait for SocketIO echo.

### Read receipts

| Path | SQL |
|------|-----|
| Open conversation page | `UPDATE messages SET is_read=true WHERE sender_id=other AND receiver_id=me` |
| SocketIO `mark_read` | Same WHERE with `sender_id` from payload |

Unread badge: `GET /chat/unread-count` → `COUNT(*) WHERE receiver_id=me AND is_read=false`.

---

## 2. Notifications

### Database row

```sql
INSERT INTO notifications (user_id, type, related_user_id, message_id)
VALUES (?, 'like'|'view'|'message'|'match'|'unlike'|'event', ?, ?)
```

`message_id` only for type `message`.

### Real-time push

```python
# app/utils/notifications.py
def emit_notification(user_id, notif_type, from_user):
    socketio.emit("notification", {
        "type": notif_type,
        "from_user_id": from_user.id,
        "from_user_name": from_user.first_name,
    }, room=f"user_{user_id}")
```

### Emit call sites

| Route | type | DB insert | emit |
|-------|------|-----------|------|
| `profile.view` | view | yes | yes |
| `browse.like` | like or match | yes | yes |
| `browse.unlike` | unlike (if was match) | yes | yes |
| `chat.send_message` | message | yes | yes (+ new_message) |
| `events.create` | event | yes | yes |
| `events.respond` | event | yes | yes |
| `events.cancel` | event | yes | yes |

### Global UI (`base.html`)

On every authenticated page:

1. `io()` connection → auto `join_room user_{id}` via server connect handler
2. Initial `fetch(/notifications/count)` and `fetch(/chat/unread-count)`
3. On `notification` or `new_message` event → re-fetch both endpoints

**Why re-fetch HTTP counts?** Socket payload is minimal; DB is authoritative; avoids desync if event missed.

History page: `GET /notifications/` renders last 50 with text from `get_notification_text(type, name)`.

---

## 3. Video signaling

See [videochat-webrtc.md](videochat-webrtc.md) for WebRTC timeline.

SocketIO role: relay SDP/ICE between `call_{min}_{max}` and send `incoming_call` to `user_{callee}`.

Handlers live in `videochat.py` — registered on same `socketio` instance as chat handlers.

---

## 4. Online presence

| Event | `is_online` | `last_seen` |
|-------|-------------|-------------|
| HTTP login | true | now |
| HTTP logout | false | now |
| WS connect | true | now |
| WS disconnect | false | now |

Shown in chat sidebar (“Online” / “Last seen HH:MM”) and map popups.

**Multi-tab caveat:** Tab A disconnect may set offline while Tab B still open.

---

## Client connections per page

| Page | SocketIO clients |
|------|------------------|
| Any page (logged in) | `base.html` — badges + incoming call |
| Chat conversation | `base.html` + `chat.js` (second `io()` — two connections) |
| Video call | `base.html` + `videochat.js` |

Multiple `io()` instances per tab are normal for Socket.IO client; each triggers server `connect` handler.

---

## Profile gate exception

`before_request` blocks incomplete profiles from most routes but allows:

```python
"/socket.io/"
"/notifications/count"
"/chat/unread-count"
```

So users finishing profile can still maintain WebSocket and poll counts.

---

## Event reference

### Server → client

| Event | Room | Payload |
|-------|------|---------|
| `new_message` | `user_{receiver}` | id, sender_id, sender_name, content, created_at |
| `notification` | `user_{id}` | type, from_user_id, from_user_name |
| `incoming_call` | `user_{target}` | caller_id, caller_name, room |
| `user_joined` | call room | user_id |
| `user_left` | call room | user_id |
| `offer` / `answer` / `ice_candidate` | call room | WebRTC payloads |
| `call_declined` / `call_ended` | call room | {} |

### Client → server

| Event | Handler file | Effect |
|-------|--------------|--------|
| `connect` / `disconnect` | chat.py | join/leave user room, online status |
| `mark_read` | chat.py | UPDATE messages |
| `join_call` / `leave_call` | videochat.py | call room membership |
| `offer` / `answer` / `ice_candidate` | videochat.py | relay |
| `call_request` | videochat.py | incoming_call to callee |
| `call_declined` / `call_ended` | videochat.py | relay |

---

## Sequence: like notification

```
User A likes User B (HTTP POST /browse/like/B)
    → INSERT notifications (user_id=B, type='like', related_user_id=A)
    → commit
    → emit_notification(B, 'like', A)
    → socketio.emit('notification', {...}, room='user_B')
User B browser (any page)
    → socket handler fires
    → fetch /notifications/count
    → update badge DOM
```

---

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| Messages in DB but not live | `flask run` instead of `python run.py` |
| Badge stuck at 0 | SocketIO failed; check Network tab for `/socket.io/` |
| Double connect errors | Firewall/proxy blocking WebSocket; try polling transport |
| Modal never shows | Callee offline; no active session; not matched |
| Works locally, not remote | Deploy without SocketIO worker; use `socketio.run` or compatible ASGI |

---

## Related documentation

| Doc | Topic |
|-----|--------|
| [videochat-webrtc.md](videochat-webrtc.md) | WebRTC peer connection |
| [authentication.md](authentication.md) | Sessions |
| [architecture-ru.md](architecture-ru.md) | Full app (Russian) |

## Related files

```
app/__init__.py
run.py
app/routes/chat.py
app/routes/videochat.py
app/utils/notifications.py
app/routes/notifications.py
app/static/js/chat.js
app/static/js/videochat.js
app/templates/base.html
app/templates/chat/conversation.html
```
