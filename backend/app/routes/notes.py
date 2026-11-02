"""Notes CRUD routes (spec D5).

Two-place save: write to storage first, then update the database row.
Front-matter format (D3.4): title, tags, notebook, created, updated + body.
"""
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

import frontmatter
from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import func, or_

from ..models import Attachment, Note, NoteTag, Tag
from ..storage.factory import get_storage
from ..utils import make_snippet, strip_markdown
from .auth import csrf_required, login_required

log = logging.getLogger(__name__)

notes_bp = Blueprint("notes", __name__, url_prefix="/api")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _db():
    return current_app._db_session()


def _now():
    return datetime.now(timezone.utc)


def _storage_key(user_id: int, note_id: str) -> str:
    return f"users/{user_id}/notes/{note_id}.md"


def _build_file(title: str, body: str, tags: list[str],
                notebook_name: str | None,
                created: datetime, updated: datetime) -> str:
    """Serialize a note as front-matter + body."""
    clean_tags = []
    for t in (tags or []):
        clean_name = str(t).strip().lower()[:30]
        if clean_name and clean_name not in clean_tags:
            clean_tags.append(clean_name)

    meta = {
        "title": title,
        "tags": clean_tags,
        "created": created.isoformat(),
        "updated": updated.isoformat(),
    }
    if notebook_name:
        meta["notebook"] = notebook_name
        meta["notebook name"] = notebook_name
    post = frontmatter.Post(body, **meta)
    return frontmatter.dumps(post)


def _note_json(note: Note, include_content: bool = False) -> dict:
    """Serialize a Note model to the JSON shape from the spec."""
    db = _db()
    tag_names = [
        nt.tag.name for nt in note.note_tags
    ]
    data = {
        "id": note.id,
        "title": note.title,
        "snippet": note.snippet,
        "notebook_id": note.notebook_id,
        "tags": tag_names,
        "is_pinned": note.is_pinned,
        "is_favorite": note.is_favorite,
        "is_archived": note.is_archived,
        "deleted_at": note.deleted_at.isoformat() if note.deleted_at else None,
        "version": note.version,
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }
    if include_content:
        try:
            storage = get_storage()
            raw = storage.get_text(note.storage_key)
            post = frontmatter.loads(raw)
            data["content"] = post.content
        except FileNotFoundError:
            data["content"] = ""
        data["attachments"] = [
            {
                "id": att.id,
                "filename": att.filename,
                "content_type": att.content_type,
                "size_bytes": att.size_bytes,
                "url": f"/api/attachments/{att.id}",
                "created_at": att.created_at.isoformat() if att.created_at else None,
            }
            for att in note.attachments
        ]
    return data


def _sync_tags(db, note: Note, tag_names: list[str], user_id: int):
    """Replace the tag list on a note.  Creates missing tags, removes old links."""
    # Validate
    clean = []
    for raw in tag_names:
        name = raw.strip().lower()[:30]
        if name and name not in clean:
            clean.append(name)
    if len(clean) > 10:
        return "A note can have at most 10 tags."

    # Remove existing links
    for nt in list(note.note_tags):
        db.delete(nt)
    db.flush()

    # Add new links
    for name in clean:
        tag = db.query(Tag).filter_by(user_id=user_id, name=name).first()
        if not tag:
            tag = Tag(user_id=user_id, name=name)
            db.add(tag)
            db.flush()
        db.add(NoteTag(note_id=note.id, tag_id=tag.id))

    return None  # success


def _lazy_purge(db, user_id: int):
    """Permanently delete notes in trash older than TRASH_PURGE_DAYS (D3.7)."""
    days = current_app.config.get("TRASH_PURGE_DAYS", 30)
    cutoff = _now() - timedelta(days=days)

    stale = (
        db.query(Note)
        .filter(
            Note.user_id == user_id,
            Note.deleted_at.isnot(None),
            Note.deleted_at < cutoff,
        )
        .all()
    )
    storage = get_storage()
    for note in stale:
        # Delete attachments' files
        for att in note.attachments:
            storage.delete(att.storage_key)
        # Delete the note file
        storage.delete(note.storage_key)
        db.delete(note)
    if stale:
        db.commit()


