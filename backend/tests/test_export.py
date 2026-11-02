"""Tests for export routes (Stage 3).

Coverage:
 - Single note export: valid .md download with correct filename
 - Single note export: 404 for another user's note
 - Full ZIP export: correct structure (notes/, attachments/)
 - Attachment refs rewritten: attachments/x.png → ../attachments/x.png
 - ZIP size cap (200 MB) — tested with mocked large content
 - Empty export: ZIP with no notes still returns 200 with valid zip
"""
import io
import struct
import zipfile

import pytest

from tests.conftest import CSRF


def _login(client, email, password="Password1!"):
    client.post("/api/auth/register", json={"email": email, "password": password}, headers=CSRF)
    client.post("/api/auth/login", json={"email": email, "password": password}, headers=CSRF)


def _create_note(client, title="Test Note", content="Hello **world**") -> str:
    resp = client.post("/api/notes", json={"title": title, "content": content}, headers=CSRF)
    assert resp.status_code == 201
    return resp.get_json()["id"]


def _png_bytes(n: int = 16) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * (n - 8)


def _upload_attachment(client, note_id: str) -> dict:
    resp = client.post(
        "/api/attachments",
        data={"note_id": note_id, "file": (io.BytesIO(_png_bytes(64)), "photo.png")},
        content_type="multipart/form-data",
        headers=CSRF,
    )
    assert resp.status_code == 201
    return resp.get_json()


# ===========================================================================
# Single note export
# ===========================================================================

class TestSingleExport:
    def test_export_single_note(self, client):
        _login(client, "single_export@test.com")
        note_id = _create_note(client, title="My Cloud Note", content="## Hello\n\nWorld")
        resp = client.get(f"/api/notes/{note_id}/export")
        assert resp.status_code == 200
        assert "markdown" in resp.content_type.lower() or "text" in resp.content_type.lower()
        cd = resp.headers.get("Content-Disposition", "")
        assert "attachment" in cd
        assert ".md" in cd
        # The file content should include front matter + body
        body = resp.data.decode("utf-8")
        assert "My Cloud Note" in body
        assert "Hello" in body

    def test_export_single_filename_safe(self, client):
        """Filename uses safe title + short ID."""
        _login(client, "single_fn@test.com")
        note_id = _create_note(client, title="Special / Title <>&")
        resp = client.get(f"/api/notes/{note_id}/export")
        assert resp.status_code == 200
        cd = resp.headers.get("Content-Disposition", "")
        # Should not contain raw special characters
        assert "/" not in cd.split("filename=")[-1].strip('"')

    def test_export_single_wrong_user(self, client):
        """Exporting another user's note returns 404."""
        _login(client, "exp_owner@test.com")
        note_id = _create_note(client)

        client.post("/api/auth/logout", headers=CSRF)
        _login(client, "exp_thief@test.com")
        resp = client.get(f"/api/notes/{note_id}/export")
        assert resp.status_code == 404

    def test_export_single_unauthenticated(self, client):
        resp = client.get("/api/notes/anything/export")
        assert resp.status_code == 401


# ===========================================================================
# Full ZIP export
# ===========================================================================

class TestZipExport:
    def test_zip_export_empty(self, client):
        """User with no notes should still get a valid (empty) zip."""
        _login(client, "zip_empty@test.com")
        resp = client.get("/api/export")
        assert resp.status_code == 200
        assert "zip" in resp.content_type.lower()
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        assert zf.namelist() == []

    def test_zip_export_contains_notes(self, client):
        _login(client, "zip_notes@test.com")
        _create_note(client, title="Alpha Note", content="Alpha content")
        _create_note(client, title="Beta Note", content="Beta content")
        resp = client.get("/api/export")
        assert resp.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        names = zf.namelist()
        # Two .md files in notes/
        md_files = [n for n in names if n.startswith("notes/") and n.endswith(".md")]
        assert len(md_files) == 2

    def test_zip_export_attachment_refs_rewritten(self, client):
        """Attachment refs in note body → ../attachments/<file>."""
        _login(client, "zip_refs@test.com")
        note_id = _create_note(
            client,
            title="Note With Attachment",
            content="Look: ![photo](attachments/abc123.png)",
        )
        resp = client.get("/api/export")
        assert resp.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        md_files = [n for n in zf.namelist() if n.startswith("notes/")]
        assert len(md_files) == 1
        content = zf.read(md_files[0]).decode("utf-8")
        # Original ref should be rewritten
        assert "../attachments/abc123.png" in content
        assert "attachments/abc123.png" not in content.replace("../attachments/", "")

    def test_zip_export_includes_attachment_file(self, client):
        """Uploaded attachments should appear under attachments/ in the ZIP."""
        _login(client, "zip_att@test.com")
        note_id = _create_note(client, title="Note For Attachment")
        att = _upload_attachment(client, note_id)
        att_filename = att["ref"].split("/")[-1]  # e.g. "<uuid>.png"

        resp = client.get("/api/export")
        assert resp.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        att_names = [n for n in zf.namelist() if n.startswith("attachments/")]
        assert any(att_filename in n for n in att_names), \
            f"{att_filename} not found in {att_names}"

    def test_zip_export_unauthenticated(self, client):
        resp = client.get("/api/export")
        assert resp.status_code == 401

    def test_zip_export_download_header(self, client):
        _login(client, "zip_hdr@test.com")
        resp = client.get("/api/export")
        assert resp.status_code == 200
        cd = resp.headers.get("Content-Disposition", "")
        assert "attachment" in cd
        assert ".zip" in cd

    def test_zip_export_iso_filename_safe(self, client):
        """Title with unicode and special chars produces safe archive entry."""
        _login(client, "zip_iso@test.com")
        _create_note(client, title="Héllo Wörld / <notes>", content="body")
        resp = client.get("/api/export")
        assert resp.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(resp.data))
        for name in zf.namelist():
            # No path traversal characters
            assert ".." not in name
            assert name.startswith("notes/") or name.startswith("attachments/")

    def test_zip_size_limit(self, client, monkeypatch):
        """Simulates a note file exceeding the 200 MB cap."""
        _login(client, "zip_size@test.com")
        _create_note(client, title="Big Note", content="x")

        from app.storage import local as local_mod

        original_get_text = local_mod.LocalStorage.get_text

        def huge_get_text(self, key):
            # Return a tiny real file (to pass frontmatter parse) only for note files,
            # but patch the size-tracking: we'll monkeypatch at route level instead.
            return original_get_text(self, key)

        # Monkeypatch the MAX constant in the export route module
        import app.routes.export_routes as exp_mod
        monkeypatch.setattr(exp_mod, "_MAX_EXPORT_BYTES", 1)  # cap at 1 byte

        resp = client.get("/api/export")
        assert resp.status_code == 413
        data = resp.get_json()
        assert data["error"]["code"] == "payload_too_large"
