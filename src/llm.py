"""Minimal OpenAI-compatible Chat Completions client (stdlib only) with token accounting.

Works with any OpenAI-compatible endpoint (Groq, OpenAI, OpenRouter, Gemini).
"""
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProviderError(RuntimeError):
    """Model/provider failure; recorded as status=error, never replaced by fake output."""


def load_api_key(names, env_file=ROOT / ".env"):
    from dotenv import dotenv_values

    values = {**dotenv_values(env_file), **os.environ}
    for name in names:
        if values.get(name):
            return values[name]
    raise ProviderError(f"Thiếu API key ({' / '.join(names)}) trong môi trường hoặc .env Lab 7")


class ChatClient:
    def __init__(self, model, *, base_url, api_key=None, api_key_env=("OPENAI_API_KEY",),
                 temperature=0.0, max_tokens=1024, extra=None, timeout=120, retries=6):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or load_api_key(api_key_env)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra = dict(extra or {})
        self.timeout = timeout
        self.retries = retries
        self.rate_limit_waits = []  # seconds slept on HTTP 429 (per-minute limits)

    def complete(self, messages, *, tools=None, tool_choice=None, json_mode=False):
        body = {"model": self.model, "messages": messages, "temperature": self.temperature,
                "max_tokens": self.max_tokens, **self.extra}
        if tools:
            body["tools"] = tools
            body["parallel_tool_calls"] = False
            if tool_choice:
                body["tool_choice"] = tool_choice
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        last = None
        for attempt in range(self.retries):
            request = urllib.request.Request(
                f"{self.base_url}/chat/completions", data=data, method="POST",
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json",
                         "User-Agent": "lab7-rag-agent/1.0"})
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:400]
                last = ProviderError(f"HTTP {exc.code}: {detail}")
                exhausted = any(s in detail for s in (
                    "insufficient_quota", "credit_balance", "tokens per day", "(TPD)",
                    "requests per day", "(RPD)", "credits are depleted"))
                # Groq returns 400 tool_use_failed when the sampled tool call is malformed.
                retryable = exc.code in (429, 500, 502, 503, 504) or (
                    exc.code == 400 and "tool_use_failed" in detail and attempt < 2)
                if exhausted or not retryable:
                    raise last from exc
                wait = self._retry_after(exc, detail, attempt)
                self.rate_limit_waits.append(wait)
                time.sleep(wait)
            except (urllib.error.URLError, TimeoutError) as exc:
                last = ProviderError(f"Lỗi kết nối provider: {exc}")
                time.sleep(2 ** attempt)
        raise last or ProviderError("Không gọi được provider (retries=0)")

    @staticmethod
    def _retry_after(exc, detail, attempt):
        header = exc.headers.get("retry-after") if exc.headers else None
        try:
            if header:
                return min(float(header) + 1, 90)
        except ValueError:
            pass
        match = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", detail)
        if match:
            return min(int(match.group(1) or 0) * 60 + float(match.group(2)) + 1, 90)
        return min(5 * 2 ** attempt, 90)


def usage_cost(usage, price):
    """USD from usage and price per 1M tokens: {'input','cached_input','output'}."""
    prompt = usage.get("prompt_tokens", 0)
    cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0
    completion = usage.get("completion_tokens", 0)
    return ((prompt - cached) * price["input"] + cached * price["cached_input"]
            + completion * price["output"]) / 1_000_000
