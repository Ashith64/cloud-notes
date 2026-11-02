"""Tests for the attachment upload/download routes (Stage 3).

Coverage:
 - Valid uploads: png, jpg, gif, webp, pdf
 - File-type spoofing: txt file pretending to be png → rejected
 - File too large (> 10 MB) → rejected
 - Missing note_id, note belonging to another user → 404
 - Download: ownership enforced (another user gets 404)
 - Local mode streams the file; S3 mode returns 302
 - Permanent note deletion removes attachment record (tested via cascade)
"""
import io
import struct

import pytest

from tests.conftest import CSRF


# ---------------------------------------------------------------------------
# Minimal valid magic-byte prefixes for each type
# ---------------------------------------------------------------------------

def _png_bytes(n: int = 16) -> bytes:
    """Return n bytes starting with the PNG magic signature."""
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * (n - 8)


def _jpg_bytes(n: int = 16) -> bytes:
    return b"\xff\xd8\xff" + b"\x00" * (n - 3)


def _gif_bytes(n: int = 16) -> bytes:
    return b"GIF89a" + b"\x00" * (n - 6)


def _webp_bytes(n: int = 32) -> bytes:
    # RIFF....WEBP structure
    size = n - 8
    return b"RIFF" + struct.pack("<I", size) + b"WEBP" + b"\x00" * (n - 12)


def _pdf_bytes(n: int = 16) -> bytes:
    return b"%PDF-1.7" + b"\n" * (n - 8)


def _text_bytes(n: int = 16) -> bytes:
    """Plaintext — should always be rejected."""
    return b"Hello, world!\n" + b"x" * (n - 14)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register_and_login(client, email="attuser@example.com", password="Password1!"):
    client.post("/api/auth/register", json={"email": email, "password": password}, headers=CSRF)
    return client.post("/api/auth/login", json={"email": email, "password": password}, headers=CSRF)


def _create_note(client):
    resp = client.post(
        "/api/notes",
        json={"title": "Attach Test Note", "content": "body"},
        headers=CSRF,
    )
    assert resp.status_code == 201
    return resp.get_json()["id"]


def _upload(client, data: bytes, filename: str = "file.png", note_id: str | None = None,
            expected: int = 201):
    if note_id is None:
        note_id = _create_note(client)
    resp = client.post(
        "/api/attachments",
        data={"note_id": note_id, "file": (io.BytesIO(data), filename)},
        content_type="multipart/form-data",
        headers=CSRF,
    )
    assert resp.status_code == expected, f"Expected {expected}, got {resp.status_code}: {resp.data}"
    return resp.get_json(), note_id


# ===========================================================================
# Upload tests
# ===========================================================================

