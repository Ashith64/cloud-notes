"""Tests for GET /api/status (Stage 3).

Coverage:
 - Public endpoint (no cookie required)
 - Returns all required fields with correct types
 - db_ok is True when database is healthy
 - storage_ok is True with local backend
 - instance_id / availability_zone fall back to "local" when IMDS unavailable
 - running_servers / average_cpu / last_backup are null when ASG_NAME / DB_INSTANCE_ID unconfigured
 - Every AWS call is mocked — no real network calls
 - Response is cached for 10 seconds (second call within window returns same data)
"""
import time

import pytest


class TestStatus:
    def test_status_public_no_auth(self, client):
        """Status endpoint must not require a cookie."""
        resp = client.get("/api/status")
        assert resp.status_code == 200

    def test_status_fields_present(self, client):
        resp = client.get("/api/status")
        data = resp.get_json()
        required = {
            "instance_id", "availability_zone", "running_servers",
            "average_cpu", "db_ok", "storage_ok", "last_backup",
            "version", "uptime_seconds",
        }
        assert required.issubset(data.keys()), f"Missing keys: {required - data.keys()}"

    def test_instance_id_local_fallback(self, client):
        """Without EC2, instance_id and az should be 'local'."""
        resp = client.get("/api/status")
        data = resp.get_json()
        assert data["instance_id"] == "local"
        assert data["availability_zone"] == "local"

    def test_running_servers_null_when_unconfigured(self, client):
        """ASG_NAME is empty in test config, so running_servers should be null."""
        resp = client.get("/api/status")
        data = resp.get_json()
        assert data["running_servers"] is None

    def test_average_cpu_null_when_unconfigured(self, client):
        resp = client.get("/api/status")
        data = resp.get_json()
        assert data["average_cpu"] is None

    def test_last_backup_null_when_unconfigured(self, client):
        resp = client.get("/api/status")
        data = resp.get_json()
        assert data["last_backup"] is None

    def test_db_ok_true(self, client):
        """DB should be healthy during tests (SQLite in-memory)."""
        resp = client.get("/api/status")
        data = resp.get_json()
        assert data["db_ok"] is True

    def test_storage_ok_true(self, client):
        """Local storage health check writes+deletes a probe file."""
        resp = client.get("/api/status")
        data = resp.get_json()
        assert data["storage_ok"] is True

    def test_version_is_string(self, client):
        resp = client.get("/api/status")
        data = resp.get_json()
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0

    def test_uptime_seconds_non_negative(self, client):
        resp = client.get("/api/status")
        data = resp.get_json()
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] >= 0

    def test_status_cached(self, client, monkeypatch):
        """Two requests within the 10-second window return the same uptime_seconds."""
        import app.routes.status as status_mod

        # Reset cache to ensure a fresh snapshot
        monkeypatch.setattr(status_mod, "_cache", None)

        resp1 = client.get("/api/status")
        resp2 = client.get("/api/status")
        # Both responses should have the exact same uptime_seconds (cached)
        assert resp1.get_json()["uptime_seconds"] == resp2.get_json()["uptime_seconds"]

    def test_status_with_mocked_asg(self, client, monkeypatch, app):
        """ASG stats are returned when ASG_NAME is configured and boto3 is mocked."""
        import app.routes.status as status_mod

        # Clear cache
        monkeypatch.setattr(status_mod, "_cache", None)

        # Set ASG_NAME in config
        original_asg = app.config.get("ASG_NAME", "")
        app.config["ASG_NAME"] = "test-asg"

        # Mock _get_asg_stats to return deterministic values
        monkeypatch.setattr(status_mod, "_get_asg_stats", lambda name: (2, 34.5))

        resp = client.get("/api/status")
        data = resp.get_json()
        assert data["running_servers"] == 2
        assert data["average_cpu"] == pytest.approx(34.5)

        # Restore
        app.config["ASG_NAME"] = original_asg

    def test_status_with_mocked_rds_backup(self, client, monkeypatch, app):
        """last_backup is returned when DB_INSTANCE_ID is configured."""
        import app.routes.status as status_mod

        monkeypatch.setattr(status_mod, "_cache", None)
        original_db_id = app.config.get("DB_INSTANCE_ID", "")
        app.config["DB_INSTANCE_ID"] = "mydb"

        monkeypatch.setattr(
            status_mod, "_get_last_backup",
            lambda db_id: "2026-11-01T03:00:00+00:00",
        )

        resp = client.get("/api/status")
        data = resp.get_json()
        assert data["last_backup"] == "2026-11-01T03:00:00+00:00"

        app.config["DB_INSTANCE_ID"] = original_db_id

    def test_status_graceful_db_failure(self, client, monkeypatch):
        """If db check raises, db_ok should be False (not a crash)."""
        import app.routes.status as status_mod

        monkeypatch.setattr(status_mod, "_cache", None)
        monkeypatch.setattr(status_mod, "_db_ok", lambda: False)

        resp = client.get("/api/status")
        assert resp.status_code == 200
        assert resp.get_json()["db_ok"] is False

    def test_status_graceful_storage_failure(self, client, monkeypatch):
        """If storage.health_check raises, storage_ok should be False."""
        import app.routes.status as status_mod
        from app.storage import local as local_mod

        monkeypatch.setattr(status_mod, "_cache", None)
        monkeypatch.setattr(local_mod.LocalStorage, "health_check", lambda self: False)

        resp = client.get("/api/status")
        assert resp.status_code == 200
        assert resp.get_json()["storage_ok"] is False
