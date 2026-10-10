"""Organization management: CRUD, resolve-by-domain, per-org config + security."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from lare_common.errors import Conflict, NotFound
from lare_common.security import new_id

from .models import DEFAULT_SECURITY, Organization


class OrgService:
    def create(self, s: Session, data) -> Organization:
        if s.execute(select(Organization).where(Organization.slug == data.slug)).scalar_one_or_none():
            raise Conflict("Slug already taken", code="slug_taken")
        tenant_id = data.tenant_id or data.slug
        if s.execute(select(Organization).where(Organization.tenant_id == tenant_id)).scalar_one_or_none():
            raise Conflict("Tenant already has an organization", code="tenant_taken")
        org = Organization(
            id=new_id(), tenant_id=tenant_id, name=data.name, slug=data.slug,
            timezone=data.timezone, custom_domain=data.custom_domain,
            branding=data.branding or {}, smtp_config={},
            security_policy=dict(DEFAULT_SECURITY), feature_overrides={})
        s.add(org)
        s.flush()
        return org

    def get(self, s: Session, org_id: str) -> Organization:
        org = s.get(Organization, org_id)
        if not org or org.deleted_at is not None:
            raise NotFound("Organization not found", code="org_not_found")
        return org

    def by_tenant(self, s: Session, tenant_id: str) -> Organization | None:
        return s.execute(
            select(Organization).where(
                Organization.tenant_id == tenant_id, Organization.deleted_at.is_(None))
        ).scalar_one_or_none()

    def by_domain(self, s: Session, domain: str) -> Organization:
        org = s.execute(
            select(Organization).where(
                Organization.custom_domain == domain, Organization.deleted_at.is_(None))
        ).scalar_one_or_none()
        if not org:
            raise NotFound("No organization for domain", code="org_domain_not_found")
        return org

    def list(self, s: Session) -> list[dict]:
        rows = s.execute(
            select(Organization).where(Organization.deleted_at.is_(None))
            .order_by(Organization.name)
        ).scalars().all()
        return [self.out(o) for o in rows]

    def update(self, s: Session, org_id: str, data) -> Organization:
        org = self.get(s, org_id)
        for f in ("name", "timezone", "custom_domain", "branding",
                  "smtp_config", "security_policy", "feature_overrides"):
            v = getattr(data, f, None)
            if v is not None:
                setattr(org, f, v)
        s.flush()
        return org

    def soft_delete(self, s: Session, org_id: str) -> dict:
        from lare_common.platform import soft_delete
        org = self.get(s, org_id)
        soft_delete(org)
        s.flush()
        return {"id": org_id, "deleted": True}

    @staticmethod
    def out(o: Organization) -> dict:
        return {
            "id": o.id, "tenant_id": o.tenant_id, "name": o.name, "slug": o.slug,
            "custom_domain": o.custom_domain, "timezone": o.timezone,
            "branding": o.branding, "security_policy": o.security_policy,
            "feature_overrides": o.feature_overrides,
            # SMTP secrets are never returned in full — only whether configured.
            "smtp_configured": bool(o.smtp_config.get("host")),
        }
