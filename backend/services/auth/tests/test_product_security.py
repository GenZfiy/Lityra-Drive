"""DB-local auth isolation tests. Uses SQLite and never reaches Supabase."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from lare_common.db import Base
from lare_common.errors import Unauthorized
from lare_common.security import create_access_token, decode_token, hash_password
from app.models import Permission, RefreshToken, Role, User, VerificationToken
from app.service import AuthService


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
