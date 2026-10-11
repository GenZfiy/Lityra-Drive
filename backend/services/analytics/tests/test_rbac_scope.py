"""Analytics object-scope tests; uses an in-memory SQLite database only."""
from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from lare_common.auth_context import Identity
from lare_common.db import Base
from app.models import Fact
from app.service import AnalyticsService


class AnalyticsScopeTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine, tables=[Fact.__table__])
        self.db = Session(self.engine, expire_on_commit=False)
        self.service = AnalyticsService()
        self.db.add_all([
            Fact(id="a1", kind="learner", college_id="college-a", cohort_id="cohort-a",
                 learner_id="learner-a", drive_id="drive-a", metric="coding", value=88),
            Fact(id="b1", kind="learner", college_id="college-b", cohort_id="cohort-b",
                 learner_id="learner-b", drive_id="drive-b", metric="coding", value=99),
        ])
        self.db.flush()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_college_dashboard_does_not_expose_other_colleges(self):
        ident = Identity(user_id="college-admin", roles=["college_admin"],
                         permissions=["analytics.college.view"], tenant_id="tenant-a",
                         college_ids=["college-a"], scope_level="college")
        dashboard = self.service.dashboard(self.db, "college_admin", ident)
        self.assertEqual(dashboard["colleges"], 1)
        self.assertEqual(dashboard["learners"], 1)
        self.assertEqual(dashboard["drives"], 1)
        self.assertEqual(dashboard["top_colleges"], [])

    def test_self_scope_scorecard_does_not_read_another_learner(self):
        ident = Identity(user_id="learner-a", roles=["student"],
                         permissions=["analytics.student.view"], tenant_id="tenant-a",
                         scope_level="self")
        own = self.service.scorecard(self.db, "learner-a", ident)
        other = self.service.scorecard(self.db, "learner-b", ident)
        self.assertEqual(own["scorecard"]["coding"], 88.0)
        self.assertEqual(other["scorecard"]["coding"], 0.0)

    def test_branch_scope_fails_closed_without_branch_fact_column(self):
        ident = Identity(user_id="hod", roles=["hod"],
                         permissions=["analytics.branch.view"], tenant_id="tenant-a",
                         college_ids=["college-a"], branch_ids=["cse"], scope_level="branch")
        dashboard = self.service.dashboard(self.db, "hod", ident)
        self.assertEqual(dashboard["colleges"], 0)
        self.assertEqual(dashboard["learners"], 0)


if __name__ == "__main__":
    unittest.main()
