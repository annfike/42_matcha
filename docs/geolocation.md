# Geolocation (browser API + manual city)

Location drives **who you see** in suggestions and **where you appear** on the map. The app stores a fixed point per user (`latitude`, `longitude`) plus metadata about how it was obtained.

---

## Why three fields?

| Column | Purpose |
|--------|---------|
| `latitude`, `longitude` | Numeric point for haversine distance and map markers |
| `location_enabled` | `true` = coordinates from device GPS; `false` = geocoded from typed city |
| `location_place` | Human-readable label ("Kreuzberg, Berlin") |

**Subject rule:** you need coordinates for matching. If you refuse GPS (`location_enabled=false`), you must provide **city or neighborhood** in `location_place`.

Enforced in `get_profile_completion_status()` and `_user_ready_for_proximity_matching()`.

---

## System diagram

```
┌─────────────────────────────────────────────────────────┐
│ profile/edit.html (browser)                              │
│  • Detect my location → Geolocation API or IP fallback   │
│  • Save location → manual city text                      │
└────────────────────────┬────────────────────────────────┘
                         │ POST /profile/update-location (JSON)
                         ▼
┌─────────────────────────────────────────────────────────┐
│ profile.update_location (Flask)                          │
│  GPS path: validate coords → reverse geocode             │
│  Manual path: forward geocode city → coords              │
└────────────────────────┬────────────────────────────────┘
                         │ geopy Nominatim (HTTP to OSM)
                         ▼
┌─────────────────────────────────────────────────────────┐
│ SQLite users row updated → matching.py uses coords       │
└─────────────────────────────────────────────────────────┘
```

There is **no background tracking** — location updates only when the user clicks a button or on first-load auto-detect.

---

## API: `POST /profile/update-location`

**Auth:** `@login_required`  
**CSRF:** `X-CSRFToken` header  
**Body:** JSON

### GPS mode (`manual: false` or omitted)

**Request example:**

```json
{
  "latitude": 46.5197,
  "longitude": 6.6323,
  "manual": false,
  "place": "optional user hint"
}
```

**Server logic (`profile.py`):**

1. Parse floats; reject if outside lat [-90,90], lng [-180,180]
2. `UPDATE users SET latitude=?, longitude=?, location_enabled=true`
3. Call `reverse_geocode_neighborhood(lat, lng)` (Nominatim reverse)
4. `final_place = resolved_label OR client place hint`
5. If `final_place`: `UPDATE location_place`
6. `commit()` → JSON `{ success, place, latitude, longitude }`

### Manual mode (`manual: true`)

**Request:**

```json
{ "manual": true, "place": "Lausanne, Switzerland" }
```

**Server:**

1. Reject empty `place`
2. `geocode_place_to_coordinates(place)` → `(lat, lng)` or None
3. `UPDATE latitude, longitude, location_enabled=false, location_place=trimmed place`
4. JSON response same shape

If Nominatim cannot resolve the string → HTTP 400 with message to try another spelling.

---

## Geocoding module (`app/utils/reverse_geocode.py`)

Uses **geopy** `Nominatim` with user agent `MatchaSchoolProject/1.0`.

### Reverse (coords → label)

```python
loc = geolocator.reverse((lat, lng), zoom=18, language="en")
label = build_place_label_from_address(address_dict, display_name)
```

`build_place_label_from_address` prefers, in order:

- neighbourhood, suburb, quarter, city_district, district, hamlet
- then city, town, village, municipality
- fallback: first 3 parts of `display_name`

Max length **200** chars (`location_place` column limit).

### Forward (place → coords)

```python
loc = geolocator.geocode(place, language="en", exactly_one=True, timeout=12)
return (loc.latitude, loc.longitude)
```

Errors (`GeocoderTimedOut`, `GeocoderServiceError`, etc.) → `None` → API error to user.

**Policy:** [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/) — low volume, no bulk geocoding.

---

## Frontend behavior (`profile/edit.html`)

### `updateLocationGps(lat, lng)`

Called after successful coordinate acquisition. Optional `place` from text field sent as hint.

### `saveCityNoGps()`

Reads `#location_place` input → manual mode JSON.

### **Detect my location** button

```
if navigator.geolocation:
    getCurrentPosition(success → updateLocationGps, error → fallbackIpLocation)
else:
    fallbackIpLocation()
```

### IP fallback (`fallbackIpLocation`)

Fetches `https://ipapi.co/json/` → approximate lat/lng (city-level accuracy). Used when user denies GPS or browser lacks API.

**Note:** Third-party service; not used for high-precision matching, only bootstrap.

### Auto on page load

If `PROFILE_NEEDS_LOCATION` (no coords yet), page automatically tries GPS then IP — helps new users pass profile gate faster.

---

## Matching integration (`app/utils/matching.py`)

### Candidate SQL always includes:

```sql
u.latitude IS NOT NULL AND u.longitude IS NOT NULL
AND (u.location_enabled = 1 OR trim(COALESCE(u.location_place, '')) <> '')
```

Users with coords but empty place and GPS off are excluded.

### Haversine distance (km)

```python
R = 6371  # Earth radius km
# standard haversine formula on lat/lng radians
```

Used in:

- `score_user()` — distance buckets add 1000/500/200/… points
- `get_suggestions()` — optional filter `location_max` (km)
- `profile.view` — show distance to viewed user

### Empty suggestions

If current user fails `_user_ready_for_proximity_matching()` → `get_suggestions` returns `[]` immediately (no SQL for candidates).

---

## Privacy model

| Mode | What others infer |
|------|-------------------|
| GPS | Point near device location at save time |
| Manual | Center of geocoded city/area (may be imprecise) |
| IP fallback | Rough city/region |

Coordinates are **static** until user updates location again — no live GPS stream to server.

---

## Example user journeys

**A — GPS allowed:** Click Detect → browser returns 46.52, 6.63 → reverse geocode → "Lausanne, Vaud" saved → `location_enabled=1`.

**B — GPS denied:** Type "Geneva" → Save location → forward geocode → coords for Geneva center → `location_enabled=0`, `location_place="Geneva"`.

**C — New user:** Opens edit without coords → auto GPS prompt → if fail, IP → still may need manual place if reverse geocode empty and GPS off.

---

## Related files

```
app/routes/profile.py
app/utils/reverse_geocode.py
app/utils/profile_completion.py
app/utils/matching.py
app/templates/profile/edit.html
requirements.txt   # geopy==2.4.1
```

See also: [map-leaflet.md](map-leaflet.md)
