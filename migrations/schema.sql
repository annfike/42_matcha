CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(128) NOT NULL,
    first_name VARCHAR(80) NOT NULL,
    last_name VARCHAR(80) NOT NULL,
    birth_date DATE,
    gender TEXT CHECK (gender IN ('male', 'female', 'other')),
    sexual_preference TEXT CHECK (sexual_preference IN ('heterosexual', 'homosexual', 'bisexual')),
    biography TEXT,
    profile_picture_id INTEGER,
    latitude REAL,
    longitude REAL,
    location_enabled INTEGER DEFAULT 0,
    location_place VARCHAR(200),
    fame_rating INTEGER DEFAULT 0,
    email_verified INTEGER DEFAULT 0,
    verification_token VARCHAR(128),
    reset_token VARCHAR(128),
    reset_token_expiry TEXT,
    is_online INTEGER DEFAULT 0,
    last_seen TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_users_username ON users (username);
CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);

CREATE TABLE IF NOT EXISTS user_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    filename VARCHAR(255) NOT NULL,
    is_profile_picture INTEGER DEFAULT 0,
    upload_order INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_user_images_user_id ON user_images (user_id);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS user_tags (
    user_id INTEGER REFERENCES users(id),
    tag_id INTEGER REFERENCES tags(id),
    PRIMARY KEY (user_id, tag_id)
);

CREATE INDEX IF NOT EXISTS ix_user_tags_tag_id ON user_tags (tag_id);

CREATE TABLE IF NOT EXISTS likes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    liker_id INTEGER NOT NULL REFERENCES users(id),
    liked_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (liker_id, liked_id)
);

CREATE INDEX IF NOT EXISTS ix_likes_liker_id ON likes (liker_id);
CREATE INDEX IF NOT EXISTS ix_likes_liked_id ON likes (liked_id);

CREATE TABLE IF NOT EXISTS profile_views (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    viewer_id INTEGER NOT NULL REFERENCES users(id),
    viewed_id INTEGER NOT NULL REFERENCES users(id),
    viewed_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_profile_views_viewed_at ON profile_views (viewed_id, viewed_at);

CREATE TABLE IF NOT EXISTS blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blocker_id INTEGER NOT NULL REFERENCES users(id),
    blocked_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (blocker_id, blocked_id)
);

CREATE INDEX IF NOT EXISTS ix_blocks_blocker_id ON blocks (blocker_id);
CREATE INDEX IF NOT EXISTS ix_blocks_blocked_id ON blocks (blocked_id);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER NOT NULL REFERENCES users(id),
    reported_id INTEGER NOT NULL REFERENCES users(id),
    reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER NOT NULL REFERENCES users(id),
    receiver_id INTEGER NOT NULL REFERENCES users(id),
    content TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_messages_receiver_read ON messages (receiver_id, is_read, created_at);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    type TEXT NOT NULL CHECK (type IN ('like', 'view', 'message', 'match', 'unlike', 'event')),
    related_user_id INTEGER REFERENCES users(id),
    message_id INTEGER REFERENCES messages(id),
    is_read INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_notifications_user_read ON notifications (user_id, is_read, created_at);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id INTEGER NOT NULL REFERENCES users(id),
    invitee_id INTEGER NOT NULL REFERENCES users(id),
    title VARCHAR(200) NOT NULL,
    description TEXT,
    event_date TEXT NOT NULL,
    location VARCHAR(300),
    latitude REAL,
    longitude REAL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'declined', 'cancelled')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
