"""Tenant-boundary regression tests for Hire organization administration."""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from pathlib import Path

# The organization API is exercised against an isolated in-memory database.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["INTERNAL_JWT_SECRET"] = "organization-test-context-secret"
os.environ["APP_ENV"] = "development"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "libs"))

from app.factory import build_app  # noqa: E402
from lare_common.internal import mint_gateway_context  # noqa: E402


class OrganizationTenantScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = build_app()
        cls.db = cls.app.extensions["db"]
        import app.models  # noqa: F401
        cls.db.create_all()
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.db.engine.dispose()

    def headers(self, *, role, tenant, permissions):
        token = mint_gateway_context({
            "sub": f"{role}-{tenant}", "roles": [role], "permissions": permissions,
            "tenant_id": tenant, "product": "hire", "scope_level": "platform",
        })
        return {"X-Internal-Token": token}

    def create_org(self, tenant):
        slug = f"org-{tenant}-{uuid.uuid4().hex[:8]}"
        response = self.client.post("/org/v1/organizations", headers=self.headers(
            role="super_admin", tenant="platform",
            permissions=["institution.manage", "institution.view"]), json={
                "name": slug, "slug": slug, "tenant_id": tenant,
            })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["data"]

    def test_company_admin_lists_only_own_tenant(self):
        own = self.create_org(f"tenant-{uuid.uuid4().hex[:8]}")
        other = self.create_org(f"tenant-{uuid.uuid4().hex[:8]}")
        response = self.client.get("/org/v1/organizations", headers=self.headers(
            role="company_admin", tenant=own["tenant_id"],
            permissions=["institution.view"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.get_json()["data"]], [own["id"]])
        self.assertNotIn(other["id"], [row["id"] for row in response.get_json()["data"]])

    def test_company_admin_cannot_read_or_update_another_tenant(self):
        own = self.create_org(f"tenant-{uuid.uuid4().hex[:8]}")
        other = self.create_org(f"tenant-{uuid.uuid4().hex[:8]}")
        headers = self.headers(role="company_admin", tenant=own["tenant_id"],
                               permissions=["institution.view", "institution.manage"])
        self.assertEqual(self.client.get(f"/org/v1/organizations/{other['id']}", headers=headers).status_code, 404)
        self.assertEqual(self.client.put(f"/org/v1/organizations/{other['id']}", headers=headers,
                                         json={"name": "cross-tenant-change"}).status_code, 404)
        self.assertEqual(self.client.get(f"/org/v1/organizations/{own['id']}", headers=headers).status_code, 200)


if __name__ == "__main__":
    unittest.main()
