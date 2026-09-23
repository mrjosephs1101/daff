"""
api/index.py - DAFF library metadata API.

Large .daff files are uploaded directly from the browser to Vercel Blob.
This Flask function only handles small metadata/database requests.
"""
from datetime import datetime, timezone
from urllib.parse import urlparse

from flask import Flask, request, jsonify

import _db
import _blob

app = Flask(__name__)


@app.errorhandler(Exception)
def handle_any_error(e):
    return jsonify({"error": str(e)}), 500


def _valid_blob_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme == "https"
            and parsed.hostname
            and parsed.hostname.endswith(".public.blob.vercel-storage.com")
            and parsed.path.startswith("/daff/")
        )
    except Exception:
        return False


@app.route("/api/library", methods=["GET"])
def list_library():
    _db.ensure_schema()
    entry_id = request.args.get("id")

    if entry_id:
        result = _db.execute("SELECT * FROM library WHERE id = ?", [int(entry_id)])
        rows = _db.rows_as_dicts(result)
        if not rows:
            return jsonify({"error": "not found"}), 404
        return jsonify(rows[0])

    result = _db.execute(
        "SELECT id, title, artist, album, stage_count, size_bytes, visibility, uploaded_at "
        "FROM library WHERE visibility = 'public' ORDER BY uploaded_at DESC LIMIT 200"
    )
    return jsonify(_db.rows_as_dicts(result))


@app.route("/api/library", methods=["POST"])
def register_upload():
    """Register a Blob object after the browser has uploaded it directly."""
    _db.ensure_schema()
    body = request.get_json(silent=True) or {}

    title = str(body.get("title") or "").strip()
    artist = str(body.get("artist") or "").strip()
    album = str(body.get("album") or "").strip()
    visibility = body.get("visibility") or "public"
    blob_url = str(body.get("blob_url") or "").strip()
    blob_pathname = str(body.get("blob_pathname") or "").strip()
    stage_count = int(body.get("stage_count") or 0)
    size_bytes = int(body.get("size_bytes") or 0)

    if not title:
        return jsonify({"error": "a title is required"}), 400
    if visibility not in ("public", "private"):
        visibility = "public"
    if not _valid_blob_url(blob_url):
        return jsonify({"error": "invalid Vercel Blob URL"}), 400
    if not blob_pathname.startswith("daff/"):
        return jsonify({"error": "invalid Blob pathname"}), 400
    if stage_count < 0 or stage_count > 100000:
        return jsonify({"error": "invalid stage count"}), 400
    if size_bytes < 0:
        return jsonify({"error": "invalid file size"}), 400

    result = _db.execute(
        "INSERT INTO library (title, artist, album, stage_count, size_bytes, blob_url, blob_pathname, visibility, uploaded_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            title, artist, album, stage_count, size_bytes,
            blob_url, blob_pathname, visibility,
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ],
    )
    return jsonify({"id": result.get("last_insert_rowid")}), 201


@app.route("/api/library/<int:entry_id>", methods=["DELETE"])
def delete_entry(entry_id):
    _db.ensure_schema()
    result = _db.execute("SELECT * FROM library WHERE id = ?", [entry_id])
    rows = _db.rows_as_dicts(result)
    if not rows:
        return jsonify({"error": "not found"}), 404
    row = rows[0]

    _blob.delete(row["blob_url"])
    _db.execute("DELETE FROM library WHERE id = ?", [entry_id])
    return jsonify({"deleted": True})


if __name__ == "__main__":
    app.run(port=5000, debug=True)
