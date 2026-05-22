from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from app.database import query_all
from app.utils.matching import calculate_age

map_bp = Blueprint("map", __name__)


@map_bp.route("/")
@login_required
def index():
    return render_template("map/index.html")


@map_bp.route("/users")
@login_required
def users_json():
    rows = query_all(
        "SELECT u.id, u.username, u.first_name, u.birth_date, u.latitude, u.longitude, "
        "u.is_online, ui.filename AS photo "
        "FROM users u "
        "LEFT JOIN user_images ui ON u.profile_picture_id = ui.id "
        "WHERE u.email_verified = true AND u.latitude IS NOT NULL AND u.longitude IS NOT NULL "
        "AND (u.location_enabled = 1 OR trim(COALESCE(u.location_place, '')) <> '') "
        "AND u.id != %s "
        "AND u.id NOT IN (SELECT blocked_id FROM blocks WHERE blocker_id = %s) "
        "AND u.id NOT IN (SELECT blocker_id FROM blocks WHERE blocked_id = %s) "
        "LIMIT 200",
        (current_user.id, current_user.id, current_user.id),
    )
    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "username": r["username"],
            "first_name": r["first_name"],
            "age": calculate_age(r["birth_date"]),
            "lat": r["latitude"],
            "lng": r["longitude"],
            "is_online": r["is_online"],
            "photo": r["photo"],
        })
    return jsonify(result)
