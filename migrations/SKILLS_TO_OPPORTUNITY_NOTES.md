# Skills-to-Opportunity — deploy notes

Two independent features (per your "both, but not connected" rule):
- **LARE Learn → Career Readiness** — a student's LMS skill twin matched to
  career-role targets ("you're X% ready for Backend Developer; learn SQL next").
  Uses only LMS data.
- **LARE Hire → Matched Opportunities** — a candidate's drive-exam skills matched
  to open drives ("TCS Drive 60% match · Arrays ✓ · SQL gap"). Uses only Hire data.

Nothing here has been pushed or deployed.

## 1. Database
```bash
cd backend/services/assessment && python manage.py init-db   # creates career_roles
cd backend/services/drive       && python manage.py init-db   # (no new table; safe)
psql "$DATABASE_URL" -f backend/migrations/skills_to_opportunity.sql   # drive_roles.skills column
```

## 2. Seed the Learn career catalog (real defaults)
```bash
cd backend/services/assessment
DB_SCHEMA=assessment PYTHONPATH=. <venv>/bin/python seed_careers.py
# 5 roles: Backend Dev, Frontend Dev, Data Analyst, SDE, QA
```
(Trainers can also add/remove career targets in **LMS → Trainer Console → Career
targets**. Recruiters add required skills per role in **Hire → Manage Drives →
Roles & Rounds → Required skills**, e.g. `Arrays, SQL:2, Python`.)

## 3. Frontend
```bash
cd frontend && npm run build
```

## 4. Restart services
```
lare-gateway      # new routes: /drive/v1/opportunities, /lms/v1/careers
drive-core        # role skills + /drive/v1/opportunities matching
lms-assessment    # career_roles + /lms/v1/careers + readiness
```

## How matching works
For each opportunity/role, match % = weighted average of the candidate's mastery
on each required skill (weight set per skill). A skill counts as "have it" at
≥55% mastery; below that it's a gap / learn-next. Skill names are matched
case-insensitively against the twin's topics, categories and coding languages —
so name your required skills to match your assessment objectives and practice
skills (Arrays, Strings, SQL, DP, Recursion, Python, JavaScript, …).

## Demo flow
- **Learn:** student → **Career Readiness** → see roles ranked by readiness →
  expand a role → "learn next" links straight to Coding Practice / Skill Map.
- **Hire:** recruiter authors a drive with role skills and opens it → candidate →
  **Matched Opportunities** → drives ranked by match with matched/gap chips.