# ---------------------------------------------------------------------------
# POST /api/notes
# ---------------------------------------------------------------------------
@notes_bp.route("/notes", methods=["POST"])
@csrf_required
@login_required
def create_note():
    data = request.get_json(silent=True) or {}
    user_id = g.current_user.id
    db = _db()

    title = (data.get("title") or "Untitled").strip()[:500]
    body = data.get("content") or ""
    notebook_id = data.get("notebook_id")
    tag_names = data.get("tags") or []
    is_pinned = bool(data.get("is_pinned", False))
    is_favorite = bool(data.get("is_favorite", False))

    # Validate notebook ownership
    notebook_name = None
    if notebook_id is not None:
        from ..models import Notebook
        nb = db.query(Notebook).filter_by(id=notebook_id, user_id=user_id).first()
        if not nb:
            return jsonify({"error": {"code": "not_found", "message": "Notebook not found"}}), 404
        notebook_name = nb.name

    # Validate tags
    if not isinstance(tag_names, list):
        return jsonify({"error": {"code": "validation_error", "message": "tags must be a list"}}), 422

    now = _now()
    note_id = str(uuid.uuid4())
    key = _storage_key(user_id, note_id)

    # Plain text / snippet
    plain = strip_markdown(body)
    snippet = make_snippet(body)

    # Step 1: write file to storage
    file_content = _build_file(title, body, tag_names, notebook_name, now, now)
    storage = get_storage()
    storage.put_text(key, file_content)

    # Step 2: database row in one transaction
    try:
        note = Note(
            id=note_id,
            user_id=user_id,
            notebook_id=notebook_id,
            title=title,
            snippet=snippet,
            search_text=plain,
            storage_key=key,
            is_pinned=is_pinned,
            is_favorite=is_favorite,
            version=1,
            created_at=now,
            updated_at=now,
        )
        db.add(note)
        db.flush()

        tag_err = _sync_tags(db, note, tag_names, user_id)
        if tag_err:
            db.rollback()
            return jsonify({"error": {"code": "validation_error", "message": tag_err}}), 422

        db.commit()
        db.refresh(note)
    except Exception:
        db.rollback()
        log.exception("DB error creating note %s", note_id)
        return jsonify({"error": {"code": "server_error", "message": "An internal error occurred."}}), 500

    return jsonify(_note_json(note, include_content=True)), 201


# ---------------------------------------------------------------------------
# GET /api/notes  (list — summaries, no body)
# ---------------------------------------------------------------------------
@notes_bp.route("/notes", methods=["GET"])
@login_required
def list_notes():
    user_id = g.current_user.id
    db = _db()

    # Lazy purge when listing trash
    view = request.args.get("view", "all")
    if view == "trash":
        _lazy_purge(db, user_id)

    q = db.query(Note).filter(Note.user_id == user_id)

    # View filters
    if view == "trash":
        q = q.filter(Note.deleted_at.isnot(None))
    elif view == "favorites":
        q = q.filter(Note.deleted_at.is_(None), Note.is_favorite.is_(True))
    elif view == "archive":
        q = q.filter(Note.deleted_at.is_(None), Note.is_archived.is_(True))
    else:
        # "all" — hide deleted and archived
        q = q.filter(Note.deleted_at.is_(None), Note.is_archived.is_(False))

    # Notebook filter
    notebook_id = request.args.get("notebook_id")
    if notebook_id and notebook_id.strip():
        try:
            q = q.filter(Note.notebook_id == int(notebook_id))
        except ValueError:
            pass

    # Tag filter
    tag_filter = request.args.get("tag")
    if tag_filter and tag_filter.strip():
        q = q.join(NoteTag).join(Tag).filter(Tag.name == tag_filter.strip().lower())

    # Search (case-insensitive LIKE on title and search_text, escape % and _)
    search = request.args.get("q")
    if search and search.strip():
        term = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{term}%"
        q = q.filter(
            or_(
                Note.title.ilike(like, escape="\\"),
                Note.search_text.ilike(like, escape="\\"),
            )
        )

    # Sorting — pinned first in "all" view
    sort_field = request.args.get("sort", "updated")
    if sort_field == "created":
        order_col = Note.created_at.desc()
    elif sort_field == "title":
        order_col = Note.title.asc()
    else:
        order_col = Note.updated_at.desc()

    if view == "all":
        q = q.order_by(Note.is_pinned.desc(), order_col)
    else:
        q = q.order_by(order_col)

    # Pagination
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = int(request.args.get("offset", 0))
    notes = q.limit(limit).offset(offset).all()

    return jsonify([_note_json(n) for n in notes]), 200


# ---------------------------------------------------------------------------
# GET /api/notes/<id>  (detail — with body)
# ---------------------------------------------------------------------------
@notes_bp.route("/notes/<note_id>", methods=["GET"])
@login_required
def get_note(note_id):
    db = _db()
    note = db.query(Note).filter_by(id=note_id, user_id=g.current_user.id).first()
    if not note:
        return jsonify({"error": {"code": "not_found", "message": "Note not found"}}), 404
    return jsonify(_note_json(note, include_content=True)), 200


