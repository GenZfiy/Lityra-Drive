"""Seed the RBAC engine: the granular permission catalog, the built-in role
ladder with default permission sets, and an initial super admin.

This is the bedrock every service enforces through. Permissions are *granular*
(one code per capability, e.g. ``analytics.branch.view``) and grouped by domain;
roles are bundles of permissions plus a data-visibility ``scope_level``. The seed
is idempotent — it adds anything missing and tops up each system role's default
permissions without ever removing an admin's later customisations.
"""
from __future__ import annotations

import os

from sqlalchemy import select

from lare_common.security import hash_password, new_id

from .config import AuthConfig
from .models import Permission, Role, User, UserRole
from .service import _permission_product

# ---------------------------------------------------------------------------
# Roles: (name, description, scope_level). scope_level is the data-visibility
# ceiling — platform > college > branch > section > self — enforced at the
# query layer. These are the SYSTEM roles (is_system=True): re-permissionable,
# never deletable. Admins may create additional custom roles at runtime.
# ---------------------------------------------------------------------------
ROLES = [
    ("super_admin",   "Platform owner (LARE). Full control across all institutions.", "platform"),
    ("company_admin", "LARE recruitment / programme operator.",                       "platform"),
    ("principal",     "Institution head — oversees one college end to end.",          "college"),
    ("dean",          "Academic head — oversees academics & development for a college.", "college"),
    ("hod",           "Head of Department — leads one branch's academics.",           "branch"),
    ("tpo",           "Training & Placement Officer — placements for one college.",   "college"),
    ("college_admin", "College coordinator / administrator.",                         "college"),
    ("training_center_admin", "Training center leader — manages one center, its programs and batches.", "college"),
    ("program_manager", "Upskilling program manager — manages assigned programs and their batches.", "branch"),
    ("trainer",       "Trainer / mentor — teaches assigned courses or training batches.", "section"),
    ("faculty",       "Faculty — teaches and assesses their assigned branch.",        "branch"),
    ("recruiter",     "Recruiter / interviewer (Drive).",                             "self"),
    ("interviewer",   "Interviewer — reviews and rates interviews assigned to them.", "self"),
    ("student",       "Learner / candidate.",                                         "self"),
]

# ---------------------------------------------------------------------------
# Permission catalog: (code, description, domain). One code == one capability.
# Every API/service enforces on these codes; frontend hiding is cosmetic only.
# ---------------------------------------------------------------------------
PERMISSIONS = [
    # platform / system
    ("platform.system.config",     "Configure platform settings",          "platform"),
    ("platform.audit.view",        "View audit logs",                      "platform"),
    # identity & access management
    ("auth.user.manage",           "Create, edit, suspend users",          "auth"),
    ("auth.user.view",             "View users",                           "auth"),
    ("auth.role.manage",           "Create, edit, delete roles",           "auth"),
    ("auth.role.assign",           "Assign roles to users",                "auth"),
    # institution structure
    ("institution.manage",         "Manage colleges, branches, years, sections", "institution"),
    ("institution.view",           "View institution structure",          "institution"),
    ("institution.access.manage",  "Manage Access IDs",                    "institution"),
    # academic / curriculum
    ("academic.course.manage",     "Manage courses & curriculum",          "academic"),
    ("academic.course.view",       "View courses & curriculum",            "academic"),
    ("academic.enrollment.manage", "Manage student enrollment",            "academic"),
    ("lms.curriculum.manage",      "Manage LMS curriculum",                "lms"),
    # assessment
    ("assessment.manage",          "Create & edit assessments",            "assessment"),
    ("assessment.grade",           "Grade & override scores",              "assessment"),
    ("assessment.result.publish",  "Publish assessment results",           "assessment"),
    # recruitment (Drive)
    ("drive.drive.manage",         "Manage recruitment drives",            "drive"),
    ("drive.drive.delete",         "Delete recruitment drives", "drive"),
    ("drive.drive.view",           "View recruitment drives in assigned scope", "drive"),
    ("drive.candidate.view",       "View candidate profiles and applications", "drive"),
    ("drive.interview.manage",     "Schedule and allocate interviews", "drive"),
    ("drive.interview.review",     "View and submit feedback for assigned interviews", "drive"),
    ("drive.question.review",      "Approve or reject shared assessment questions", "drive"),
    ("drive.question.manage",      "Manage hiring assessments and question banks", "drive"),
    ("drive.access.manage",        "Manage drive access codes", "drive"),
    ("drive.analytics.view",       "View drive analytics", "drive"),
    ("drive.data.export",          "Export recruitment data", "drive"),
    ("drive.result.publish",       "Publish results / offers",             "drive"),
    ("drive.participation.manage", "Invite and coordinate drive participants", "drive"),
    ("drive.adoption.respond",     "Accept or decline company adoption invitations", "drive"),
    ("drive.approval.manage",      "Approve college-organized drive publication", "drive"),
    # analytics — one code per hierarchy tier; the role's scope decides whose data
    ("analytics.platform.view",    "Platform-wide analytics (all colleges)", "analytics"),
    ("analytics.event.ingest",     "Ingest analytics events",              "analytics"),
    ("analytics.college.view",     "College-level analytics",              "analytics"),
    ("analytics.branch.view",      "Branch / department analytics",        "analytics"),
    ("analytics.section.view",     "Section / class analytics",            "analytics"),
    ("analytics.student.view",     "Individual student analytics",         "analytics"),
    ("analytics.export",           "Export reports & data",                "analytics"),
    # self-service
    ("self.profile.manage",        "Manage own profile",                   "self"),
    ("self.progress.view",         "View own progress",                    "self"),
    # training center operations
    ("training.center.view",       "View assigned training centers",       "training"),
    ("training.center.manage",     "Manage training center operations",   "training"),
    ("training.program.view",      "View assigned upskilling programs",    "training"),
    ("training.program.manage",    "Create and manage training programs", "training"),
    ("training.batch.view",        "View assigned cohorts and batches",   "training"),
    ("training.batch.manage",      "Create and manage training batches",  "training"),
    ("training.participant.view",  "View learner and employee rosters",   "training"),
    ("training.participant.manage","Enroll and manage participants",      "training"),
]

