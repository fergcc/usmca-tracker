"""Enricher — reads items.jsonl and adds AI-analysis fields from the Engine pipeline."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .analyzer import Analyzer
from .deepseek_client import DeepSeekClient
from .trust import get_trust
from .lean import get_source_lean, compute_lean
from .fallback import calculate_fallback_score

AI_FIELDS = [
    "impactScore", "impactReason", "aiSummary", "sentiment", "aiEntities",
    "stance", "tensionScore", "tensionOrigin", "tensionTarget", "tensionReason",
    "contentLeanScore", "leanScore", "leanReason",
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


_READONLY = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH  # 0o444
_OWNER_WRITABLE = _READONLY | stat.S_IWUSR  # 0o644


def _unlock_writable(path: str | Path) -> None:
    p = Path(path)
    if p.exists():
        os.chmod(p, _OWNER_WRITABLE)


def _lock_readonly(path: str | Path) -> None:
    p = Path(path)
    if p.exists():
        os.chmod(p, _READONLY)


def _save_enriched_output(output_path: str | Path, items: list[dict[str, Any]]) -> None:
    """The one place allowed to write the enriched dataset.

    The file (and its .bak) are left read-only (0o444) so that any other
    script or tool — from this repo or another AI editing it in parallel —
    gets a hard OS-level PermissionError if it tries to overwrite them
    directly, instead of silently wiping impactScore/trustScore/aiSummary/
    leanScore/etc. for everything already enriched.
    """
    backup_path = str(output_path) + ".bak"
    _unlock_writable(output_path)
    _save_jsonl(output_path, items)
    _lock_readonly(output_path)

    _unlock_writable(backup_path)
    _save_jsonl(backup_path, items)
    _lock_readonly(backup_path)


def _scored_fraction(items: list[dict[str, Any]]) -> float:
    if not items:
        return 0.0
    scored = sum(1 for it in items if it.get("impactScore"))
    return scored / len(items)


def _check_no_regression(output_path: str | Path, new_items: list[dict[str, Any]]) -> None:
    """Refuse to overwrite a fully-enriched file with one that has lost its AI fields.

    Guards against exactly what happened once before: a script that reloads raw
    items and writes them back out, silently wiping impactScore/trustScore/etc.
    for everything already enriched.
    """
    previous = _load_jsonl(output_path)
    if not previous:
        return
    old_fraction = _scored_fraction(previous)
    new_fraction = _scored_fraction(new_items)
    if old_fraction > 0.5 and new_fraction < old_fraction - 0.2:
        raise RuntimeError(
            f"[enricher] Refusing to overwrite {output_path}: previously "
            f"{old_fraction:.0%} of items had impactScore, new data only has "
            f"{new_fraction:.0%}. This looks like a regression (e.g. a script "
            f"reloading raw items and losing prior enrichment) rather than a "
            f"real update — aborting instead of silently zeroing out scores."
        )


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


def _source_metrics_available(item: dict[str, Any]) -> bool:
    """A Google redirect alone is not enough to rate the underlying outlet."""
    if item.get("publisher_url"):
        return True
    host = urlparse(item.get("url", "")).netloc.lower().removeprefix("www.")
    return host != "news.google.com"


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
            # Full analysis is only needed for new records. Older records that
            # lack contentLeanScore receive a much cheaper lean-only refresh
            # below, preserving their prior summaries and entity analysis.
            items_to_enrich = [
                it for it in items
                if "impactScore" not in it
                or it.get("impactScore", 0) == 0
            ]
            already = len(items) - len(items_to_enrich)
            if already:
                print(f"[enricher] {already} items already enriched — skipping.")

        if items_to_enrich:
            print(f"[enricher] Analyzing {len(items_to_enrich)} items with DeepSeek...")
            self.analyzer.analyze_batch(items_to_enrich)

        lean_refresh = [
            it for it in items
            if not isinstance(it.get("contentLeanScore"), (int, float))
        ]
        if lean_refresh:
            print(f"[enricher] Refreshing lean for {len(lean_refresh)} records...")
            self.analyzer.analyze_lean_batch(lean_refresh)
        elif not items_to_enrich:
            print("[enricher] All items already enriched.")

        for it in items:
            scoring_url = it.get("publisher_url") or it.get("url", "")
            metrics_available = _source_metrics_available(it)
            it["sourceMetricsAvailable"] = metrics_available
            if metrics_available:
                it["trustScore"] = get_trust(scoring_url, config)
                sl = get_source_lean(scoring_url, config)
                cl = it.get("contentLeanScore")
                if isinstance(cl, (int, float)):
                    it["leanScore"] = compute_lean(sl, cl)
                elif "leanScore" not in it:
                    # A failed analysis still receives a transparent,
                    # source-only fallback rather than an invented score.
                    it["leanScore"] = compute_lean(sl, None)
            if not it.get("impactScore") or it.get("impactScore", 0) == 0:
                fallback_score, fallback_reason = calculate_fallback_score(it, config)
                it["impactScore"] = fallback_score
                it["impactReason"] = it.get("impactReason", "") or fallback_reason

        if output_path:
            _check_no_regression(output_path, items)
            _save_enriched_output(output_path, items)

        return items

    def merge_new_items(
        self,
        source_path: str | Path,
        new_items: list[dict[str, Any]],
    ) -> None:
        existing = _load_jsonl(source_path)
        merged = _merge_items(existing, new_items)
        _save_jsonl(source_path, merged)
