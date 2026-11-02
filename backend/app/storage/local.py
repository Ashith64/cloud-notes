"""Local filesystem storage backend.

Files are stored under LOCAL_STORAGE_PATH.  The key is used as a relative
path with forward-slashes converted to OS separators.
"""
import os
from pathlib import Path

from .base import StorageBase


class LocalStorage(StorageBase):
    def __init__(self, base_path: str) -> None:
        self._base = Path(base_path)
        self._base.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Prevent directory traversal.
        safe = Path(key.lstrip("/"))
        full = (self._base / safe).resolve()
        if not str(full).startswith(str(self._base.resolve())):
            raise ValueError(f"Key '{key}' escapes storage root")
        return full

    # ------------------------------------------------------------------ text
    def put_text(self, key: str, text: str) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def get_text(self, key: str) -> str:
        p = self._path(key)
        if not p.exists():
            raise FileNotFoundError(f"Storage key not found: {key}")
        return p.read_text(encoding="utf-8")

    # ----------------------------------------------------------------- bytes
    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get_bytes(self, key: str) -> bytes:
        p = self._path(key)
        if not p.exists():
            raise FileNotFoundError(f"Storage key not found: {key}")
        return p.read_bytes()

    # --------------------------------------------------------------- helpers
    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def presigned_url_or_none(self, key: str, expires_in: int = 300) -> None:
        # Local storage has no presigned URLs; callers stream the file instead.
        return None

    def health_check(self) -> bool:
        try:
            probe = self._base / ".health"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return True
        except OSError:
            return False
