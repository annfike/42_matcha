import math
from datetime import date
from types import SimpleNamespace
from app.database import query_all
from app.utils.tags import canonical_tag_name, split_tags_input


def calculate_age(birth_date):
    if not birth_date:
        return None
    if isinstance(birth_date, str):
        birth_date = date.fromisoformat(birth_date[:10])
    today = date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def haversine_distance(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return None
    R = 6371
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def get_user_tag_ids(user_id):
    rows = query_all("SELECT tag_id FROM user_tags WHERE user_id = %s", (user_id,))
    return set(r["tag_id"] for r in rows)


def _build_user(row):
    pp = None
    if row.get("pp_filename"):
        pp = SimpleNamespace(id=row.get("pp_id"), filename=row["pp_filename"])
    data = {k: v for k, v in row.items() if k not in ("pp_filename", "pp_id")}
    user = SimpleNamespace(**data)
    user.profile_picture = pp
    return user


def get_matching_candidates(current_user, filters=None):
    filters = filters or {}
    params = [current_user.id, current_user.id, current_user.id]
    where = [
        "u.id != %s",
        "u.email_verified = true",
        "u.id NOT IN (SELECT blocked_id FROM blocks WHERE blocker_id = %s)",
        "u.id NOT IN (SELECT blocker_id FROM blocks WHERE blocked_id = %s)",
    ]

    if current_user.gender and current_user.sexual_preference:
        if current_user.sexual_preference == "heterosexual":
            if current_user.gender == "male":
                where.append("u.gender = 'female'")
            elif current_user.gender == "female":
                where.append("u.gender = 'male'")
        elif current_user.sexual_preference == "homosexual":
            where.append("u.gender = %s")
            params.append(current_user.gender)

    if current_user.gender:
        where.append(
            "(u.sexual_preference IS NULL OR u.sexual_preference = 'bisexual' OR "
            "(u.sexual_preference = 'heterosexual' AND u.gender != %s) OR "
            "(u.sexual_preference = 'homosexual' AND u.gender = %s))"
        )
        params.extend([current_user.gender, current_user.gender])

    if filters.get("age_min"):
        max_birth = date.today().replace(year=date.today().year - int(filters["age_min"]))
        where.append("(u.birth_date IS NULL OR u.birth_date <= %s)")
        params.append(max_birth)
    if filters.get("age_max"):
        min_birth = date.today().replace(year=date.today().year - int(filters["age_max"]) - 1)
        where.append("(u.birth_date IS NULL OR u.birth_date >= %s)")
        params.append(min_birth)
    if filters.get("fame_min"):
        where.append("u.fame_rating >= %s")
        params.append(int(filters["fame_min"]))
    if filters.get("fame_max"):
        where.append("u.fame_rating <= %s")
        params.append(int(filters["fame_max"]))
    if filters.get("tags"):
        seen_names = set()
        tag_names = []
        for t in split_tags_input(filters.get("tags")):
            c = canonical_tag_name(t)
            if c and c not in seen_names:
                seen_names.add(c)
                tag_names.append(c)
        if tag_names:
            ph = ",".join(["%s"] * len(tag_names))
            where.append(
                f"u.id IN (SELECT ut.user_id FROM user_tags ut "
                f"JOIN tags t ON ut.tag_id = t.id WHERE t.name IN ({ph}))"
            )
            params.extend(tag_names)

    # Proximity matching requires coordinates; without GPS, subject requires declared city/area.
    where.append("u.latitude IS NOT NULL AND u.longitude IS NOT NULL")
    where.append("(u.location_enabled = 1 OR trim(COALESCE(u.location_place, '')) <> '')")

    sql = (
        "SELECT u.*, ui.filename AS pp_filename, ui.id AS pp_id "
        "FROM users u LEFT JOIN user_images ui ON u.profile_picture_id = ui.id "
        "WHERE " + " AND ".join(where)
    )
    return query_all(sql, params)


def score_user(user, current_user, my_tag_ids):
    score = 0
    if current_user.latitude and current_user.longitude and user.latitude and user.longitude:
        dist = haversine_distance(current_user.latitude, current_user.longitude, user.latitude, user.longitude)
        if dist is not None:
            if dist < 10:
                score += 1000
            elif dist < 50:
                score += 500
            elif dist < 100:
                score += 200
            else:
                score += max(0, 100 - int(dist / 10))
    user_tag_ids = get_user_tag_ids(user.id)
    common = len(my_tag_ids & user_tag_ids)
    score += common * 50
    score += user.fame_rating
    return score


def _user_ready_for_proximity_matching(user):
    """Coordinates always; if GPS is off, city/neighborhood must be set (subject)."""
    if user.latitude is None or user.longitude is None:
        return False
    if getattr(user, "location_enabled", False):
        return True
    place = getattr(user, "location_place", None) or ""
    return bool(str(place).strip())


def get_suggestions(current_user, sort_by=None, filters=None, limit=50):
    if not _user_ready_for_proximity_matching(current_user):
        return []
    rows = get_matching_candidates(current_user, filters)
    users = [_build_user(r) for r in rows]
    my_tag_ids = get_user_tag_ids(current_user.id)
    scored = []
    for u in users:
        dist = None
        if current_user.latitude and current_user.longitude and u.latitude and u.longitude:
            dist = haversine_distance(current_user.latitude, current_user.longitude, u.latitude, u.longitude)
        age = calculate_age(u.birth_date)
        common_tags = len(my_tag_ids & get_user_tag_ids(u.id))
        score = score_user(u, current_user, my_tag_ids)
        scored.append({
            "user": u,
            "score": score,
            "distance": dist,
            "age": age,
            "common_tags": common_tags,
        })
    if sort_by == "age":
        scored.sort(key=lambda x: (x["age"] is None, x["age"] or 0))
    elif sort_by == "location":
        scored.sort(key=lambda x: (x["distance"] is None, x["distance"] or 9999))
    elif sort_by == "fame":
        scored.sort(key=lambda x: -x["user"].fame_rating)
    elif sort_by == "tags":
        scored.sort(key=lambda x: -x["common_tags"])
    else:
        scored.sort(key=lambda x: -x["score"])
    if filters and filters.get("location_max"):
        max_dist = float(filters["location_max"])
        scored = [s for s in scored if s["distance"] is not None and s["distance"] <= max_dist]
    return scored[:limit]


def search_users(current_user, filters, sort_by=None, limit=50):
    return get_suggestions(current_user, sort_by=sort_by, filters=filters, limit=limit)
