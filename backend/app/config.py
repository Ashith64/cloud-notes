import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")
    DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///dev.db")
    STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local")
    LOCAL_STORAGE_PATH = os.environ.get("LOCAL_STORAGE_PATH", "./local_data")
    S3_BUCKET = os.environ.get("S3_BUCKET", "")
    AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")
    JWT_EXPIRY_DAYS = int(os.environ.get("JWT_EXPIRY_DAYS", "7"))
    ASG_NAME = os.environ.get("ASG_NAME", "")
    DB_INSTANCE_ID = os.environ.get("DB_INSTANCE_ID", "")
    APP_VERSION = "0.1.0"
    TRASH_PURGE_DAYS = int(os.environ.get("TRASH_PURGE_DAYS", "30"))
    # Allow tests to override TESTING without inheriting irrelevant config keys.
    TESTING = False

