# Phase 0 completion — deploy checklist

Everything below is for **your one final deploy** — nothing here has been pushed
or deployed. Run these steps on the server after you pull the code.

## What shipped
1. **Coding → Twin fusion** — a real LMS Coding Practice surface (live sandbox),
   per-learner coding skill profile, fused into the Skill Map (coding by
   language + verified counts).
2. **Persistent, auto-nudging coach** — the study plan is stored (`study_plans`),
   stable across logins, with per-day progress tracking and a scheduled nudger.
3. **Adversarial viva** — after solving a problem the AI asks the learner to
   explain their approach and grades it; passing marks the skill **Verified**
   (cheat-resistant proof of competence).

## 1. Database migration
```bash
# creates the two NEW tables (coding_vivas, study_plans)
cd backend/services/coding      && python manage.py init-db
cd backend/services/assessment  && python manage.py init-db

# adds the NEW columns on existing tables (init-db does not alter columns)
psql "$DATABASE_URL" -f backend/migrations/phase0_completion.sql
```

## 2. Seed the practice bank (real problems)
```bash
cd backend/services/coding
DB_SCHEMA=drive_coding PYTHONPATH=. <venv>/bin/python seed_practice.py
# -> 10 problems across Math/Strings/Arrays/Recursion/Bit Manipulation
```

## 3. Frontend
```bash
cd frontend && npm run build   # copy dist/ to the web root as usual
```

## 4. Restart services
```
lare-gateway        # new route: /lms/v1/practice -> drive-coding; SLOW_ROUTES
drive-coding        # practice endpoints, viva, skills aggregation
lare-assessment     # twin fusion, persistent coach, progress, nudge-due
```
(No shared-lib `pip install ./libs` needed for this round — `lare_common` was
not changed here. The earlier `events.py` coach.nudge change, if not yet
deployed, still needs `pip install ./libs` + a `lare-notification` restart.)

## 5. Schedule the auto-nudger (systemd timer or cron)
See the header of `backend/services/assessment/nudge_scheduler.py` for the
ready-to-paste `lare-coach-nudge.service` + `.timer` (daily at 09:00), or the
cron one-liner. It calls `POST /lms/v1/assessments/coach/nudge-due` for every
learner whose plan is due (not nudged in 3 days and not finished).

## Demo flow (after deploy)
1. Log in as a **student** → **Coding Practice** → solve a problem (Run, then
   Submit). Watch hidden tests pass.
2. On the solved card, click **Start viva** → answer the question → get
   **Verified ✓**.
3. Go to **My Skill Map** → coding shows up by language with a *verified* badge;
   overall mastery now blends written + coding.
4. Click **Get my plan** (or it auto-loads) → tick off plan days (persists).
   **Email me my plan** sends the nudge; the daily timer nudges automatically.

## Rollback
The migration is additive (new columns default-safe, new tables). To roll back
code, redeploy the previous build; the extra columns/tables are harmless if
unused.
