"""Enricher — reads items.jsonl and adds AI-analysis fields from the Engine pipeline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .analyzer import Analyzer
from .deepseek_client import DeepSeekClient
from .trust import get_trust
from .bias import get_source_bias, compute_bias
from .fallback import calculate_fallback_score

AI_FIELDS = [
    "impactScore", "impactReason", "aiSummary", "sentiment", "aiEntities",
    "stance", "tensionScore", "tensionOrigin", "tensionTarget", "tensionReason",
    "biasScore", "biasReason",
]


def _item_uid(title: str, url: str) -> str:
    raw = f"{url}|{title}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


def _load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    p = Path(path)
    if not p.exists():
        print(f"[enricher] {path} not found — nothing to enrich.")
        return items
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def _save_jsonl(path: str | Path, items: list[dict[str, Any]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(it, ensure_ascii=False) + "\n" for it in items]
    p.write_text("".join(lines), encoding="utf-8")
    print(f"[enricher] Wrote {len(items)} items to {p}")


def _merge_items(
    existing: list[dict[str, Any]], new_items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    seen = {_item_uid(it["title"], it["url"]) for it in existing}
    added = 0
    for item in new_items:
        uid = _item_uid(item["title"], item["url"])
        if uid not in seen:
            seen.add(uid)
            existing.append(item)
            added += 1
    if added:
        print(f"[enricher] Merged {added} new items (total: {len(existing)}).")
    return existing


class Enricher:
    def __init__(
        self,
        analyzer: Analyzer | None = None,
        config_path: str | None = None,
    ):
        if analyzer is None:
            deepseek = DeepSeekClient()
            analyzer = Analyzer(deepseek=deepseek, config_path=config_path)
        self.analyzer = analyzer

    def enrich_items(
        self,
        source_path: str | Path,
        output_path: str | Path | None = None,
        skip_existing: bool = True,
        config: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        items = _load_jsonl(source_path)
        if not items:
            return []

        if skip_existing and output_path:
            previously_enriched = _load_jsonl(output_path)
            by_uid = {
                _item_uid(it["title"], it["url"]): it for it in previously_enriched
            }
            carried = 0
            for it in items:
                prev = by_uid.get(_item_uid(it["title"], it["url"]))
                if prev:
                    for field in AI_FIELDS:
                        if field in prev:
                            it[field] = prev[field]
                    carried += 1
            if carried:
                print(f"[enricher] Carried forward AI fields for {carried} previously-enriched items.")

        items_to_enrich = items
        if skip_existing:
            items_to_enrich = [it for it in items if "impactScore" not in it
                               or it.get("impactScore", 0) == 0]
            already = len(items) - len(items_to_enrich)
            if already:
                print(f"[enricher] {already} items already enriched — skipping.")

        if not items_to_enrich:
            print("[enricher] All items already enriched.")
            for it in items:
                it["trustScore"] = get_trust(it.get("url", ""), config)
            return items

        print(f"[enricher] Analyzing {len(items_to_enrich)} items with DeepSeek...")
        self.analyzer.analyze_batch(items_to_enrich)

        for it in items:
            it["trustScore"] = get_trust(it.get("url", ""), config)
            sb = get_source_bias(it.get("url", ""), config)
            cb = it.get("biasScore")
            it["biasScore"] = compute_bias(sb, cb if cb else None)
            if not it.get("impactScore") or it.get("impactScore", 0) == 0:
                fallback_score, fallback_reason = calculate_fallback_score(it, config)
                it["impactScore"] = fallback_score
                it["impactReason"] = it.get("impactReason", "") or fallback_reason

        if output_path:
            _save_jsonl(output_path, items)

        return items

    def merge_new_items(
        self,
        source_path: str | Path,
        new_items: list[dict[str, Any]],
    ) -> None:
        existing = _load_jsonl(source_path)
        merged = _merge_items(existing, new_items)
        _save_jsonl(source_path, merged)
