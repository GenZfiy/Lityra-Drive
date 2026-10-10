"""Seed the Lityra Learn coding-practice bank with real, language-agnostic
problems (stdin -> stdout, so any of the sandbox languages works). Every
problem is flagged practice=True so it appears only in the LMS practice bank,
never in Drive exams.

Run from the coding service directory:

    cd backend/services/coding
    DB_SCHEMA=drive_coding PYTHONPATH=. \
      backend/venv/bin/python seed_practice.py

Idempotent: re-running updates the same problems (matched by title). Remove the
seeded bank with:  ... seed_practice.py clean
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("DB_SCHEMA", "drive_coding")

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

import app.models  # noqa: E402,F401  (register models on Base.metadata)
from app.config import CodingConfig  # noqa: E402
from app.models import Problem  # noqa: E402
from lare_common.db import Database  # noqa: E402
from lare_common.security import new_id  # noqa: E402
from sqlalchemy import select  # noqa: E402

LANGS = ["python", "javascript", "cpp", "java", "c"]


def C(inp, out):
    return {"input": inp, "expected": out}


# (title, skill, difficulty, statement, samples, hidden)
BANK = [
    ("Sum of Two Numbers", "Math", "easy",
     "Read two space-separated integers a and b on one line. Print their sum.",
     [C("3 5", "8"), C("10 20", "30")],
     [C("0 0", "0"), C("-4 9", "5"), C("100 250", "350"), C("-7 -8", "-15")]),

    ("Factorial", "Math", "easy",
     "Read an integer n (0 <= n <= 12). Print n! (n factorial).",
     [C("5", "120"), C("0", "1")],
     [C("1", "1"), C("3", "6"), C("7", "5040"), C("10", "3628800")]),

    ("Reverse a String", "Strings", "easy",
     "Read a single line string. Print the string reversed.",
     [C("hello", "olleh"), C("LARE", "ERAL")],
     [C("a", "a"), C("racecar", "racecar"), C("abcdef", "fedcba"),
      C("12345", "54321")]),

    ("Count Vowels", "Strings", "easy",
     "Read a lowercase string. Print how many vowels (a, e, i, o, u) it has.",
     [C("hello", "2"), C("sky", "0")],
     [C("education", "5"), C("aeiou", "5"), C("rhythm", "0"),
      C("programming", "3")]),

    ("Palindrome Check", "Strings", "medium",
     "Read a single line string. Print YES if it is a palindrome, otherwise NO.",
     [C("racecar", "YES"), C("hello", "NO")],
     [C("a", "YES"), C("abba", "YES"), C("abcba", "YES"), C("abc", "NO")]),

    ("Sum of an Array", "Arrays", "easy",
     "First line: n. Second line: n space-separated integers. Print their sum.",
     [C("4\n1 2 3 4", "10"), C("3\n5 5 5", "15")],
     [C("1\n42", "42"), C("5\n1 1 1 1 1", "5"), C("3\n-1 -2 -3", "-6"),
      C("4\n10 20 30 40", "100")]),

    ("Maximum Element", "Arrays", "easy",
     "First line: n. Second line: n space-separated integers. Print the largest.",
     [C("4\n3 7 2 9", "9"), C("3\n5 1 4", "5")],
     [C("1\n8", "8"), C("5\n-3 -1 -7 -2 -9", "-1"), C("4\n2 2 2 2", "2"),
      C("6\n10 40 30 90 20 5", "90")]),

    ("Second Largest", "Arrays", "medium",
     "First line: n (n >= 2). Second line: n integers (distinct). Print the "
     "second largest value.",
     [C("4\n3 7 2 9", "7"), C("3\n10 5 8", "8")],
     [C("2\n1 2", "1"), C("5\n5 1 4 2 3", "4"), C("4\n100 50 75 20", "75"),
      C("5\n9 8 7 6 5", "8")]),

    ("Nth Fibonacci", "Recursion", "medium",
     "Read an integer n (0 <= n <= 30). Print the nth Fibonacci number, where "
     "F(0)=0, F(1)=1.",
     [C("6", "8"), C("0", "0")],
     [C("1", "1"), C("2", "1"), C("10", "55"), C("15", "610")]),

    ("Power of Two", "Bit Manipulation", "medium",
     "Read an integer n. Print YES if n is a power of two (1, 2, 4, 8, ...), "
     "otherwise NO.",
     [C("8", "YES"), C("6", "NO")],
     [C("1", "YES"), C("1024", "YES"), C("0", "NO"), C("12", "NO")]),
]

TAG = "[practice]"


def main():
    cfg = CodingConfig()
    db = Database(cfg.DATABASE_URL, echo=False, schema=cfg.DB_SCHEMA)
    db.create_all()

    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        with db.session() as s:
            rows = s.execute(select(Problem).where(Problem.practice.is_(True))).scalars().all()
            for p in rows:
                s.delete(p)
        print("Removed {} practice problems.".format(len(rows)))
        return

    created = updated = 0
    with db.session() as s:
        for title, skill, diff, statement, samples, hidden in BANK:
            p = s.execute(select(Problem).where(Problem.title == title)).scalars().first()
            if p is None:
                p = Problem(id=new_id(), title=title)
                s.add(p)
                created += 1
            else:
                updated += 1
            p.statement = statement
            p.skill = skill
            p.difficulty = diff
            p.practice = True
            p.languages = LANGS
            p.time_limit_sec = 5
            p.max_score = 100.0
            p.sample_cases = samples
            p.hidden_cases = hidden
        s.flush()

    print("Practice bank seeded: {} created, {} updated ({} problems).".format(
        created, updated, len(BANK)))
    print("Skills:", ", ".join(sorted({b[1] for b in BANK})))
    print("These appear in Lityra Learn -> Practice. Solve them to grow your Skill Map.")


if __name__ == "__main__":
    main()
