"""Provider-agnostic AI client shared by every service (LMS and Drive alike).

This lives in ``lare_common`` — not inside any one service — so a product can
generate content without importing another product's code. Providers implement
the same ``complete()`` / ``complete_json()`` interface and return an
``AIResult``.

Callers that merely *enrich* a page should degrade to the stub. Callers that
produce graded artefacts (exam questions) must check ``result.stub`` and refuse
to continue — inventing placeholder questions would be worse than an error.
"""
from __future__ import annotations

import json
import logging
import os
import time

log = logging.getLogger("lare-ai")


class AIResult:
    def __init__(self, text: str, *, stub: bool, input_tokens: int = 0,
                 output_tokens: int = 0, model: str = "", latency_ms: int = 0,
                 error: str = ""):
        self.text = text
        self.stub = stub
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.model = model
        self.latency_ms = latency_ms
        # Machine-readable reason a live call fell back to stub: "" (none, e.g.
        # no key), "rate_limited", or "provider_error". Lets callers explain why.
        self.error = error


def _retry_delay(exc: Exception) -> float:
    """Extract the server-suggested retry delay (seconds) from a 429 error, if
    any. Returns 0 when absent or unparseable."""
    import re
    m = re.search(r"retry in ([0-9.]+)s|'retryDelay': '([0-9.]+)s'", str(exc))
    if not m:
        return 0.0
    try:
        return float(m.group(1) or m.group(2))
    except (TypeError, ValueError):
        return 0.0


def _last_user(messages: list[dict]) -> str:
    v = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
    if isinstance(v, list):
        v = " ".join(b.get("text", "") for b in v if isinstance(b, dict))
    return str(v)


class _Base:
    mode = "base"

    def complete(self, *, system: str, messages: list[dict], max_tokens=None,
                 response_json: bool = False) -> AIResult:
        raise NotImplementedError

    def _stub(self, messages, start, note="") -> AIResult:
        text = (
            "[AI stub — set a GEMINI_API_KEY or ANTHROPIC_API_KEY for live responses]\n\n"
            f"Here's a grounded response to: \"{_last_user(messages)[:160]}\". "
            "Focus on fundamentals, practise daily, and track your scorecard "
            "(communication, coding, aptitude, project)."
        )
        return AIResult(text, stub=True, model="stub", error=note,
                        latency_ms=int((time.time() - start) * 1000))

    @staticmethod
    def _err_note(exc: Exception) -> str:
        """Classify a provider exception for the caller's error message."""
        s = str(exc).lower()
        if "429" in s or "resource_exhausted" in s or "quota" in s or "rate limit" in s:
            return "rate_limited"
        return "provider_error"

    def complete_json(self, *, system: str, messages: list[dict], fallback,
                      max_tokens=None):
        """Return (parsed, AIResult). Requests native JSON output where the
        provider supports it, and still tolerates ```json fences / prose as a
        fallback for providers that don't."""
        res = self.complete(system=system + "\nRespond with strict JSON only.",
                            messages=messages, max_tokens=max_tokens,
                            response_json=True)
        if res.stub:
            return fallback, res
        text = res.text.strip()
        if "```" in text:  # strip markdown fences
            parts = text.split("```")
            text = max(parts, key=len).removeprefix("json").strip()
        for opener, closer in (("{", "}"), ("[", "]")):
            try:
                start, end = text.index(opener), text.rindex(closer) + 1
                return json.loads(text[start:end]), res
            except Exception:  # noqa: BLE001 — try the other bracket shape
                continue
        log.warning("AI response was not parseable JSON (%d chars)", len(res.text))
        return fallback, res


class StubClient(_Base):
    mode = "stub"

    def complete(self, *, system, messages, max_tokens=None, response_json=False) -> AIResult:
        return self._stub(messages, time.time())


class AnthropicClient(_Base):
    mode = "anthropic"

    def __init__(self, api_key: str, model: str, max_tokens: int, thinking: str):
        import anthropic  # type: ignore
        self._c = anthropic.Anthropic(api_key=api_key)
        self.model, self.max_tokens, self.thinking = model, max_tokens, thinking

    def complete(self, *, system, messages, max_tokens=None, response_json=False) -> AIResult:
        start = time.time()
        try:
            kw = dict(model=self.model, max_tokens=max_tokens or self.max_tokens,
                      system=system, messages=messages)
            # Claude has no JSON mode here; the prompt already asks for strict
            # JSON and complete_json() tolerates fences. Thinking stays enabled.
            if self.thinking:
                kw["thinking"] = {"type": self.thinking}
            r = self._c.messages.create(**kw)
            text = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
            u = getattr(r, "usage", None)
            return AIResult(text, stub=False,
                            input_tokens=getattr(u, "input_tokens", 0) if u else 0,
                            output_tokens=getattr(u, "output_tokens", 0) if u else 0,
                            model=self.model, latency_ms=int((time.time() - start) * 1000))
        except Exception as exc:  # noqa: BLE001
            log.exception("Anthropic call failed; using stub")
            return self._stub(messages, start, self._err_note(exc))


