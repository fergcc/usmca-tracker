"""SearchAPI.io HTTP client — web and news search for TMEC content."""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "TMEC-Engine/1.0 (+scientika.mx intelligence engine)"
)


class SearchClient:
    """Thin wrapper around SearchAPI.io (https://www.searchapi.io/)."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None, timeout: int = 25):
        self.api_key = api_key or os.environ.get("SEARCH_API_KEY", "")
        if not self.api_key:
            raise RuntimeError(
                "SEARCH_API_KEY is not set. Export it or pass it to SearchClient(api_key=...)."
            )
        self.base_url = base_url or "https://www.searchapi.io/api/v1/search"
        self.timeout = timeout

    def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        params["api_key"] = self.api_key
        qs = urllib.parse.urlencode(params)
        url = f"{self.base_url}?{qs}"

        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            print(f"[search] HTTP error: {exc}")
            return {}

    def _parse_results(self, raw: dict[str, Any]) -> list[dict[str, str]]:
        organic = raw.get("organic_results") or raw.get("news_results") or []
        items: list[dict[str, str]] = []
        for r in organic:
            items.append(
                {
                    "title": (r.get("title") or "").strip(),
                    "url": (r.get("link") or "").strip(),
                    "snippet": (r.get("snippet") or r.get("description") or "").strip(),
                    "source": (r.get("source") or r.get("displayed_link") or "").strip(),
                    "published": (r.get("date") or "").strip(),
                }
            )
        return items

    def search_web(self, query: str, num: int = 10) -> list[dict[str, str]]:
        params: dict[str, Any] = {
            "engine": "google",
            "q": query,
            "num": str(num),
            "gl": "us",
            "hl": "en",
        }
        raw = self._get(params)
        return self._parse_results(raw)

    def search_news(self, query: str, num: int = 10) -> list[dict[str, str]]:
        params: dict[str, Any] = {
            "engine": "google_news",
            "q": query,
            "num": str(num),
            "gl": "us",
            "hl": "en",
        }
        raw = self._get(params)
        return self._parse_results(raw)

    def fetch_article_content(self, url: str, max_bytes: int = 200_000) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=min(self.timeout, 15)) as resp:
                content = resp.read(max_bytes)
                return content.decode("utf-8", errors="replace")
        except Exception as exc:
            print(f"[search] fetch error for {url}: {exc}")
            return ""

    def search_all_queries(
        self, queries: dict[str, dict[str, str]], results_per_query: int = 10
    ) -> list[dict[str, str]]:
        all_items: list[dict[str, str]] = []
        seen_urls: set[str] = set()

        for name, cfg in queries.items():
            label = cfg.get("label", name)
            q = cfg.get("q", "")
            if not q:
                continue
            print(f"[search] Query '{label}'...")
            items = self.search_web(q, num=results_per_query)
            for item in items:
                url = item["url"]
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    item["query_label"] = label
                    all_items.append(item)
            time.sleep(1.2)

        print(f"[search] Found {len(all_items)} unique results across {len(queries)} queries.")
        return all_items
