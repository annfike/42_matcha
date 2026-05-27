#!/usr/bin/env python3

import os
import sys
import io
import ssl
import uuid
import random
import argparse
import urllib.request

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.database import query_one, query_all, execute, execute_returning, commit


MAX_IMAGES = 5


def _download_randomuser_portrait(gender: str, idx: int) -> Image.Image:
    if gender not in ("male", "female"):
        raise ValueError("gender must be 'male' or 'female'")
    url = f"https://randomuser.me/api/portraits/{'men' if gender == 'male' else 'women'}/{idx}.jpg"
    ssl_context = ssl._create_unverified_context()
    with urllib.request.urlopen(url, timeout=15, context=ssl_context) as resp:
        data = resp.read()
    return Image.open(io.BytesIO(data)).convert("RGB")


def _ensure_upload_folder(upload_folder: str) -> None:
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder, exist_ok=True)


def _delete_user_images(user_id: int, upload_folder: str) -> None:
    rows = query_all("SELECT id, filename FROM user_images WHERE user_id = %s", (user_id,))
    execute("UPDATE users SET profile_picture_id = NULL WHERE id = %s", (user_id,))
    execute("DELETE FROM user_images WHERE user_id = %s", (user_id,))
    commit()
    for r in rows:
        fn = r.get("filename")
        if not fn:
            continue
        path = os.path.join(upload_folder, fn)
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", type=int, help="Target user id")
    parser.add_argument("--username", type=str, help="Target username")
    parser.add_argument("--gender", choices=["male", "female"], required=True, help="Photo gender")
    parser.add_argument("--count", type=int, default=3, help="How many photos to add (default 3)")
    parser.add_argument("--replace", action="store_true", help="Delete existing user photos first")
    parser.add_argument("--set-main", action="store_true", help="Set first generated photo as main")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow exceeding MAX_IMAGES limit (not recommended)",
    )
    args = parser.parse_args()

    if not args.user_id and not args.username:
        print("Error: provide --user-id or --username", file=sys.stderr)
        return 2
    if args.user_id and args.username:
        print("Error: provide only one of --user-id or --username", file=sys.stderr)
        return 2
    if args.count <= 0:
        print("Error: --count must be > 0", file=sys.stderr)
        return 2

    app = create_app()
    with app.app_context():
        if args.user_id:
            user = query_one("SELECT id, username FROM users WHERE id = %s", (args.user_id,))
        else:
            user = query_one("SELECT id, username FROM users WHERE username = %s", (args.username,))
        if not user:
            print("Error: user not found", file=sys.stderr)
            return 1

        upload_folder = app.config.get("UPLOAD_FOLDER", "./app/uploads")
        _ensure_upload_folder(upload_folder)

        if args.replace:
            _delete_user_images(int(user["id"]), upload_folder)

        row = query_one("SELECT COUNT(*) AS cnt FROM user_images WHERE user_id = %s", (user["id"],))
        existing_count = int(row["cnt"]) if row else 0
        if not args.force and existing_count >= MAX_IMAGES:
            print(f"User already has {existing_count} photos (MAX {MAX_IMAGES}). Use --replace.", file=sys.stderr)
            return 1

        start_order_row = query_one(
            "SELECT COALESCE(MAX(upload_order), -1) AS m FROM user_images WHERE user_id = %s",
            (user["id"],),
        )
        start_order = int(start_order_row["m"]) + 1 if start_order_row else 0

        remaining = (MAX_IMAGES - existing_count) if not args.force else args.count
        to_add = min(args.count, remaining) if not args.force else args.count
        if to_add <= 0:
            print("Nothing to do (no remaining slots).", file=sys.stderr)
            return 0

        made_main = False
        for i in range(to_add):
            portrait_idx = random.randint(0, 99)
            try:
                img = _download_randomuser_portrait(args.gender, portrait_idx)
            except Exception as e:
                print(f"Warning: failed to download portrait: {e}", file=sys.stderr)
                continue

            filename = f"{uuid.uuid4().hex}.jpg"
            filepath = os.path.join(upload_folder, filename)
            img.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
            img.save(filepath, quality=90, optimize=True)

            is_profile = bool(args.set_main and not made_main and existing_count == 0 and i == 0)
            img_row = execute_returning(
                "INSERT INTO user_images (user_id, filename, is_profile_picture, upload_order) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (user["id"], filename, is_profile, start_order + i),
            )
            if is_profile:
                execute("UPDATE users SET profile_picture_id = %s WHERE id = %s", (img_row["id"], user["id"]))
                made_main = True

        if args.set_main and not made_main:
            first_new = query_one(
                "SELECT id FROM user_images WHERE user_id=%s ORDER BY upload_order ASC LIMIT 1",
                (user["id"],),
            )
            if first_new:
                execute("UPDATE user_images SET is_profile_picture=false WHERE user_id=%s", (user["id"],))
                execute("UPDATE user_images SET is_profile_picture=true WHERE id=%s", (first_new["id"],))
                execute("UPDATE users SET profile_picture_id=%s WHERE id=%s", (first_new["id"], user["id"]))

        commit()
        print(f"Done. User @{user['username']} now has photos in {upload_folder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
