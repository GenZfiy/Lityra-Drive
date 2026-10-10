import os

from lare_common.config import BaseConfig


class AIConfig(BaseConfig):
    SERVICE_NAME = os.getenv("SERVICE_NAME", "platform-ai")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///ai_orchestration.sqlite3")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "lms_ai") or None

    # Provider: 'auto' (gemini if GEMINI_API_KEY else anthropic if ANTHROPIC_API_KEY
    # else stub), or force 'anthropic' | 'gemini' | 'stub'. Absent key / SDK ->
    # deterministic STUB so the platform always runs; lights up when a key exists.
    AI_PROVIDER = os.getenv("AI_PROVIDER", "auto")

    # Anthropic (Claude)
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    AI_MODEL = os.getenv("AI_MODEL", "claude-opus-4-8")
    AI_THINKING = os.getenv("AI_THINKING", "adaptive")

    # Google (Gemini)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "1024"))
