"""API-level tenant isolation check using separate signed Hire identities."""
import unittest
from types import SimpleNamespace

from lare_common.app_factory import create_app
from lare_common.db import Database
from lare_common.errors import Forbidden, Unauthorized
from lare_common.internal import mint_gateway_context

from app.models import Drive, DriveCompanyParticipation, DriveInstitutionParticipation
from app.routes import bp
from app.service import DriveService


def headers(*, user, tenant, roles, colleges=(), permissions=()):
    token = mint_gateway_context({
        "sub": user, "roles": list(roles), "permissions": list(permissions),
        "tenant_id": tenant, "college_ids": list(colleges), "branch_ids": [],
        "cohort_ids": [], "scope_level": "college" if colleges else "self",
        "product": "hire",
    })
    return {"X-Internal-Token": token}


class OrganizationApiIsolationTests(unittest.TestCase):
    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        import app.models  # noqa: F401
        self.db.create_all()
        self.app = create_app(SimpleNamespace(SERVICE_NAME="drive-test", CORS_ORIGINS=[], DEBUG=False),
                              blueprints=[(bp, "")])
        self.app.extensions["db"] = self.db
        self.app.extensions["svc"] = DriveService()
        self.client = self.app.test_client()
        with self.db.session() as session:
            session.add(Drive(
                id="shared-event", company_id="college-tenant", company_name="Campus",
                title="Campus drive", status="published", tenant_id="college-tenant",
                drive_type="college_hosted", organizer_type="college", organizer_id="college-1",
                host_college_id="college-1", workflow_config={"company_pipelines": True},
            ))
            session.add(DriveInstitutionParticipation(
                drive_id="shared-event", college_id="college-1", status="accepted"))
            session.add_all([
                DriveCompanyParticipation(drive_id="shared-event", company_id="company-1",
                                          status="invited", responsibilities={"recruitment": True}),
                DriveCompanyParticipation(drive_id="shared-event", company_id="company-2",
                                          status="invited", responsibilities={"recruitment": True}),
            ])

    def tearDown(self):
        self.db.engine.dispose()

    def accept(self, company, admin):
        response = self.client.post(
            f"/drive/v1/drives/shared-event/participation/company/{company}",
            headers=headers(user=admin, tenant=company, roles=("company_admin",),
                            permissions=("drive.adoption.respond",)),
            json={"decision": "accept"},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()["data"]["pipeline_drive_id"]

    def test_company_accounts_get_independent_pipelines_and_college_cannot_read_candidates(self):
        pipeline_one = self.accept("company-1", "company-admin-1")
        pipeline_two = self.accept("company-2", "company-admin-2")
        self.assertNotEqual(pipeline_one, pipeline_two)

        one_headers = headers(user="company-admin-1", tenant="company-1",
                              roles=("company_admin",),
                              permissions=("drive.drive.view", "drive.drive.manage"))
        create = self.client.post(f"/drive/v1/drives/{pipeline_one}/register",
                                  headers=one_headers, json={"candidate_id": "candidate-1"})
        self.assertEqual(create.status_code, 201, create.get_json())

        two_headers = headers(user="company-admin-2", tenant="company-2",
                              roles=("company_admin",),
                              permissions=("drive.drive.view", "drive.drive.manage"))
        own = self.client.get(f"/drive/v1/drives/{pipeline_two}/registrations", headers=two_headers)
        self.assertEqual(own.status_code, 200, own.get_json())
        self.assertEqual(own.get_json()["data"], [])
        cross_company = self.client.get(f"/drive/v1/drives/{pipeline_one}/registrations", headers=two_headers)
        self.assertEqual(cross_company.status_code, 403)

        college_headers = headers(user="college-tpo", tenant="college-tenant",
                                  roles=("tpo",), colleges=("college-1",),
                                  permissions=("drive.drive.view", "drive.drive.manage"))
        college_read = self.client.get(f"/drive/v1/drives/{pipeline_one}/registrations",
                                       headers=college_headers)
        self.assertEqual(college_read.status_code, 403)


if __name__ == "__main__":
    unittest.main()
