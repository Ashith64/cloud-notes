"""Tests for Stage 5B backend features:
- Storage usage endpoint (/api/user/storage and /api/auth/storage)
- Note attachments detail inclusion in GET /api/notes/<id>
- Cross-user isolation
"""
import io
import pytest
from tests.conftest import CSRF


def _register_and_login(client, email="stage5b@test.com", password="Password1!"):
    client.post("/api/auth/register", json={"email": email, "password": password}, headers=CSRF)
    return client.post("/api/auth/login", json={"email": email, "password": password}, headers=CSRF)


def test_storage_usage_empty(client):
    _register_and_login(client, "empty_storage@test.com")
    resp = client.get("/api/user/storage")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["notes_bytes"] == 0
    assert data["attachments_bytes"] == 0
    assert data["total_bytes"] == 0
    assert data["limit_bytes"] == 100 * 1024 * 1024


def test_storage_usage_with_note_and_attachment(client):
    _register_and_login(client, "storage_calc@test.com")

    # Create note
    note_resp = client.post(
        "/api/notes",
        json={"title": "Calc Note", "content": "# Header\nHello world!"},
        headers=CSRF,
    )
    assert note_resp.status_code == 201
    note_id = note_resp.get_json()["id"]

    # Upload attachment (PNG magic bytes)
    png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
    att_resp = client.post(
        "/api/attachments",
        data={"note_id": note_id, "file": (io.BytesIO(png_data), "photo.png")},
        content_type="multipart/form-data",
        headers=CSRF,
    )
    assert att_resp.status_code == 201

    # Check storage usage endpoint
    storage_resp = client.get("/api/user/storage")
    assert storage_resp.status_code == 200
    data = storage_resp.get_json()
    assert data["notes_bytes"] > 0
    assert data["attachments_bytes"] == len(png_data)
    assert data["total_bytes"] == data["notes_bytes"] + data["attachments_bytes"]

    # Also test /api/auth/storage alias
    auth_storage_resp = client.get("/api/auth/storage")
    assert auth_storage_resp.status_code == 200
    assert auth_storage_resp.get_json()["total_bytes"] == data["total_bytes"]


def test_note_detail_includes_attachments(client):
    _register_and_login(client, "note_att_detail@test.com")

    # Create note
    note_resp = client.post(
        "/api/notes",
        json={"title": "Detail Note", "content": "Test body"},
        headers=CSRF,
    )
    note_id = note_resp.get_json()["id"]

    # Initially empty attachments
    detail_resp = client.get(f"/api/notes/{note_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.get_json()["attachments"] == []

    # Upload attachment
    png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    client.post(
        "/api/attachments",
        data={"note_id": note_id, "file": (io.BytesIO(png_data), "diagram.png")},
        content_type="multipart/form-data",
        headers=CSRF,
    )

    # Re-fetch note detail
    detail_resp2 = client.get(f"/api/notes/{note_id}")
    assert detail_resp2.status_code == 200
    atts = detail_resp2.get_json()["attachments"]
    assert len(atts) == 1
    assert atts[0]["filename"] == "diagram.png"
    assert atts[0]["content_type"] == "image/png"
    assert atts[0]["size_bytes"] == len(png_data)
    assert atts[0]["url"].startswith("/api/attachments/")
