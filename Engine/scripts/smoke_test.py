#!/usr/bin/env python3
"""Smoke test — verifies connectivity with SearchAPI.io and DeepSeek.

Run from Engine/ directory:
  python scripts/smoke_test.py

Requires a .env file with real keys in Engine/.env
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def load_dotenv(dotenv_path: str) -> None:
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


def test_search_api() -> bool:
    from search_client import SearchClient

    api_key = os.environ.get("SEARCH_API_KEY", "")
    if not api_key or api_key == "__PLACEHOLDER__":
        print("[SMOKE] SKIP SearchAPI — SEARCH_API_KEY not set or is placeholder.")
        return None

    print("[SMOKE] Testing SearchAPI.io...")
    t0 = time.monotonic()
    try:
        client = SearchClient(api_key=api_key)
        results = client.search_web("USMCA joint review", num=3)
        elapsed = time.monotonic() - t0
        print(f"  OK — {len(results)} results in {elapsed:.1f}s")
        for r in results[:2]:
            print(f"    {r['title'][:90]}")
        return True
    except Exception as exc:
        print(f"  FAIL — {exc}")
        return False


def test_deepseek() -> bool:
    from deepseek_client import DeepSeekClient

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key or api_key == "__PLACEHOLDER__":
        print("[SMOKE] SKIP DeepSeek — DEEPSEEK_API_KEY not set or is placeholder.")
        return None

    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    print("[SMOKE] Testing DeepSeek API...")
    t0 = time.monotonic()
    try:
        client = DeepSeekClient(api_key=api_key, base_url=base_url)
        response = client.chat(
            messages=[{"role": "user", "content": "Responde solo con la palabra: OK"}],
            temperature=0.0,
            max_tokens=10,
        )
        elapsed = time.monotonic() - t0
        print(f"  OK — '{response}' in {elapsed:.1f}s")
        return True
    except Exception as exc:
        print(f"  FAIL — {exc}")
        return False


def main() -> None:
    here = Path(__file__).resolve().parent.parent
    load_dotenv(str(here / ".env"))

    print("TMEC Engine — Smoke Test\n")

    results = {
        "search": test_search_api(),
        "deepseek": test_deepseek(),
    }

    print()
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)

    if failed:
        print(f"RESULT: {passed} passed, {failed} failed, {skipped} skipped — check your keys.")
        sys.exit(1)
    elif skipped == len(results):
        print("RESULT: All skipped — set your API keys in .env first.")
        sys.exit(2)
    else:
        print(f"RESULT: {passed} passed, {skipped} skipped — engine is ready.")
        sys.exit(0)


if __name__ == "__main__":
    main()
