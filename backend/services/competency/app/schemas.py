from __future__ import annotations

from pydantic import BaseModel, Field


class CompetencyIn(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None


class WeightIn(BaseModel):
    competency_key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    weight: float = Field(default=1.0, gt=0, le=10)
    band_good: float = Field(default=75.0, ge=0, le=100)
    band_warn: float = Field(default=50.0, ge=0, le=100)


class ModelIn(BaseModel):
    drive_id: str = Field(min_length=1, max_length=64)
    weights: list[WeightIn] = Field(min_length=1)
