r"""Seed 30 demo student accounts and write the shared roster the other
seed_demo.py scripts read. Idempotent (matches on email).

    cd backend/services/auth
    $env:DB_SCHEMA="lare_auth"; $env:PYTHONPATH="."
    ..\..\.venv\Scripts\python.exe seed_demo.py

Login for all: <email> / Lare@1234   (student01@lare.dev .. student30@lare.dev)
"""
from __future__ import annotations

import json
import os
import sys

os.environ.setdefault("DB_SCHEMA", "lare_auth")

from dotenv import load_dotenv  # noqa: E402

load_dotenv("../../.env")

import app.models  # noqa: E402,F401
from app.config import AuthConfig  # noqa: E402
from app.models import Role, User, UserRole  # noqa: E402
from lare_common.db import Database  # noqa: E402
from lare_common.security import hash_password, new_id  # noqa: E402
from sqlalchemy import select  # noqa: E402

NAMES = [
    "Aarav Sharma", "Diya Patel", "Vivaan Reddy", "Ananya Iyer", "Aditya Nair",
    "Ishaan Rao", "Sara Khan", "Kabir Menon", "Myra Gupta", "Arjun Verma",
    "Aisha Fernandes", "Rohan Das", "Kiara Joshi", "Vihaan Kulkarni", "Anika Bose",
    "Reyansh Pillai", "Navya Chauhan", "Advik Malhotra", "Riya Saxena", "Dev Mehta",
    "Zara Sheikh", "Neil Kapoor", "Tara Krishnan", "Yash Agarwal", "Meera Nanda",
    "Krish Bhat", "Saanvi Rao", "Ayaan Qureshi", "Ira Deshpande", "Om Prakash",
]
PASSWORD = "Lare@1234"
COLLEGE_ID = "demo-college-01"
COHORTS = ["demo-cohort-a", "demo-cohort-b", "demo-cohort-c"]


def main():
    cfg = AuthConfig()
    db = Database(cfg.DATABASE_URL, echo=False, schema=cfg.DB_SCHEMA)
    db.create_all()

    emails = ["student{:02d}@lare.dev".format(i) for i in range(1, len(NAMES) + 1)]
    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        with db.session() as s:
            users = s.execute(select(User).where(User.email.in_(emails))).scalars().all()
            for u in users:
                for ur in s.execute(select(UserRole).where(UserRole.user_id == u.id)).scalars().all():
                    s.delete(ur)
                s.delete(u)
        print("Removed {} demo student accounts.".format(len(users)))
        return

    pw = hash_password(PASSWORD)
    roster = []
    with db.session() as s:
        role = s.execute(select(Role).where(Role.name == "student")).scalars().first()
        if role is None:
            role = Role(id=new_id(), name="student", description="Learner")
            s.add(role)
            s.flush()
        created = 0
        for i, name in enumerate(NAMES, 1):
            email = "student{:02d}@lare.dev".format(i)
            u = s.execute(select(User).where(User.email == email)).scalars().first()
            if u is None:
                u = User(id=new_id(), email=email, password_hash=pw, full_name=name,
                         status="active", email_verified=True, tenant_id="lare")
                s.add(u)
                s.flush()
                created += 1
            if not s.execute(select(UserRole).where(
                    UserRole.user_id == u.id, UserRole.role_id == role.id)).scalars().first():
                s.add(UserRole(id=new_id(), user_id=u.id, role_id=role.id, college_id=None))
                s.flush()
            roster.append({
                "user_id": u.id, "email": email, "name": name,
                "roll": "LARE24{:03d}".format(i),
                "year_no": ((i - 1) % 4) + 1,
                "college_id": COLLEGE_ID,
                "cohort_id": COHORTS[(i - 1) % len(COHORTS)],
                "cgpa": round(6.0 + (i % 40) / 10.0, 2),
                "idx": i,
            })
    os.makedirs("../../.run", exist_ok=True)
    with open("../../.run/demo_students.json", "w", encoding="utf-8") as f:
        json.dump(roster, f, indent=2)
    print("Seeded {} students ({} new). Roster -> backend/.run/demo_students.json".format(
        len(roster), created))
    print("Login: student01@lare.dev .. student{:02d}@lare.dev  /  {}".format(len(NAMES), PASSWORD))


if __name__ == "__main__":
    main()
