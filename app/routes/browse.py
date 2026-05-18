from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import cache
from app.database import query_one, query_all, execute, execute_returning, commit
from app.utils.fame import update_user_fame
from app.utils.matching import get_suggestions, search_users, calculate_age
from app.utils.notifications import emit_notification

browse_bp = Blueprint("browse", __name__)


@cache.cached(timeout=600, key_prefix="all_tags")
def get_all_tags():
    from types import SimpleNamespace
    rows = query_all("SELECT id, name FROM tags ORDER BY name LIMIT 100")
    return [SimpleNamespace(**r) for r in rows]


PER_PAGE = 20


@browse_bp.route("/")
@browse_bp.route("/suggestions")
@login_required
def suggestions():
    page = request.args.get("page", 1, type=int)
    sort_by = request.args.get("sort", "score")
    filters = {
        "age_min": request.args.get("age_min"),
        "age_max": request.args.get("age_max"),
        "fame_min": request.args.get("fame_min"),
        "fame_max": request.args.get("fame_max"),
        "location_max": request.args.get("location_max"),
        "tags": request.args.get("tags"),
    }
    filters = {k: v for k, v in filters.items() if v}
    all_results = get_suggestions(current_user, sort_by=sort_by, filters=filters, limit=500)
    total = len(all_results)
    total_pages = (total + PER_PAGE - 1) // PER_PAGE
    start = (page - 1) * PER_PAGE
    end = start + PER_PAGE
    results = all_results[start:end]
    my_likes_rows = query_all("SELECT liked_id FROM likes WHERE liker_id = %s", (current_user.id,))
    my_likes = set(r["liked_id"] for r in my_likes_rows)
    return render_template(
        "browse/suggestions.html",
        results=results, my_likes=my_likes, sort_by=sort_by,
        filters=filters, calculate_age=calculate_age,
        page=page, total_pages=total_pages,
    )


@browse_bp.route("/search")
@login_required
def search():
    page = request.args.get("page", 1, type=int)
    sort_by = request.args.get("sort", "score")
    filters = {
        "age_min": request.args.get("age_min"),
        "age_max": request.args.get("age_max"),
        "fame_min": request.args.get("fame_min"),
        "fame_max": request.args.get("fame_max"),
        "location_max": request.args.get("location_max"),
        "tags": request.args.get("tags"),
    }
    filters = {k: v for k, v in filters.items() if v}
    results = []
    total_pages = 1
    # run=1 is set when the user clicks Search; empty filters then mean "all eligible profiles"
    searched = request.args.get("run") == "1"
    if searched:
        all_results = search_users(current_user, filters=filters, sort_by=sort_by, limit=500)
        total = len(all_results)
        total_pages = (total + PER_PAGE - 1) // PER_PAGE
        start = (page - 1) * PER_PAGE
        end = start + PER_PAGE
        results = all_results[start:end]
    my_likes_rows = query_all("SELECT liked_id FROM likes WHERE liker_id = %s", (current_user.id,))
    my_likes = set(r["liked_id"] for r in my_likes_rows)
    all_tags = get_all_tags()
    return render_template(
        "browse/search.html",
        results=results, my_likes=my_likes, sort_by=sort_by,
        filters=filters, searched=searched, all_tags=all_tags,
        calculate_age=calculate_age, page=page, total_pages=total_pages,
    )


