"""Recruitment drive models (schema: drive_core)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lare_common.db import Base
from lare_common.security import new_id


def _uuid() -> str:
    return new_id()


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class Drive(Base):
    __tablename__ = "drives"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(String(64))
    company_name: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(24), default="draft")  # draft|open|closed
    reporting_time: Mapped[str | None] = mapped_column(String(64))
    venue: Mapped[str | None] = mapped_column(String(255))
    # Company's own email — candidate notifications are sent "from" this address
    # (as From-name + Reply-To), so replies reach the recruiter directly.
    contact_email: Mapped[str | None] = mapped_column(String(255))
    # Recruitment calendar dates (req #16): registration_deadline, exam_date,
    # interview_date, joining_date (ISO strings).
    schedule: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    roles: Mapped[list["DriveRole"]] = relationship(cascade="all, delete-orphan")
    rounds: Mapped[list["Round"]] = relationship(cascade="all, delete-orphan")


class DriveRole(Base):
    __tablename__ = "drive_roles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    drive_id: Mapped[str] = mapped_column(ForeignKey("drives.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    ctc: Mapped[str | None] = mapped_column(String(64))
    positions: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[str | None] = mapped_column(String(1024))
    # Required skills for the Skills-to-Opportunity match: [{"name","weight"}].
    # Recruiter-authored; drives the candidate's "Matched Opportunities" ranking.
    skills: Mapped[list] = mapped_column(JSON, default=list)


class EligibilityRule(Base):
    __tablename__ = "eligibility_rules"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    drive_id: Mapped[str] = mapped_column(ForeignKey("drives.id", ondelete="CASCADE"), index=True)
    # rule: {"min_cgpa":7.0,"branches":["CSE"],"max_backlogs":0,"min_lms_score":60}
    rule: Mapped[dict] = mapped_column(JSON, default=dict)


class Round(Base):
    __tablename__ = "rounds"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    drive_id: Mapped[str] = mapped_column(ForeignKey("drives.id", ondelete="CASCADE"), index=True)
    order: Mapped[int] = mapped_column(Integer, default=1)
    type: Mapped[str] = mapped_column(String(24))  # aptitude|technical|verbal|coding|interview
    label: Mapped[str | None] = mapped_column(String(120))
    optional: Mapped[bool] = mapped_column(default=False)  # configurable workflow (req #4)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    service_ref: Mapped[str | None] = mapped_column(String(64))


class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (UniqueConstraint("drive_id", "candidate_id", name="uq_registration"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    drive_id: Mapped[str] = mapped_column(ForeignKey("drives.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[str] = mapped_column(String(64), index=True)
    # applied -> shortlisted -> in_round -> selected/rejected
    status: Mapped[str] = mapped_column(String(24), default="applied")
    current_round: Mapped[int] = mapped_column(Integer, default=0)
    eligible: Mapped[str] = mapped_column(String(8), default="unknown")  # yes|no|unknown
    # Extended post-selection workflow (req #3): offer_accepted -> docs_verified -> joined
    joining_status: Mapped[str | None] = mapped_column(String(24))


class RoundScore(Base):
    """Per-candidate marks for a round. Written rounds are auto-analysed then
    editable by the admin; JAM/GD/interview rounds are scored by the panel."""
    __tablename__ = "round_scores"
    __table_args__ = (UniqueConstraint("drive_id", "round_order", "candidate_id", name="uq_round_score"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    drive_id: Mapped[str] = mapped_column(ForeignKey("drives.id", ondelete="CASCADE"), index=True)
    round_order: Mapped[int] = mapped_column(Integer, index=True)
    candidate_id: Mapped[str] = mapped_column(String(64), index=True)
    marks: Mapped[float] = mapped_column(default=0.0)
    max_marks: Mapped[float] = mapped_column(default=100.0)
    remarks: Mapped[str | None] = mapped_column(String(500))
    cleared: Mapped[bool] = mapped_column(default=False)
    referred: Mapped[bool] = mapped_column(default=False)   # manually added by admin
    entered_by: Mapped[str | None] = mapped_column(String(64))
    # Coding-question attempt tracking (written round): how many of the exam's
    # coding questions this candidate attempted, and how many there were.
    coding_attempted: Mapped[int | None] = mapped_column(Integer)
    coding_correct: Mapped[int | None] = mapped_column(Integer)
    coding_total: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SeatAllocation(Base):
    """Exam-hall seat assignment (req #18): lab + system + seat per candidate."""
    __tablename__ = "seat_allocations"
    __table_args__ = (UniqueConstraint("drive_id", "candidate_id", name="uq_seat"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    drive_id: Mapped[str] = mapped_column(ForeignKey("drives.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[str] = mapped_column(String(64), index=True)
    lab: Mapped[str] = mapped_column(String(64))
    system_no: Mapped[int] = mapped_column(Integer)
    seat_no: Mapped[str] = mapped_column(String(16))


class ApplicationForm(Base):
    """Company-specific application form (req #21): a JSON field schema per drive."""
    __tablename__ = "application_forms"

    drive_id: Mapped[str] = mapped_column(
        ForeignKey("drives.id", ondelete="CASCADE"), primary_key=True)
    # schema: [{key, label, type: text|number|select|checkbox|date, required, options?}]
    fields: Mapped[list] = mapped_column(JSON, default=list)


class FormSubmission(Base):
    __tablename__ = "form_submissions"
    __table_args__ = (UniqueConstraint("drive_id", "candidate_id", name="uq_form_sub"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    drive_id: Mapped[str] = mapped_column(ForeignKey("drives.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[str] = mapped_column(String(64), index=True)
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PpoConfig(Base):
    __tablename__ = "ppo_config"

    drive_id: Mapped[str] = mapped_column(
        ForeignKey("drives.id", ondelete="CASCADE"), primary_key=True
    )
    eligibility: Mapped[dict] = mapped_column(JSON, default=dict)
    stages: Mapped[list] = mapped_column(JSON, default=list)
    conversion_criteria: Mapped[dict] = mapped_column(JSON, default=dict)


class DriveAccessCode(Base):
    """A secure, admin-managed code that gates entry to ONE recruitment drive.
    A candidate (Hire login) presents it to access only that drive."""
    __tablename__ = "drive_access_codes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    drive_id: Mapped[str] = mapped_column(ForeignKey("drives.id", ondelete="CASCADE"), index=True)
    label: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | inactive
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class DriveAccessSession(Base):
    """Records a candidate passed the Drive gate this session, bound to a drive."""
    __tablename__ = "drive_access_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    drive_id: Mapped[str] = mapped_column(String(64), index=True)
    code_id: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
