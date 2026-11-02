"""Storage factory: returns the configured storage backend."""
from .base import StorageBase


def get_storage(app=None) -> StorageBase:
    """Return the storage backend dictated by STORAGE_BACKEND in Flask config.

    Pass the Flask *app* object so the factory can read its config.  When
    called inside a request context you can pass *None* and import current_app.
    """
    from flask import current_app

    cfg = app.config if app is not None else current_app.config

    backend = cfg.get("STORAGE_BACKEND", "local").lower()

    if backend == "s3":
        from .s3 import S3Storage
        return S3Storage(
            bucket=cfg["S3_BUCKET"],
            region=cfg.get("AWS_REGION"),
        )

    # Default to local.
    from .local import LocalStorage
    return LocalStorage(base_path=cfg.get("LOCAL_STORAGE_PATH", "./local_data"))
