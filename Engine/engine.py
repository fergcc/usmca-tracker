#!/usr/bin/env python3
"""TMEC Intelligence Engine — CLI orchestrator.

Usage:
  python engine.py search   Search for TMEC content via SearchAPI.io and add to items.jsonl.
  python engine.py enrich   Run AI analysis (DeepSeek) on items.jsonl → items_enriched.jsonl.
  python engine.py run      Full pipeline: search + enrich.
  python engine.py dry-run  Same as run but don't write any files.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import yaml

from .search_client import SearchClient
from .deepseek_client import DeepSeekClient
from .analyzer import Analyzer
from .enrich import Enricher, _load_jsonl, _save_jsonl, _merge_items

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "config.yaml"
DEFAULT_SOURCE = HERE.parent / "data" / "items.jsonl"
DEFAULT_ENRICHED = HERE.parent / "data" / "items_enriched.jsonl"


def _load_config(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_dotenv(dotenv_path: str | Path) -> None:
    p = Path(dotenv_path)
    if not p.exists():
        return
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = val


def cmd_search(args: argparse.Namespace) -> None:
    source_path = Path(args.source)
    config = _load_config(args.config)

    search_cfg = config.get("search_api", {})
    queries = search_cfg.get("queries", {})
    max_results = search_cfg.get("max_results_per_query", 10)

    print("[engine] === SEARCH PHASE ===")
    client = SearchClient(timeout=search_cfg.get("timeout_seconds", 25))
    results = client.search_all_queries(queries, results_per_query=max_results)

    if not results:
        print("[engine] No new results found.")
        return

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    new_items = []
    for r in results:
        new_items.append({
            "title": r["title"],
            "url": r["url"],
            "summary": r["snippet"],
            "source": r.get("source", ""),
            "origin": "search_api",
            "published": r.get("published", now_iso),
            "score": 0,
            "tags": [f"#{r.get('query_label', 'search')}"],
        })

    if args.dry_run:
        print(f"[engine] DRY RUN — would add {len(new_items)} items:")
        for it in new_items:
            print(f"  - {it['title'][:100]}")
        return

    _merge_items(_load_jsonl(source_path), new_items)
    print(f"[engine] Added {len(new_items)} items to {source_path}")


def cmd_enrich(args: argparse.Namespace) -> None:
    source_path = Path(args.source)
    output_path = Path(args.output) if args.output else DEFAULT_ENRICHED

    print("[engine] === ENRICH PHASE ===")
    enricher = Enricher(config_path=args.config)

    if args.dry_run:
        items = _load_jsonl(source_path)
        to_analyze = [it for it in items if "aiSummary" not in it]
        print(f"[engine] DRY RUN — would analyze {len(to_analyze)}/{len(items)} items.")
        return

    enricher.enrich_items(source_path, output_path)


def cmd_run(args: argparse.Namespace) -> None:
    print("[engine] === TMEC INTELLIGENCE ENGINE ===\n")
    if not hasattr(args, "dry_run"):
        args.dry_run = False
    cmd_search(args)
    print()
    cmd_enrich(args)
    print(f"\n[engine] Pipeline complete.")


def main() -> None:
    _load_dotenv(HERE / ".env")

    parser = argparse.ArgumentParser(
        description="TMEC Intelligence Engine — search, analyze, and enrich TMEC/USMCA data.",
    )
    sub = parser.add_subparsers(dest="command")

    sp_search = sub.add_parser("search", help="Search for TMEC content via SearchAPI.io")
    sp_search.add_argument("--source", default=str(DEFAULT_SOURCE), help="Path to items.jsonl")
    sp_search.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to config.yaml")
    sp_search.add_argument("--dry-run", action="store_true", help="Preview without writing")

    sp_enrich = sub.add_parser("enrich", help="Run DeepSeek AI analysis on items")
    sp_enrich.add_argument("--source", default=str(DEFAULT_SOURCE), help="Path to items.jsonl")
    sp_enrich.add_argument("--output", default=str(DEFAULT_ENRICHED), help="Output path for enriched JSONL")
    sp_enrich.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to config.yaml")
    sp_enrich.add_argument("--dry-run", action="store_true", help="Preview without writing")

    sp_run = sub.add_parser("run", help="Full pipeline: search + enrich")
    sp_run.add_argument("--source", default=str(DEFAULT_SOURCE), help="Path to items.jsonl")
    sp_run.add_argument("--output", default=str(DEFAULT_ENRICHED), help="Output path for enriched JSONL")
    sp_run.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to config.yaml")

    sp_dry = sub.add_parser("dry-run", help="Full pipeline preview — no files written")
    sp_dry.add_argument("--source", default=str(DEFAULT_SOURCE), help="Path to items.jsonl")
    sp_dry.add_argument("--output", default=str(DEFAULT_ENRICHED), help="Output path for enriched JSONL")
    sp_dry.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to config.yaml")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    if args.command == "search":
        cmd_search(args)
    elif args.command == "enrich":
        cmd_enrich(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "dry-run":
        args.dry_run = True
        cmd_run(args)


if __name__ == "__main__":
    main()
