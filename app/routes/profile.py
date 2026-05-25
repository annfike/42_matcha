from datetime import date, datetime, timezone
from types import SimpleNamespace
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app.database import query_one, query_all, execute, execute_returning, commit, rollback, get_db
from app.models import make_user
from app.utils.security import sanitize_string
from app.utils.images import save_image, delete_image_file
from app.utils.fame import update_user_fame
from app.utils.matching import calculate_age, haversine_distance
from app.utils.notifications import emit_notification
from app.utils.tags import canonical_tag_name, split_tags_input
from app.utils.reverse_geocode import reverse_geocode_neighborhood, geocode_place_to_coordinates

profile_bp = Blueprint("profile", __name__)

MAX_IMAGES = 5
MAX_TAGS = 10


def get_user_tags(user_id):
    rows = query_all(
        "SELECT t.name FROM tags t JOIN user_tags ut ON t.id = ut.tag_id WHERE ut.user_id = %s",
        (user_id,),
    )
    return [r["name"] for r in rows]


def set_user_tags(user_id, tag_names):
    execute("DELETE FROM user_tags WHERE user_id = %s", (user_id,))
    seen = set()
    for raw in tag_names[:MAX_TAGS]:
        name = canonical_tag_name(raw)
        if not name or name in seen:
            continue
        seen.add(name)
        tag = query_one("SELECT id FROM tags WHERE name = %s", (name,))
        if not tag:
            tag = execute_returning("INSERT INTO tags (name) VALUES (%s) RETURNING id", (name,))
        execute(
            "INSERT INTO user_tags (user_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (user_id, tag["id"]),
        )
    commit()


def _render_profile_edit(user):
    imgs = [
        SimpleNamespace(**r)
        for r in query_all(
            "SELECT * FROM user_images WHERE user_id = %s ORDER BY upload_order",
            (user.id,),
        )
    ]
    return render_template(
        "profile/edit.html",
        user=user,
        tags=get_user_tags(user.id),
        images=imgs,
        today_iso=date.today().isoformat(),
    )


@profile_bp.route("/")
@profile_bp.route("/edit", methods=["GET", "POST"])
@login_required
def edit():
    user = current_user
    if request.method == "POST":
        first_name = sanitize_string(request.form.get("first_name"), 80)
        last_name = sanitize_string(request.form.get("last_name"), 80)
        email = sanitize_string(request.form.get("email"), 120)
        birth_date_str = request.form.get("birth_date", "")
        gender = request.form.get("gender")
        sexual_preference = request.form.get("sexual_preference")
        biography = sanitize_string(request.form.get("biography"), 2000)
        tags_raw = request.form.get("tags", "")
        if not birth_date_str or not str(birth_date_str).strip():
            flash("Birth date is required.", "error")
            return _render_profile_edit(user)
        try:
            birth_date = datetime.strptime(birth_date_str.strip(), "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid birth date.", "error")
            return _render_profile_edit(user)
        if birth_date > date.today():
            flash("Birth date cannot be in the future.", "error")
            return _render_profile_edit(user)
        age = calculate_age(birth_date)
        if age is None or age < 18:
            flash("You must be at least 18 years old.", "error")
            return _render_profile_edit(user)
        if not first_name or not last_name or not email:
            flash("First name, last name and email are required.", "error")
            return _render_profile_edit(user)
        if gender not in ("male", "female", "other", ""):
            gender = None
        if sexual_preference not in ("heterosexual", "homosexual", "bisexual", ""):
            sexual_preference = None
        if email != user.email:
            existing = query_one(
                "SELECT id FROM users WHERE email = %s AND id != %s", (email, user.id)
            )
            if existing:
                flash("Email already in use.", "error")
                return _render_profile_edit(user)
        execute(
            "UPDATE users SET first_name=%s, last_name=%s, email=%s, birth_date=%s, "
            "gender=%s, sexual_preference=%s, biography=%s, updated_at=%s WHERE id=%s",
            (
                first_name, last_name, email, birth_date,
                gender if gender else None,
                sexual_preference if sexual_preference else None,
                biography,
                datetime.now(timezone.utc).replace(tzinfo=None),
                user.id,
            ),
        )
        commit()
        tag_names = split_tags_input(tags_raw)
        set_user_tags(user.id, tag_names)
        flash("Profile updated.", "success")
        return redirect(url_for("profile.edit"))
    return _render_profile_edit(user)


