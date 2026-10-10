"""Provider-agnostic AI client: Anthropic (Claude), Google (Gemini), or STUB.

All providers implement the same `complete()` / `complete_json()` interface and
return an ``AIResult``, so the rest of the platform (tutor, resume parse/rank,
subjective hints) is provider-independent. Any failure (missing key/SDK, bad
model, network) degrades to deterministic stub text — the platform never breaks.
"""
from __future__ import annotations

import json
import logging
import time

log = logging.getLogger("lare-ai")


class AIResult:
    def __init__(self, text: str, *, stub: bool, input_tokens: int = 0,
                 output_tokens: int = 0, model: str = "", latency_ms: int = 0):
        self.text = text
        self.stub = stub
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.model = model
        self.latency_ms = latency_ms


def _last_user(messages: list[dict]) -> str:
    v = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
    if isinstance(v, list):
        v = " ".join(b.get("text", "") for b in v if isinstance(b, dict))
    return str(v)


class _Base:
    def complete(self, *, system: str, messages: list[dict], max_tokens=None) -> AIResult:
        raise NotImplementedError

    def _stub(self, messages, start, note="") -> AIResult:
        text = (
            "[AI stub — set a GEMINI_API_KEY or ANTHROPIC_API_KEY for live responses]\n\n"
            f"Here's a grounded response to: \"{_last_user(messages)[:160]}\". "
            "Focus on fundamentals, practise daily, and track your scorecard "
            "(communication, coding, aptitude, project)."
        )
        return AIResult(text, stub=True, model="stub",
                        latency_ms=int((time.time() - start) * 1000))

    def complete_json(self, *, system: str, messages: list[dict], fallback: dict):
        res = self.complete(system=system + "\nRespond with strict JSON only.",
                            messages=messages)
        if res.stub:
            return fallback, res
        try:
            start, end = res.text.index("{"), res.text.rindex("}") + 1
            return json.loads(res.text[start:end]), res
        except Exception:  # noqa: BLE001
            return fallback, res


class StubClient(_Base):
    mode = "stub"

    def complete(self, *, system, messages, max_tokens=None) -> AIResult:
        return self._stub(messages, time.time())


class AnthropicClient(_Base):
    mode = "anthropic"

    def __init__(self, api_key: str, model: str, max_tokens: int, thinking: str):
        import anthropic  # type: ignore
        self._c = anthropic.Anthropic(api_key=api_key)
        self.model, self.max_tokens, self.thinking = model, max_tokens, thinking

    def complete(self, *, system, messages, max_tokens=None) -> AIResult:
        start = time.time()
        try:
            kw = dict(model=self.model, max_tokens=max_tokens or self.max_tokens,
                      system=system, messages=messages)
            if self.thinking:
                kw["thinking"] = {"type": self.thinking}
            r = self._c.messages.create(**kw)
            text = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
            u = getattr(r, "usage", None)
            return AIResult(text, stub=False,
                            input_tokens=getattr(u, "input_tokens", 0) if u else 0,
                            output_tokens=getattr(u, "output_tokens", 0) if u else 0,
                            model=self.model, latency_ms=int((time.time() - start) * 1000))
        except Exception:  # noqa: BLE001
            log.exception("Anthropic call failed; using stub")
            return self._stub(messages, start)


class GeminiClient(_Base):
    mode = "gemini"

    def __init__(self, api_key: str, model: str, max_tokens: int):
        from google import genai  # type: ignore
        self._genai = genai
        self._c = genai.Client(api_key=api_key)
        self.model, self.max_tokens = model, max_tokens

    def complete(self, *, system, messages, max_tokens=None) -> AIResult:
        start = time.time()
        try:
            # Map our messages to Gemini contents (assistant -> model).
            contents = []
            for m in messages:
                role = "model" if m.get("role") == "assistant" else "user"
                text = m["content"] if isinstance(m["content"], str) else _last_user([m])
                contents.append({"role": role, "parts": [{"text": text}]})
            resp = self._c.models.generate_content(
                model=self.model, contents=contents,
                config={"system_instruction": system,
                        "max_output_tokens": max_tokens or self.max_tokens})
            text = getattr(resp, "text", "") or ""
            um = getattr(resp, "usage_metadata", None)
            return AIResult(text, stub=False,
                            input_tokens=getattr(um, "prompt_token_count", 0) if um else 0,
                            output_tokens=getattr(um, "candidates_token_count", 0) if um else 0,
                            model=self.model, latency_ms=int((time.time() - start) * 1000))
        except Exception:  # noqa: BLE001
            log.exception("Gemini call failed; using stub")
            return self._stub(messages, start)


def build_client(cfg) -> _Base:
    provider = cfg.AI_PROVIDER
    if provider == "auto":
        if cfg.GEMINI_API_KEY:
            provider = "gemini"
        elif cfg.ANTHROPIC_API_KEY:
            provider = "anthropic"
        else:
            provider = "stub"
    try:
        if provider == "gemini" and cfg.GEMINI_API_KEY:
            return GeminiClient(cfg.GEMINI_API_KEY, cfg.GEMINI_MODEL, cfg.AI_MAX_TOKENS)
        if provider == "anthropic" and cfg.ANTHROPIC_API_KEY:
            return AnthropicClient(cfg.ANTHROPIC_API_KEY, cfg.AI_MODEL,
                                   cfg.AI_MAX_TOKENS, cfg.AI_THINKING)
    except Exception:  # noqa: BLE001 — SDK/init failure -> stub
        log.exception("AI provider init failed (%s); using stub", provider)
    return StubClient()