# ---------------------------------------------------------------------------
# Default permission set per system role. super_admin is handled separately
# (gets everything). "*" as a prefix wildcard is expanded against the catalog.
# ---------------------------------------------------------------------------
_ANALYTICS_DOWN = ["analytics.college.view", "analytics.branch.view",
                   "analytics.section.view", "analytics.student.view",
                   "analytics.export"]

ROLE_DEFAULTS: dict[str, list[str]] = {
    "company_admin": [
        # Programme operator: full user & role administration, but not
        # platform.system.config or auth.role.manage (those stay super-admin-tier).
        "auth.user.manage", "auth.user.view", "auth.role.assign",
        "institution.manage", "institution.view", "institution.access.manage",
        "academic.course.manage", "academic.enrollment.manage", "lms.curriculum.manage",
        "assessment.manage", "assessment.grade", "assessment.result.publish",
        "drive.drive.manage", "drive.drive.delete", "drive.drive.view", "drive.candidate.view",
        "drive.interview.manage", "drive.interview.review", "drive.question.manage",
        "drive.question.review",
        "drive.access.manage", "drive.analytics.view", "drive.data.export",
        "drive.result.publish", "drive.participation.manage", "drive.adoption.respond",
        "training.center.view", "training.center.manage",
        "training.program.view", "training.program.manage",
        "training.batch.view", "training.batch.manage",
        "training.participant.view", "training.participant.manage",
        "analytics.platform.view", *_ANALYTICS_DOWN,
        "analytics.event.ingest",
    ],
    "principal": [
        "auth.user.view", "institution.view", "academic.course.view",
        "drive.drive.view", "drive.approval.manage", "drive.participation.manage",
        "training.center.view", "training.program.view", "training.batch.view",
        "training.participant.view",
        *_ANALYTICS_DOWN,
    ],
    "dean": [
        "institution.view", "academic.course.manage", "academic.course.view",
        "drive.drive.manage", "drive.drive.view", "drive.participation.manage", "drive.approval.manage",
        "training.center.view", "training.program.view", "training.batch.view",
        "training.participant.view",
        "analytics.college.view", "analytics.branch.view", "analytics.section.view",
        "analytics.student.view", "analytics.export",
    ],
    "hod": [
        # Department head: manages their branch's curriculum/assessments and sees
        # their branch's analytics. Scope (branch) limits it to their department.
        "institution.view", "academic.course.manage", "academic.course.view",
        "assessment.manage", "assessment.grade",
        "training.center.view", "training.program.view", "training.batch.view",
        "training.participant.view",
        "analytics.branch.view", "analytics.section.view", "analytics.student.view",
        "analytics.export", "self.profile.manage",
    ],
    "tpo": [
        "institution.view", "institution.access.manage", "academic.course.view",
        "drive.participation.manage", "drive.approval.manage",
        "drive.drive.manage", "drive.drive.delete", "drive.drive.view", "drive.candidate.view",
        "drive.interview.manage", "drive.interview.review", "drive.question.manage",
        "drive.question.review",
        "drive.access.manage", "drive.analytics.view", "drive.data.export",
        "drive.result.publish",
        *_ANALYTICS_DOWN,
    ],
    "college_admin": [
        "auth.user.view", "institution.view", "institution.access.manage",
        "academic.course.manage", "academic.enrollment.manage",
        "drive.drive.manage", "drive.drive.view", "drive.participation.manage", "drive.approval.manage",
        "training.center.view", "training.center.manage",
        "training.program.view", "training.program.manage",
        "training.batch.view", "training.batch.manage",
        "training.participant.view", "training.participant.manage",
        *_ANALYTICS_DOWN,
    ],
    "training_center_admin": [
        "auth.user.view", "training.center.view", "training.center.manage",
        "training.program.view", "training.program.manage",
        "training.batch.view", "training.batch.manage",
        "training.participant.view", "training.participant.manage",
        "analytics.college.view", "analytics.branch.view", "analytics.section.view",
        "analytics.student.view", "analytics.export",
    ],
    "program_manager": [
        "training.center.view", "training.program.view",
        "training.batch.view", "training.batch.manage",
        "training.participant.view", "training.participant.manage",
        "analytics.branch.view", "analytics.section.view", "analytics.student.view",
        "analytics.export",
    ],
    "trainer": [
        "lms.curriculum.manage", "academic.course.view",
        "assessment.manage", "assessment.grade",
        "training.center.view", "training.program.view", "training.batch.view",
        "training.participant.view",
        "analytics.section.view", "analytics.student.view",
        "self.profile.manage",
    ],
    "faculty": [
        "academic.course.manage", "academic.course.view",
        "assessment.manage", "assessment.grade",
        "training.center.view", "training.program.view", "training.batch.view",
        "training.participant.view",
        "analytics.branch.view", "analytics.section.view", "analytics.student.view",
        "self.profile.manage",
    ],
    "recruiter": [
        "drive.drive.manage", "drive.drive.delete", "drive.drive.view", "drive.candidate.view",
        "drive.interview.manage", "drive.interview.review", "drive.question.manage",
        "drive.access.manage", "drive.analytics.view", "drive.data.export",
        "drive.result.publish", "drive.participation.manage", "drive.adoption.respond",
        "self.profile.manage",
    ],
    "interviewer": [
        "drive.interview.review", "self.profile.manage",
    ],
    "student": [
        "self.profile.manage", "self.progress.view", "analytics.student.view",
        "drive.drive.view",
    ],
}