@profile_bp.route("/upload-image", methods=["POST"])
@login_required
def upload_image():
    conn = get_db()
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = query_one(
            "SELECT COUNT(*) AS cnt FROM user_images WHERE user_id = %s",
            (current_user.id,),
        )
        count = row["cnt"]
        if count >= MAX_IMAGES:
            rollback()
            flash(f"Maximum {MAX_IMAGES} images allowed.", "error")
            return redirect(url_for("profile.edit"))
        file = request.files.get("image")
        upload_folder = current_app.config.get("UPLOAD_FOLDER", "./app/uploads")
        filename, err = save_image(file, upload_folder)
        if err:
            rollback()
            flash(err, "error")
            return redirect(url_for("profile.edit"))
        row = query_one(
            "SELECT COUNT(*) AS cnt FROM user_images WHERE user_id = %s",
            (current_user.id,),
        )
        if row["cnt"] >= MAX_IMAGES:
            rollback()
            if filename:
                delete_image_file(filename, upload_folder)
            flash(f"Maximum {MAX_IMAGES} images allowed.", "error")
            return redirect(url_for("profile.edit"))
        is_first = count == 0
        img = execute_returning(
            "INSERT INTO user_images (user_id, filename, is_profile_picture, upload_order) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (current_user.id, filename, is_first, count),
        )
        if is_first:
            execute(
                "UPDATE users SET profile_picture_id = %s WHERE id = %s",
                (img["id"], current_user.id),
            )
        commit()
    except Exception:
        rollback()
        raise
    flash("Image uploaded.", "success")
    return redirect(url_for("profile.edit"))


@profile_bp.route("/delete-image/<int:image_id>", methods=["POST"])
@login_required
def delete_image(image_id):
    img = query_one(
        "SELECT * FROM user_images WHERE id = %s AND user_id = %s", (image_id, current_user.id)
    )
    if not img:
        flash("Image not found.", "error")
        return redirect(url_for("profile.edit"))
    was_profile = img["is_profile_picture"]
    current_profile = query_one(
        "SELECT profile_picture_id FROM users WHERE id = %s",
        (current_user.id,),
    )
    referenced_by_current_user = current_profile and current_profile["profile_picture_id"] == image_id
    execute("UPDATE users SET profile_picture_id = NULL WHERE profile_picture_id = %s", (image_id,))
    execute("DELETE FROM user_images WHERE id = %s", (image_id,))
    if was_profile or referenced_by_current_user:
        next_img = query_one(
            "SELECT id FROM user_images WHERE user_id = %s ORDER BY upload_order LIMIT 1",
            (current_user.id,),
        )
        if next_img:
            execute(
                "UPDATE user_images SET is_profile_picture = true WHERE id = %s", (next_img["id"],)
            )
            execute(
                "UPDATE users SET profile_picture_id = %s WHERE id = %s",
                (next_img["id"], current_user.id),
            )
    commit()
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "./app/uploads")
    delete_image_file(img["filename"], upload_folder)
    flash("Image deleted.", "success")
    return redirect(url_for("profile.edit"))


@profile_bp.route("/set-profile-picture/<int:image_id>", methods=["POST"])
@login_required
def set_profile_picture(image_id):
    img = query_one(
        "SELECT id FROM user_images WHERE id = %s AND user_id = %s", (image_id, current_user.id)
    )
    if not img:
        flash("Image not found.", "error")
        return redirect(url_for("profile.edit"))
    execute(
        "UPDATE user_images SET is_profile_picture = false WHERE user_id = %s", (current_user.id,)
    )
    execute("UPDATE user_images SET is_profile_picture = true WHERE id = %s", (image_id,))
    execute("UPDATE users SET profile_picture_id = %s WHERE id = %s", (image_id, current_user.id))
    commit()
    flash("Profile picture updated.", "success")
    return redirect(url_for("profile.edit"))


