#!/usr/bin/env python3
import os
import sys
import random
import uuid
import argparse
import io
import urllib.request
import ssl
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, bcrypt
from app.database import query_one, query_all, execute, execute_returning, commit

FIRST_NAMES_M = [
    "James", "John", "Robert", "Michael", "David", "William", "Richard", "Joseph",
    "Thomas", "Christopher", "Charles", "Daniel", "Matthew", "Anthony", "Mark",
    "Donald", "Steven", "Paul", "Andrew", "Joshua", "Kenneth", "Kevin", "Brian",
    "George", "Timothy", "Ronald", "Edward", "Jason", "Jeffrey", "Ryan", "Jacob",
    "Gary", "Nicholas", "Eric", "Jonathan", "Stephen", "Larry", "Justin", "Scott",
    "Brandon", "Benjamin", "Samuel", "Raymond", "Gregory", "Frank", "Alexander",
    "Patrick", "Jack", "Dennis", "Jerry", "Tyler", "Aaron", "Jose", "Adam", "Nathan",
]
FIRST_NAMES_F = [
    "Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Elizabeth", "Susan",
    "Jessica", "Sarah", "Karen", "Lisa", "Nancy", "Betty", "Margaret", "Sandra",
    "Ashley", "Kimberly", "Emily", "Donna", "Michelle", "Dorothy", "Carol", "Amanda",
    "Melissa", "Deborah", "Stephanie", "Rebecca", "Sharon", "Laura", "Cynthia",
    "Kathleen", "Amy", "Angela", "Shirley", "Anna", "Brenda", "Pamela", "Emma",
    "Nicole", "Helen", "Samantha", "Katherine", "Christine", "Debra", "Rachel",
    "Carolyn", "Janet", "Catherine", "Maria", "Heather", "Diane", "Ruth", "Julie",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Turner", "Phillips", "Evans", "Parker", "Edwards", "Collins",
]
TAGS = [
    "hiking", "photography", "music", "movies", "travel", "cooking", "reading",
    "gaming", "fitness", "yoga", "dancing", "art", "coffee", "wine", "beer",
    "cats", "dogs", "nature", "beach", "mountains", "skiing", "snowboarding",
    "surfing", "climbing", "running", "cycling", "swimming", "camping", "fishing",
    "gardening", "painting", "writing", "poetry", "theater", "concerts", "festivals",
    "foodie", "vegan", "vegetarian", "sushi", "pizza", "tacos", "brunch", "bbq",
    "meditation", "spirituality", "astrology", "science", "technology", "programming",
]
BIOS = [
    "Love exploring new places and meeting new people.",
    "Coffee addict and bookworm.",
    "Looking for someone to share adventures with.",
    "Music lover and concert enthusiast.",
    "Foodie who loves trying new restaurants.",
    "Outdoor enthusiast and nature lover.",
    "Creative soul with a passion for art.",
    "Tech geek by day, gamer by night.",
    "Fitness junkie who enjoys a good workout.",
    "Simple person looking for genuine connections.",
    "Life is short, let's make it sweet.",
    "Always up for a spontaneous road trip.",
    "Dog parent looking for a partner in crime.",
    "Cat lover seeking someone special.",
    "Traveler with a wanderlust heart.",
]
CITIES = [
    (46.5197, 6.6323),
    (46.2044, 6.1432),
    (47.3769, 8.5417),
    (46.9480, 7.4474),
    (47.5596, 7.5886),
    (46.0037, 8.9511),
    (47.0502, 8.3093),
    (46.8499, 9.5329),
    (47.4245, 9.3767),
    (46.2018, 6.1466),
]


AVATAR_COLORS = [
    "#5b6cff", "#7c3aed", "#0891b2", "#2563eb", "#0f766e",
    "#15803d", "#c2410c", "#b91c1c", "#9333ea", "#1d4ed8",
]


def create_tags():
    for tag_name in TAGS:
        existing = query_one("SELECT id FROM tags WHERE name = %s", (tag_name,))
        if not existing:
            execute("INSERT INTO tags (name) VALUES (%s)", (tag_name,))
    commit()
    return query_all("SELECT id, name FROM tags")


