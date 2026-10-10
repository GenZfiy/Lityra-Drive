from __future__ import annotations

from pydantic import BaseModel, Field

TYPE = "^(mcq|multi|fill_blank|match|true_false|coding|sql|output)$"
CATEGORY = "^(aptitude|technical|verbal|programming)$"
DIFF = "^(easy|medium|hard)$"


class QuestionIn(BaseModel):
    type: str = Field(pattern=TYPE)
    category: str = Field(pattern=CATEGORY)
    difficulty: str = Field(default="easy", pattern=DIFF)
    tags: list[str] = []
    stem: str = Field(min_length=1, max_length=2048)
    options: list[dict] = []
    answer_key: dict = {}
    explanation: str | None = None
    weight: float = Field(default=1.0, gt=0)


class QuestionEdit(BaseModel):
    stem: str | None = None
    options: list[dict] | None = None
    answer_key: dict | None = None
    explanation: str | None = None
    difficulty: str | None = Field(default=None, pattern=DIFF)
    tags: list[str] | None = None


class BulkIn(BaseModel):
    questions: list[QuestionIn]


class BlueprintIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    spec: list[dict]  # [{"category","difficulty","count"}]


class GenerateIn(BaseModel):
    """Ask the configured AI provider to draft exam-ready questions."""
    topic: str = Field(min_length=2, max_length=200)
    type: str = Field(default="mcq", pattern="^(mcq|coding)$")
    category: str = Field(default="aptitude", pattern=CATEGORY)
    difficulty: str = Field(default="easy", pattern=DIFF)
    count: int = Field(default=5, ge=1, le=15)
    languages: list[str] = ["python", "java", "c", "cpp", "javascript"]