@profile_bp.route("/update-location", methods=["POST"])
@login_required
def update_location():
    data = request.get_json() or {}
    lat = data.get("latitude")
    lng = data.get("longitude")
    manual = data.get("manual") in (True, "true", 1, "1")
    place = sanitize_string(data.get("place"), 200) if data.get("place") else ""
    place = (place or "").strip() or None

    if manual:
        if not place:
            return jsonify(
                {
                    "success": False,
                    "error": "Enter a city or neighborhood.",
                }
            ), 400
        coords = geocode_place_to_coordinates(place)
        if not coords:
            return jsonify(
                {
                    "success": False,
                    "error": "Could not find that location. Try another spelling or add a region or country.",
                }
            ), 400
        lat, lng = coords
        fp = place[:200]
        execute(
            "UPDATE users SET latitude=%s, longitude=%s, location_enabled=false, location_place=%s WHERE id=%s",
            (lat, lng, fp, current_user.id),
        )
        commit()
        return jsonify({"success": True, "place": fp, "latitude": lat, "longitude": lng})

    if lat is None or lng is None:
        return jsonify({"success": False, "error": "Invalid coordinates"}), 400
    try:
        lat = float(lat)
        lng = float(lng)
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return jsonify({"success": False, "error": "Invalid coordinates"}), 400
        execute(
            "UPDATE users SET latitude=%s, longitude=%s, location_enabled=true WHERE id=%s",
            (lat, lng, current_user.id),
        )
        resolved = reverse_geocode_neighborhood(lat, lng)
        resolved = (resolved or "").strip() or None
        final_place = resolved or place
        if final_place:
            fp = final_place[:200]
            execute(
                "UPDATE users SET location_place=%s WHERE id=%s",
                (fp, current_user.id),
            )
        commit()
        return jsonify({"success": True, "place": final_place, "latitude": lat, "longitude": lng})
    except (ValueError, TypeError):
        pass
    return jsonify({"success": False, "error": "Invalid coordinates"}), 400


@profile_bp.route("/view/<int:user_id>")
@login_required
def view(user_id):
    if user_id == current_user.id:
        return redirect(url_for("profile.edit"))
    row = query_one(
        "SELECT u.*, ui.filename AS pp_filename, ui.id AS pp_id "
        "FROM users u LEFT JOIN user_images ui ON u.profile_picture_id = ui.id "
        "WHERE u.id = %s",
        (user_id,),
    )
    if not row:
        flash("User not found.", "error")
        return redirect(url_for("browse.suggestions"))
    user = make_user(row)
    if not user.email_verified:
        flash("User not found.", "error")
        return redirect(url_for("browse.suggestions"))
    i_blocked = query_one(
        "SELECT id FROM blocks WHERE blocker_id=%s AND blocked_id=%s",
        (current_user.id, user.id),
    )
    if i_blocked:
        flash("You have blocked this user.", "error")
        return redirect(url_for("browse.suggestions"))
    they_blocked = query_one(
        "SELECT id FROM blocks WHERE blocker_id=%s AND blocked_id=%s",
        (user.id, current_user.id),
    )
    if they_blocked:
        flash("User not found.", "error")
        return redirect(url_for("browse.suggestions"))
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    execute(
        "INSERT INTO profile_views (viewer_id, viewed_id, viewed_at) VALUES (%s, %s, %s)",
        (current_user.id, user.id, now),
    )
    execute(
        "INSERT INTO notifications (user_id, type, related_user_id) VALUES (%s, 'view', %s)",
        (user.id, current_user.id),
    )
    commit()
    emit_notification(user.id, "view", current_user)
    # fame_rating was loaded before profile_views insert; refresh so the page shows current value
    user.fame_rating = update_user_fame(user.id)
    images = [
        SimpleNamespace(**r)
        for r in query_all(
            "SELECT * FROM user_images WHERE user_id = %s ORDER BY upload_order", (user.id,)
        )
    ]
    tags = get_user_tags(user.id)
    i_liked = query_one(
        "SELECT id FROM likes WHERE liker_id=%s AND liked_id=%s", (current_user.id, user.id)
    ) is not None
    they_liked = query_one(
        "SELECT id FROM likes WHERE liker_id=%s AND liked_id=%s", (user.id, current_user.id)
    ) is not None
    is_match = i_liked and they_liked
    age = calculate_age(user.birth_date)
    distance = None
    if current_user.latitude and current_user.longitude and user.latitude and user.longitude:
        distance = haversine_distance(
            current_user.latitude, current_user.longitude,
            user.latitude, user.longitude,
        )
    return render_template(
        "profile/view.html",
        user=user, images=images, tags=tags,
        i_liked=i_liked, they_liked=they_liked, is_match=is_match,
        age=age, distance=distance,
    )


