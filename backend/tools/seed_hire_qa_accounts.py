"""Create one isolated QA login per built-in role in the Hire product.

Run from the Lityra-hire project root after configuring its .env:
    python backend/tools/seed_hire_qa_accounts.py

Passwords are generated per account and saved to a timestamped file under
backend/.run (gitignored). Existing accounts are never reset or modified.
This seeds login/RBAC records only; organization-scoped roles need real scope
assignments before they can see organization data.
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND / "libs"))
sys.path.insert(0, str(BACKEND / "services" / "auth"))
load_dotenv(ROOT / ".env")

import app.models  # noqa: E402,F401
from app.config import AuthConfig  # noqa: E402
from app.models import Role, User, UserRole  # noqa: E402
from app.seed import ROLES, seed  # noqa: E402
from lare_common.db import Database  # noqa: E402
from lare_common.security import hash_password, new_id  # noqa: E402
from sqlalchemy import select  # noqa: E402


def main() -> int:
    cfg = AuthConfig()
    if os.getenv("APP_PRODUCT", "").lower() != "hire" or cfg.AUTH_ALLOWED_PRODUCT != "hire":
        raise SystemExit("Refusing to seed: .env must set APP_PRODUCT=hire and AUTH_ALLOWED_PRODUCT=hire")
    if not cfg.DATABASE_URL or cfg.DATABASE_URL.startswith("sqlite"):
        raise SystemExit("Set the Hire PostgreSQL DATABASE_URL in the project .env first")

    db = Database(cfg.DATABASE_URL, echo=False, schema=cfg.DB_SCHEMA)
    # Synchronize only this product's role/permission catalog. This deliberately
    # does not invoke the default admin seeder or alter existing accounts.
    seed(db, cfg, create_admin=False)

    credentials: list[tuple[str, str, str]] = []
    with db.session() as s:
        for role_name, description, _scope in ROLES:
            role = s.execute(
                select(Role).where(Role.name == role_name, Role.product == "hire")
            ).scalar_one()
            email = f"lityra-qa-hire-{role_name}@hire.example.com"
            existing = s.execute(
                select(User).where(User.email == email, User.product == "hire")
            ).scalar_one_or_none()
            if existing:
                raise SystemExit(
                    f"Account {email} already exists. No credentials were changed; "
                    "reset it through an authorized admin flow before rerunning."
                )
            password = secrets.token_urlsafe(24)
            user = User(
                id=new_id(), email=email, product="hire",
                password_hash=hash_password(password, rounds=cfg.BCRYPT_ROUNDS),
                full_name=f"Hire QA {role_name.replace('_', ' ').title()}",
                status="active", email_verified=True,
                tenant_id=cfg.DEFAULT_TENANT_ID,
            )
            s.add(user)
            s.flush()
            s.add(UserRole(
                id=new_id(), user_id=user.id, role_id=role.id,
                college_id=None, branch_id=None, cohort_id=None,
            ))
            credentials.append((role_name, email, password))

    output_dir = BACKEND / ".run"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output = output_dir / f"hire-qa-credentials-{stamp}.txt"
    lines = [
        "Lityra Hire QA credentials",
        "Accounts are active and product-scoped to Hire.",
        "Change each password after first sign-in; keep this file private.",
        "Organization-scoped roles need a real center/company assignment for scoped data access.",
        "",
    ]
    lines.extend(f"{role}\t{email}\t{password}" for role, email, password in credentials)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        output.chmod(0o600)
    except OSError:
        pass
    print(f"Created {len(credentials)} Hire QA accounts.")
    print(f"Credentials saved locally to: {output}")
    print("Do not commit or share that file; it contains plaintext passwords.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
