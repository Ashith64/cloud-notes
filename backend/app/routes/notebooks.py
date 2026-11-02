"""Notebooks CRUD routes (spec D5).

Deleting a notebook sets its notes' notebook_id to NULL (unfiled).
"""
import logging

from flask import Blueprint, current_app, g, jsonify, request

from ..models import Note, Notebook
from .auth import csrf_required, login_required

log = logging.getLogger(__name__)

notebooks_bp = Blueprint("notebooks", __name__, url_prefix="/api")


def _db():
    return current_app._db_session()


def _notebook_json(nb: Notebook) -> dict:
    return {
        "id": nb.id,
        "name": nb.name,
        "created_at": nb.created_at.isoformat() if nb.created_at else None,
    }


# ---------------------------------------------------------------------------
# GET /api/notebooks
# ---------------------------------------------------------------------------
@notebooks_bp.route("/notebooks", methods=["GET"])
@login_required
def list_notebooks():
    db = _db()
    nbs = (
        db.query(Notebook)
        .filter_by(user_id=g.current_user.id)
        .order_by(Notebook.name)
        .all()
    )
    return jsonify([_notebook_json(nb) for nb in nbs]), 200


# ---------------------------------------------------------------------------
# POST /api/notebooks
# ---------------------------------------------------------------------------
@notebooks_bp.route("/notebooks", methods=["POST"])
@csrf_required
@login_required
def create_notebook():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": {"code": "validation_error", "message": "Name is required"}}), 422
    if len(name) > 120:
        return jsonify({"error": {"code": "validation_error", "message": "Name must be at most 120 characters"}}), 422

    db = _db()
    user_id = g.current_user.id

    existing = db.query(Notebook).filter_by(user_id=user_id, name=name).first()
    if existing:
        return jsonify({"error": {"code": "conflict", "message": "A notebook with that name already exists"}}), 409

    nb = Notebook(user_id=user_id, name=name)
    db.add(nb)
    db.commit()
    db.refresh(nb)

    return jsonify(_notebook_json(nb)), 201


# ---------------------------------------------------------------------------
# PATCH /api/notebooks/<id>
# ---------------------------------------------------------------------------
@notebooks_bp.route("/notebooks/<int:notebook_id>", methods=["PATCH"])
@csrf_required
@login_required
def update_notebook(notebook_id):
    db = _db()
    nb = db.query(Notebook).filter_by(id=notebook_id, user_id=g.current_user.id).first()
    if not nb:
        return jsonify({"error": {"code": "not_found", "message": "Notebook not found"}}), 404

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": {"code": "validation_error", "message": "Name is required"}}), 422
    if len(name) > 120:
        return jsonify({"error": {"code": "validation_error", "message": "Name must be at most 120 characters"}}), 422

    # Check for duplicate name
    existing = db.query(Notebook).filter_by(user_id=g.current_user.id, name=name).first()
    if existing and existing.id != notebook_id:
        return jsonify({"error": {"code": "conflict", "message": "A notebook with that name already exists"}}), 409

    nb.name = name
    db.commit()
    db.refresh(nb)

    return jsonify(_notebook_json(nb)), 200


# ---------------------------------------------------------------------------
# DELETE /api/notebooks/<id>
# ---------------------------------------------------------------------------
@notebooks_bp.route("/notebooks/<int:notebook_id>", methods=["DELETE"])
@csrf_required
@login_required
def delete_notebook(notebook_id):
    db = _db()
    nb = db.query(Notebook).filter_by(id=notebook_id, user_id=g.current_user.id).first()
    if not nb:
        return jsonify({"error": {"code": "not_found", "message": "Notebook not found"}}), 404

    # Unfile all notes in this notebook (set notebook_id = NULL)
    db.query(Note).filter_by(notebook_id=notebook_id).update({"notebook_id": None})
    db.delete(nb)
    db.commit()

    return jsonify({"message": "Notebook deleted"}), 200