@profile_bp.route("/visitors")
@login_required
def visitors():
    rows = query_all(
        "SELECT pv.viewed_at, u.id, u.username, u.first_name, u.last_name, "
        "u.profile_picture_id, ui.filename AS pp_filename "
        "FROM profile_views pv "
        "JOIN users u ON pv.viewer_id = u.id "
        "LEFT JOIN user_images ui ON u.profile_picture_id = ui.id "
        "WHERE pv.viewed_id = %s "
        "ORDER BY pv.viewed_at DESC LIMIT 100",
        (current_user.id,),
    )
    views = []
    for r in rows:
        pv = SimpleNamespace(viewed_at=r["viewed_at"])
        pp = SimpleNamespace(filename=r["pp_filename"]) if r["pp_filename"] else None
        viewer = SimpleNamespace(
            id=r["id"], username=r["username"],
            first_name=r["first_name"], last_name=r["last_name"],
            profile_picture=pp,
        )
        views.append((pv, viewer))
    return render_template("profile/visitors.html", views=views)


@profile_bp.route("/likes")
@login_required
def likes():
    rows = query_all(
        "SELECT l.created_at, u.id, u.username, u.first_name, u.last_name, "
        "u.profile_picture_id, ui.filename AS pp_filename "
        "FROM likes l "
        "JOIN users u ON l.liker_id = u.id "
        "LEFT JOIN user_images ui ON u.profile_picture_id = ui.id "
        "WHERE l.liked_id = %s "
        "ORDER BY l.created_at DESC LIMIT 100",
        (current_user.id,),
    )
    likes_list = []
    for r in rows:
        like = SimpleNamespace(created_at=r["created_at"])
        pp = SimpleNamespace(filename=r["pp_filename"]) if r["pp_filename"] else None
        liker = SimpleNamespace(
            id=r["id"], username=r["username"],
            first_name=r["first_name"], last_name=r["last_name"],
            profile_picture=pp,
        )
        likes_list.append((like, liker))
    my_likes_rows = query_all("SELECT liked_id FROM likes WHERE liker_id = %s", (current_user.id,))
    my_likes = set(r["liked_id"] for r in my_likes_rows)
    return render_template("profile/likes.html", likes=likes_list, my_likes=my_likes)


@profile_bp.route("/reorder-images", methods=["POST"])
@login_required
def reorder_images():
    data = request.get_json() or {}
    order = data.get("order", [])
    try:
        order = [int(x) for x in order]
    except (ValueError, TypeError):
        return jsonify({"success": False}), 400
    images = query_all(
        "SELECT id FROM user_images WHERE user_id = %s", (current_user.id,)
    )
    valid_ids = {r["id"] for r in images}
    for idx, img_id in enumerate(order):
        if img_id in valid_ids:
            execute(
                "UPDATE user_images SET upload_order=%s, is_profile_picture=%s WHERE id=%s",
                (idx, idx == 0, img_id),
            )
            if idx == 0:
                execute("UPDATE users SET profile_picture_id=%s WHERE id=%s", (img_id, current_user.id))
    commit()
    return jsonify({"success": True})


@profile_bp.route("/edit-image", methods=["POST"])
@login_required
def edit_image():
    from PIL import Image, ImageEnhance
    import os
    data = request.get_json() or {}
    image_id = data.get("image_id")
    rotation = data.get("rotation", 0)
    flip_h = data.get("flip_h", False)
    flip_v = data.get("flip_v", False)
    brightness = data.get("brightness", 100)
    contrast = data.get("contrast", 100)
    try:
        image_id = int(image_id)
        rotation = int(rotation) % 360
        brightness = int(brightness)
        contrast = int(contrast)
    except (ValueError, TypeError):
        return jsonify({"success": False}), 400
    img = query_one(
        "SELECT filename FROM user_images WHERE id = %s AND user_id = %s",
        (image_id, current_user.id),
    )
    if not img:
        return jsonify({"success": False, "error": "Image not found"}), 404
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "./app/uploads")
    filepath = os.path.join(upload_folder, img["filename"])
    if not os.path.exists(filepath):
        return jsonify({"success": False, "error": "File not found"}), 404
    try:
        pil_img = Image.open(filepath)
        if rotation:
            pil_img = pil_img.rotate(-rotation, expand=True)
        if flip_h:
            pil_img = pil_img.transpose(Image.FLIP_LEFT_RIGHT)
        if flip_v:
            pil_img = pil_img.transpose(Image.FLIP_TOP_BOTTOM)
        if brightness != 100:
            enhancer = ImageEnhance.Brightness(pil_img)
            pil_img = enhancer.enhance(brightness / 100.0)
        if contrast != 100:
            enhancer = ImageEnhance.Contrast(pil_img)
            pil_img = enhancer.enhance(contrast / 100.0)
        pil_img.save(filepath)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
