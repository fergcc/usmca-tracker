#!/usr/bin/env python3
"""TMEC Intelligence Engine v2.0 — CLI orchestrator.

Usage:
  python -m Engine.engine search      Search for TMEC content via SearchAPI.io and add to items.jsonl.
  python -m Engine.engine enrich      Run AI analysis (DeepSeek) on items.jsonl → items_enriched.jsonl.
  python -m Engine.engine briefing    Generate daily briefing markdown from enriched data.
  python -m Engine.engine run         Full pipeline: search + enrich + briefing.
  python -m Engine.engine dry-run     Same as run but don't write any files.
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
from .buzz import calculate_buzz, detect_early_warnings
from .briefer import generate_briefing

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "config.yaml"
DEFAULT_SOURCE = HERE.parent / "data" / "items.jsonl"
DEFAULT_ENRICHED = HERE.parent / "data" / "items_enriched.jsonl"
DEFAULT_BRIEFINGS = HERE.parent / "briefings"

ENGINE_HEADER = """
╔══════════════════════════════════════════╗
║   TMEC Intelligence Engine v2.0         ║
║   Scientika · Trade Intelligence        ║
╚══════════════════════════════════════════╝"""


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

    if getattr(args, "dry_run", False):
        print(f"[engine] DRY RUN — would add {len(new_items)} items:")
        for it in new_items:
            print(f"  - {it['title'][:100]}")
        return

    _merge_items(_load_jsonl(source_path), new_items)
    print(f"[engine] Added {len(new_items)} items to {source_path}")


def cmd_enrich(args: argparse.Namespace) -> None:
    source_path = Path(args.source)
    output_path = Path(args.output) if args.output else DEFAULT_ENRICHED
    config = _load_config(args.config)

    print("[engine] === ENRICH PHASE ===")
    enricher = Enricher(config_path=args.config)

    if getattr(args, "dry_run", False):
        items = _load_jsonl(source_path)
        to_analyze = [it for it in items if "impactScore" not in it]
        print(f"[engine] DRY RUN — would analyze {len(to_analyze)}/{len(items)} items.")
        return

    enricher.enrich_items(source_path, output_path, config=config)


def cmd_briefing(args: argparse.Namespace) -> None:
    enriched_path = Path(args.source) if args.source else DEFAULT_ENRICHED
    output_dir = DEFAULT_BRIEFINGS
    try:
        output_arg = Path(args.output)
        if output_arg != Path(DEFAULT_ENRICHED):
            output_dir = output_arg
    except Exception:
        pass
    config = _load_config(args.config)

    print("[engine] === BRIEFING ===")
    content = generate_briefing(enriched_path, output_dir, config)
    if content:
        print(content[:500] + ("..." if len(content) > 500 else ""))
    else:
        print("[engine] No data available for briefing.")


def cmd_buzz(args: argparse.Namespace) -> None:
    source_path = Path(args.source)
    config = _load_config(args.config)

    print("[engine] === BUZZ ANALYSIS ===")
    buzz = calculate_buzz(source_path, config)
    print("Sector buzz factors (1.0 = baseline):")
    for sector, factor in sorted(buzz.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(factor * 10) if factor > 1 else ""
        print(f"  {sector:20s} {factor:.2f}x {bar}")

    alerts = detect_early_warnings(source_path, config)
    if alerts:
        print("\n⚠️  Early Warnings:")
        for a in alerts:
            print(f"  {a['sector']}: {a['buzz']}× (threshold: {a['threshold']}×)")


def cmd_run(args: argparse.Namespace) -> None:
    print(ENGINE_HEADER)
    print()
    if not hasattr(args, "dry_run"):
        args.dry_run = False
    cmd_search(args)
    print()
    cmd_enrich(args)
    print()
    cmd_briefing(args)
    print(f"\n[engine] Pipeline complete.")


def main() -> None:
    _load_dotenv(HERE / ".env")

    parser = argparse.ArgumentParser(
        description="TMEC Intelligence Engine v2.0 — search, analyze, and enrich TMEC/USMCA data.",
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

    sp_briefing = sub.add_parser("briefing", help="Generate daily briefing markdown")
    sp_briefing.add_argument("--source", default=str(DEFAULT_ENRICHED), help="Path to enriched JSONL")
    sp_briefing.add_argument("--output", default=str(DEFAULT_BRIEFINGS), help="Briefing output directory")
    sp_briefing.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to config.yaml")

    sp_buzz = sub.add_parser("buzz", help="Show buzz factors by sector")
    sp_buzz.add_argument("--source", default=str(DEFAULT_SOURCE), help="Path to items.jsonl")
    sp_buzz.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to config.yaml")

    sp_run = sub.add_parser("run", help="Full pipeline: search + enrich + briefing")
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

    commands = {
        "search": cmd_search, "enrich": cmd_enrich,
        "briefing": cmd_briefing, "buzz": cmd_buzz,
        "run": cmd_run, "dry-run": lambda a: (setattr(a, "dry_run", True), cmd_run(a)),
    }
    fn = commands.get(args.command)
    if fn:
        fn(args)


if __name__ == "__main__":
    main()
