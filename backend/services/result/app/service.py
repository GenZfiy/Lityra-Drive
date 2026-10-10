"""Result & offer logic: compile outcomes, controlled publish, offer/PPO letters
with public verification, offer lifecycle, exports.

Letter PDF rendering + storage goes through the File Service in production; here
we mint the record + verifiable IDs and a CSV export payload."""
from __future__ import annotations

import csv
import io

from sqlalchemy import select
from sqlalchemy.orm import Session

from lare_common.errors import Conflict, NotFound
from lare_common.security import new_id, random_token

from .models import Offer, Result


class ResultService:
    def compile(self, s: Session, data) -> dict:
        # rank by final_score desc; outcome from cutoff + interview decision.
        ranked = sorted(data.rows, key=lambda r: -r.final_score)
        # Batch-load existing results in ONE query (was N+1 — a SELECT per candidate,
        # which times out over a remote/tunneled DB with hundreds of candidates).
        existing = {r.candidate_id: r for r in s.execute(
            select(Result).where(Result.drive_id == data.drive_id)
        ).scalars().all()}
        compiled = 0
        for i, row in enumerate(ranked):
            if row.interview_decision == "select":
                outcome = "selected"
            elif row.final_score >= data.cutoff:
                outcome = "shortlist"
            else:
                outcome = "fail"
            res = existing.get(row.candidate_id)
            if res is None:
                res = Result(id=new_id(), drive_id=data.drive_id, candidate_id=row.candidate_id)
                s.add(res)
                existing[row.candidate_id] = res
            if res.status == "published":
                continue  # don't mutate published results silently
            res.final_score = row.final_score
            res.rank = i + 1
            res.outcome = outcome
            compiled += 1
        s.flush()
        return {"drive_id": data.drive_id, "compiled": compiled, "total": len(ranked)}

    def results(self, s: Session, drive_id: str, published_only: bool = False) -> list[dict]:
        q = select(Result).where(Result.drive_id == drive_id).order_by(Result.rank)
        if published_only:
            q = q.where(Result.status == "published")
        return [self.result_out(r) for r in s.execute(q).scalars().all()]

    def publish(self, s: Session, drive_id: str) -> dict:
        from datetime import datetime, timezone
        rows = s.execute(select(Result).where(Result.drive_id == drive_id)).scalars().all()
        if not rows:
            raise NotFound("No compiled results to publish", code="nothing_to_publish")
        now = datetime.now(tz=timezone.utc)
        published = 0
        for r in rows:
            if r.status != "published":
                r.status = "published"
                r.published_at = now
                published += 1
        s.flush()
        return {"drive_id": drive_id, "published": published}

    def generate_offer(self, s: Session, data) -> dict:
        offer = Offer(id=new_id(), drive_id=data.drive_id, candidate_id=data.candidate_id,
                      role_id=data.role_id, type=data.type, company_name=data.company_name,
                      role_title=data.role_title, ctc=data.ctc, verify_id=random_token(12))
        # In production: render PDF via File Service and set letter_file_id.
        s.add(offer)
        s.flush()
        return self.offer_out(offer)

    def set_offer_status(self, s: Session, offer_id: str, status: str) -> dict:
        offer = s.get(Offer, offer_id)
        if not offer:
            raise NotFound("Offer not found", code="offer_not_found")
        if offer.status in ("accepted", "declined"):
            raise Conflict("Offer already finalized", code="offer_finalized")
        offer.status = status
        s.flush()
        return self.offer_out(offer)

    def verify_offer(self, s: Session, verify_id: str) -> dict:
        offer = s.execute(
            select(Offer).where(Offer.verify_id == verify_id)
        ).scalar_one_or_none()
        if not offer:
            raise NotFound("Offer not found", code="offer_not_found")
        return {"valid": True, "type": offer.type, "company_name": offer.company_name,
                "role_title": offer.role_title, "status": offer.status,
                "issued_at": offer.issued_at.isoformat()}

    def _result_rows(self, s: Session, drive_id: str):
        return s.execute(
            select(Result).where(Result.drive_id == drive_id).order_by(Result.rank)
        ).scalars().all()

    def export_csv(self, s: Session, drive_id: str) -> str:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["rank", "candidate_id", "final_score", "outcome", "status"])
        for r in self._result_rows(s, drive_id):
            w.writerow([r.rank, r.candidate_id, r.final_score, r.outcome, r.status])
        return buf.getvalue()

    def export(self, s: Session, drive_id: str, fmt: str) -> tuple[bytes, str, str]:
        """Return (bytes, mimetype, filename) for csv | excel | pdf."""
        rows = self._result_rows(s, drive_id)
        headers = ["Rank", "Candidate", "Score", "Outcome", "Status"]
        data = [[r.rank, r.candidate_id, r.final_score, r.outcome, r.status] for r in rows]
        if fmt == "excel":
            from lare_common.exports import to_xlsx
            return (to_xlsx(headers, data, sheet="Results"),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    f"results-{drive_id}.xlsx")
        if fmt == "pdf":
            from lare_common.exports import to_pdf
            lines = [f"{r.rank:>3}.  {r.candidate_id}   score {r.final_score}   {r.outcome}"
                     for r in rows] or ["No results."]
            return (to_pdf(f"Drive Results — {drive_id}", lines),
                    "application/pdf", f"results-{drive_id}.pdf")
        return (self.export_csv(s, drive_id).encode("utf-8"), "text/csv",
                f"results-{drive_id}.csv")

    def offer_letter_pdf(self, s: Session, offer_id: str) -> tuple[bytes, str]:
        """Render a downloadable offer/PPO letter PDF from a template."""
        offer = s.get(Offer, offer_id)
        if not offer:
            raise NotFound("Offer not found", code="offer_not_found")
        from lare_common.exports import to_pdf
        kind = "Pre-Placement Offer" if offer.type == "ppo" else "Offer of Employment"
        lines = [
            "", f"Ref: {offer.verify_id}",
            f"Date: {offer.issued_at.strftime('%d %b %Y')}",
            "", f"Dear Candidate ({offer.candidate_id}),", "",
            f"We are pleased to extend a {kind} for the position of",
            f"{offer.role_title} at {offer.company_name}.",
            f"Compensation (CTC): {offer.ctc}.",
            "", "This letter can be verified online at:",
            f"  /verify/offer/{offer.verify_id}",
            "", "Warm regards,", f"{offer.company_name} — Talent Acquisition",
        ]
        return to_pdf(f"{kind} — {offer.company_name}", lines), f"offer-{offer_id}.pdf"

    @staticmethod
    def result_out(r) -> dict:
        return {"candidate_id": r.candidate_id, "final_score": r.final_score,
                "rank": r.rank, "outcome": r.outcome, "status": r.status}

    @staticmethod
    def offer_out(o) -> dict:
        return {"id": o.id, "candidate_id": o.candidate_id, "type": o.type,
                "company_name": o.company_name, "role_title": o.role_title, "ctc": o.ctc,
                "status": o.status, "verify_id": o.verify_id,
                "verify_url": f"/verify/offer/{o.verify_id}"}
