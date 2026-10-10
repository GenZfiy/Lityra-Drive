"""Governed AI orchestration: render a named prompt, call Claude (or stub),
audit usage. This is the single controlled egress to the model for the whole
platform — callers pick a prompt_key + variables, never raw system prompts."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from lare_common.security import new_id

from .client import _Base as AIClient
from .models import AiCall
from .prompts import PROMPTS, render


class AIService:
    def __init__(self, client: AIClient):
        self.client = client

    def prompts(self) -> list[dict]:
        return [{"key": k, "system": v["system"][:120] + "..."} for k, v in PROMPTS.items()]

    def run(self, s: Session, *, prompt_key: str, variables: dict, actor_id: str,
            purpose: str = "general", want_json: bool = False,
            history: list[dict] | None = None, json_fallback: dict | None = None) -> dict:
        system, user = render(prompt_key, variables)
        messages = list(history or [])
        messages.append({"role": "user", "content": user})

        if want_json:
            data, res = self.client.complete_json(
                system=system, messages=messages, fallback=json_fallback or {})
            output = data
            text_preview = str(data)[:200]
        else:
            res = self.client.complete(system=system, messages=messages)
            output = res.text
            text_preview = res.text[:200]

        s.add(AiCall(
            id=new_id(), prompt_key=prompt_key, purpose=purpose, actor_id=actor_id,
            model=res.model, mode="stub" if res.stub else "live",
            input_tokens=res.input_tokens, output_tokens=res.output_tokens,
            latency_ms=res.latency_ms, status="ok", preview=text_preview))
        s.flush()
        return {"prompt_key": prompt_key, "mode": "stub" if res.stub else "live",
                "model": res.model, "latency_ms": res.latency_ms, "output": output,
                "usage": {"input_tokens": res.input_tokens,
                          "output_tokens": res.output_tokens}}

    def usage(self, s: Session, limit: int = 50) -> dict:
        rows = s.execute(
            select(AiCall).order_by(AiCall.created_at.desc()).limit(limit)
        ).scalars().all()
        total_in = sum(r.input_tokens for r in rows)
        total_out = sum(r.output_tokens for r in rows)
        return {"calls": len(rows), "input_tokens": total_in, "output_tokens": total_out,
                "recent": [{"prompt_key": r.prompt_key, "mode": r.mode,
                            "model": r.model, "latency_ms": r.latency_ms,
                            "created_at": r.created_at.isoformat()} for r in rows]}
