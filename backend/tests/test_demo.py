"""Tests for demo seeding (Stage 3).

Coverage:
 - POST /api/auth/demo returns a valid session
 - Exactly 3 notebooks are created after demo login
 - Exactly 12 notes are created after demo login
 - Seeding is idempotent: calling demo twice does not duplicate data
 - Notes have expected properties (pins, favorites, tags)
 - Notes are listed via GET /api/notes after demo login
"""
from tests.conftest import CSRF


def _demo_login(client) -> dict:
    resp = client.post("/api/auth/demo", headers=CSRF)
    assert resp.status_code == 200
    return resp.get_json()


class TestDemoSeed:
    def test_demo_returns_user(self, client):
        user = _demo_login(client)
        assert user["email"] == "demo@cloudnotes.app"
        assert user["name"] == "Demo User"

    def test_demo_creates_exactly_12_notes(self, client):
        _demo_login(client)
        resp = client.get("/api/notes?limit=50")
        assert resp.status_code == 200
        notes = resp.get_json()
        assert len(notes) == 12, f"Expected 12 notes, got {len(notes)}"

    def test_demo_creates_exactly_3_notebooks(self, client):
        _demo_login(client)
        resp = client.get("/api/notebooks")
        assert resp.status_code == 200
        notebooks = resp.get_json()
        names = {nb["name"] for nb in notebooks}
        assert names == {"College", "Projects", "Personal"}, f"Got: {names}"

    def test_demo_seeding_idempotent(self, client):
        """Calling /api/auth/demo twice must not duplicate any data."""
        _demo_login(client)
        _demo_login(client)  # second call

        resp = client.get("/api/notes?limit=200")
        notes = resp.get_json()
        assert len(notes) == 12, f"Expected 12 notes after 2 demo calls, got {len(notes)}"

        resp = client.get("/api/notebooks")
        notebooks = resp.get_json()
        assert len(notebooks) == 3, f"Expected 3 notebooks, got {len(notebooks)}"

    def test_demo_seeding_idempotent_three_times(self, client):
        """Triple call still yields exactly 12 notes."""
        for _ in range(3):
            _demo_login(client)

        resp = client.get("/api/notes?limit=200")
        notes = resp.get_json()
        assert len(notes) == 12

    def test_demo_has_pinned_notes(self, client):
        """Spec: pin one note."""
        _demo_login(client)
        resp = client.get("/api/notes")
        notes = resp.get_json()
        pinned = [n for n in notes if n["is_pinned"]]
        assert len(pinned) == 1, f"Expected exactly 1 pinned note, got {len(pinned)}"

    def test_demo_has_favorite_notes(self, client):
        """Spec: favorite two notes."""
        _demo_login(client)
        resp = client.get("/api/notes")
        notes = resp.get_json()
        favorites = [n for n in notes if n["is_favorite"]]
        assert len(favorites) == 2, f"Expected exactly 2 favorite notes, got {len(favorites)}"

    def test_demo_notes_have_tags(self, client):
        """Demo notes should have tags."""
        _demo_login(client)
        resp = client.get("/api/notes?limit=50")
        notes = resp.get_json()
        tagged = [n for n in notes if n["tags"]]
        assert len(tagged) > 0, "Expected some notes with tags"

    def test_demo_notes_in_notebooks(self, client):
        """All 12 demo notes should be filed in a notebook."""
        _demo_login(client)
        resp = client.get("/api/notes?limit=50")
        notes = resp.get_json()
        without_notebook = [n for n in notes if n["notebook_id"] is None]
        assert len(without_notebook) == 0, \
            f"{len(without_notebook)} notes have no notebook"

    def test_demo_college_notebook_has_9_notes(self, client):
        """College notebook should have 9 notes (all exam topics + plan)."""
        _demo_login(client)
        resp = client.get("/api/notebooks")
        notebooks = resp.get_json()
        college = next(nb for nb in notebooks if nb["name"] == "College")
        resp = client.get(f"/api/notes?notebook_id={college['id']}&limit=50")
        notes = resp.get_json()
        assert len(notes) == 9, f"Expected 9 College notes, got {len(notes)}"

    def test_demo_projects_notebook_has_1_note(self, client):
        """Projects notebook should have 1 note."""
        _demo_login(client)
        resp = client.get("/api/notebooks")
        notebooks = resp.get_json()
        projects = next(nb for nb in notebooks if nb["name"] == "Projects")
        resp = client.get(f"/api/notes?notebook_id={projects['id']}&limit=50")
        notes = resp.get_json()
        assert len(notes) == 1, f"Expected 1 Projects note, got {len(notes)}"

    def test_demo_personal_notebook_has_2_notes(self, client):
        """Personal notebook should have 2 notes."""
        _demo_login(client)
        resp = client.get("/api/notebooks")
        notebooks = resp.get_json()
        personal = next(nb for nb in notebooks if nb["name"] == "Personal")
        resp = client.get(f"/api/notes?notebook_id={personal['id']}&limit=50")
        notes = resp.get_json()
        assert len(notes) == 2, f"Expected 2 Personal notes, got {len(notes)}"

    def test_demo_note_titles_unique(self, client):
        """All 12 note titles must be unique."""
        _demo_login(client)
        resp = client.get("/api/notes?limit=50")
        notes = resp.get_json()
        titles = [n["title"] for n in notes]
        assert len(set(titles)) == len(titles), f"Duplicate titles found: {titles}"

    def test_demo_tags_endpoint(self, client):
        """GET /api/tags should return tags with counts after seeding."""
        _demo_login(client)
        resp = client.get("/api/tags")
        assert resp.status_code == 200
        tags = resp.get_json()
        assert len(tags) > 0
        for tag in tags:
            assert "name" in tag
            assert "count" in tag
            assert tag["count"] > 0
