"""Storage package.  Import get_storage() to obtain the configured backend."""
from .factory import get_storage

__all__ = ["get_storage"]

