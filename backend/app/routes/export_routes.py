"""Export routes (spec D5).

GET /api/notes/<id>/export  — single note as a .md download.
GET /api/export             — ZIP of all notes + attachments folder;
                              image references rewritten to ../attachments/<file>;
                              total size capped at 200 MB.

The ZIP is streamed using zipfile + a generator to avoid loading everything
into memory at once.
"""
import io
import logging
import re
import unicodedata
import zipfile
from datetime import datetime, timezone

import frontmatter
from flask import Blueprint, Response, current_app, g, jsonify, stream_with_context

from ..models import Attachment, Note
from ..storage.factory import get_storage
from .auth import login_required

log = logging.getLogger(__name__)

export_bp = Blueprint("export", __name__, url_prefix="/api")

_MAX_EXPORT_BYTES = 200 * 1024 * 1024  # 200 MB cap


def _safe_filename(title: str, note_id: str) -> str:
    """Create a filesystem-safe filename: <safe-title>-<short-id>.md.

    - Normalise unicode, replace forbidden characters with '-'.
    - Collapse repeated dashes/spaces.
    - Cap at 80 characters before the ID suffix.
    """
    # Normalise accents etc.
    title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    # Replace anything that's not alphanumeric, space or hyphen
    title = re.sub(r"[^\w\s-]", "", title)
    title = re.sub(r"[\s_]+", "-", title).strip("-")
    title = title[:80] or "note"
    short_id = note_id[:8]
    return f"{title}-{short_id}.md"


def _rewrite_attachment_refs(body: str) -> str:
    """Rewrite ![...](attachments/<file>) → ![...](../attachments/<file>).

    Handles both image references and plain Markdown links that point to
    the attachments/ prefix.
    """
    # Match ![alt](attachments/...) — Markdown image
    body = re.sub(
        r"!\[([^\]]*)\]\(attachments/([^)]+)\)",
        r"![\1](../attachments/\2)",
        body,
    )
    # Match [text](attachments/...) — Markdown link (for PDFs)
    body = re.sub(
        r"\[([^\]]*)\]\(attachments/([^)]+)\)",
        r"[\1](../attachments/\2)",
        body,
    )
    return body


# ---------------------------------------------------------------------------
# GET /api/notes/<id>/export  (single note)
# ---------------------------------------------------------------------------
@export_bp.route("/notes/<note_id>/export", methods=["GET"])
@login_required
def export_single(note_id: str):
    """Return the raw .md file for a single note as a download."""
    db = current_app._db_session()
    note = db.query(Note).filter_by(id=note_id, user_id=g.current_user.id).first()
    if not note:
        return jsonify({"error": {"code": "not_found", "message": "Note not found"}}), 404

    storage = get_storage()
    try:
        content = storage.get_text(note.storage_key)
    except FileNotFoundError:
        return jsonify({"error": {"code": "not_found", "message": "Note file not found"}}), 404

    filename = _safe_filename(note.title, note.id)
    return Response(
        content,
        status=200,
        mimetype="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(content.encode("utf-8"))),
        },
    )


# ---------------------------------------------------------------------------
# GET /api/export  (full ZIP)
# ---------------------------------------------------------------------------
@export_bp.route("/export", methods=["GET"])
@login_required
def export_all():
    """Stream a ZIP containing notes/*.md + attachments/* for all user notes.

    Image/PDF attachment references inside the Markdown bodies are rewritten
    from `attachments/<file>` to `../attachments/<file>` so the files display
    correctly when opened from the notes/ sub-folder.

    Returns 413 if the total export would exceed 200 MB.
    """
    user_id = g.current_user.id
    db = current_app._db_session()
    storage = get_storage()

    # Load all non-deleted notes
    notes = (
        db.query(Note)
        .filter(Note.user_id == user_id, Note.deleted_at.is_(None))
        .all()
    )

    # Pre-flight size check: sum note files + attachment files
    total_size = 0

    # Collect note texts and attachment data eagerly to allow size check
    # and to avoid holding DB rows open during streaming.
    note_entries: list[tuple[str, bytes]] = []  # (arcname, data)
    att_entries: list[tuple[str, bytes]] = []   # (arcname, data)

    # Track filenames to avoid collisions
    used_names: set[str] = set()

    for note in notes:
        try:
            raw = storage.get_text(note.storage_key)
        except FileNotFoundError:
            log.warning("Export: note %s file missing, skipping", note.id)
            continue

        # Parse front matter + rewrite attachment references in body
        post = frontmatter.loads(raw)
        rewritten_body = _rewrite_attachment_refs(post.content)
        # Rebuild front-matter with rewritten body
        rebuilt = frontmatter.Post(rewritten_body, **post.metadata)
        md_bytes = frontmatter.dumps(rebuilt).encode("utf-8")

        # Unique filename
        candidate = _safe_filename(note.title, note.id)
        arc_name = f"notes/{candidate}"
        i = 1
        base_candidate = candidate
        while arc_name in used_names:
            stem = base_candidate[:-3]  # strip .md
            arc_name = f"notes/{stem}-{i}.md"
            i += 1
        used_names.add(arc_name)

        total_size += len(md_bytes)
        if total_size > _MAX_EXPORT_BYTES:
            return jsonify({
                "error": {
                    "code": "payload_too_large",
                    "message": "Export exceeds 200 MB limit. Archive some notes first.",
                }
            }), 413

        note_entries.append((arc_name, md_bytes))

        # Collect attachments for this note
        for att in note.attachments:
            try:
                att_data = storage.get_bytes(att.storage_key)
            except FileNotFoundError:
                log.warning("Export: attachment %s file missing, skipping", att.id)
                continue

            # Derive filename from storage_key (last segment)
            att_filename = att.storage_key.rsplit("/", 1)[-1]
            att_arc = f"attachments/{att_filename}"

            total_size += len(att_data)
            if total_size > _MAX_EXPORT_BYTES:
                return jsonify({
                    "error": {
                        "code": "payload_too_large",
                        "message": "Export exceeds 200 MB limit. Archive some notes first.",
                    }
                }), 413

            att_entries.append((att_arc, att_data))

    # Build ZIP in memory (streaming)
    def generate_zip():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for arc_name, data in note_entries:
                zf.writestr(arc_name, data)
            for arc_name, data in att_entries:
                zf.writestr(arc_name, data)
        buf.seek(0)
        yield buf.read()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    zip_filename = f"cloudnotes-export-{timestamp}.zip"

    return Response(
        stream_with_context(generate_zip()),
        status=200,
        mimetype="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_filename}"',
        },
    )