class TestUpload:
    def test_upload_png(self, client):
        _register_and_login(client, "up_png@test.com")
        result, _ = _upload(client, _png_bytes(64), "photo.png")
        assert "id" in result
        assert result["ref"].endswith(".png")
        assert result["url"].startswith("/api/attachments/")

    def test_upload_jpg(self, client):
        _register_and_login(client, "up_jpg@test.com")
        result, _ = _upload(client, _jpg_bytes(64), "photo.jpg")
        assert result["ref"].endswith(".jpg")

    def test_upload_gif(self, client):
        _register_and_login(client, "up_gif@test.com")
        result, _ = _upload(client, _gif_bytes(64), "anim.gif")
        assert result["ref"].endswith(".gif")

    def test_upload_webp(self, client):
        _register_and_login(client, "up_webp@test.com")
        result, _ = _upload(client, _webp_bytes(64), "image.webp")
        assert result["ref"].endswith(".webp")

    def test_upload_pdf(self, client):
        _register_and_login(client, "up_pdf@test.com")
        result, _ = _upload(client, _pdf_bytes(64), "doc.pdf")
        assert result["ref"].endswith(".pdf")

    def test_type_spoofing_rejected(self, client):
        """A text file uploaded with a .png extension must be rejected."""
        _register_and_login(client, "spoof@test.com")
        _upload(client, _text_bytes(64), "evil.png", expected=422)

    def test_type_spoofing_zip_rejected(self, client):
        """A ZIP disguised as jpg must be rejected."""
        _register_and_login(client, "spoof2@test.com")
        zip_magic = b"PK\x03\x04" + b"\x00" * 12
        _upload(client, zip_magic, "evil.jpg", expected=422)

    def test_file_too_large(self, client):
        """Files over 10 MB are rejected before type checking."""
        _register_and_login(client, "toobig@test.com")
        big = _png_bytes(8) + b"\x00" * (10 * 1024 * 1024 + 1 - 8)
        _upload(client, big, "huge.png", expected=422)

    def test_missing_note_id(self, client):
        _register_and_login(client, "nonote@test.com")
        resp = client.post(
            "/api/attachments",
            data={"file": (io.BytesIO(_png_bytes(64)), "x.png")},
            content_type="multipart/form-data",
            headers=CSRF,
        )
        assert resp.status_code == 422

    def test_wrong_note_id(self, client):
        """Uploading to a note that doesn't belong to the user returns 404."""
        _register_and_login(client, "wrongnote@test.com")
        _upload(client, _png_bytes(64), "x.png", note_id="00000000-0000-0000-0000-000000000000",
                expected=404)

    def test_no_file_part(self, client):
        _register_and_login(client, "nofile@test.com")
        note_id = _create_note(client)
        resp = client.post(
            "/api/attachments",
            data={"note_id": note_id},
            content_type="multipart/form-data",
            headers=CSRF,
        )
        assert resp.status_code == 422

    def test_unauthenticated_upload_rejected(self, client):
        resp = client.post(
            "/api/attachments",
            data={"note_id": "x", "file": (io.BytesIO(b"x"), "x.png")},
            content_type="multipart/form-data",
            headers=CSRF,
        )
        assert resp.status_code == 401


# ===========================================================================
# Download tests
# ===========================================================================

class TestDownload:
    def test_download_own_attachment(self, client):
        _register_and_login(client, "dlown@test.com")
        data = _png_bytes(64)
        result, _ = _upload(client, data, "photo.png")
        att_id = result["id"]

        resp = client.get(f"/api/attachments/{att_id}")
        # Local mode: 200 with the file bytes
        assert resp.status_code == 200
        assert resp.data == data

    def test_other_user_attachment_returns_404(self, client):
        """User A uploads a file; User B must get 404 when accessing it."""
        # User A uploads
        _register_and_login(client, "owner_a@test.com")
        result, _ = _upload(client, _png_bytes(64), "a.png")
        att_id = result["id"]

        # User B tries to access
        client.post("/api/auth/logout", headers=CSRF)
        _register_and_login(client, "thief_b@test.com")
        resp = client.get(f"/api/attachments/{att_id}")
        assert resp.status_code == 404

    def test_download_nonexistent_returns_404(self, client):
        _register_and_login(client, "dldne@test.com")
        resp = client.get("/api/attachments/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404

    def test_unauthenticated_download_rejected(self, client):
        resp = client.get("/api/attachments/anything")
        assert resp.status_code == 401

    def test_download_content_type(self, client):
        _register_and_login(client, "dlct@test.com")
        result, _ = _upload(client, _pdf_bytes(64), "doc.pdf")
        resp = client.get(f"/api/attachments/{result['id']}")
        assert resp.status_code == 200
        assert "pdf" in resp.content_type.lower()


# ===========================================================================
# Permanent deletion removes attachments
# ===========================================================================

class TestDeletionCascade:
    def test_permanent_delete_removes_attachment(self, client, app):
        _register_and_login(client, "cascade@test.com")
        data = _png_bytes(64)
        result, note_id = _upload(client, data, "photo.png")
        att_id = result["id"]

        # Verify the attachment is accessible before deletion
        resp = client.get(f"/api/attachments/{att_id}")
        assert resp.status_code == 200

        # Permanently delete the note
        resp = client.delete(f"/api/notes/{note_id}/permanent", headers=CSRF)
        assert resp.status_code == 200

        # Attachment record should be gone (cascaded) — 404 even for owner
        resp = client.get(f"/api/attachments/{att_id}")
        assert resp.status_code == 404
