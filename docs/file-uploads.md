# File uploads (Werkzeug + Pillow)

User photos power profiles, likes (both users need a profile picture), suggestions cards, and the map. Files are uploaded via **multipart forms**, validated and resized on the server with **Pillow**, stored under **`app/uploads/`** with random UUID names.

---

## End-to-end upload path

```
Browser: profile/edit.html
    │  form POST multipart field "image"
    │  or drag-drop → same form submit
    ▼
Flask: MAX_CONTENT_LENGTH check (5 MB body)
    ▼
profile.upload_image → save_image(file, UPLOAD_FOLDER)
    │  extension whitelist
    │  size check
    │  PIL verify + decode
    │  thumbnail 1200×1200
    │  save as {uuid}.jpg|png|...
    ▼
INSERT user_images (user_id, filename, is_profile_picture, upload_order)
    │  if first photo → UPDATE users.profile_picture_id
    ▼
Browser reload → <img src="/uploads/{filename}">
```

Serving does **not** go through a DB lookup — URL is built from stored `filename` only.

---

## Stack

| Piece | Role |
|-------|------|
| `Werkzeug` | `request.files`, `FileStorage`, `MAX_CONTENT_LENGTH` |
| `Pillow` | Decode, verify, resize, re-encode, in-browser edit transforms |
| `uuid` | Opaque filenames |
| `app/utils/images.py` | Core save/delete logic |
| `app/routes/profile.py` | HTTP routes + gallery UI coordination |

---

## Configuration

| Setting | Source | Value |
|---------|--------|-------|
| `UPLOAD_FOLDER` | `.env` / config | `./app/uploads` → resolved to absolute path in `create_app` |
| `MAX_CONTENT_LENGTH` | config | `5242880` (5 MB) |

If body exceeds limit **before** route runs:

```python
@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    flash("File too large...")
    return redirect(url_for("profile.edit"))
```

Directory created at startup if missing:

```python
if not os.path.exists(upload_folder):
    os.makedirs(upload_folder)
```

---

## `save_image()` — internal steps (`app/utils/images.py`)

```python
def save_image(file, upload_folder):
```

| Step | Check / action |
|------|----------------|
| 1 | Reject if no file or empty filename |
| 2 | `allowed_file()` — extension in `{png,jpg,jpeg,gif,webp}` |
| 3 | `file.seek(0,2); size = tell()` — must be ≤ `MAX_FILE_SIZE` (5 MB) |
| 4 | `Image.open(file); img.verify()` — detect truncated/corrupt files |
| 5 | Re-open (verify closes file), check `img.format` in allowed PIL formats (+ **MPO** for some phones) |
| 6 | Normalize extension (`jpeg`→`jpg`, MPO→jpg on disk) |
| 7 | `filename = f"{uuid.uuid4().hex}.{ext}"` |
| 8 | Convert RGBA/P/CMYK → RGB for JPEG compatibility |
| 9 | `img.thumbnail((1200, 1200), LANCZOS)` — aspect ratio preserved |
| 10 | `img.save(filepath, quality=85, optimize=True)` |
| 11 | Return `(filename, None)` or `(None, error_string)` |

**Why verify + open twice:** PIL `verify()` reads headers only; a second open is required to process pixels.

---

## Upload route (`POST /profile/upload-image`)

```python
MAX_IMAGES = 5

count = SELECT COUNT(*) FROM user_images WHERE user_id = current_user
if count >= MAX_IMAGES: flash error

filename, err = save_image(request.files.get("image"), upload_folder)
is_first = (count == 0)

INSERT user_images (user_id, filename, is_profile_picture=is_first, upload_order=count)
if is_first:
    UPDATE users SET profile_picture_id = new_image_id
```

- `upload_order` = current count (0-based index before insert)
- First image automatically becomes profile picture (`is_profile_picture=1`)

---

## Delete (`POST /profile/delete-image/<image_id>`)

1. `SELECT * FROM user_images WHERE id=? AND user_id=current_user`
2. Remember if deleted image was profile picture
3. `UPDATE users SET profile_picture_id=NULL WHERE profile_picture_id=this_id`
4. `DELETE FROM user_images`
5. If main photo removed → pick next by `ORDER BY upload_order LIMIT 1`, set as profile picture
6. `delete_image_file(filename)` — `os.remove` if exists
7. `commit()`

Orphan files on disk are avoided because delete always removes the file after DB delete.

---

## Reorder (`POST /profile/reorder-images`)

JSON body: `{ "order": [3, 1, 5, 2] }` — image IDs in display order.

```python
for idx, img_id in enumerate(order):
    if img_id in valid_ids:
        UPDATE user_images SET upload_order=idx, is_profile_picture=(idx==0)
        if idx == 0:
            UPDATE users SET profile_picture_id=img_id
```

Frontend drag-and-drop in `profile/edit.html` sends this after drop.

---

## In-browser edit (`POST /profile/edit-image`)

JSON: `image_id`, `rotation` (0–360), `flip_h`, `flip_v`, `brightness`, `contrast` (percent, 100 = normal).

Server:

1. Verify image belongs to user
2. Open `{UPLOAD_FOLDER}/{filename}` with Pillow
3. Apply transforms in order: rotate → flip → brightness → contrast
4. **Overwrite same file** — URL unchanged, no new DB row

This is destructive edit (no undo except re-upload).

---

## Serving files (`GET /uploads/<path:filename>`)

```python
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)
```

- No auth check — anyone with URL can view (typical for dating profile photos)
- `path:` converter prevents `../` in URL segment; stored names are UUID-only

Templates use:

```jinja2
{{ url_for('uploaded_file', filename=user.profile_picture.filename) }}
```

---

## Integration with other features

| Feature | Requirement |
|---------|-------------|
| Like someone | `current_user.profile_picture_id` and target must have picture |
| Profile completion | ≥1 image + valid `profile_picture_id` pointing to owned image |
| Map popup | `photo` filename in JSON → `/uploads/...` |
| Browse cards | JOIN `user_images` on `profile_picture_id` |

---

## Security

| Risk | Mitigation |
|------|------------|
| Non-image malware | PIL verify + format whitelist |
| Double extension attack | Saved name is UUID + controlled ext |
| Path traversal | UUID only; `send_from_directory` rooted at upload folder |
| Huge upload | Flask `MAX_CONTENT_LENGTH` + pre-save size check |
| XSS in filename | Never embed raw filename in HTML |

---

## Related files

```
app/config.py
app/__init__.py
app/utils/images.py
app/routes/profile.py
app/templates/profile/edit.html
app/templates/profile/view.html
```
