import os

from lare_common.config import BaseConfig


class FilesConfig(BaseConfig):
    SERVICE_NAME = os.getenv("SERVICE_NAME", "lare-files")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///files.sqlite3")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "shared_files") or None
    # Storage backend: 'local' (dev) or 'supabase' (prod).
    STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")
    STORAGE_DIR = os.getenv("STORAGE_DIR", "_storage")
    UPLOAD_TOKEN_TTL_MIN = int(os.getenv("UPLOAD_TOKEN_TTL_MIN", "15"))
    DOWNLOAD_TOKEN_TTL_MIN = int(os.getenv("DOWNLOAD_TOKEN_TTL_MIN", "10"))
