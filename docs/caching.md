# Caching (Flask-Caching)

Matcha uses [Flask-Caching](https://flask-caching.readthedocs.io/) to cache one expensive-but-rarely-changing dataset: the **global tag list** on the search page. Everything else hits SQLite on every request.

---

## Why cache tags?

Tags are stored normalized in `tags` + `user_tags`. The search UI needs a dropdown of existing tag names so users can filter by interest.

Query:

```sql
SELECT id, name FROM tags ORDER BY name LIMIT 100
```

As the user base grows, this query runs on every `/browse/search` page view. Tags change infrequently (only when someone adds a new tag to their profile), so caching for 10 minutes is a good tradeoff.

---

## Initialization (`app/__init__.py`)

```python
cache = Cache()

cache.init_app(app, config={
    "CACHE_TYPE": app.config.get("CACHE_TYPE", "SimpleCache"),
    "CACHE_DEFAULT_TIMEOUT": app.config.get("CACHE_DEFAULT_TIMEOUT", 300),
})
```

| Setting | Default | Meaning |
|---------|---------|---------|
| `CACHE_TYPE` | `SimpleCache` | Python dict in process memory |
| `CACHE_DEFAULT_TIMEOUT` | `300` | 5 minutes for functions without explicit timeout |

No env vars in `.env.example` — defaults always apply unless you extend `Config`.

---

## Cached function

```python
@cache.cached(timeout=600, key_prefix="all_tags")
def get_all_tags():
    rows = query_all("SELECT id, name FROM tags ORDER BY name LIMIT 100")
    return [SimpleNamespace(**r) for r in rows]
```

### How `@cache.cached` works

1. First call: runs function body, stores return value in cache under key derived from `key_prefix` + function args (no args here → single key)
2. Subsequent calls within **600 seconds**: returns cached list without SQL
3. After TTL expires: next call refreshes from DB

**Important:** cached value is a list of `SimpleNamespace` objects in memory — not JSON serialized.

### Where it is used

```python
# browse.search route
all_tags = get_all_tags()
return render_template("browse/search.html", ..., all_tags=all_tags)
```

Suggestions page (`/browse/suggestions`) does **not** call `get_all_tags` — only search page needs the full tag picklist.

---

## Tag creation path (cache miss source)

When user saves profile (`profile.edit` POST):

```python
def set_user_tags(user_id, tag_names):
    DELETE user_tags for user
    for each tag:
        canonical_tag_name(raw)
        SELECT or INSERT INTO tags (name)
        INSERT INTO user_tags
    commit()
```

New tag names appear in DB immediately but may **not** appear in search dropdown until cache TTL expires (600 s).

---

## What is NOT cached

| Data | Always fresh from DB |
|------|----------------------|
| Suggestions / search results | Per-user matching query |
| User profiles | |
| Messages, notifications | |
| Map `/map/users` JSON | |
| `get_all_tags` on suggestions | Not used there |
| Session / `current_user` | Flask-Login each request |

---

## Invalidation strategies (not implemented)

Current code: **time-based expiry only**.

To fix stale tags immediately after profile save, add to `set_user_tags`:

```python
from app import cache
cache.delete("all_tags")  # key must match Flask-Caching internal key
# or: cache.clear()
```

Flask-Caching key format may include prefix; test in dev or use `cache.delete_memoized(get_all_tags)`.

---

## Production considerations

### Multiple workers

`SimpleCache` is **per process**. With Gunicorn `-w 4`, each worker has its own cache — same tag query may run once per worker on cold start, not once globally.

**Upgrade path:**

```python
CACHE_TYPE = "RedisCache"
CACHE_REDIS_URL = "redis://localhost:6379/0"
```

### Tests

If tests share app instance and call `get_all_tags` after inserting tags, either:

- Wait for TTL (bad)
- Clear cache in fixture
- Use `TESTING` config with `CACHE_TYPE="NullCache"` or `SimpleCache` + clear between tests

---

## Mental model

```
GET /browse/search
    │
    ▼
get_all_tags()
    │
    ├─ cache HIT  → return list (no SQL)
    │
    └─ cache MISS → SELECT tags → store 600s → return list
```

Single cache entry for entire app — not per user.

---

## Related files

```
app/__init__.py
app/routes/browse.py      # get_all_tags, search template
app/routes/profile.py     # set_user_tags (creates new tags)
app/utils/tags.py         # canonical_tag_name
requirements.txt          # Flask-Caching==2.1.0
```
