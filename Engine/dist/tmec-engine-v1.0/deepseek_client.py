"""DeepSeek API client via OpenAI-compatible SDK — AI analysis for TMEC articles."""

from __future__ import annotations

import os
from typing import Any


class DeepSeekClient:
    """Thin wrapper around the DeepSeek chat-completions API (OpenAI-compatible).

    Reads DEEPSEEK_API_KEY and DEEPSEEK_BASE_URL from environment.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "deepseek-chat",
    ):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        if not self.api_key:
            raise RuntimeError(
                "DEEPSEEK_API_KEY is not set. Export it or pass it to DeepSeekClient(api_key=...)."
            )
        self.base_url = base_url or os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = model

    def _get_openai_client(self):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai package is required. Install with: pip install openai>=1.0.0"
            )
        return OpenAI(api_key=self.api_key, base_url=self.base_url)

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 600,
    ) -> str:
        client = self._get_openai_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        choice = response.choices[0]
        return (choice.message.content or "").strip()

    def summarize(self, text: str, system_prompt: str, user_prompt: str) -> str:
        user_msg = user_prompt.format(text=text[:4000])
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ]
        return self.chat(messages, temperature=0.3, max_tokens=300)

    def analyze_sentiment(self, text: str, system_prompt: str, user_prompt: str) -> str:
        user_msg = user_prompt.format(text=text[:4000])
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ]
        result = self.chat(messages, temperature=0.0, max_tokens=10)
        result = result.lower().strip().rstrip(".")
        if result not in ("positive", "negative", "neutral"):
            return "neutral"
        return result

    def extract_entities(self, text: str, system_prompt: str, user_prompt: str) -> list[str]:
        user_msg = user_prompt.format(text=text[:4000])
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ]
        result = self.chat(messages, temperature=0.1, max_tokens=200)
        if not result or result.strip().upper() == "NONE":
            return []
        entities: list[str] = []
        for line in result.splitlines():
            line = line.strip()
            if line.startswith("@") or line.startswith("#"):
                entities.append(line)
        return entities[:8]

    def assess_impact(self, text: str, system_prompt: str, user_prompt: str) -> tuple[int, str]:
        user_msg = user_prompt.format(text=text[:4000])
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ]
        result = self.chat(messages, temperature=0.2, max_tokens=200)
        parts = result.split("|", 1)
        try:
            score = max(1, min(10, int(parts[0].strip())))
        except (ValueError, IndexError):
            score = 1
        reason = parts[1].strip()[:200] if len(parts) > 1 else ""
        return score, reason
