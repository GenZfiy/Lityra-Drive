"""Competency catalogue + evaluation-model domain logic."""
from __future__ import annotations

from sqlalchemy import select

from .models import Competency, EvaluationModel, ModelWeight


class CompetencyService:
    def catalogue(self, s):
        rows = s.scalars(select(Competency).order_by(Competency.name)).all()
        return [self._dump_comp(c) for c in rows]

    def add_competency(self, s, *, key, name, description):
        existing = s.scalar(select(Competency).where(Competency.key == key))
        if existing:
            existing.name = name
            existing.description = description
            s.flush()
            return self._dump_comp(existing)
        c = Competency(key=key, name=name, description=description)
        s.add(c)
        s.flush()
        return self._dump_comp(c)

    def set_model(self, s, *, drive_id, weights):
        prior = s.scalars(select(EvaluationModel).where(
            EvaluationModel.drive_id == drive_id, EvaluationModel.active.is_(True))).all()
        for m in prior:
            m.active = False
        model = EvaluationModel(drive_id=drive_id, active=True)
        s.add(model)
        s.flush()
        for w in weights:
            s.add(ModelWeight(
                model_id=model.id, competency_key=w["competency_key"], name=w["name"],
                weight=w["weight"], band_good=w["band_good"], band_warn=w["band_warn"]))
        s.flush()
        return self.active_model(s, drive_id)

    def active_model(self, s, drive_id):
        model = s.scalar(select(EvaluationModel).where(
            EvaluationModel.drive_id == drive_id, EvaluationModel.active.is_(True)
        ).order_by(EvaluationModel.created_at.desc()))
        if not model:
            return {"drive_id": drive_id, "model_id": None, "weights": []}
        ws = s.scalars(select(ModelWeight).where(ModelWeight.model_id == model.id)).all()
        total = sum(w.weight for w in ws) or 1.0
        return {
            "drive_id": drive_id, "model_id": model.id,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "weights": [{
                "competency_key": w.competency_key, "name": w.name, "weight": w.weight,
                "weight_pct": round(w.weight / total * 100, 1),
                "band_good": w.band_good, "band_warn": w.band_warn,
            } for w in ws],
        }

    @staticmethod
    def _dump_comp(c):
        return {"id": c.id, "key": c.key, "name": c.name, "description": c.description}
