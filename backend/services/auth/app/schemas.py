"""Request/response validation via pydantic v2."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field

# The two products own separate accounts. Every credential flow must name one.
Product = Literal["learn", "hire"]


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)
    product: Product = "learn"


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    device: str | None = Field(default=None, max_length=255)
    product: Product = "learn"


class RefreshIn(BaseModel):
    refresh_token: str


class AssignRoleIn(BaseModel):
    user_id: str
    role: str
    college_id: str | None = None
    branch_id: str | None = None
    cohort_id: str | None = None


class AdminUserCreateIn(BaseModel):
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=255)
    product: Product = "learn"
    password: str = Field(min_length=8, max_length=128)
    role: str | None = None            # optional initial role
    college_id: str | None = None
    branch_id: str | None = None
    cohort_id: str | None = None


ScopeLevel = Literal["platform", "college", "branch", "section", "self"]


class RoleCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    description: str | None = Field(default=None, max_length=255)
    scope_level: ScopeLevel = "self"
    permissions: list[str] = []


class RoleCloneIn(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    description: str | None = Field(default=None, max_length=255)


class RoleUpdateIn(BaseModel):
    description: str | None = Field(default=None, max_length=255)
    scope_level: ScopeLevel | None = None
    is_active: bool | None = None
    permissions: list[str] | None = None


class OtpRequestIn(BaseModel):
    email: EmailStr
    product: Product = "learn"


class OtpVerifyIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=8)
    device: str | None = Field(default=None, max_length=255)
    product: Product = "learn"


class PasswordForgotIn(BaseModel):
    email: EmailStr
    product: Product = "learn"


class PasswordResetIn(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class EmailVerifyIn(BaseModel):
    token: str


class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str | None
    status: str
    email_verified: bool
    mfa_enabled: bool
    tenant_id: str
    product: str = "learn"
    roles: list[str] = []


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
