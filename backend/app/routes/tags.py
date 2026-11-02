"""Tags read-only route (spec D5): GET /api/tags returns name + note count."""
from flask import Blueprint, current_app, g, jsonify
from sqlalchemy import func

from ..models import NoteTag, Tag
from .auth import login_required

tags_bp = Blueprint("tags", __name__, url_prefix="/api")


def _db():
    return current_app._db_session()


@tags_bp.route("/tags", methods=["GET"])
@login_required
def list_tags():
    db = _db()
    user_id = g.current_user.id
    rows = (
        db.query(Tag.name, func.count(NoteTag.note_id).label("count"))
        .outerjoin(NoteTag, Tag.id == NoteTag.tag_id)
        .filter(Tag.user_id == user_id)
        .group_by(Tag.id, Tag.name)
        .order_by(Tag.name)
        .all()
    )
    return jsonify([{"name": r.name, "count": r.count} for r in rows]), 200
