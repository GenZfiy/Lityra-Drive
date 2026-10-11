"""DB-local auth isolation tests. Uses SQLite and never reaches Supabase."""
from __future__ import annotations

import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from flask import Flask

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from lare_common.db import Base
from lare_common.errors import Forbidden, NotFound, Unauthorized
from lare_common.security import create_access_token, decode_token, hash_password
from app.models import Permission, RefreshToken, Role, User, UserRole, VerificationToken
from app.routes import bp as auth_bp
from app.service import AuthService
from lare_common.auth_context import current_identity
from lare_common.internal import mint_gateway_context, mint_service_token


class ProductSecurityTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, expire_on_commit=False)
        cfg = SimpleNamespace(
            BCRYPT_ROUNDS=4, MAX_LOGIN_ATTEMPTS=5, LOCKOUT_MINUTES=15,
            JWT_ALG="HS256", signing_key="test-signing-key", verify_key="test-signing-key",
            JWT_ISSUER="learn-auth", JWT_AUDIENCE="learn-api",
            ACCESS_TOKEN_TTL_MIN=5, REFRESH_TOKEN_TTL_DAYS=1,
        )
        self.service = AuthService(cfg)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def add_user(self, product: str) -> User:
        user = User(id=f"user-{product}", email="same@example.test", product=product,
                    password_hash=hash_password("test-password", rounds=4),
                    tenant_id="test", status="active")
        self.db.add(user)
        self.db.flush()
        return user

    def verification(self, user: User, purpose: str) -> str:
        raw = self.service._issue_verification(self.db, user, purpose, ttl_min=15, numeric=False)
        self.db.flush()
        return raw

    def test_equal_email_accounts_are_independent_by_product(self):
        learn = self.add_user("learn")
        hire = self.add_user("hire")
        learn_tokens = self.service.login(self.db, learn.email, "test-password", None, "learn")
        hire_tokens = self.service.login(self.db, hire.email, "test-password", None, "hire")
        self.assertNotEqual(learn.id, hire.id)
        for tokens, product in ((learn_tokens, "learn"), (hire_tokens, "hire")):
            claims = decode_token(tokens["access_token"], alg="HS256", verify_key="test-signing-key",
                                  issuer="learn-auth", audience="learn-api")
            self.assertEqual(claims["product"], product)

    def test_role_catalog_and_assignment_are_product_scoped(self):
        learn = self.add_user("learn")
        hire_role = Role(id="hire-role", name="program_manager", product="hire",
                         scope_level="branch", is_system=True, is_active=True)
        self.db.add(hire_role)
        self.db.flush()
        with self.assertRaisesRegex(Exception, "Unknown role"):
            self.service.assign_role(self.db, learn.id, "program_manager", None)
        learn_role = Role(id="learn-role", name="program_manager", product="learn",
                          scope_level="branch", is_system=True, is_active=True)
        self.db.add(learn_role)
        self.db.add_all([
            Permission(id="p-drive", code="drive.drive.manage", domain="drive"),
            Permission(id="p-training", code="training.program.manage", domain="training"),
        ])
        self.db.flush()
        scoped = AuthService(SimpleNamespace(AUTH_ALLOWED_PRODUCT="learn"))
        self.assertEqual([r["product"] for r in scoped.list_roles(self.db)], ["learn"])
        self.assertEqual([p["code"] for p in scoped.list_permissions(self.db)],
                         ["training.program.manage"])
        with self.assertRaisesRegex(Exception, "another product"):
            scoped.create_role(self.db, "bad_learn_role", None, "self",
                               ["drive.drive.manage"], product="learn")

    def test_role_grants_reject_self_escalation_cross_tenant_and_broader_permissions(self):
        actor = self.add_user("hire")
        target = User(id="target", email="target@example.test", product="hire",
                      password_hash="x", tenant_id="tenant-a", status="active")
        other_tenant = User(id="other", email="other@example.test", product="hire",
                            password_hash="x", tenant_id="tenant-b", status="active")
        self.db.add_all([target, other_tenant])
        view = Permission(id="p-view", code="drive.drive.view", domain="drive")
        admin = Permission(id="p-admin", code="auth.user.manage", domain="auth")
        safe = Role(id="safe", name="recruiter", product="hire", scope_level="self",
                    is_system=True, is_active=True, permissions=[view])
        elevated = Role(id="elevated", name="hire_admin", product="hire", scope_level="self",
                        is_system=False, is_active=True, permissions=[view, admin])
        self.db.add_all([view, admin, safe, elevated])
        self.db.flush()
        ident = SimpleNamespace(user_id=actor.id, product="hire", tenant_id="tenant-a",
                                 roles=["recruiter"], permissions=["drive.drive.view"],
                                 scope_level="self", college_ids=[], branch_ids=[], cohort_ids=[])

        with self.assertRaises(Forbidden):
            self.service.authorize_role_grant(self.db, ident, actor.id, "recruiter", None)
        with self.assertRaises(NotFound):
            self.service.authorize_role_grant(self.db, ident, other_tenant.id, "recruiter", None)
        with self.assertRaises(Forbidden):
            self.service.authorize_role_grant(self.db, ident, target.id, "hire_admin", None)
        self.service.authorize_role_grant(self.db, ident, target.id, "recruiter", None)

    def test_non_platform_role_grant_requires_in_scope_binding(self):
        actor = self.add_user("hire")
        target = User(id="target", email="target@example.test", product="hire",
                      password_hash="x", tenant_id=actor.tenant_id, status="active")
        permission = Permission(id="p", code="drive.drive.view", domain="drive")
        role = Role(id="college-role", name="college_recruiter", product="hire",
                    scope_level="college", is_active=True, permissions=[permission])
        self.db.add_all([target, permission, role])
        self.db.flush()
        ident = SimpleNamespace(user_id=actor.id, product="hire", tenant_id=actor.tenant_id,
                                 roles=["college_admin"], permissions=["drive.drive.view"],
                                 scope_level="college", college_ids=["college-1"],
                                 branch_ids=[], cohort_ids=[])
        with self.assertRaises(Forbidden):
            self.service.authorize_role_grant(self.db, ident, target.id,
                                              "college_recruiter", "college-2")
        self.service.authorize_role_grant(self.db, ident, target.id,
                                          "college_recruiter", "college-1")

    def test_company_admin_user_scope_is_tenant_bounded(self):
        local = self.add_user("hire")
        remote = User(id="remote", email="remote@example.test", product="hire",
                      password_hash="x", tenant_id="another-tenant", status="active")
        self.db.add(remote)
        self.db.flush()
        ident = SimpleNamespace(user_id="admin", product="hire", tenant_id=local.tenant_id,
                                roles=["company_admin"], permissions=["auth.user.view"],
                                scope_level="platform", college_ids=[], branch_ids=[], cohort_ids=[],
                                has_role=lambda *names: any(n in ["company_admin"] for n in names))
        self.assertTrue(self.service.user_in_scope(self.db, ident, local.id))
        self.assertFalse(self.service.user_in_scope(self.db, ident, remote.id))
        rows = self.service.list_admin_users(self.db, None, None, "hire", 100,
                                             tenant_id=local.tenant_id)
        self.assertEqual([u.id for u in rows], [local.id])

    def test_internal_invitation_resolver_targets_hire_staff_not_students(self):
        company_admin_role = Role(id="invite-company-admin", name="company_admin", product="hire",
                                  scope_level="platform", is_system=True, is_active=True)
        college_tpo_role = Role(id="invite-tpo", name="tpo", product="hire",
                                scope_level="college", is_system=True, is_active=True)
        student_role = Role(id="invite-student", name="student", product="hire",
                            scope_level="self", is_system=True, is_active=True)
        users = [
            User(id="company-staff", email="company@example.test", product="hire",
                 password_hash="x", tenant_id="company-x", status="active"),
            User(id="company-student", email="candidate@example.test", product="hire",
                 password_hash="x", tenant_id="company-x", status="active"),
            User(id="college-staff", email="tpo@example.test", product="hire",
                 password_hash="x", tenant_id="college-tenant", status="active"),
            User(id="college-student", email="learner@example.test", product="hire",
                 password_hash="x", tenant_id="college-tenant", status="active"),
        ]
        self.db.add_all([company_admin_role, college_tpo_role, student_role, *users])
        self.db.flush()
        self.db.add_all([
            UserRole(id="company-staff-binding", user_id="company-staff", role_id=company_admin_role.id),
            UserRole(id="company-student-binding", user_id="company-student", role_id=student_role.id),
            UserRole(id="college-staff-binding", user_id="college-staff", role_id=college_tpo_role.id,
                     college_id="college-x"),
            UserRole(id="college-student-binding", user_id="college-student", role_id=student_role.id,
                     college_id="college-x"),
        ])
        self.db.flush()

        class SessionContext:
            @contextmanager
            def session(_self):
                yield self.db

        app = Flask(__name__)
        app.config["LARE"] = SimpleNamespace(AUTH_ALLOWED_PRODUCT="hire")
        app.extensions["db"] = SessionContext()
        app.register_blueprint(auth_bp, url_prefix="/auth/v1")
        token = mint_service_token("notification", permissions=["auth.user.view"])
        client = app.test_client()
        company = client.post("/auth/v1/internal/organization-users",
                              headers={"X-Internal-Token": token},
                              json={"kind": "company", "organization_id": "company-x", "product": "hire"})
        college = client.post("/auth/v1/internal/organization-users",
                              headers={"X-Internal-Token": token},
                              json={"kind": "college", "organization_id": "college-x", "product": "hire"})
        self.assertEqual(company.status_code, 200, company.get_json())
        self.assertEqual(college.status_code, 200, college.get_json())
        self.assertEqual([u["id"] for u in company.get_json()["data"]], ["company-staff"])
        self.assertEqual([u["id"] for u in college.get_json()["data"]], ["college-staff"])

    def test_inactive_and_cross_product_grants_do_not_enter_tokens(self):
        user = self.add_user("learn")
        wrong_product = Permission(id="p-drive", code="drive.drive.manage", domain="drive")
        learn_permission = Permission(id="p-course", code="academic.course.view", domain="academic")
        inactive = Role(id="inactive", name="company_admin", product="learn",
                        scope_level="platform", is_active=False,
                        permissions=[wrong_product])
        active = Role(id="active", name="student", product="learn",
                      scope_level="self", is_active=True,
                      permissions=[wrong_product, learn_permission])
        self.db.add_all([wrong_product, learn_permission, inactive, active])
        self.db.flush()
        self.db.add_all([
            UserRole(id="inactive-binding", user_id=user.id, role_id=inactive.id,
                     college_id="stale-college"),
            UserRole(id="active-binding", user_id=user.id, role_id=active.id,
                     college_id=None),
        ])
        self.db.flush()

        token_pair = self.service._issue_tokens(self.db, user, None)
        claims = decode_token(token_pair["access_token"], alg="HS256",
                              verify_key="test-signing-key", issuer="learn-auth",
                              audience="learn-api")
        self.assertEqual(claims["roles"], ["student"])
        self.assertEqual(claims["permissions"], ["academic.course.view"])
        self.assertEqual(claims["college_ids"], [])
        self.assertEqual(claims["scope_level"], "self")

    def test_identity_headers_require_a_signed_internal_context(self):
        app = Flask(__name__)
        with app.test_request_context("/private", headers={
            "X-User-Id": "attacker", "X-Roles": "super_admin",
            "X-Permissions": "auth.user.manage",
        }):
            with self.assertRaises(Unauthorized):
                current_identity()

    def test_gateway_context_is_signature_bound_and_role_headers_cannot_be_tampered(self):
        app = Flask(__name__)
        signed = mint_gateway_context({
            "sub": "admin-1", "roles": ["company_admin"],
            "permissions": ["auth.user.view"], "tenant_id": "tenant-1",
            "college_ids": [], "branch_ids": [], "cohort_ids": [],
            "scope_level": "platform", "product": "hire",
        })
        with app.test_request_context("/private", headers={
            "X-Internal-Token": signed, "X-User-Id": "forged",
            "X-Roles": "super_admin",
        }):
            ident = current_identity()
            self.assertEqual(ident.user_id, "admin-1")
            self.assertEqual(ident.roles, ["company_admin"])
            self.assertEqual(ident.permissions, ["auth.user.view"])

        service_token = mint_service_token("test-service", roles=["recruiter"], user_id="candidate-1")
        with app.test_request_context("/private", headers={
            "X-Internal-Token": service_token, "X-User-Id": "candidate-1",
            "X-Roles": "super_admin",
        }):
            with self.assertRaises(Unauthorized):
                current_identity()

    def test_wrong_product_reset_does_not_consume_token(self):
        user = self.add_user("hire")
        raw = self.verification(user, "password_reset")
        with self.assertRaisesRegex(Unauthorized, "another product"):
            self.service.reset_password(self.db, raw, "changed-password", "learn")
        self.assertIsNone(self.db.execute(select(VerificationToken)).scalar_one().consumed_at)

    def test_wrong_product_email_verification_does_not_consume_token(self):
        user = self.add_user("hire")
        raw = self.verification(user, "email_verify")
        with self.assertRaisesRegex(Unauthorized, "another product"):
            self.service.verify_email(self.db, raw, "learn")
        self.assertIsNone(self.db.execute(select(VerificationToken)).scalar_one().consumed_at)

    def test_cross_product_refresh_and_logout_have_no_revocation_side_effect(self):
        user = self.add_user("hire")
        tokens = self.service._issue_tokens(self.db, user, "browser")
        refresh = self.db.execute(select(RefreshToken)).scalar_one()
        with self.assertRaisesRegex(Unauthorized, "another product"):
            self.service.refresh(self.db, tokens["refresh_token"], "learn")
        self.assertIsNone(refresh.revoked_at)
        with self.assertRaisesRegex(Unauthorized, "another product"):
            self.service.logout(self.db, tokens["refresh_token"], "learn")
        self.assertIsNone(refresh.revoked_at)

    def test_refresh_rotation_and_reuse_detection(self):
        user = self.add_user("learn")
        first = self.service._issue_tokens(self.db, user, None)
        self.service.refresh(self.db, first["refresh_token"], "learn")
        with self.assertRaisesRegex(Unauthorized, "reuse"):
            self.service.refresh(self.db, first["refresh_token"], "learn")
        rows = self.db.execute(select(RefreshToken)).scalars().all()
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row.revoked_at is not None for row in rows))

    def test_wrong_audience_signature_and_expiry_are_rejected(self):
        args = dict(subject="u1", roles=[], tenant_id="t", college_ids=[], alg="HS256",
                    signing_key="test-signing-key", issuer="learn-auth", audience="learn-api",
                    ttl_minutes=5, extra={"product": "learn"})
        valid = create_access_token(**args)
        for key, issuer, audience, token in (
            ("test-signing-key", "learn-auth", "hire-api", valid),
            ("test-signing-key", "hire-auth", "learn-api", valid),
            ("bad-signing-key", "learn-auth", "learn-api", valid),
            ("test-signing-key", "learn-auth", "learn-api",
             create_access_token(**{**args, "ttl_minutes": -1})),
        ):
            with self.assertRaises(Exception):
                decode_token(token, alg="HS256", verify_key=key, issuer=issuer, audience=audience)


if __name__ == "__main__":
    unittest.main()