@browse_bp.route("/like/<int:user_id>", methods=["POST"])
@login_required
def like(user_id):
    if user_id == current_user.id:
        flash("You cannot like yourself.", "error")
        return redirect(url_for("browse.suggestions"))
    user = query_one("SELECT id, profile_picture_id FROM users WHERE id = %s", (user_id,))
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("browse.suggestions"))
    if not current_user.profile_picture_id:
        flash("You need a profile picture to like someone.", "error")
        return redirect(url_for("profile.view", user_id=user_id))
    if not user["profile_picture_id"]:
        flash("You cannot like a user without a profile picture.", "error")
        return redirect(url_for("profile.view", user_id=user_id))
    existing = query_one(
        "SELECT id FROM likes WHERE liker_id=%s AND liked_id=%s", (current_user.id, user_id)
    )
    if existing:
        flash("You already liked this user.", "error")
        return redirect(url_for("profile.view", user_id=user_id))
    blocked = query_one(
        "SELECT id FROM blocks WHERE (blocker_id=%s AND blocked_id=%s) OR (blocker_id=%s AND blocked_id=%s)",
        (user_id, current_user.id, current_user.id, user_id),
    )
    if blocked:
        flash("You cannot like this user.", "error")
        return redirect(url_for("browse.suggestions"))
    execute(
        "INSERT INTO likes (liker_id, liked_id) VALUES (%s, %s)", (current_user.id, user_id)
    )
    they_liked = query_one(
        "SELECT id FROM likes WHERE liker_id=%s AND liked_id=%s", (user_id, current_user.id)
    )
    if they_liked:
        execute(
            "INSERT INTO notifications (user_id, type, related_user_id) VALUES (%s, 'match', %s)",
            (user_id, current_user.id),
        )
        execute(
            "INSERT INTO notifications (user_id, type, related_user_id) VALUES (%s, 'match', %s)",
            (current_user.id, user_id),
        )
        commit()
        emit_notification(user_id, "match", current_user)
        flash("It's a match! You can now chat.", "success")
    else:
        execute(
            "INSERT INTO notifications (user_id, type, related_user_id) VALUES (%s, 'like', %s)",
            (user_id, current_user.id),
        )
        commit()
        emit_notification(user_id, "like", current_user)
        flash("You liked this user.", "success")
    update_user_fame(user_id)
    update_user_fame(current_user.id)
    return redirect(url_for("profile.view", user_id=user_id))


@browse_bp.route("/unlike/<int:user_id>", methods=["POST"])
@login_required
def unlike(user_id):
    if user_id == current_user.id:
        return redirect(url_for("browse.suggestions"))
    existing = query_one(
        "SELECT id FROM likes WHERE liker_id=%s AND liked_id=%s", (current_user.id, user_id)
    )
    if not existing:
        flash("You have not liked this user.", "error")
        return redirect(url_for("profile.view", user_id=user_id))
    was_match = query_one(
        "SELECT id FROM likes WHERE liker_id=%s AND liked_id=%s", (user_id, current_user.id)
    ) is not None
    execute("DELETE FROM likes WHERE liker_id=%s AND liked_id=%s", (current_user.id, user_id))
    commit()
    if was_match:
        execute(
            "INSERT INTO notifications (user_id, type, related_user_id) VALUES (%s, 'unlike', %s)",
            (user_id, current_user.id),
        )
        commit()
        emit_notification(user_id, "unlike", current_user)
    update_user_fame(user_id)
    update_user_fame(current_user.id)
    flash("You unliked this user.", "success")
    return redirect(url_for("profile.view", user_id=user_id))


@browse_bp.route("/block/<int:user_id>", methods=["POST"])
@login_required
def block(user_id):
    if user_id == current_user.id:
        return redirect(url_for("browse.suggestions"))
    user = query_one("SELECT id FROM users WHERE id = %s", (user_id,))
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("browse.suggestions"))
    existing = query_one(
        "SELECT id FROM blocks WHERE blocker_id=%s AND blocked_id=%s", (current_user.id, user_id)
    )
    if existing:
        flash("User already blocked.", "error")
        return redirect(url_for("browse.suggestions"))
    execute("INSERT INTO blocks (blocker_id, blocked_id) VALUES (%s, %s)", (current_user.id, user_id))
    execute("DELETE FROM likes WHERE liker_id=%s AND liked_id=%s", (current_user.id, user_id))
    execute("DELETE FROM likes WHERE liker_id=%s AND liked_id=%s", (user_id, current_user.id))
    commit()
    flash("User blocked.", "success")
    return redirect(url_for("browse.suggestions"))


@browse_bp.route("/report/<int:user_id>", methods=["POST"])
@login_required
def report(user_id):
    if user_id == current_user.id:
        return redirect(url_for("browse.suggestions"))
    user = query_one("SELECT id FROM users WHERE id = %s", (user_id,))
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("browse.suggestions"))
    reason = request.form.get("reason", "Reported as fake account")
    execute(
        "INSERT INTO reports (reporter_id, reported_id, reason) VALUES (%s, %s, %s)",
        (current_user.id, user_id, reason),
    )
    commit()
    flash("User reported. Thank you.", "success")
    return redirect(url_for("browse.suggestions"))
