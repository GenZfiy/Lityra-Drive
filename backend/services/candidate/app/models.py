"""Candidate domain models (schema: drive_candidate)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lare_common.db import Base
from lare_common.security import new_id


def _uuid() -> str:
    return new_id()


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    learner_id: Mapped[str | None] = mapped_column(String(64), index=True)
    college_id: Mapped[str | None] = mapped_column(String(64))
    full_name: Mapped[str | None] = mapped_column(String(255))
    # Public "Attend Drive" registration: student's own details + issued Student ID.
    first_name: Mapped[str | None] = mapped_column(String(120))
    last_name: Mapped[str | None] = mapped_column(String(120))
    roll_number: Mapped[str | None] = mapped_column(String(64), index=True)
    student_id: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32))
    branch: Mapped[str | None] = mapped_column(String(64))
    cgpa: Mapped[float | None] = mapped_column(Float)
    photo_file_id: Mapped[str | None] = mapped_column(String(64))
    resume_file_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    education: Mapped[list["Education"]] = relationship(cascade="all, delete-orphan")
    skills: Mapped[list["Skill"]] = relationship(cascade="all, delete-orphan")
    projects: Mapped[list["Project"]] = relationship(cascade="all, delete-orphan")


class Education(Base):
    __tablename__ = "education"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    degree: Mapped[str] = mapped_column(String(128))
    institution: Mapped[str | None] = mapped_column(String(255))
    year: Mapped[int | None] = mapped_column(Integer)
    score: Mapped[str | None] = mapped_column(String(32))


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    skill: Mapped[str] = mapped_column(String(64))
    level: Mapped[str | None] = mapped_column(String(32))


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(1024))
    repo_url: Mapped[str | None] = mapped_column(String(512))


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("candidate_id", "drive_id", name="uq_application"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), index=True)
    drive_id: Mapped[str] = mapped_column(String(64), index=True)
    drive_role_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="applied")
    eligibility_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
