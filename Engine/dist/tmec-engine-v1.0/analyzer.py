"""Analysis pipeline — orchestrates DeepSeek calls per article with retries and rate-limiting."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .deepseek_client import DeepSeekClient


def _load_prompts(config_path: str | None = None) -> dict[str, Any]:
    config_path = config_path or str(Path(__file__).resolve().parent / "config.yaml")
    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML is required. Install with: pip install PyYAML>=6.0.1")
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg


class Analyzer:
    """Runs the AI analysis pipeline on one or more articles.

    Each article gets:
      - aiSummary: 2-3 sentence summary in Spanish
      - sentiment: 'positive', 'negative', or 'neutral'
      - impactScore: 1-10 integer
      - impactReason: short justification string
      - aiEntities: list of "@name" / "#sector" tags
    """

    def __init__(
        self,
        deepseek: DeepSeekClient | None = None,
        config_path: str | None = None,
    ):
        cfg = _load_prompts(config_path)
        ds_cfg = cfg.get("deepseek", {})
        limits = cfg.get("limits", {})

        if deepseek is None:
            deepseek = DeepSeekClient(
                model=ds_cfg.get("model", "deepseek-chat"),
            )
        self.deepseek = deepseek
        self.prompts = ds_cfg.get("prompts", {})
        self.max_retries = limits.get("max_retries", 3)
        self.retry_delay = limits.get("retry_delay_seconds", 5)
        self.max_concurrent = limits.get("max_concurrent_deepseek", 3)
        self.max_tokens_for_analysis = limits.get("max_tokens_for_analysis", 4000)

    def _truncate(self, text: str) -> str:
        return text[: self.max_tokens_for_analysis]

    def analyze_article(self, article: dict[str, str]) -> dict[str, Any]:
        text = self._truncate(article.get("summary", "") or article.get("title", ""))
        if not text.strip():
            return {}

        result: dict[str, Any] = {}

        tasks: list[tuple[str, str, callable]] = [
            ("summary", "summarize", self._run_summarize),
            ("sentiment", "sentiment", self._run_sentiment),
            ("entities", "entities", self._run_entities),
            ("impact", "impact", self._run_impact),
        ]

        for _key, prompt_key, fn in tasks:
            prompt_cfg = self.prompts.get(prompt_key, {})
            if not prompt_cfg:
                continue
            try:
                fn_result = fn(text, prompt_cfg)
                if isinstance(fn_result, dict):
                    result.update(fn_result)
                elif fn_result is not None:
                    result[prompt_key] = fn_result
            except Exception as exc:
                print(f"  [analyzer] {prompt_key} failed: {exc}")

        return result

    def _run_summarize(self, text: str, prompt_cfg: dict[str, str]) -> dict[str, str]:
        for attempt in range(self.max_retries):
            try:
                summary = self.deepseek.summarize(
                    text,
                    system_prompt=prompt_cfg.get("system", ""),
                    user_prompt=prompt_cfg.get("user", ""),
                )
                return {"aiSummary": summary}
            except Exception:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
        return {"aiSummary": ""}

    def _run_sentiment(self, text: str, prompt_cfg: dict[str, str]) -> dict[str, str]:
        for attempt in range(self.max_retries):
            try:
                sentiment = self.deepseek.analyze_sentiment(
                    text,
                    system_prompt=prompt_cfg.get("system", ""),
                    user_prompt=prompt_cfg.get("user", ""),
                )
                return {"sentiment": sentiment}
            except Exception:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
        return {"sentiment": "neutral"}

    def _run_entities(self, text: str, prompt_cfg: dict[str, str]) -> dict[str, list[str]]:
        for attempt in range(self.max_retries):
            try:
                entities = self.deepseek.extract_entities(
                    text,
                    system_prompt=prompt_cfg.get("system", ""),
                    user_prompt=prompt_cfg.get("user", ""),
                )
                return {"aiEntities": entities}
            except Exception:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
        return {"aiEntities": []}

    def _run_impact(self, text: str, prompt_cfg: dict[str, str]) -> dict[str, Any]:
        for attempt in range(self.max_retries):
            try:
                score, reason = self.deepseek.assess_impact(
                    text,
                    system_prompt=prompt_cfg.get("system", ""),
                    user_prompt=prompt_cfg.get("user", ""),
                )
                return {"impactScore": score, "impactReason": reason}
            except Exception:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
        return {"impactScore": 1, "impactReason": ""}

    def analyze_batch(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        total = len(articles)
        for i, article in enumerate(articles, 1):
            print(f"  [analyzer] Article {i}/{total}: {article.get('title', '?')[:80]}...")
            ai_data = self.analyze_article(article)
            article.update(ai_data)
            enriched.append(article)
            time.sleep(0.6)
        return enriched
