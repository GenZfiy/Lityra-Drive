r"""Seed coding-practice demo data for the 30 students: per-student practice
submissions (varied scores) + a passed viva or two, so Coding Practice, verified
skills and the coding side of the Skill Map are populated. Run seed_practice.py
and auth/seed_demo.py first.

    cd backend/services/coding
    $env:DB_SCHEMA="coding"; $env:PYTHONPATH="."
    ..\..\.venv\Scripts\python.exe seed_demo.py
"""
from __future__ import annotations

import json
import os
import sys

os.environ.setdefault("DB_SCHEMA", "coding")

from dotenv import load_dotenv  # noqa: E402

load_dotenv("../../.env")

import app.models  # noqa: E402,F401
from app.config import CodingConfig  # noqa: E402
from app.models import CodingSession, CodingSubmission, CodingViva, Problem  # noqa: E402
from lare_common.db import Database  # noqa: E402
from lare_common.security import new_id  # noqa: E402
from sqlalchemy import select  # noqa: E402

ROSTER = json.load(open("../../.run/demo_students.json", encoding="utf-8"))


def main():
    cfg = CodingConfig()
    db = Database(cfg.DATABASE_URL, echo=False, schema=cfg.DB_SCHEMA)
    db.create_all()
    ids = [r["user_id"] for r in ROSTER]
    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        with db.session() as s:
            sessions = s.execute(select(CodingSession).where(
                CodingSession.candidate_id.in_(ids),
                CodingSession.kind == "practice")).scalars().all()
            sids = [cs.id for cs in sessions]
            for sub in s.execute(select(CodingSubmission).where(
                    CodingSubmission.coding_session_id.in_(sids))).scalars().all():
                s.delete(sub)
            for v in s.execute(select(CodingViva).where(CodingViva.candidate_id.in_(ids))).scalars().all():
                s.delete(v)
            for cs in sessions:
                s.delete(cs)
        print("Removed coding practice demo data for {} students.".format(len(ids)))
        return
    with db.session() as s:
        problem_ids = [p.id for p in s.execute(
            select(Problem).where(Problem.practice.is_(True))).scalars().all()]
    if not problem_ids:
        print("No practice problems - run seed_practice.py first. Skipping.")
        return

    made = fail = 0
    for r in ROSTER:
        uid, i = r["user_id"], r["idx"]
        try:
            with db.session() as s:
                if s.execute(select(CodingSession).where(
                        CodingSession.candidate_id == uid,
                        CodingSession.kind == "practice")).scalars().first():
                    continue
                n = 3 + (i % 3)  # 3-5 problems each
                for k in range(min(n, len(problem_ids))):
                    pid = problem_ids[(i + k) % len(problem_ids)]
                    cs = CodingSession(id=new_id(), problem_id=pid, candidate_id=uid,
                                       exam_session_id=None, kind="practice", language="python",
                                       status="submitted", draft_code="print('demo')")
                    s.add(cs)
                    s.flush()
                    total = 4
                    passed = min(total if (i + k) % 3 == 0 else (2 + ((i + k) % 3)), total)
                    s.add(CodingSubmission(id=new_id(), coding_session_id=cs.id,
                                           code="print('demo')", score=round(100.0 * passed / total, 1),
                                           cases_passed=passed, total_cases=total, detail=[]))
                    if passed == total and k == 0:
                        s.add(CodingViva(id=new_id(), coding_session_id=cs.id, problem_id=pid,
                                         candidate_id=uid, question="Explain your approach.",
                                         answer="I iterate once; O(n) time.", score=80.0,
                                         passed=True, verdict="Clear understanding.",
                                         ai_generated=False, status="graded"))
                    s.flush()
            made += 1
        except Exception as e:  # noqa: BLE001
            fail += 1
            print("  FAILED {}: {}".format(r["email"], e))
    print("Coding practice demo seeded: {} OK, {} failed.".format(made, fail))


if __name__ == "__main__":
    main()
