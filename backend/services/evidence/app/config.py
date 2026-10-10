import os

from lare_common.config import BaseConfig


class EvidenceConfig(BaseConfig):
    SERVICE_NAME = os.getenv("SERVICE_NAME", "drive-evidence")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///evidence.sqlite3")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "drive_evidence") or None
    # Two evidence rows for the same candidate + competency that diverge by more
    # than this many signal points (0..100) are flagged as a conflict.
    CONFLICT_DELTA = float(os.getenv("EVIDENCE_CONFLICT_DELTA", "25"))