def seed(db, cfg: AuthConfig, *, create_admin: bool = True) -> None:
    with db.session() as s:
        # --- permissions ---
        perm_map: dict[str, Permission] = {}
        for code, desc, domain in PERMISSIONS:
            p = s.execute(select(Permission).where(Permission.code == code)).scalar_one_or_none()
            if not p:
                p = Permission(id=new_id(), code=code, description=desc, domain=domain)
                s.add(p)
                s.flush()
            perm_map[code] = p

        # --- roles ---
        role_maps: dict[str, dict[str, Role]] = {}
        allowed_product = getattr(cfg, "AUTH_ALLOWED_PRODUCT", "combined")
        products = [allowed_product] if allowed_product in ("learn", "hire") else ["learn", "hire"]
        for product in products:
            role_map: dict[str, Role] = {}
            for name, desc, scope in ROLES:
                role = s.execute(select(Role).where(Role.name == name,
                                                    Role.product == product)).scalar_one_or_none()
                if not role:
                    role = Role(id=new_id(), name=name, product=product, description=desc,
                                scope_level=scope, is_system=True, is_active=True)
                    s.add(role)
                    s.flush()
                else:
                    role.is_system = True
                    role.scope_level = scope
                    if desc:
                        role.description = desc
                role_map[name] = role
            role_maps[product] = role_map

        # --- default permission grants (idempotent top-up; never revokes) ---
        def grant(role: Role, codes, product: str) -> None:
            have = {p.code for p in role.permissions}
            for code in codes:
                if (code not in have and code in perm_map
                        and _permission_product(code) in (None, product)):
                    role.permissions.append(perm_map[code])

        for product, role_map in role_maps.items():
            grant(role_map["super_admin"], list(perm_map.keys()), product)
            for name, codes in ROLE_DEFAULTS.items():
                if name in role_map:
                    grant(role_map[name], codes, product)

        if create_admin:
            # --- optional initial super admin; init-db syncs the catalog only ---
            admin_email = os.getenv("SEED_ADMIN_EMAIL")
            admin_pw = os.getenv("SEED_ADMIN_PASSWORD")
            if getattr(cfg, "ENV", "development") == "production" and not (admin_email and admin_pw):
                raise RuntimeError(
                    "Production admin seeding requires SEED_ADMIN_EMAIL and "
                    "SEED_ADMIN_PASSWORD to be set explicitly"
                )
            admin_email = (admin_email or "admin@lareitcloudsolutions.com").lower()
            admin_pw = admin_pw or "ChangeMe#123"
            admin_product = allowed_product if allowed_product in ("learn", "hire") else "learn"
            admin = s.execute(select(User).where(User.email == admin_email,
                                                 User.product == admin_product)).scalar_one_or_none()
            if not admin:
                admin = User(
                    id=new_id(),
                    email=admin_email,
                    product=admin_product,
                    password_hash=hash_password(admin_pw, rounds=cfg.BCRYPT_ROUNDS),
                    full_name="LARE Super Admin",
                    status="active",
                    email_verified=True,
                    tenant_id=cfg.DEFAULT_TENANT_ID,
                )
                s.add(admin)
                s.flush()
                s.add(UserRole(id=new_id(), user_id=admin.id,
                               role_id=role_maps[admin_product]["super_admin"].id, college_id=None))
                print(f"[seed] created super admin: {admin_email}")
            else:
                print(f"[seed] super admin already exists: {admin_email}")

    print(f"[seed] RBAC ready — {len(PERMISSIONS)} permissions, {len(ROLES)} roles per product")
