"""Matcha subject IV.2: profile must include birth date, gender, orientation, bio, tags, photos + main picture.

Location for matching (subject): coordinates are required for proximity; if device GPS is not used,
the user must declare city or neighborhood (location_place).
"""

from app.database import query_one


def get_profile_completion_status(user_id):
    """
    Returns {"ok": bool, "missing": [str, ...]} — missing items are short English labels for flash text.
    """
    row = query_one(
        "SELECT u.gender, u.sexual_preference, u.biography, u.birth_date, u.profile_picture_id, "
        "u.latitude, u.longitude, u.location_enabled, u.location_place, "
        "(SELECT COUNT(*) FROM user_tags ut WHERE ut.user_id = u.id) AS tag_count, "
        "(SELECT COUNT(*) FROM user_images ui WHERE ui.user_id = u.id) AS img_count "
        "FROM users u WHERE u.id = %s",
        (user_id,),
    )
    if not row:
        return {"ok": False, "missing": ["account"]}

    missing = []
    if not row["birth_date"]:
        missing.append("birth date")
    if not row["gender"]:
        missing.append("gender")
    if not row["sexual_preference"]:
        missing.append("sexual preference")
    if not (row["biography"] or "").strip():
        missing.append("biography")
    if row["tag_count"] < 1:
        missing.append("at least one interest tag")

    pp_ok = False
    if row["profile_picture_id"] and row["img_count"] >= 1:
        chk = query_one(
            "SELECT 1 AS ok FROM user_images WHERE id = %s AND user_id = %s",
            (row["profile_picture_id"], user_id),
        )
        pp_ok = chk is not None
    if row["img_count"] < 1 or not pp_ok:
        missing.append("at least one photo with a main profile picture")

    lat, lng = row.get("latitude"), row.get("longitude")
    if lat is None or lng is None:
        missing.append("location")
    elif not row.get("location_enabled"):
        place = (row.get("location_place") or "").strip()
        if not place:
            missing.append("city or neighborhood (required when not using device GPS)")

    return {"ok": len(missing) == 0, "missing": missing}
