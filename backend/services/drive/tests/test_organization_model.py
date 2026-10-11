"""Risk-focused checks for organization boundaries and drive transitions."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lare_common.db import Database
from lare_common.errors import Conflict
from app.models import Drive, DriveCompanyParticipation, DriveInstitutionParticipation, DriveRole, Round, Registration
from app.schemas import DriveIn
from app import service as drive_service_module
from app.service import DriveService
from migrate_cols import migrate_existing_columns


def identity(*, user="user-1", roles=(), tenant="tenant-a", colleges=()):
    return SimpleNamespace(user_id=user, roles=list(roles), tenant_id=tenant,
                           college_ids=list(colleges),
                           has_role=lambda *want: any(role in roles for role in want))


class DriveOrganizationTests(unittest.TestCase):
    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        import app.models  # noqa: F401
        self.db.create_all()
        self.session_context = self.db.session()
        self.s = self.session_context.__enter__()

    def tearDown(self):
        self.session_context.__exit__(None, None, None)
        self.db.engine.dispose()

    def test_college_coordination_does_not_grant_recruitment_access(self):
        drive = Drive(id="d1", company_id="tenant-a", company_name="Acme", title="Campus",
                      tenant_id="tenant-a", drive_type="company_hosted", organizer_type="company",
                      organizer_id="tenant-a", host_college_id="college-1")
        self.s.add(drive)
        self.s.add(DriveInstitutionParticipation(drive_id="d1", college_id="college-1",
                                                 status="accepted", attendance_allowed=True))
        self.s.flush()
        service = DriveService()
        college = identity(roles=("tpo",), colleges=("college-1",))
        self.assertTrue(service.can_access_drive(self.s, drive, college))
        self.assertFalse(service.recruitment_access(self.s, drive, college))

    def test_invited_host_cannot_open_drive_before_acceptance(self):
        drive = Drive(id="d9", company_id="company-1", company_name="Acme", title="Hosted",
                      tenant_id="company-1", drive_type="company_hosted", organizer_type="company",
                      organizer_id="company-1", host_college_id="college-1")
        self.s.add(drive)
        self.s.add(DriveInstitutionParticipation(drive_id="d9", college_id="college-1",
                                                 status="invited", attendance_allowed=True))
        self.s.flush()
        service = DriveService()
        host = identity(roles=("tpo",), colleges=("college-1",), tenant="college-tenant")
        self.assertFalse(service.can_access_drive(self.s, drive, host))


    def test_company_participation_grants_only_accepted_recruitment_scope(self):
        drive = Drive(id="d2", company_id="college-tenant", company_name="Partner", title="Hosted",
                      tenant_id="college-tenant", drive_type="college_adopted", organizer_type="college",
                      organizer_id="college-1", adoption_status="accepted")
        self.s.add(drive)
        self.s.add(DriveCompanyParticipation(drive_id="d2", company_id="company-1",
            participation_role="adopter", status="accepted", responsibilities={"recruitment": True}))
        self.s.flush()
        service = DriveService()
        accepted = identity(roles=("recruiter",), tenant="company-1")
        other = identity(roles=("recruiter",), tenant="company-2")
        self.assertTrue(service.can_access_drive(self.s, drive, accepted))
        self.assertTrue(service.recruitment_access(self.s, drive, accepted))
        self.assertFalse(service.can_access_drive(self.s, drive, other))


    def test_adoption_must_be_accepted_before_publishing(self):
        drive = Drive(id="d3", company_id="college-tenant", company_name="Pending", title="Adopt",
                      tenant_id="college-tenant", drive_type="college_adopted", organizer_type="college",
                      organizer_id="college-1", adoption_status="pending", status="draft",
                      workflow_config={"company_confirmation_required": True})
        self.s.add(drive)
        self.s.flush()
        with self.assertRaisesRegex(Conflict, "adopting company"):
            DriveService().transition(self.s, "d3", "published")

    def test_each_company_invited_to_joint_drive_can_recruit(self):
        drive = Drive(id="d5", company_id="college-tenant", company_name="College event", title="Joint",
                      tenant_id="college-tenant", drive_type="college_hosted", organizer_type="college",
                      organizer_id="college-1", workflow_config={})
        self.s.add(drive)
        self.s.flush()
        rows = DriveService().invite_companies(self.s, drive, ["company-1", "company-2"], "tpo-1")
        self.s.flush()
        responsibilities = {row.company_id: row.responsibilities for row in self.s.query(DriveCompanyParticipation).filter_by(drive_id="d5").all()}
        self.assertTrue(responsibilities["company-1"]["recruitment"])
        self.assertTrue(responsibilities["company-2"]["recruitment"])
        self.assertTrue(responsibilities["company-2"]["coordination"])
        self.assertEqual(len(rows), 2)

    def test_company_acceptance_creates_independent_pipeline_per_company(self):
        parent = Drive(id="event-1", company_id="college-tenant", company_name="Campus",
                       title="Joint drive", tenant_id="college-tenant", drive_type="college_hosted",
                       organizer_type="college", organizer_id="college-1",
                       workflow_config={"company_pipelines": True})
        self.s.add(parent)
        self.s.add(DriveRole(drive_id="event-1", title="Engineer", positions=2, skills=[]))
        self.s.add(Round(drive_id="event-1", order=1, type="technical", config={"time": 60}))
        self.s.add(DriveCompanyParticipation(drive_id="event-1", company_id="company-1",
            status="invited", responsibilities={"recruitment": True}))
        self.s.add(DriveCompanyParticipation(drive_id="event-1", company_id="company-2",
            status="invited", responsibilities={"recruitment": True}))
        self.s.flush()
        service = DriveService()
        first = service.set_participation(self.s, "event-1", company_id="company-1",
                                          decision="accept", actor_id="company-admin-1")
        second = service.set_participation(self.s, "event-1", company_id="company-2",
                                           decision="accept", actor_id="company-admin-2")
        self.s.flush()
        self.assertNotEqual(first["pipeline_drive_id"], second["pipeline_drive_id"])
        one = service.get(self.s, first["pipeline_drive_id"])
        two = service.get(self.s, second["pipeline_drive_id"])
        self.assertEqual(one.pipeline_company_id, "company-1")
        self.assertEqual(two.pipeline_company_id, "company-2")
        self.assertEqual(one.event_group_id, two.event_group_id)
        self.assertEqual(len(one.roles), 1)
        self.assertEqual(len(two.rounds), 1)
        company_one = identity(user="company-admin-1", roles=("recruiter",), tenant="company-1")
        company_two = identity(user="company-admin-2", roles=("recruiter",), tenant="company-2")
        self.assertFalse(service.recruitment_access(self.s, parent, company_one))
        self.assertTrue(service.recruitment_access(self.s, one, company_one))
        self.assertFalse(service.recruitment_access(self.s, two, company_one))
        self.assertTrue(service.recruitment_access(self.s, two, company_two))
        data = SimpleNamespace(candidate_id="candidate-1", cgpa=None, branch=None,
                                backlogs=0, lms_score=None)
        service.register(self.s, one.id, data)
        with patch.object(drive_service_module, "_resolve_names", return_value={}):
            self.assertEqual(service.registrations(self.s, one.id)[0]["candidate_id"], "candidate-1")
            self.assertEqual(service.registrations(self.s, two.id), [])

    def test_coordinator_company_cannot_satisfy_recruiter_acceptance_gate(self):
        drive = Drive(id="d6", company_id="college-tenant", company_name="College event", title="Hosted",
                      tenant_id="college-tenant", drive_type="college_hosted", organizer_type="college",
                      organizer_id="college-1", status="draft",
                      workflow_config={"company_confirmation_required": True})
        self.s.add(drive)
        self.s.add(DriveCompanyParticipation(drive_id="d6", company_id="company-2",
            participation_role="recruiter", status="accepted", responsibilities={"recruitment": False, "coordination": True}))
        self.s.flush()
        with self.assertRaisesRegex(Conflict, "recruiting company"):
            DriveService().transition(self.s, "d6", "published")

    def test_publication_rechecks_company_acceptance_after_review(self):
        drive = Drive(id="d7", company_id="college-tenant", company_name="College event", title="Review",
                      tenant_id="college-tenant", drive_type="college_hosted", organizer_type="college",
                      organizer_id="college-1", status="pending_review",
                      workflow_config={"company_confirmation_required": True, "college_approval_required": True})
        self.s.add(drive)
        self.s.add(DriveCompanyParticipation(drive_id="d7", company_id="company-1",
            participation_role="recruiter", status="withdrawn", responsibilities={"recruitment": True}))
        self.s.flush()
        with self.assertRaisesRegex(Conflict, "recruiting company"):
            DriveService().transition(self.s, "d7", "published")

    def test_search_returns_only_drives_visible_to_the_identity(self):
        self.s.add(Drive(id="d8", company_id="company-a", company_name="Acme", title="Campus role",
                         tenant_id="company-a", drive_type="company_off_campus",
                         organizer_type="company", organizer_id="company-a"))
        self.s.flush()
        visible = DriveService().search(self.s, "campus", identity(roles=("company_admin",), tenant="company-a"))
        hidden = DriveService().search(self.s, "campus", identity(roles=("company_admin",), tenant="company-b"))
        self.assertEqual([row["id"] for row in visible], ["d8"])
        self.assertEqual(hidden, [])


    def test_invalid_lifecycle_transition_is_rejected(self):
        drive = Drive(id="d4", company_id="tenant-a", company_name="Acme", title="Draft",
                      tenant_id="tenant-a", status="draft")
        self.s.add(drive)
        self.s.flush()
        with self.assertRaisesRegex(Conflict, "Cannot move"):
            DriveService().transition(self.s, "d4", "completed")

    def test_company_off_campus_uses_authenticated_tenant_and_starts_without_colleges(self):
        drive = DriveService().create(self.s, DriveIn(
            company_id="attacker-controlled-id", company_name="Acme", title="Off campus"),
            identity(roles=("recruiter",), tenant="verified-company"))
        self.assertEqual(drive.company_id, "verified-company")
        self.assertEqual(drive.organizer_id, "verified-company")
        self.assertEqual(drive.drive_type, "company_off_campus")
        self.assertEqual(drive.institutions, [])

    def test_existing_drive_table_migration_is_idempotent(self):
        legacy = Database("sqlite:///:memory:")
        with legacy.engine.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE drives (id VARCHAR PRIMARY KEY, company_id VARCHAR(64) NOT NULL, company_name VARCHAR(255) NOT NULL, title VARCHAR(255) NOT NULL, status VARCHAR(24), created_at DATETIME)")
            conn.exec_driver_sql("INSERT INTO drives (id, company_id, company_name, title) VALUES ('legacy-drive', 'legacy-company', 'Legacy Co', 'Legacy drive')")
        first = migrate_existing_columns(legacy)
        second = migrate_existing_columns(legacy)
        from sqlalchemy import inspect
        columns = {col["name"] for col in inspect(legacy.engine).get_columns("drives")}
        self.assertEqual(first, 10)
        self.assertEqual(second, 0)
        self.assertTrue({"tenant_id", "drive_type", "organizer_type", "organizer_id",
                         "host_college_id", "adoption_status", "workflow_config",
                         "event_group_id", "parent_drive_id", "pipeline_company_id"}.issubset(columns))
        with legacy.engine.connect() as conn:
            row = conn.exec_driver_sql("SELECT tenant_id, organizer_id FROM drives WHERE id = 'legacy-drive'").one()
        self.assertEqual(tuple(row), ("legacy-company", "legacy-company"))
        legacy.engine.dispose()
