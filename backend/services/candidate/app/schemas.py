from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class AttendIn(BaseModel):
    """Public 'Attend Drive' registration — no login required."""
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=255)
    phone: str = Field(min_length=8, max_length=20)
    roll_number: str = Field(min_length=1, max_length=64)

    @field_validator("roll_number")
    @classmethod
    def _alnum(cls, v: str) -> str:
        v = v.strip()
        if not v.isalnum():
            raise ValueError("roll number must be alphanumeric (letters and digits only)")
        return v.upper()

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        digits = "".join(ch for ch in v if ch.isdigit())
        if len(digits) < 10:
            raise ValueError("enter a valid phone number (at least 10 digits)")
        return digits

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("enter a valid email address")
        return v


class ResumeAttendIn(BaseModel):
    student_id: str = Field(min_length=3, max_length=32)
    email: EmailStr


class ProfileIn(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    branch: str | None = None
    cgpa: float | None = Field(default=None, ge=0, le=10)


class ResumeIn(BaseModel):
    resume_file_id: str




class EducationIn(BaseModel):
    degree: str = Field(min_length=1, max_length=128)
    institution: str | None = None
    year: int | None = None
    score: str | None = None


class ProjectIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    repo_url: str | None = None


class ApplyIn(BaseModel):
    drive_id: str
    drive_role_id: str | None = None
