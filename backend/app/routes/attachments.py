"""Attachment upload and download routes (spec D3.6, D5).

POST /api/attachments  — upload a file (png, jpg, gif, webp, pdf; ≤ 10 MB).
GET  /api/attachments/<id> — serve the file (presigned redirect in S3 mode,
                             stream in local mode).

File-type validation uses magic bytes, not the extension or Content-Type header.
Storage key: users/{user_id}/attachments/{attachment_id}.{ext}
"""
import logging
import mimetypes
from io import BytesIO

from flask import Blueprint, Response, current_app, g, jsonify, request

from ..models import Attachment, Note
from ..storage.factory import get_storage
from .auth import csrf_required, login_required

log = logging.getLogger(__name__)

attachments_bp = Blueprint("attachments", __name__, url_prefix="/api")

# Maximum upload size: 10 MB
_MAX_BYTES = 10 * 1024 * 1024

# Allowed file types: magic signature → (canonical_ext, mime_type)
# Each entry: (magic_bytes_offset, magic_bytes, ext, mime)
_MAGIC: list[tuple[int, bytes, str, str]] = [
    (0, b"\x89PNG\r\n\x1a\n", "png", "image/png"),
    (0, b"\xff\xd8\xff",       "jpg", "image/jpeg"),
    (0, b"GIF87a",             "gif", "image/gif"),
    (0, b"GIF89a",             "gif", "image/gif"),
    (0, b"RIFF",               "webp", "image/webp"),  # checked with extra offset below
    (0, b"%PDF",               "pdf", "application/pdf"),
]

# For WEBP the bytes at offset 8..12 must be b"WEBP"
_WEBP_MARKER = b"WEBP"


def _detect_type(data: bytes) -> tuple[str, str] | None:
    """Return (extension, mime_type) by inspecting magic bytes.

    Returns None if the file type is not allowed.
    """
    for offset, magic, ext, mime in _MAGIC:
        if data[offset: offset + len(magic)] == magic:
            if ext == "webp":
                # Verify WEBP marker at byte 8
                if data[8:12] != _WEBP_MARKER:
                    continue
            return ext, mime
    return None


def _storage_key(user_id: int, attachment_id: str, ext: str) -> str:
    return f"users/{user_id}/attachments/{attachment_id}.{ext}"


# ---------------------------------------------------------------------------
# POST /api/attachments
# ---------------------------------------------------------------------------
@attachments_bp.route("/attachments", methods=["POST"])
@csrf_required
@login_required
def upload_attachment():
    """Accept a multipart upload, validate type from magic bytes, store and index."""
    user_id = g.current_user.id
    db = current_app._db_session()

    # note_id is required
    note_id = request.form.get("note_id", "").strip()
    if not note_id:
        return jsonify({"error": {"code": "validation_error", "message": "note_id is required"}}), 422

    # Verify note ownership
    note = db.query(Note).filter_by(id=note_id, user_id=user_id).first()
    if not note:
        return jsonify({"error": {"code": "not_found", "message": "Note not found"}}), 404

    # Check that a file was provided
    if "file" not in request.files:
        return jsonify({"error": {"code": "validation_error", "message": "No file part in request"}}), 422

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": {"code": "validation_error", "message": "No file selected"}}), 422

    # Read up to MAX_BYTES + 1 to detect oversized uploads without reading all
    chunk = file.read(_MAX_BYTES + 1)
    if len(chunk) > _MAX_BYTES:
        return jsonify({"error": {"code": "validation_error", "message": "File exceeds 10 MB limit"}}), 422

    data = chunk  # exactly the file content (≤ 10 MB)

    # Validate file type from magic bytes
    detected = _detect_type(data)
    if detected is None:
        return jsonify({
            "error": {
                "code": "validation_error",
                "message": "File type not allowed. Accepted: png, jpg, gif, webp, pdf",
            }
        }), 422
    ext, mime = detected

    # Persist attachment record and store file
    from ..models import _uuid  # reuse the project's UUID generator
    att_id = _uuid()
    key = _storage_key(user_id, att_id, ext)

    try:
        storage = get_storage()
        storage.put_bytes(key, data, content_type=mime)
    except Exception:
        log.exception("Storage error saving attachment %s", att_id)
        return jsonify({"error": {"code": "server_error", "message": "Could not store attachment"}}), 500

    try:
        att = Attachment(
            id=att_id,
            user_id=user_id,
            note_id=note_id,
            filename=file.filename or f"{att_id}.{ext}",
            content_type=mime,
            size_bytes=len(data),
            storage_key=key,
        )
        db.add(att)
        db.commit()
        db.refresh(att)
    except Exception:
        db.rollback()
        log.exception("DB error saving attachment %s", att_id)
        # Clean up stored object
        try:
            get_storage().delete(key)
        except Exception:
            pass
        return jsonify({"error": {"code": "server_error", "message": "Could not save attachment record"}}), 500

    ref = f"attachments/{att_id}.{ext}"
    url = f"/api/attachments/{att_id}"
    return jsonify({"id": att_id, "ref": ref, "url": url}), 201


# ---------------------------------------------------------------------------
# GET /api/attachments/<id>
# ---------------------------------------------------------------------------
@attachments_bp.route("/attachments/<att_id>", methods=["GET"])
@login_required
def get_attachment(att_id: str):
    """Serve attachment: 302 presigned URL in S3 mode, stream in local mode.

    Enforces ownership — returns 404 for another user's attachment.
    """
    user_id = g.current_user.id
    db = current_app._db_session()

    att = db.query(Attachment).filter_by(id=att_id, user_id=user_id).first()
    if not att:
        return jsonify({"error": {"code": "not_found", "message": "Attachment not found"}}), 404

    storage = get_storage()
    presigned = storage.presigned_url_or_none(att.storage_key, expires_in=300)

    if presigned:
        # S3 mode: redirect to a short-lived URL
        return Response(status=302, headers={"Location": presigned})

    # Local mode: stream the bytes
    try:
        data = storage.get_bytes(att.storage_key)
    except FileNotFoundError:
        return jsonify({"error": {"code": "not_found", "message": "Attachment file not found"}}), 404

    return Response(
        data,
        status=200,
        mimetype=att.content_type,
        headers={
            "Content-Disposition": f'inline; filename="{att.filename}"',
            "Content-Length": str(len(data)),
        },
    )
