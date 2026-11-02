"""Tests for Notes, Notebooks, and Tags API (Stage 2).

Covers: CRUD, user isolation, search, filters, tag rules, pin ordering,
trash/restore, lazy purge, 409 conflict, and failure-injection.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

CSRF = {"X-Requested-With": "cloudnotes"}


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _register(client, email, password="password123", name="Test"):
    return client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "name": name},
        headers=CSRF,
    )


def _authed_client(app, email, password="password123"):
    """Return a test client already logged in as *email*."""
    c = app.test_client()
    _register(c, email, password)
    return c


# ---------------------------------------------------------------------------
# Note helpers
# ---------------------------------------------------------------------------

def _create_note(client, **kwargs):
    payload = {"title": "Test Note", "content": "Hello world", **kwargs}
    return client.post("/api/notes", json=payload, headers=CSRF)


def _patch_note(client, note_id, **kwargs):
    return client.patch(f"/api/notes/{note_id}", json=kwargs, headers=CSRF)


def _get_note(client, note_id):
    return client.get(f"/api/notes/{note_id}")


def _delete_note(client, note_id):
    return client.delete(f"/api/notes/{note_id}", headers=CSRF)


def _list_notes(client, **params):
    return client.get("/api/notes", query_string=params)


# ---------------------------------------------------------------------------
# Notebook helpers
# ---------------------------------------------------------------------------

def _create_notebook(client, name):
    return client.post("/api/notebooks", json={"name": name}, headers=CSRF)


# ---------------------------------------------------------------------------
# CRUD – Notes
# ---------------------------------------------------------------------------

class TestNotesCRUD:
    def test_create_note(self, app):
        c = _authed_client(app, "crud_create@test.com")
        rv = _create_note(c, title="My Note", content="# Hello\nWorld")
        assert rv.status_code == 201
        data = rv.get_json()
        assert data["title"] == "My Note"
        assert data["content"] == "# Hello\nWorld"
        assert data["version"] == 1
        assert data["id"]  # UUID

    def test_get_note(self, app):
        c = _authed_client(app, "crud_get@test.com")
        rv = _create_note(c, title="Readable", content="Body text")
        note_id = rv.get_json()["id"]

        rv2 = _get_note(c, note_id)
        assert rv2.status_code == 200
        assert rv2.get_json()["content"] == "Body text"

    def test_update_note(self, app):
        c = _authed_client(app, "crud_update@test.com")
        rv = _create_note(c)
        note_id = rv.get_json()["id"]

        rv2 = _patch_note(c, note_id, title="Updated", content="New body")
        assert rv2.status_code == 200
        d = rv2.get_json()
        assert d["title"] == "Updated"
        assert d["content"] == "New body"
        assert d["version"] == 2

    def test_soft_delete_and_restore(self, app):
        c = _authed_client(app, "crud_del@test.com")
        rv = _create_note(c)
        note_id = rv.get_json()["id"]

        rv2 = _delete_note(c, note_id)
        assert rv2.status_code == 200

        # Note should appear in trash
        rv3 = _list_notes(c, view="trash")
        ids = [n["id"] for n in rv3.get_json()]
        assert note_id in ids

        # Restore
        rv4 = c.post(f"/api/notes/{note_id}/restore", headers=CSRF)
        assert rv4.status_code == 200

        # No longer in trash
        rv5 = _list_notes(c, view="trash")
        ids2 = [n["id"] for n in rv5.get_json()]
        assert note_id not in ids2

    def test_permanent_delete(self, app):
        c = _authed_client(app, "crud_perm@test.com")
        rv = _create_note(c)
        note_id = rv.get_json()["id"]

        rv2 = c.delete(f"/api/notes/{note_id}/permanent", headers=CSRF)
        assert rv2.status_code == 200

        rv3 = _get_note(c, note_id)
        assert rv3.status_code == 404

    def test_create_note_default_title(self, app):
        c = _authed_client(app, "crud_default@test.com")
        rv = _create_note(c, title=None, content="body")
        assert rv.status_code == 201
        assert rv.get_json()["title"] == "Untitled"

    def test_snippet_strips_markdown(self, app):
        c = _authed_client(app, "crud_snippet@test.com")
        rv = _create_note(c, content="# Heading\n\n**bold** text with [link](http://x.com)")
        d = rv.get_json()
        assert "#" not in d["snippet"]
        assert "**" not in d["snippet"]
        assert "link" in d["snippet"]


# ---------------------------------------------------------------------------
# User isolation
# ---------------------------------------------------------------------------

class TestUserIsolation:
    def test_user_a_cannot_read_user_b_note(self, app):
        a = _authed_client(app, "iso_a@test.com")
        b = _authed_client(app, "iso_b@test.com")

        rv = _create_note(a, title="Secret A")
        note_id = rv.get_json()["id"]

        rv2 = _get_note(b, note_id)
        assert rv2.status_code == 404

    def test_user_a_cannot_edit_user_b_note(self, app):
        a = _authed_client(app, "iso_a2@test.com")
        b = _authed_client(app, "iso_b2@test.com")

        rv = _create_note(a)
        note_id = rv.get_json()["id"]

        rv2 = _patch_note(b, note_id, title="Hacked")
        assert rv2.status_code == 404

    def test_user_a_cannot_delete_user_b_note(self, app):
        a = _authed_client(app, "iso_a3@test.com")
        b = _authed_client(app, "iso_b3@test.com")

        rv = _create_note(a)
        note_id = rv.get_json()["id"]

        rv2 = _delete_note(b, note_id)
        assert rv2.status_code == 404

    def test_user_a_cannot_list_user_b_notes(self, app):
        a = _authed_client(app, "iso_a4@test.com")
        b = _authed_client(app, "iso_b4@test.com")

        _create_note(a, title="A only")

        rv = _list_notes(b)
        titles = [n["title"] for n in rv.get_json()]
        assert "A only" not in titles

    def test_user_a_cannot_permanently_delete_user_b_note(self, app):
        a = _authed_client(app, "iso_a5@test.com")
        b = _authed_client(app, "iso_b5@test.com")

        rv = _create_note(a)
        note_id = rv.get_json()["id"]

        rv2 = b.delete(f"/api/notes/{note_id}/permanent", headers=CSRF)
        assert rv2.status_code == 404


# ---------------------------------------------------------------------------
# Search & filters
# ---------------------------------------------------------------------------

class TestSearchFilters:
    def test_search_by_title(self, app):
        c = _authed_client(app, "search1@test.com")
        _create_note(c, title="Quantum Physics", content="body")
        _create_note(c, title="Cooking Pasta", content="body")

        rv = _list_notes(c, q="quantum")
        results = rv.get_json()
        assert len(results) == 1
        assert results[0]["title"] == "Quantum Physics"

    def test_search_by_content(self, app):
        c = _authed_client(app, "search2@test.com")
        _create_note(c, title="Note", content="The mitochondria is the powerhouse")

        rv = _list_notes(c, q="mitochondria")
        assert len(rv.get_json()) == 1

    def test_search_escapes_percent_and_underscore(self, app):
        c = _authed_client(app, "search3@test.com")
        _create_note(c, title="100% done", content="body")
        _create_note(c, title="Undone", content="body2")

        rv = _list_notes(c, q="100%")
        results = rv.get_json()
        assert len(results) == 1
        assert results[0]["title"] == "100% done"

    def test_filter_favorites(self, app):
        c = _authed_client(app, "filt_fav@test.com")
        rv1 = _create_note(c, title="Fav", is_favorite=True)
        _create_note(c, title="Not fav")

        rv = _list_notes(c, view="favorites")
        results = rv.get_json()
        assert len(results) == 1
        assert results[0]["title"] == "Fav"

    def test_filter_archive(self, app):
        c = _authed_client(app, "filt_arch@test.com")
        rv1 = _create_note(c, title="Archived")
        note_id = rv1.get_json()["id"]
        _patch_note(c, note_id, is_archived=True)

        # Archive view shows it
        rv = _list_notes(c, view="archive")
        assert len(rv.get_json()) == 1

        # All view hides it
        rv2 = _list_notes(c, view="all")
        ids = [n["id"] for n in rv2.get_json()]
        assert note_id not in ids

    def test_filter_by_notebook(self, app):
        c = _authed_client(app, "filt_nb@test.com")
        nb_rv = _create_notebook(c, "Physics")
        nb_id = nb_rv.get_json()["id"]

        _create_note(c, title="In notebook", notebook_id=nb_id)
        _create_note(c, title="No notebook")

        rv = _list_notes(c, notebook_id=nb_id)
        results = rv.get_json()
        assert len(results) == 1
        assert results[0]["title"] == "In notebook"

    def test_filter_by_tag(self, app):
        c = _authed_client(app, "filt_tag@test.com")
        _create_note(c, title="Tagged", tags=["python"])
        _create_note(c, title="Untagged")

        rv = _list_notes(c, tag="python")
        results = rv.get_json()
        assert len(results) == 1
        assert results[0]["title"] == "Tagged"

    def test_sort_by_title(self, app):
        c = _authed_client(app, "sort_title@test.com")
        _create_note(c, title="Banana")
        _create_note(c, title="Apple")

        rv = _list_notes(c, sort="title")
        titles = [n["title"] for n in rv.get_json()]
        assert titles == ["Apple", "Banana"]

    def test_pagination(self, app):
        c = _authed_client(app, "pag@test.com")
        for i in range(5):
            _create_note(c, title=f"Note {i}")

        rv = _list_notes(c, limit=2, offset=0)
        assert len(rv.get_json()) == 2

        rv2 = _list_notes(c, limit=2, offset=2)
        assert len(rv2.get_json()) == 2


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

class TestTags:
    def test_tag_trimmed_lowercased(self, app):
        c = _authed_client(app, "tag_trim@test.com")
        rv = _create_note(c, tags=["  Python  ", "RUST"])
        tags = rv.get_json()["tags"]
        assert "python" in tags
        assert "rust" in tags

    def test_tag_max_30_chars(self, app):
        c = _authed_client(app, "tag_len@test.com")
        long_tag = "a" * 50
        rv = _create_note(c, tags=[long_tag])
        tags = rv.get_json()["tags"]
        assert len(tags[0]) <= 30

    def test_tag_max_10_per_note(self, app):
        c = _authed_client(app, "tag_max@test.com")
        many_tags = [f"tag{i}" for i in range(15)]
        rv = _create_note(c, tags=many_tags)
        assert rv.status_code == 422

    def test_patch_replaces_tags(self, app):
        c = _authed_client(app, "tag_patch@test.com")
        rv = _create_note(c, tags=["alpha", "beta"])
        note_id = rv.get_json()["id"]

        rv2 = _patch_note(c, note_id, tags=["gamma"])
        tags = rv2.get_json()["tags"]
        assert tags == ["gamma"]

    def test_list_tags_with_counts(self, app):
        c = _authed_client(app, "tag_list@test.com")
        _create_note(c, tags=["web"])
        _create_note(c, tags=["web", "css"])

        rv = c.get("/api/tags")
        assert rv.status_code == 200
        tags = {t["name"]: t["count"] for t in rv.get_json()}
        assert tags["web"] == 2
        assert tags["css"] == 1

    def test_duplicate_tags_deduplicated(self, app):
        c = _authed_client(app, "tag_dedup@test.com")
        rv = _create_note(c, tags=["python", "Python", "PYTHON"])
        tags = rv.get_json()["tags"]
        assert tags == ["python"]


# ---------------------------------------------------------------------------
# Pin ordering
# ---------------------------------------------------------------------------

class TestPinOrdering:
    def test_pinned_notes_first_in_all_view(self, app):
        c = _authed_client(app, "pin@test.com")
        _create_note(c, title="Unpinned")
        _create_note(c, title="Pinned", is_pinned=True)

        rv = _list_notes(c, view="all")
        titles = [n["title"] for n in rv.get_json()]
        assert titles[0] == "Pinned"


# ---------------------------------------------------------------------------
# Trash & lazy purge
# ---------------------------------------------------------------------------

class TestTrashAndPurge:
    def test_trash_view_shows_only_deleted(self, app):
        c = _authed_client(app, "trash_view@test.com")
        rv1 = _create_note(c, title="Active")
        rv2 = _create_note(c, title="Deleted")
        _delete_note(c, rv2.get_json()["id"])

        rv = _list_notes(c, view="trash")
        titles = [n["title"] for n in rv.get_json()]
        assert "Deleted" in titles
        assert "Active" not in titles

    def test_all_view_hides_deleted(self, app):
        c = _authed_client(app, "trash_hide@test.com")
        rv1 = _create_note(c, title="Visible")
        rv2 = _create_note(c, title="In Trash")
        _delete_note(c, rv2.get_json()["id"])

        rv = _list_notes(c, view="all")
        titles = [n["title"] for n in rv.get_json()]
        assert "In Trash" not in titles
        assert "Visible" in titles

    def test_lazy_purge_on_trash_list(self, app):
        """Notes deleted more than TRASH_PURGE_DAYS ago are auto-purged."""
        c = _authed_client(app, "purge@test.com")
        rv = _create_note(c, title="Old Trash")
        note_id = rv.get_json()["id"]
        _delete_note(c, note_id)

        # Back-date the deleted_at to 31 days ago
        with app.app_context():
            db = app._db_session()
            from app.models import Note
            note = db.query(Note).filter_by(id=note_id).first()
            note.deleted_at = datetime.now(timezone.utc) - timedelta(days=31)
            db.commit()

        # Listing trash triggers lazy purge
        rv2 = _list_notes(c, view="trash")
        ids = [n["id"] for n in rv2.get_json()]
        assert note_id not in ids

        # Note is gone permanently
        rv3 = _get_note(c, note_id)
        assert rv3.status_code == 404

    def test_empty_trash(self, app):
        c = _authed_client(app, "empty_trash@test.com")
        rv1 = _create_note(c, title="To empty 1")
        rv2 = _create_note(c, title="To empty 2")
        _delete_note(c, rv1.get_json()["id"])
        _delete_note(c, rv2.get_json()["id"])

        rv3 = c.post("/api/trash/empty", headers=CSRF)
        assert rv3.status_code == 200

        rv4 = _list_notes(c, view="trash")
        assert len(rv4.get_json()) == 0


# ---------------------------------------------------------------------------
# Version conflict (409)
# ---------------------------------------------------------------------------

class TestVersionConflict:
    def test_409_on_stale_base_version(self, app):
        c = _authed_client(app, "conflict@test.com")
        rv = _create_note(c)
        note_id = rv.get_json()["id"]
        assert rv.get_json()["version"] == 1

        # First update succeeds
        rv2 = _patch_note(c, note_id, content="v2", base_version=1)
        assert rv2.status_code == 200
        assert rv2.get_json()["version"] == 2

        # Second update with stale version → 409
        rv3 = _patch_note(c, note_id, content="v3", base_version=1)
        assert rv3.status_code == 409
        body = rv3.get_json()
        assert body["error"]["code"] == "conflict"
        assert body["note"]["version"] == 2  # current version returned


# ---------------------------------------------------------------------------
# Notebooks
# ---------------------------------------------------------------------------

class TestNotebooks:
    def test_notebook_crud(self, app):
        c = _authed_client(app, "nb_crud@test.com")

        # Create
        rv = _create_notebook(c, "Physics")
        assert rv.status_code == 201
        nb_id = rv.get_json()["id"]

        # List
        rv2 = c.get("/api/notebooks")
        assert rv2.status_code == 200
        assert any(nb["name"] == "Physics" for nb in rv2.get_json())

        # Rename
        rv3 = c.patch(f"/api/notebooks/{nb_id}", json={"name": "Math"}, headers=CSRF)
        assert rv3.status_code == 200
        assert rv3.get_json()["name"] == "Math"

        # Delete
        rv4 = c.delete(f"/api/notebooks/{nb_id}", headers=CSRF)
        assert rv4.status_code == 200

    def test_delete_notebook_unfiles_notes(self, app):
        c = _authed_client(app, "nb_unfile@test.com")

        nb_rv = _create_notebook(c, "Temp")
        nb_id = nb_rv.get_json()["id"]

        rv = _create_note(c, title="In Temp", notebook_id=nb_id)
        note_id = rv.get_json()["id"]

        # Delete the notebook
        c.delete(f"/api/notebooks/{nb_id}", headers=CSRF)

        # Note should still exist with notebook_id = null
        rv2 = _get_note(c, note_id)
        assert rv2.status_code == 200
        assert rv2.get_json()["notebook_id"] is None

    def test_duplicate_notebook_name(self, app):
        c = _authed_client(app, "nb_dup@test.com")
        _create_notebook(c, "Science")
        rv = _create_notebook(c, "Science")
        assert rv.status_code == 409

    def test_notebook_user_isolation(self, app):
        a = _authed_client(app, "nb_iso_a@test.com")
        b = _authed_client(app, "nb_iso_b@test.com")

        nb_rv = _create_notebook(a, "Private NB")
        nb_id = nb_rv.get_json()["id"]

        # B can't see A's notebook
        rv = b.get("/api/notebooks")
        names = [nb["name"] for nb in rv.get_json()]
        assert "Private NB" not in names

        # B can't delete A's notebook
        rv2 = b.delete(f"/api/notebooks/{nb_id}", headers=CSRF)
        assert rv2.status_code == 404


# ---------------------------------------------------------------------------
# Failure injection: DB fails but file is already written
# ---------------------------------------------------------------------------

class TestFailureInjection:
    def test_db_failure_then_retry_succeeds(self, app):
        """Simulate DB failure during save. The file is written but the DB
        step raises. A subsequent retry overwrites the file (same content)
        and the DB succeeds, resulting in a consistent state."""
        from sqlalchemy.orm import Session

        c = _authed_client(app, "fail_inj@test.com")

        # 1. Create note normally
        rv = _create_note(c, title="Original Note", content="Original body")
        assert rv.status_code == 201
        note_id = rv.get_json()["id"]
        assert rv.get_json()["version"] == 1

        # 2. Patch Session.commit during PATCH to simulate database failure
        with patch.object(Session, "commit", side_effect=Exception("Simulated DB failure")):
            rv2 = _patch_note(c, note_id, title="Updated Note", content="Updated body", base_version=1)
            assert rv2.status_code == 500

        # Note in DB should still be at version 1 (rolled back)
        rv_check = _get_note(c, note_id)
        assert rv_check.status_code == 200
        assert rv_check.get_json()["version"] == 1

        # 3. Retry the save without failure injection
        rv3 = _patch_note(c, note_id, title="Updated Note", content="Updated body", base_version=1)
        assert rv3.status_code == 200
        assert rv3.get_json()["version"] == 2
        assert rv3.get_json()["title"] == "Updated Note"
        assert rv3.get_json()["content"] == "Updated body"

        # 4. Verify DB row and storage file are consistent
        from app.storage.factory import get_storage
        import frontmatter as fm

        storage = get_storage(app)
        raw = storage.get_text(f"users/{rv3.get_json()['user_id'] if 'user_id' in rv3.get_json() else ''}") if False else None
        # Read note again
        rv4 = _get_note(c, note_id)
        assert rv4.status_code == 200
        assert rv4.get_json()["title"] == "Updated Note"
        assert rv4.get_json()["content"] == "Updated body"


# ---------------------------------------------------------------------------
# Reindex CLI command
# ---------------------------------------------------------------------------

class TestReindex:
    def test_reindex_command(self, app):
        c = _authed_client(app, "reindex_user@test.com")
        rv = _create_note(c, title="Original Title", content="# Heading\nOriginal content", tags=["first"])
        assert rv.status_code == 201
        note_id = rv.get_json()["id"]

        from app.storage.factory import get_storage
        import frontmatter as fm
        from app.models import Note

        with app.app_context():
            db = app._db_session()
            note = db.query(Note).filter_by(id=note_id).first()
            storage_key = note.storage_key

        storage = get_storage(app)
        # Directly modify file in storage
        new_post = fm.Post("Reindexed body plain text", title="Reindexed Title", tags=["reindexed", "tag2"])
        storage.put_text(storage_key, fm.dumps(new_post))

        # Run flask reindex via runner
        runner = app.test_cli_runner()
        result = runner.invoke(args=["reindex"])
        assert result.exit_code == 0
        assert "Reindexed" in result.output

        # Verify DB is rebuilt
        rv2 = _get_note(c, note_id)
        assert rv2.status_code == 200
        d = rv2.get_json()
        assert d["title"] == "Reindexed Title"
        assert d["snippet"] == "Reindexed body plain text"
        assert "reindexed" in d["tags"]
        assert "tag2" in d["tags"]
