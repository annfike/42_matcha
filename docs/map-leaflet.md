# Interactive map (Leaflet.js)

The **Map** page (`/map/`) visualizes other users who have shared location data. It is a read-only view: markers come from SQLite via JSON; Leaflet handles pan/zoom and popups.

---

## Page load sequence

```
1. User navigates to GET /map/
2. @login_required + profile gate pass
3. map.index renders map/index.html
4. Template sets data-lat/lng from current_user (or Swiss default 46.5, 6.6)
5. Leaflet CSS/JS loaded from unpkg CDN
6. map.js runs:
   a. Initialize map centered on user
   b. Add OSM tile layer
   c. Place red "You are here" marker
   d. fetch(GET /map/users) → add blue markers + popups
```

No WebSocket — map does not live-update when users move (coords change only on profile save).

---

## Backend routes (`app/routes/map.py`)

### `GET /map/`

Returns HTML only. Passes to template:

- `current_user.latitude` / `longitude` for initial map center
- `url_for('map.users_json')` as `data-api`

### `GET /map/users`

**Auth:** required  
**Response:** JSON array, max **200** users

**Full SQL filter logic:**

```sql
WHERE u.email_verified = true
  AND u.latitude IS NOT NULL AND u.longitude IS NOT NULL
  AND (u.location_enabled = 1 OR trim(COALESCE(u.location_place, '')) <> '')
  AND u.id != :current_user_id
  AND u.id NOT IN (SELECT blocked_id FROM blocks WHERE blocker_id = :me)
  AND u.id NOT IN (SELECT blocker_id FROM blocks WHERE blocked_id = :me)
LIMIT 200
```

**Why `location_place` OR `location_enabled`:** same rule as matching — manual city users still appear if they declared a place.

**Per-row JSON:**

```json
{
  "id": 42,
  "username": "alice",
  "first_name": "Alice",
  "age": 28,
  "lat": 46.5197,
  "lng": 6.6323,
  "is_online": true,
  "photo": "a1b2c3.jpg"
}
```

- `age` from `calculate_age(birth_date)` — may be `null`
- `photo` is filename only; `null` if no profile picture

No server-side distance filter — all eligible users within limit shown globally (not “near me” radius on map API).

---

## Frontend (`app/static/js/map.js`)

### Map initialization

```javascript
var map = L.map('user-map').setView([defaultLat, defaultLng], 10);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);
```

Zoom level **10** — city/regional view.

### Current user marker

Custom `L.divIcon` — red circle with white border:

```javascript
L.marker([defaultLat, defaultLng], {icon: myIcon})
  .bindPopup('<strong>You are here</strong>');
```

If user has no coords, template defaults to **46.5, 6.6** (Switzerland) — map still loads but “You are here” may not reflect real position until profile updated.

### Other users

```javascript
fetch(apiUrl).then(r => r.json()).then(function(users) {
    users.forEach(function(u) {
        L.marker([u.lat, u.lng]).addTo(map).bindPopup(popupHtml);
    });
});
```

Popup HTML built as string:

- Photo: `/uploads/` + filename (not `url_for` — hardcoded path in JS)
- Online status text from `u.is_online`
- Link: `/profile/view/` + id

**XSS note:** `first_name` comes from DB sanitized at input; popup uses text in HTML string — names are restricted by `is_valid_name` at registration.

---

## Template (`app/templates/map/index.html`)

```html
<div id="user-map"
     data-lat="{{ current_user.latitude or 46.5 }}"
     data-lng="{{ current_user.longitude or 6.6 }}"
     data-api="{{ url_for('map.users_json') }}"></div>
```

Inline CSS: map height 500px, popup styling, green online color `#27ae60`.

Leaflet **1.9.4** from unpkg (CSS + JS).

---

## Data dependencies

| Requirement | Source |
|-------------|--------|
| User on map | Saved lat/lng via [geolocation.md](geolocation.md) |
| Verified email | `email_verified` |
| Visible to you | Not blocked either way |
| Profile photo in popup | Optional — placeholder if missing |
| Online badge | `users.is_online` from login/SocketIO |

---

## What the map does NOT do

- No marker clustering (MarkerCluster plugin not used)
- No “search this area” or radius filter
- No real-time position updates
- No gender/orientation filter on map endpoint
- No pagination beyond 200 cap

---

## Tile usage

Tiles from `tile.openstreetmap.org`. For production traffic, review [OSM tile usage policy](https://operations.osmfoundation.org/policies/tiles/) and consider self-hosted tiles or a commercial provider.

---

## Extending the map (conceptual)

To add “users within 50 km”:

1. Pass current user lat/lng to API (already known server-side)
2. Add haversine in SQL or filter in Python after query
3. Or use Leaflet `circle` + client filter (less secure for hidden users)

Current codebase intentionally keeps API simple.

---

## Related files

```
app/routes/map.py
app/templates/map/index.html
app/static/js/map.js
app/utils/matching.py     # shared calculate_age, location rules
```
