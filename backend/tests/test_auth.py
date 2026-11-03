"""Tests for auth routes: register, login, logout, me, change-password, demo.

Also covers the CSRF header check (X-Requested-With: cloudnotes) and
account lockout after 5 failed login attempts.
"""
import pytest


CSRF = {"X-Requested-With": "cloudnotes"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def register(client, email="user@example.com", password="password123", name="Test User"):
    return client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "name": name},
        headers=CSRF,
    )


def login(client, email="user@example.com", password="password123"):
    return client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
        headers=CSRF,
    )


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

def test_register_success(client):
    rv = register(client, email="new@example.com", password="securepass1")
    assert rv.status_code == 201
    data = rv.get_json()
    assert data["email"] == "new@example.com"
    # Cookie should be set
    assert "cloudnotes_token" in rv.headers.get("Set-Cookie", "")


def test_register_duplicate_email(client):
    register(client, email="dup@example.com", password="password123")
    rv = register(client, email="dup@example.com", password="password123")
    assert rv.status_code == 409
    assert rv.get_json()["error"]["code"] == "conflict"


def test_register_invalid_email(client):
    rv = register(client, email="not-an-email", password="password123")
    assert rv.status_code == 422
    body = rv.get_json()
    assert body["error"]["code"] == "validation_error"
    assert "email" in body["error"]["fields"]


def test_register_short_password(client):
    rv = register(client, email="short@example.com", password="short")
    assert rv.status_code == 422
    body = rv.get_json()
    assert "password" in body["error"]["fields"]


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def test_login_success(client):
    register(client, email="login@example.com", password="mypassword")
    rv = login(client, email="login@example.com", password="mypassword")
    assert rv.status_code == 200
    assert rv.get_json()["email"] == "login@example.com"


def test_login_wrong_password(client):
    register(client, email="wrong@example.com", password="correctpass")
    rv = login(client, email="wrong@example.com", password="wrongpass")
    assert rv.status_code == 401
    # Generic error – must not reveal whether it was email or password
    assert "doesn't look right" in rv.get_json()["error"]["message"]


def test_login_nonexistent_user(client):
    rv = login(client, email="nobody@example.com", password="anything")
    assert rv.status_code == 401


# ---------------------------------------------------------------------------
# Lockout after 5 failures
# ---------------------------------------------------------------------------

def test_lockout_after_five_failures(client):
    register(client, email="lockme@example.com", password="realpassword")

    for i in range(5):
        rv = login(client, email="lockme@example.com", password="wrongpass")
        assert rv.status_code == 401

    # 6th attempt should be locked
    rv = login(client, email="lockme@example.com", password="wrongpass")
    assert rv.status_code == 429
    assert rv.get_json()["error"]["code"] == "locked"


def test_lockout_blocks_correct_password(client):
    register(client, email="lockme2@example.com", password="realpassword2")

    for _ in range(5):
        login(client, email="lockme2@example.com", password="wrongpass")

    # Even correct password is blocked while locked
    rv = login(client, email="lockme2@example.com", password="realpassword2")
    assert rv.status_code == 429


# ---------------------------------------------------------------------------
# Me (authenticated)
# ---------------------------------------------------------------------------

def test_me_with_cookie(client):
    # Register sets a session cookie; immediately call /me in the same client
    rv = register(client, email="me@example.com", password="password123")
    assert rv.status_code == 201  # cookie is set

    # /me should work because the client jar carries the cookie
    rv2 = client.get("/api/auth/me")
    assert rv2.status_code == 200
    assert rv2.get_json()["email"] == "me@example.com"


def test_me_without_cookie(app):
    """A fresh test client with no cookie must get 401."""
    # Use the session-scoped app fixture so the test is DB-agnostic
    # (works with both SQLite and MySQL).
    with app.test_client() as c:
        # Do NOT set any cookie — just hit the protected endpoint.
        rv = c.get("/api/auth/me")
        assert rv.status_code == 401


# ---------------------------------------------------------------------------
# Change password
# ---------------------------------------------------------------------------

def test_change_password(client):
    # Register (sets cookie), then change password in the same session
    rv = register(client, email="chpass@example.com", password="oldpassword")
    assert rv.status_code == 201

    rv = client.post(
        "/api/auth/change-password",
        json={"old_password": "oldpassword", "new_password": "newpassword1"},
        headers=CSRF,
    )
    assert rv.status_code == 200

    # Old password no longer works (test with a fresh client to avoid using cached cookie)
    rv2 = client.post(
        "/api/auth/login",
        json={"email": "chpass@example.com", "password": "oldpassword"},
        headers=CSRF,
    )
    assert rv2.status_code == 401

    # New password works
    rv3 = client.post(
        "/api/auth/login",
        json={"email": "chpass@example.com", "password": "newpassword1"},
        headers=CSRF,
    )
    assert rv3.status_code == 200


def test_change_password_wrong_old(client):
    # Register to get a session cookie, then try wrong old password
    rv = register(client, email="chpass2@example.com", password="mypassword")
    assert rv.status_code == 201

    rv = client.post(
        "/api/auth/change-password",
        json={"old_password": "wrongold", "new_password": "newpassword1"},
        headers=CSRF,
    )
    assert rv.status_code == 401


def test_change_password_short_new(client):
    # Register to get a session cookie, then try a too-short new password
    rv = register(client, email="chpass3@example.com", password="mypassword")
    assert rv.status_code == 201

    rv = client.post(
        "/api/auth/change-password",
        json={"old_password": "mypassword", "new_password": "short"},
        headers=CSRF,
    )
    assert rv.status_code == 422


# ---------------------------------------------------------------------------
# CSRF header check
# ---------------------------------------------------------------------------

def test_csrf_header_required_for_register(client):
    rv = client.post(
        "/api/auth/register",
        json={"email": "csrf@example.com", "password": "password123"},
        # No CSRF header
    )
    assert rv.status_code == 403
    assert rv.get_json()["error"]["code"] == "forbidden"


def test_csrf_header_required_for_login(client):
    rv = client.post(
        "/api/auth/login",
        json={"email": "someone@example.com", "password": "somepass"},
    )
    assert rv.status_code == 403


def test_csrf_header_required_for_logout(client):
    rv = client.post("/api/auth/logout")
    assert rv.status_code == 403


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def test_demo_creates_session(client):
    rv = client.post("/api/auth/demo", headers=CSRF)
    assert rv.status_code == 200
    assert rv.get_json()["email"] == "demo@cloudnotes.app"
    assert "cloudnotes_token" in rv.headers.get("Set-Cookie", "")


def test_demo_idempotent(client):
    """Calling demo twice should not create a duplicate user."""
    rv1 = client.post("/api/auth/demo", headers=CSRF)
    rv2 = client.post("/api/auth/demo", headers=CSRF)
    assert rv1.status_code == 200
    assert rv2.status_code == 200
    # Same user id returned both times
    assert rv1.get_json()["id"] == rv2.get_json()["id"]
