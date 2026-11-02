"""Abstract storage interface for Cloud Notes.

Implementations must provide every method defined here.
"""
from abc import ABC, abstractmethod


class StorageBase(ABC):
    """Interface every storage backend must implement."""

    # ------------------------------------------------------------------ text
    @abstractmethod
    def put_text(self, key: str, text: str) -> None:
        """Write a UTF-8 string at *key*, creating or overwriting."""

    @abstractmethod
    def get_text(self, key: str) -> str:
        """Return the UTF-8 content stored at *key*.

        Raises FileNotFoundError if the key does not exist.
        """

    # ----------------------------------------------------------------- bytes
    @abstractmethod
    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        """Write raw bytes at *key*."""

    @abstractmethod
    def get_bytes(self, key: str) -> bytes:
        """Return raw bytes stored at *key*.

        Raises FileNotFoundError if the key does not exist.
        """

    # --------------------------------------------------------------- helpers
    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete the object at *key*.  No-op if it does not exist."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return True if *key* exists in storage."""

    @abstractmethod
    def presigned_url_or_none(self, key: str, expires_in: int = 300) -> str | None:
        """Return a short-lived GET URL for *key*, or None for local storage."""

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if the storage backend is reachable."""
