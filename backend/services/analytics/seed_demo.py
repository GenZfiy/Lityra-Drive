r"""Seed admin-side analytics facts so the Dashboard tiles, college rankings, and
per-learner scorecards populate. Run auth/seed_demo.py first.

    cd backend/services/analytics
    $env:DB_SCHEMA="analytics"; $env:PYTHONPATH="."
    ..\..\.venv\Scripts\python.exe seed_demo.py
"""
from __future__ import annotations

import json
import os
import sys

os.environ.setdefault("DB_SCHEMA", "analytics")

from dotenv import load_dotenv  # noqa: E402

load_dotenv("../../.env")

import app.models  # noqa: E402,F401
from app.config import AnalyticsConfig  # noqa: E402
from app.models import Fact  # noqa: E402
from lare_common.db import Database  # noqa: E402
from lare_common.security import new_id  # noqa: E402
from sqlalchemy import or_, select  # noqa: E402

ROSTER = json.load(open("../../.run/demo_students.json", encoding="utf-8"))
STUDENT_COLLEGE = "LARE Demo College"

# college_id (readable — the ranking shows it) -> readiness base (0-100)
COLLEGES = {
    "LARE Demo College": 82,
    "IIT Delhi": 91,
    "NIT Trichy": 78,
    "BITS Pilani": 85,
    "VIT Vellore": 71,
}
READINESS_METRICS = ["attendance", "avg_score", "placement", "certification", "engagement"]
SCORECARD_DIMS = ["communication", "coding", "aptitude", "project"]
DRIVES = {"drive-tcs-2026": (120, 40, 18), "drive-infosys-2026": (95, 30, 12)}


def val(base, seed, spread=14):
    return round(max(35.0, min(99.0, base - spread / 2 + (seed * 37 % spread))), 1)


def main():
    cfg = AnalyticsConfig()
    db = Database(cfg.DATABASE_URL, echo=False, schema=cfg.DB_SCHEMA)
    db.create_all()
    ids = [r["user_id"] for r in ROSTER]
    with db.session() as s:
        # idempotent (and `clean` mode): clear prior demo facts
        removed = 0
        for f in s.execute(select(Fact).where(or_(
                Fact.college_id.in_(list(COLLEGES.keys())),
                Fact.learner_id.in_(ids),
                Fact.drive_id.in_(list(DRIVES.keys()))))).scalars().all():
            s.delete(f)
            removed += 1
        s.flush()
        if len(sys.argv) > 1 and sys.argv[1] == "clean":
            print("Removed {} demo analytics facts.".format(removed))
            return

        # college readiness facts -> ranking + readiness index
        for ci, (college, base) in enumerate(COLLEGES.items()):
            for mi, metric in enumerate(READINESS_METRICS):
                s.add(Fact(id=new_id(), kind="college", college_id=college,
                           metric=metric, value=val(base, ci * 5 + mi)))
        s.flush()

        # per-learner scorecard dims
        for r in ROSTER:
            for di, dim in enumerate(SCORECARD_DIMS):
                s.add(Fact(id=new_id(), kind="learner", learner_id=r["user_id"],
                           college_id=STUDENT_COLLEGE, cohort_id=r["cohort_id"],
                           metric=dim, value=val(75, r["idx"] * 3 + di, spread=40)))
        s.flush()

        # drive funnel facts
        for drive, (applied, shortlisted, selected) in DRIVES.items():
            for metric, value in (("applied", applied), ("shortlisted", shortlisted),
                                  ("selected", selected)):
                s.add(Fact(id=new_id(), kind="drive", drive_id=drive,
                           metric=metric, value=float(value)))
        s.flush()

    print("Analytics facts seeded: {} colleges, {} learners, {} drives.".format(
        len(COLLEGES), len(ROSTER), len(DRIVES)))


if __name__ == "__main__":
    main()
