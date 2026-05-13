"""
Base agent with Groq LLM integration, retry logic, and token tracking.
"""
from __future__ import annotations
import json
import logging
import time
from typing import Any

from groq import Groq
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_groq_client: Groq | None = None


def get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=settings.groq_api_key)
    return _groq_client


class BaseAgent:
    """
    Base class for all arbitration agents.
    Provides: Groq chat, JSON mode, retry with exponential backoff, token tracking.
    """

    name: str = "base_agent"
    temperature: float = 0.2
    max_tokens: int = 4096
    max_retries: int = 2

    def _chat(
        self,
        messages: list[dict],
        json_mode: bool = True,
        tools: list[dict] | None = None,
        temperature: float | None = None,
    ) -> tuple[str, int]:
        """
        Call Groq API with retry.
        Returns (response_text, total_tokens_used).
        """
        client = get_groq_client()
        temp = temperature if temperature is not None else self.temperature
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                t0 = time.time()
                kwargs: dict[str, Any] = {
                    "model": settings.groq_model,
                    "messages": messages,
                    "temperature": temp,
                    "max_tokens": self.max_tokens,
                }
                if json_mode and not tools:
                    kwargs["response_format"] = {"type": "json_object"}
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"

                response = client.chat.completions.create(**kwargs)
                elapsed_ms = int((time.time() - t0) * 1000)
                tokens = response.usage.total_tokens if response.usage else 0

                logger.info("groq_call", extra={
                    "agent": self.name,
                    "tokens": tokens,
                    "duration_ms": elapsed_ms,
                    "attempt": attempt,
                })

                content = response.choices[0].message.content or ""
                return content, tokens

            except Exception as exc:
                last_error = exc
                wait = 2 ** attempt  # exponential backoff
                logger.warning("groq_retry", extra={
                    "agent": self.name,
                    "attempt": attempt,
                    "error": str(exc),
                    "wait_s": wait,
                })
                if attempt < self.max_retries:
                    time.sleep(wait)

        raise RuntimeError(f"Groq API failed after {self.max_retries + 1} attempts: {last_error}")

    def _parse_json(self, text: str, fallback: dict | None = None) -> dict:
        """Parse JSON response, with fallback on error."""
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            # Try to find JSON object in the text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except (json.JSONDecodeError, ValueError):
                    pass
            logger.warning("json_parse_failed", extra={"agent": self.name, "text_preview": text[:200]})
            return fallback or {}
