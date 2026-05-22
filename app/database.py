import os
import sqlite3
from datetime import date, datetime
from flask import g

sqlite3.register_adapter(
    datetime,
    lambda val: val.isoformat(sep=" ", timespec="seconds"),
)
sqlite3.register_adapter(date, lambda val: val.isoformat())

_db_path = None
_schema_path = None


def _parse_database_url(url):
    if url.startswith("sqlite:///"):
        path = url[len("sqlite:///") :]
    elif url.startswith("sqlite://"):
        path = url[len("sqlite://") :]
    else:
        path = url
    if not os.path.isabs(path):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, path)
    return os.path.abspath(path)


def _schema_file():
    global _schema_path
    if _schema_path is None:
        _schema_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "migrations",
            "schema.sql",
        )
    return _schema_path


def init_db(app):
    global _db_path
    url = app.config.get("DATABASE_URL") or app.config.get(
        "SQLALCHEMY_DATABASE_URI", "sqlite:///matcha.db"
    )
    _db_path = _parse_database_url(url)
    directory = os.path.dirname(_db_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    app.teardown_appcontext(_teardown)


def _connect():
    conn = sqlite3.connect(_db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    if "db_conn" not in g:
        g.db_conn = _connect()
    return g.db_conn


def _teardown(exc=None):
    conn = g.pop("db_conn", None)
    if conn is not None:
        if exc is None:
            try:
                conn.commit()
            except Exception:
                conn.rollback()
        else:
            conn.rollback()
        conn.close()


def _adapt_sql(sql):
    return sql.replace("%s", "?")


_BOOL_COLUMNS = frozenset({
    "email_verified",
    "location_enabled",
    "is_online",
    "is_read",
    "is_profile_picture",
})
_DATE_COLUMNS = frozenset({"birth_date"})
_DATETIME_COLUMNS = frozenset({
    "created_at",
    "updated_at",
    "last_seen",
    "viewed_at",
    "reset_token_expiry",
    "event_date",
})


def _parse_date(value):
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def _parse_datetime(value):
    text = value.strip()
    if len(text) == 10:
        return datetime.strptime(text, "%Y-%m-%d")
    if "." in text:
        return datetime.strptime(text[:26], "%Y-%m-%d %H:%M:%S.%f")
    return datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S")


def _normalize_cell(key, value):
    if value is None:
        return None
    if key in _BOOL_COLUMNS:
        return bool(value)
    if key in _DATE_COLUMNS and isinstance(value, str):
        return _parse_date(value)
    if key in _DATETIME_COLUMNS and isinstance(value, str):
        return _parse_datetime(value)
    return value


def _row_to_dict(row):
    if row is None:
        return None
    return {key: _normalize_cell(key, row[key]) for key in row.keys()}


def query_one(sql, params=None):
    conn = get_db()
    cur = conn.execute(_adapt_sql(sql), params or ())
    return _row_to_dict(cur.fetchone())


def query_all(sql, params=None):
    conn = get_db()
    cur = conn.execute(_adapt_sql(sql), params or ())
    return [_row_to_dict(r) for r in cur.fetchall()]


def execute(sql, params=None):
    conn = get_db()
    cur = conn.execute(_adapt_sql(sql), params or ())
    return cur.rowcount


def execute_returning(sql, params=None):
    conn = get_db()
    cur = conn.execute(_adapt_sql(sql), params or ())
    return _row_to_dict(cur.fetchone())


def commit():
    conn = g.get("db_conn")
    if conn:
        conn.commit()


def rollback():
    conn = g.get("db_conn")
    if conn:
        conn.rollback()


def apply_schema(conn=None):
    conn = conn or get_db()
    with open(_schema_file()) as f:
        conn.executescript(f.read())


def reset_schema(conn=None):
    conn = conn or get_db()
    conn.executescript(
        "PRAGMA foreign_keys = OFF;"
        "DROP TABLE IF EXISTS events;"
        "DROP TABLE IF EXISTS notifications;"
        "DROP TABLE IF EXISTS messages;"
        "DROP TABLE IF EXISTS reports;"
        "DROP TABLE IF EXISTS blocks;"
        "DROP TABLE IF EXISTS profile_views;"
        "DROP TABLE IF EXISTS likes;"
        "DROP TABLE IF EXISTS user_tags;"
        "DROP TABLE IF EXISTS tags;"
        "DROP TABLE IF EXISTS user_images;"
        "DROP TABLE IF EXISTS users;"
        "PRAGMA foreign_keys = ON;"
    )
    apply_schema(conn)


def to_obj(row):
    from types import SimpleNamespace

    if row is None:
        return None
    return SimpleNamespace(**row)


def to_objs(rows):
    from types import SimpleNamespace

    return [SimpleNamespace(**r) for r in rows]
