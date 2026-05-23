# Video chat (WebRTC + SocketIO signaling)

Matched users can conduct **peer-to-peer** audio/video calls. The Flask server never sees RTP packets — it only relays **signaling** (SDP and ICE) through SocketIO rooms.

Deep dive on SocketIO events: [realtime-socketio.md](realtime-socketio.md)

---

## Two layers

| Layer | Technology | Data |
|-------|------------|------|
| **Signaling** | Flask-SocketIO | SDP offer/answer, ICE candidates, call state |
| **Media** | WebRTC (`RTCPeerConnection`) | Encrypted audio/video between browsers |

```
     ┌──────────┐                      ┌──────────┐
     │ Browser A│◄──── WebRTC P2P ────►│ Browser B│
     └────┬─────┘                      └─────┬────┘
          │         offer/answer/ICE          │
          └──────────────┬────────────────────┘
                         ▼
                  Flask-SocketIO
              room: call_{min}_{max}
```

---

## Access control (HTTP gate)

Before any WebRTC code runs, user must load **`GET /videochat/call/<user_id>`**.

Checks in `videochat.py`:

```python
are_matched(current_user.id, user_id)   # mutual likes
not _is_blocked(...)                     # either direction
user exists
```

Failure → flash message, redirect to `/chat/`.

Entry from chat UI:

```html
<a href="{{ url_for('videochat.call', user_id=other.id) }}">📹 Call</a>
```

---

## Call room ID

Deterministic so both peers join the same SocketIO room without server assignment:

```python
room_id = f"call_{min(current_user.id, user_id)}_{max(current_user.id, user_id)}"
```

Users 3 and 17 → `call_3_17` whether user 3 or 17 opens the page first.

Passed to template as `data-room-id` on `#videochat-container`.

---

## Caller vs callee

| | Caller | Callee |
|---|--------|--------|
| Opens | `/videochat/call/17` | Accepts modal → `/videochat/call/3?incoming=1` |
| `data-incoming` | `0` | `1` |
| After media ready | `call_request` → target's modal | Waits for `offer` |
| On `user_joined` | Creates **offer** | (already in room) |
| On `offer` | — | Creates **answer** |

`isIncoming` prevents glare (both sides sending offer simultaneously).

---

## Outgoing call — detailed timeline

### Phase 1: Caller page load (`videochat.js`)

1. `startCall()` → `acquireLocalMedia()`  
   Tries `getUserMedia` with fallbacks: video+audio → facingMode user → video only → audio only
2. Local preview on `#local-video` (muted)
3. `socket.emit('join_call', { room, user_id })`
4. Server: `join_room(room)`, `active_calls[user_id]=room`, emit `user_joined` to others
5. If not incoming: `socket.emit('call_request', { target_user_id, caller_id, caller_name, room })`
6. Server emits `incoming_call` to room `user_{target}`

### Phase 2: Callee (`base.html` modal)

1. `socket.on('incoming_call')` — skip if already on `/videochat/call/`
2. Show modal with caller name
3. **Accept** → `window.location = '/videochat/call/' + caller_id + '?incoming=1'`
4. **Decline** → `socket.emit('call_declined', { room })`

### Phase 3: WebRTC negotiation

**Caller** on `user_joined`:

```javascript
peerConnection = new RTCPeerConnection(config);
localStream.getTracks().forEach(t => peerConnection.addTrack(t, localStream));
offer = await peerConnection.createOffer();
await peerConnection.setLocalDescription(offer);
socket.emit('offer', { room, offer });
```

**Callee** on `offer`:

```javascript
createPeerConnection();
await peerConnection.setRemoteDescription(offer);
answer = await peerConnection.createAnswer();
await peerConnection.setLocalDescription(answer);
socket.emit('answer', { room, answer });
```

**Both** on `ice_candidate`:

```javascript
await peerConnection.addIceCandidate(candidate);
```

Local `onicecandidate` emits each candidate to peer via server relay.

### Phase 4: Connected

`peerConnection.ontrack` → assign `event.streams[0]` to `#remote-video`, hide placeholder, status "Connected".

---

## Signaling handlers (`videochat.py`)

All relays use `include_self=False`:

```python
@socketio.on("offer")
def handle_offer(data):
    emit("offer", data, room=data.get("room"), include_self=False)
```

| Event | Server action |
|-------|---------------|
| `join_call` | Join room; notify others `user_joined` |
| `leave_call` | Leave room; `user_left`; remove from `active_calls` |
| `offer` / `answer` / `ice_candidate` | Forward payload to room |
| `call_request` | `incoming_call` → `user_{target_user_id}` |
| `call_declined` / `call_ended` | Broadcast to call room |

No auth re-check inside handlers — assumes HTTP page already validated match.

---

## STUN configuration

```javascript
iceServers: [
  { urls: 'stun:stun.l.google.com:19302' },
  { urls: 'stun:stun1.l.google.com:19302' }
]
```

STUN helps peers discover public addresses. **No TURN** — symmetric NAT / corporate firewall may block connection. Production apps often add a TURN server for relay fallback.

---

## Media error handling

`mediaErrorMessage(err)` maps browser errors:

| `err.name` | User message |
|------------|--------------|
| `NotAllowedError` | Permission blocked in browser |
| `NotFoundError` | No camera/mic |
| `NotReadableError` | Device busy |
| `SecurityError` | Need HTTPS or localhost |

---

## End call cleanup

```javascript
function endCall(notify) {
    peerConnection.close();
    localStream.getTracks().forEach(t => t.stop());
    if (notify) {
        socket.emit('call_ended', { room });
        socket.emit('leave_call', { room, user_id });
    }
    setTimeout(() => location.href = redirectUrl, 1000);  // back to chat
}
```

`beforeunload` also emits `leave_call` to release tracks.

Peer receives `call_ended` or `user_left` → local cleanup.

---

## In-memory state

```python
active_calls = {}  # user_id -> room_id
```

Lost on server restart. No persistence of call history.

---

## Requirements checklist

- [ ] `python run.py` (SocketIO running)
- [ ] Both users matched and logged in
- [ ] Callee has open page with SocketIO (for incoming modal)
- [ ] Camera/mic permission granted
- [ ] Use `http://127.0.0.1:5001` or HTTPS

---

## Related files

```
app/routes/videochat.py
app/static/js/videochat.js
app/templates/videochat/call.html
app/templates/base.html
docs/realtime-socketio.md
```