def random_date(start_year=1985, end_year=2003):
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start
    random_days = random.randint(0, delta.days)
    return (start + timedelta(days=random_days)).date()


PLACE_NAMES = [
    "Lausanne", "Geneva", "Zürich", "Bern", "Basel", "Lugano", "Chur", "St. Gallen", "Zug", "Nyon",
]


def create_users(count=500):
    all_tags = create_tags()
    password_hash = bcrypt.generate_password_hash("Test1234!").decode("utf-8")
    users = []
    for i in range(count):
        gender = random.choice(["male", "female"])
        if gender == "male":
            first_name = random.choice(FIRST_NAMES_M)
        else:
            first_name = random.choice(FIRST_NAMES_F)
        last_name = random.choice(LAST_NAMES)
        username = f"{first_name.lower()}{last_name.lower()}{random.randint(1, 9999)}"
        email = f"{username}@example.com"
        if query_one("SELECT id FROM users WHERE username = %s", (username,)):
            continue
        if query_one("SELECT id FROM users WHERE email = %s", (email,)):
            continue
        city = random.choice(CITIES)
        lat = city[0] + random.uniform(-0.1, 0.1)
        lon = city[1] + random.uniform(-0.1, 0.1)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        last_seen = now - timedelta(minutes=random.randint(0, 10080))
        place_label = PLACE_NAMES[i % len(PLACE_NAMES)]
        row = execute_returning(
            "INSERT INTO users (username, email, password_hash, first_name, last_name, "
            "birth_date, gender, sexual_preference, biography, latitude, longitude, "
            "location_enabled, location_place, fame_rating, email_verified, is_online, last_seen) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true,%s,%s,true,%s,%s) RETURNING id",
            (
                username, email, password_hash, first_name, last_name,
                random_date(), gender,
                random.choice(["heterosexual", "homosexual", "bisexual"]),
                random.choice(BIOS), lat, lon,
                place_label,
                random.randint(0, 100), random.choice([True, False]), last_seen,
            ),
        )
        users.append({"id": row["id"], "username": username})
        if len(users) % 100 == 0:
            commit()
            print(f"Created {len(users)} users...")
    commit()
    print(f"Total users created: {len(users)}")
    for u in users:
        num_tags = random.randint(2, 6)
        selected = random.sample(all_tags, num_tags)
        for tag in selected:
            execute(
                "INSERT INTO user_tags (user_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (u["id"], tag["id"]),
            )
    commit()
    print("Tags assigned to users.")
    return users


def create_avatar_file(filepath, initials, color):
    image = Image.new("RGB", (512, 512), color=color)
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 180)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), initials, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (512 - text_width) / 2
    y = (512 - text_height) / 2 - 8
    draw.text((x, y), initials, fill="white", font=font)
    image.save(filepath, "PNG", optimize=True)


def create_profile_images_for_users():
    from flask import current_app
    users_without_images = query_all(
        "SELECT id, first_name, last_name FROM users "
        "WHERE id NOT IN (SELECT user_id FROM user_images)"
    )
    if not users_without_images:
        print("No users without images found.")
        return 0
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "./app/uploads")
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    created = 0
    for row in users_without_images:
        first = (row["first_name"] or "").strip()
        last = (row["last_name"] or "").strip()
        initials = ((first[:1] or "U") + (last[:1] or "")).upper()
        color = AVATAR_COLORS[row["id"] % len(AVATAR_COLORS)]
        filename = f"{uuid.uuid4().hex}.png"
        filepath = os.path.join(upload_folder, filename)
        create_avatar_file(filepath, initials, color)
        image_row = execute_returning(
            "INSERT INTO user_images (user_id, filename, is_profile_picture, upload_order) "
            "VALUES (%s, %s, true, 0) RETURNING id",
            (row["id"], filename),
        )
        execute(
            "UPDATE users SET profile_picture_id = %s WHERE id = %s",
            (image_row["id"], row["id"]),
        )
        created += 1
        if created % 100 == 0:
            commit()
            print(f"Created {created} profile images...")
    commit()
    print(f"Total profile images created: {created}")
    return created


