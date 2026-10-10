"""Analytics logic: fact ingestion + read-side KPIs, skill scorecard rollups,
college readiness index, and the 'best college' ranking."""
from __future__ import annotations

import csv
import io

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lare_common.security import new_id

from .models import Fact

# College readiness index — weighted composite (weights sum to 1.0). Metrics
# missing for a college are skipped and the remaining weights renormalized.
READINESS_WEIGHTS = {
    "attendance": 0.15,
    "avg_score": 0.30,
    "placement": 0.25,
    "certification": 0.15,
    "engagement": 0.15,
}
SCORECARD_DIMS = ("communication", "coding", "aptitude", "project")


class AnalyticsService:
    def ingest(self, s: Session, facts) -> dict:
        for f in facts:
            s.add(Fact(id=new_id(), kind=f.kind, metric=f.metric, value=f.value,
                       college_id=f.college_id, cohort_id=f.cohort_id,
                       learner_id=f.learner_id, drive_id=f.drive_id))
        s.flush()
        return {"ingested": len(facts)}

    def _college_metric_avgs(self, s: Session, college_id: str) -> dict[str, float]:
        rows = s.execute(
            select(Fact.metric, func.avg(Fact.value))
            .where(Fact.college_id == college_id)
            .group_by(Fact.metric)
        ).all()
        return {m: round(float(v), 1) for m, v in rows}

    def readiness(self, s: Session, college_id: str) -> dict:
        avgs = self._college_metric_avgs(s, college_id)
        present = {m: w for m, w in READINESS_WEIGHTS.items() if m in avgs}
        total_w = sum(present.values())
        if total_w == 0:
            index = 0.0
        else:
            index = round(sum(avgs[m] * (w / total_w) for m, w in present.items()), 1)
        return {"college_id": college_id, "readiness_index": index,
                "metrics": {m: avgs.get(m) for m in READINESS_WEIGHTS},
                "components": {m: avgs[m] for m in present}}

    def ranking(self, s: Session) -> list[dict]:
        college_ids = [
            c for (c,) in s.execute(
                select(Fact.college_id).where(Fact.college_id.is_not(None)).distinct()
            ).all()
        ]
        results = [self.readiness(s, cid) for cid in college_ids]
        results.sort(key=lambda r: -r["readiness_index"])
        return [{"rank": i + 1, "college_id": r["college_id"],
                 "readiness_index": r["readiness_index"]}
                for i, r in enumerate(results)]

    def scorecard(self, s: Session, learner_id: str) -> dict:
        rows = s.execute(
            select(Fact.metric, func.avg(Fact.value))
            .where(Fact.learner_id == learner_id, Fact.metric.in_(SCORECARD_DIMS))
            .group_by(Fact.metric)
        ).all()
        card = {m: round(float(v), 1) for m, v in rows}
        return {"learner_id": learner_id,
                "scorecard": {d: card.get(d, 0.0) for d in SCORECARD_DIMS}}

    def drive_analytics(self, s: Session, drive_id: str) -> dict:
        rows = s.execute(
            select(Fact.metric, func.count(Fact.id), func.avg(Fact.value), func.sum(Fact.value))
            .where(Fact.drive_id == drive_id)
            .group_by(Fact.metric)
        ).all()
        metrics = {m: {"count": int(cnt), "avg": round(float(avg), 1), "sum": round(float(tot), 1)}
                   for m, cnt, avg, tot in rows}
        return {"drive_id": drive_id, "metrics": metrics}

    def dashboard(self, s: Session, role: str) -> dict:
        colleges = s.execute(
            select(func.count(func.distinct(Fact.college_id)))
        ).scalar_one()
        learners = s.execute(
            select(func.count(func.distinct(Fact.learner_id)))
        ).scalar_one()
        drives = s.execute(
            select(func.count(func.distinct(Fact.drive_id)))
        ).scalar_one()
        return {"role": role, "colleges": int(colleges or 0),
                "learners": int(learners or 0), "drives": int(drives or 0),
                "top_colleges": self.ranking(s)[:5]}

    def export_ranking_csv(self, s: Session) -> str:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["rank", "college_id", "readiness_index"])
        for r in self.ranking(s):
            w.writerow([r["rank"], r["college_id"], r["readiness_index"]])
        return buf.getvalue()

    # ---------- customizable dashboard widgets (req #24) ----------
    DEFAULT_WIDGETS = [
        {"id": "readiness", "type": "college_readiness", "w": 6, "h": 2, "x": 0, "y": 0},
        {"id": "funnel", "type": "hiring_funnel", "w": 6, "h": 2, "x": 6, "y": 0},
        {"id": "top", "type": "top_colleges", "w": 12, "h": 3, "x": 0, "y": 2},
    ]

    def get_widgets(self, s: Session, user_id: str) -> dict:
        from .models import DashboardLayout
        row = s.get(DashboardLayout, user_id)
        return {"user_id": user_id, "widgets": row.widgets if row else list(self.DEFAULT_WIDGETS)}

    def set_widgets(self, s: Session, user_id: str, widgets: list) -> dict:
        from .models import DashboardLayout
        row = s.get(DashboardLayout, user_id)
        if row is None:
            row = DashboardLayout(user_id=user_id, widgets=widgets)
            s.add(row)
        else:
            row.widgets = widgets
        s.flush()
        return {"user_id": user_id, "widgets": row.widgets}

    # ---------- advanced analytics (req #25) ----------
    def hiring_funnel(self, s: Session, drive_id: str) -> dict:
        """Funnel counts derived from drive facts (applied→shortlisted→selected)."""
        rows = s.execute(
            select(Fact.metric, func.sum(Fact.value))
            .where(Fact.drive_id == drive_id).group_by(Fact.metric)
        ).all()
        m = {metric: float(v or 0) for metric, v in rows}
        applied = m.get("applied", m.get("exam_submitted", 0))
        return {"drive_id": drive_id, "stages": {
            "applied": applied, "assessed": m.get("exam_submitted", 0),
            "shortlisted": m.get("shortlisted", 0), "selected": m.get("placement", 0)}}

    def recruiter_performance(self, s: Session) -> list[dict]:
        rows = s.execute(
            select(Fact.learner_id, func.count(Fact.id), func.avg(Fact.value))
            .where(Fact.kind == "recruiter").group_by(Fact.learner_id)
        ).all()
        return [{"recruiter_id": rid, "actions": int(c), "avg": round(float(a or 0), 1)}
                for rid, c, a in rows]

    def report_rows(self, s: Session, kind: str, ref: str | None):
        """(title, headers, rows) for a report kind → exportable in any format."""
        if kind == "drive" and ref:
            da = self.drive_analytics(s, ref)
            headers = ["Metric", "Count", "Average", "Sum"]
            rows = [[m, v["count"], v["avg"], v["sum"]] for m, v in da["metrics"].items()]
            return f"Drive Analytics — {ref}", headers, rows
        if kind == "funnel" and ref:
            f = self.hiring_funnel(s, ref)
            return (f"Hiring Funnel — {ref}", ["Stage", "Count"],
                    [[k, v] for k, v in f["stages"].items()])
        # default: college ranking ("best college")
        headers = ["Rank", "College", "Readiness Index"]
        rows = [[r["rank"], r["college_id"], r["readiness_index"]] for r in self.ranking(s)]
        return "College Readiness Ranking", headers, rows

    def export_report(self, s: Session, kind: str, ref: str | None, fmt: str):
        title, headers, rows = self.report_rows(s, kind, ref)
        if fmt == "excel":
            from lare_common.exports import to_xlsx
            return (to_xlsx(headers, rows, sheet=kind[:20]),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    f"{kind}-report.xlsx")
        if fmt == "pdf":
            from lare_common.exports import to_pdf
            lines = ["  ".join(str(c) for c in row) for row in rows] or ["No data."]
            return to_pdf(title, [" | ".join(headers)] + lines), "application/pdf", f"{kind}-report.pdf"
        buf = io.StringIO(); w = csv.writer(buf); w.writerow(headers)
        for row in rows:
            w.writerow(row)
        return buf.getvalue().encode("utf-8"), "text/csv", f"{kind}-report.csv"