# ---------------------------------------------------------------------------
# PATCH /api/notes/<id>
# ---------------------------------------------------------------------------
@notes_bp.route("/notes/<note_id>", methods=["PATCH"])
@csrf_required
@login_required
def update_note(note_id):
    db = _db()
    user_id = g.current_user.id
    note = db.query(Note).filter_by(id=note_id, user_id=user_id).first()
    if not note:
        return jsonify({"error": {"code": "not_found", "message": "Note not found"}}), 404

    data = request.get_json(silent=True) or {}

    # Conflict check
    if "base_version" in data:
        if data["base_version"] != note.version:
            return jsonify({
                "error": {"code": "conflict", "message": "Version conflict"},
                "note": _note_json(note, include_content=True),
            }), 409

    # Collect updates
    title = note.title
    if "title" in data:
        title = (data["title"] or "Untitled").strip()[:500]

    # Read current body from storage
    storage = get_storage()
    try:
        raw = storage.get_text(note.storage_key)
        post = frontmatter.loads(raw)
        body = post.content
    except FileNotFoundError:
        body = ""

    if "content" in data:
        body = data["content"] or ""

    notebook_id = note.notebook_id
    notebook_name = None
    if "notebook_id" in data:
        notebook_id = data["notebook_id"]
        if notebook_id is not None:
            from ..models import Notebook
            nb = db.query(Notebook).filter_by(id=notebook_id, user_id=user_id).first()
            if not nb:
                return jsonify({"error": {"code": "not_found", "message": "Notebook not found"}}), 404
            notebook_name = nb.name
    elif notebook_id is not None:
        from ..models import Notebook
        nb = db.query(Notebook).filter_by(id=notebook_id, user_id=user_id).first()
        notebook_name = nb.name if nb else None

    if "is_pinned" in data:
        note.is_pinned = bool(data["is_pinned"])
    if "is_favorite" in data:
        note.is_favorite = bool(data["is_favorite"])
    if "is_archived" in data:
        note.is_archived = bool(data["is_archived"])

    now = _now()
    plain = strip_markdown(body)
    snippet = make_snippet(body)

    # Resolve tag names for file
    tag_names_for_file = [nt.tag.name for nt in note.note_tags]
    if "tags" in data:
        tag_names_for_file = data["tags"] or []
        if not isinstance(tag_names_for_file, list):
            return jsonify({"error": {"code": "validation_error", "message": "tags must be a list"}}), 422

    # Step 1: write file
    created_at = note.created_at
    if created_at and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    file_content = _build_file(title, body, tag_names_for_file, notebook_name, created_at, now)
    storage.put_text(note.storage_key, file_content)

    # Step 2: database update
    try:
        note.title = title
        note.snippet = snippet
        note.search_text = plain
        note.notebook_id = notebook_id
        note.updated_at = now
        note.version += 1

        if "tags" in data:
            tag_err = _sync_tags(db, note, data["tags"], user_id)
            if tag_err:
                db.rollback()
                return jsonify({"error": {"code": "validation_error", "message": tag_err}}), 422

        db.commit()
        db.refresh(note)
    except Exception:
        db.rollback()
        log.exception("DB error updating note %s", note_id)
        return jsonify({"error": {"code": "server_error", "message": "An internal error occurred."}}), 500

    return jsonify(_note_json(note, include_content=True)), 200


# ---------------------------------------------------------------------------
# DELETE /api/notes/<id>  (soft delete → trash)
# ---------------------------------------------------------------------------
@notes_bp.route("/notes/<note_id>", methods=["DELETE"])
@csrf_required
@login_required
def delete_note(note_id):
    db = _db()
    note = db.query(Note).filter_by(id=note_id, user_id=g.current_user.id).first()
    if not note:
        return jsonify({"error": {"code": "not_found", "message": "Note not found"}}), 404

    note.deleted_at = _now()
    db.commit()
    return jsonify({"message": "Note moved to trash"}), 200


# ---------------------------------------------------------------------------
# POST /api/notes/<id>/restore
# ---------------------------------------------------------------------------
@notes_bp.route("/notes/<note_id>/restore", methods=["POST"])
@csrf_required
@login_required
def restore_note(note_id):
    db = _db()
    note = db.query(Note).filter_by(id=note_id, user_id=g.current_user.id).first()
    if not note:
        return jsonify({"error": {"code": "not_found", "message": "Note not found"}}), 404

    note.deleted_at = None
    db.commit()
    return jsonify(_note_json(note)), 200


# ---------------------------------------------------------------------------
# DELETE /api/notes/<id>/permanent
# ---------------------------------------------------------------------------
@notes_bp.route("/notes/<note_id>/permanent", methods=["DELETE"])
@csrf_required
@login_required
def permanent_delete(note_id):
    db = _db()
    note = db.query(Note).filter_by(id=note_id, user_id=g.current_user.id).first()
    if not note:
        return jsonify({"error": {"code": "not_found", "message": "Note not found"}}), 404

    storage = get_storage()
    # Delete attachment files
    for att in note.attachments:
        storage.delete(att.storage_key)
    # Delete the note file
    storage.delete(note.storage_key)
    db.delete(note)
    db.commit()
    return jsonify({"message": "Note permanently deleted"}), 200


# ---------------------------------------------------------------------------
# POST /api/trash/empty
# ---------------------------------------------------------------------------
@notes_bp.route("/trash/empty", methods=["POST"])
@csrf_required
@login_required
def empty_trash():
    db = _db()
    user_id = g.current_user.id

    # Lazy purge first
    _lazy_purge(db, user_id)

    # Then delete remaining trashed notes
    trashed = (
        db.query(Note)
        .filter(Note.user_id == user_id, Note.deleted_at.isnot(None))
        .all()
    )
    storage = get_storage()
    count = 0
    for note in trashed:
        for att in note.attachments:
            storage.delete(att.storage_key)
        storage.delete(note.storage_key)
        db.delete(note)
        count += 1
    db.commit()
    return jsonify({"message": f"Permanently deleted {count} note(s)"}), 200
