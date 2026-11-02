"""Authentication routes: register, login, logout, me, change-password, demo.

All state-changing endpoints also require the X-Requested-With: cloudnotes
header (CSRF guard, checked by the csrf_required decorator).
JWT is stored in an httpOnly, SameSite=Lax cookie (Secure when not in debug
or testing mode).
"""
import logging
import re
from datetime import datetime, timedelta, timezone
from functools import wraps

import bcrypt
import jwt
from flask import Blueprint, current_app, g, jsonify, request

from ..models import User

log = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_COOKIE_NAME = "cloudnotes_token"
_FAILED_LIMIT = 5
_LOCK_MINUTES = 10
_DEMO_EMAIL = "demo@cloudnotes.app"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _db():
    """Return the SQLAlchemy session bound to the current app instance.

    Using current_app._db_session() ensures each app instance (e.g. test apps)
    has its own scoped session and does not pollute the module-level global.
    """
    return current_app._db_session()


def _set_cookie(response, token: str) -> None:
    """Attach the JWT cookie to *response*."""
    debug = current_app.debug
    testing = current_app.config.get("TESTING", False)
    response.set_cookie(
        _COOKIE_NAME,
        token,
        httponly=True,
        samesite="Lax",
        # Secure flag only in production (not in debug or test environments).
        secure=(not debug and not testing),
        max_age=int(current_app.config["JWT_EXPIRY_DAYS"]) * 86400,
        path="/",
    )


def _make_token(user_id: int) -> str:
    secret = current_app.config["SECRET_KEY"]
    expiry_days = int(current_app.config["JWT_EXPIRY_DAYS"])
    payload = {
        "sub": str(user_id),  # JWT spec requires sub to be a string
        "exp": datetime.now(timezone.utc) + timedelta(days=expiry_days),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _decode_token(token: str) -> dict | None:
    try:
        secret = current_app.config["SECRET_KEY"]
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _check_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def login_required(fn):
    """Require a valid JWT cookie; sets g.current_user."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = request.cookies.get(_COOKIE_NAME)
        if not token:
            return jsonify({"error": {"code": "unauthorized", "message": "Not authenticated"}}), 401
        payload = _decode_token(token)
        if not payload:
            return jsonify({"error": {"code": "unauthorized", "message": "Invalid or expired session"}}), 401

        db = _db()
        user = db.get(User, int(payload["sub"]))  # sub is stored as string
        if not user:
            return jsonify({"error": {"code": "unauthorized", "message": "User not found"}}), 401

        g.current_user = user
        return fn(*args, **kwargs)
    return wrapper


def csrf_required(fn):
    """Reject state-changing requests missing X-Requested-With: cloudnotes."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if request.method in ("POST", "PATCH", "PUT", "DELETE"):
            header = request.headers.get("X-Requested-With", "")
            if header.lower() != "cloudnotes":
                return jsonify({
                    "error": {
                        "code": "forbidden",
                        "message": "Missing or invalid X-Requested-With header",
                    }
                }), 403
        return fn(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@auth_bp.route("/register", methods=["POST"])
@csrf_required
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    name = (data.get("name") or "").strip()

    errors = {}
    if not email or not _EMAIL_RE.match(email):
        errors["email"] = "A valid email address is required."
    if len(password) < 8:
        errors["password"] = "Password must be at least 8 characters."
    if errors:
        return jsonify({"error": {"code": "validation_error", "message": "Invalid input", "fields": errors}}), 422

    db = _db()
    if db.query(User).filter_by(email=email).first():
        return jsonify({"error": {"code": "conflict", "message": "An account with that email already exists."}}), 409

    user = User(
        email=email,
        name=name or email.split("@")[0],
        password_hash=_hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = _make_token(user.id)
    resp = jsonify({"id": user.id, "email": user.email, "name": user.name})
    _set_cookie(resp, token)
    log.info("Registered user %s", user.email)
    return resp, 201


@auth_bp.route("/login", methods=["POST"])
@csrf_required
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    _BAD = {"error": {"code": "unauthorized", "message": "That email or password doesn't look right."}}

    if not email or not password:
        return jsonify(_BAD), 401

    db = _db()
    user: User | None = db.query(User).filter_by(email=email).first()
    if not user:
        return jsonify(_BAD), 401

    now = datetime.now(timezone.utc)

    # Check lockout
    if user.locked_until:
        locked_until = user.locked_until
        # SQLite stores naive datetimes; normalise to UTC-aware.
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if now < locked_until:
            return jsonify({
                "error": {
                    "code": "locked",
                    "message": "Account is temporarily locked due to too many failed login attempts. Try again in a few minutes.",
                }
            }), 429

    if not _check_password(password, user.password_hash):
        user.failed_logins = (user.failed_logins or 0) + 1
        if user.failed_logins >= _FAILED_LIMIT:
            user.locked_until = now + timedelta(minutes=_LOCK_MINUTES)
            user.failed_logins = 0
        db.commit()
        return jsonify(_BAD), 401

    # Successful login – reset counters
    user.failed_logins = 0
    user.locked_until = None
    db.commit()

    token = _make_token(user.id)
    resp = jsonify({"id": user.id, "email": user.email, "name": user.name})
    _set_cookie(resp, token)
    return resp, 200


@auth_bp.route("/logout", methods=["POST"])
@csrf_required
def logout():
    resp = jsonify({"message": "Logged out"})
    resp.delete_cookie(_COOKIE_NAME, path="/")
    return resp, 200


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    user: User = g.current_user
    return jsonify({"id": user.id, "email": user.email, "name": user.name}), 200


@auth_bp.route("/change-password", methods=["POST"])
@csrf_required
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    old_password = data.get("old_password") or ""
    new_password = data.get("new_password") or ""

    if len(new_password) < 8:
        return jsonify({"error": {"code": "validation_error", "message": "New password must be at least 8 characters."}}), 422

    user: User = g.current_user
    if not _check_password(old_password, user.password_hash):
        return jsonify({"error": {"code": "unauthorized", "message": "Current password is incorrect."}}), 401

    db = _db()
    db_user = db.get(User, user.id)
    db_user.password_hash = _hash_password(new_password)
    db.commit()

    return jsonify({"message": "Password updated."}), 200


@auth_bp.route("/demo", methods=["POST"])
@csrf_required
def demo():
    """Create or reuse the demo account and return a session cookie.

    Note content is seeded in Stage 3.  This route just ensures the user exists.
    """
    db = _db()
    user: User | None = db.query(User).filter_by(email=_DEMO_EMAIL).first()
    if not user:
        user = User(
            email=_DEMO_EMAIL,
            name="Demo User",
            password_hash=_hash_password("demo-password-not-for-login"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = _make_token(user.id)
    resp = jsonify({"id": user.id, "email": user.email, "name": user.name})
    _set_cookie(resp, token)
    return resp, 200