class GeminiClient(_Base):
    mode = "gemini"

    def __init__(self, api_key: str, model: str, max_tokens: int):
        from google import genai  # type: ignore
        self._genai = genai
        self._c = genai.Client(api_key=api_key)
        self.model, self.max_tokens = model, max_tokens

    def complete(self, *, system, messages, max_tokens=None, response_json=False) -> AIResult:
        start = time.time()
        try:
            contents = []
            for m in messages:
                role = "model" if m.get("role") == "assistant" else "user"
                text = m["content"] if isinstance(m["content"], str) else _last_user([m])
                contents.append({"role": role, "parts": [{"text": text}]})
            cfg = {"system_instruction": system,
                   "max_output_tokens": max_tokens or self.max_tokens}
            if response_json:
                # Native JSON mode returns pure, complete JSON (no ``` fences).
                # Disable "thinking" so its tokens can't eat the output budget
                # and truncate the JSON — the failure mode behind the 503s.
                cfg["response_mime_type"] = "application/json"
                cfg["thinking_config"] = {"thinking_budget": 0}
            # One bounded retry for a per-MINUTE rate limit (recovers in seconds);
            # a per-DAY cap won't recover, so we don't wait long for it.
            for attempt in range(2):
                try:
                    resp = self._c.models.generate_content(
                        model=self.model, contents=contents, config=cfg)
                    break
                except Exception as exc:  # noqa: BLE001
                    delay = _retry_delay(exc)
                    if attempt == 0 and 0 < delay <= 20:
                        log.warning("Gemini rate-limited; retrying in %.0fs", delay)
                        time.sleep(delay)
                        continue
                    raise
            text = getattr(resp, "text", "") or ""
            um = getattr(resp, "usage_metadata", None)
            return AIResult(text, stub=False,
                            input_tokens=getattr(um, "prompt_token_count", 0) if um else 0,
                            output_tokens=getattr(um, "candidates_token_count", 0) if um else 0,
                            model=self.model, latency_ms=int((time.time() - start) * 1000))
        except Exception as exc:  # noqa: BLE001
            log.exception("Gemini call failed; using stub")
            return self._stub(messages, start, self._err_note(exc))


class MistralClient(_Base):
    """Mistral via its HTTP chat-completions API (no extra SDK dependency).

    Used by the Drive product for question generation. Supports native JSON
    output (`response_format: json_object`), which needs the word "json" in the
    prompt — our system instruction already asks for strict JSON."""
    mode = "mistral"
    URL = "https://api.mistral.ai/v1/chat/completions"

    def __init__(self, api_key: str, model: str, max_tokens: int):
        self.api_key, self.model, self.max_tokens = api_key, model, max_tokens

    def complete(self, *, system, messages, max_tokens=None, response_json=False) -> AIResult:
        import requests
        start = time.time()
        msgs = [{"role": "system", "content": system}]
        for m in messages:
            role = "assistant" if m.get("role") == "assistant" else "user"
            content = m["content"] if isinstance(m["content"], str) else _last_user([m])
            msgs.append({"role": role, "content": content})
        body = {"model": self.model, "messages": msgs,
                "max_tokens": max_tokens or self.max_tokens}
        if response_json:
            body["response_format"] = {"type": "json_object"}
        try:
            for attempt in range(2):
                r = requests.post(
                    self.URL, json=body, timeout=90,
                    headers={"Authorization": f"Bearer {self.api_key}",
                             "Content-Type": "application/json"})
                if r.status_code == 429 and attempt == 0:
                    delay = _retry_delay(Exception(r.text)) or 3.0
                    if delay <= 20:
                        log.warning("Mistral rate-limited; retrying in %.0fs", delay)
                        time.sleep(delay)
                        continue
                if r.status_code != 200:
                    raise RuntimeError(f"{r.status_code} {r.text[:300]}")
                break
            data = r.json()
            text = data["choices"][0]["message"]["content"] or ""
            u = data.get("usage") or {}
            return AIResult(text, stub=False,
                            input_tokens=u.get("prompt_tokens", 0),
                            output_tokens=u.get("completion_tokens", 0),
                            model=self.model, latency_ms=int((time.time() - start) * 1000))
        except Exception as exc:  # noqa: BLE001
            log.exception("Mistral call failed; using stub")
            return self._stub(messages, start, self._err_note(exc))


class _EnvCfg:
    """Config view over the environment, for services with no AI config class."""
    AI_PROVIDER = os.getenv("AI_PROVIDER", "auto")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    AI_MODEL = os.getenv("AI_MODEL", "claude-opus-4-8")
    AI_THINKING = os.getenv("AI_THINKING", "adaptive")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
    MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
    AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "1024"))


def build_client(cfg=None) -> _Base:
    """Build the configured provider. Falls back to the stub on any failure so a
    missing key or SDK never takes a service down.

    `AI_PROVIDER` forces a provider (e.g. Drive sets `mistral`); `auto` prefers
    Mistral, then Gemini, then Anthropic, based on which key is present."""
    cfg = cfg or _EnvCfg
    provider = getattr(cfg, "AI_PROVIDER", "auto")
    if provider == "auto":
        if getattr(cfg, "MISTRAL_API_KEY", ""):
            provider = "mistral"
        elif getattr(cfg, "GEMINI_API_KEY", ""):
            provider = "gemini"
        elif getattr(cfg, "ANTHROPIC_API_KEY", ""):
            provider = "anthropic"
        else:
            provider = "stub"
    try:
        if provider == "mistral" and getattr(cfg, "MISTRAL_API_KEY", ""):
            return MistralClient(cfg.MISTRAL_API_KEY, cfg.MISTRAL_MODEL, cfg.AI_MAX_TOKENS)
        if provider == "gemini" and cfg.GEMINI_API_KEY:
            return GeminiClient(cfg.GEMINI_API_KEY, cfg.GEMINI_MODEL, cfg.AI_MAX_TOKENS)
        if provider == "anthropic" and cfg.ANTHROPIC_API_KEY:
            return AnthropicClient(cfg.ANTHROPIC_API_KEY, cfg.AI_MODEL,
                                   cfg.AI_MAX_TOKENS, cfg.AI_THINKING)
    except Exception:  # noqa: BLE001 — SDK/init failure -> stub
        log.exception("AI provider init failed (%s); using stub", provider)
    return StubClient()


def build_client_from_env() -> _Base:
    return build_client(_EnvCfg)