def assign_real_photos_to_seeded_users():
    from flask import current_app
    users = query_all(
        "SELECT u.id, u.gender, u.profile_picture_id, ui.filename "
        "FROM users u "
        "LEFT JOIN user_images ui ON ui.id = u.profile_picture_id "
        "WHERE u.email LIKE %s "
        "ORDER BY u.id",
        ("%@example.com",),
    )
    if not users:
        print("No seeded users found for real photo assignment.")
        return 0
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "./app/uploads")
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    updated = 0
    ssl_context = ssl._create_unverified_context()
    for idx, row in enumerate(users):
        photo_idx = (row["id"] + idx) % 100
        if row["gender"] == "female":
            source_url = f"https://randomuser.me/api/portraits/women/{photo_idx}.jpg"
        else:
            source_url = f"https://randomuser.me/api/portraits/men/{photo_idx}.jpg"
        try:
            with urllib.request.urlopen(source_url, timeout=10, context=ssl_context) as resp:
                data = resp.read()
            img = Image.open(io.BytesIO(data)).convert("RGB")
        except Exception:
            continue
        filename = row["filename"]
        if not filename:
            filename = f"{uuid.uuid4().hex}.jpg"
            image_row = execute_returning(
                "INSERT INTO user_images (user_id, filename, is_profile_picture, upload_order) "
                "VALUES (%s, %s, true, 0) RETURNING id",
                (row["id"], filename),
            )
            execute(
                "UPDATE users SET profile_picture_id = %s WHERE id = %s",
                (image_row["id"], row["id"]),
            )
        filepath = os.path.join(upload_folder, filename)
        img.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
        img.save(filepath, quality=90, optimize=True)
        updated += 1
        if updated % 100 == 0:
            commit()
            print(f"Assigned {updated} real profile photos...")
    commit()
    print(f"Total seeded users with real photos: {updated}")
    return updated


def create_interactions(users, like_count=2000, view_count=5000):
    user_ids = [u["id"] for u in users]
    likes_created = 0
    for _ in range(like_count):
        liker_id = random.choice(user_ids)
        liked_id = random.choice(user_ids)
        if liker_id == liked_id:
            continue
        existing = query_one(
            "SELECT id FROM likes WHERE liker_id=%s AND liked_id=%s", (liker_id, liked_id)
        )
        if existing:
            continue
        execute("INSERT INTO likes (liker_id, liked_id) VALUES (%s, %s)", (liker_id, liked_id))
        likes_created += 1
        if likes_created % 500 == 0:
            commit()
    commit()
    print(f"Created {likes_created} likes.")
    views_created = 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for _ in range(view_count):
        viewer_id = random.choice(user_ids)
        viewed_id = random.choice(user_ids)
        if viewer_id == viewed_id:
            continue
        viewed_at = now - timedelta(minutes=random.randint(0, 43200))
        execute(
            "INSERT INTO profile_views (viewer_id, viewed_id, viewed_at) VALUES (%s, %s, %s)",
            (viewer_id, viewed_id, viewed_at),
        )
        views_created += 1
        if views_created % 1000 == 0:
            commit()
    commit()
    print(f"Created {views_created} profile views.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--images-only", action="store_true")
    parser.add_argument("--real-photos", action="store_true")
    args = parser.parse_args()
    app = create_app()
    with app.app_context():
        if args.real_photos:
            print("Assigning real photos to seeded users...")
            assign_real_photos_to_seeded_users()
            print("Real photo assignment complete!")
            return
        if args.images_only:
            print("Generating profile images for existing users...")
            create_profile_images_for_users()
            print("Image generation complete!")
            return
        print("Starting seed data generation...")
        users = create_users(500)
        if users:
            create_interactions(users)
        create_profile_images_for_users()
        print("Seed data generation complete!")

        print("Assigning real photos to seeded users (fallbacks may remain)...")
        assign_real_photos_to_seeded_users()
        print("Real photo assignment complete!")


if __name__ == "__main__":
    main()
