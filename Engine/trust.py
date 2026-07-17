"""Source trust scores — rates domains by credibility for TMEC intelligence."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def _load_trust_table(config: dict[str, Any] | None = None) -> dict[str, int]:
    if config is None:
        return DEFAULT_TRUST

    trust_cfg = config.get("scoring", {}).get("source_trust", {})
    if not trust_cfg:
        return DEFAULT_TRUST

    table: dict[str, int] = {}
    for _tier_name, tier in trust_cfg.items():
        score = tier.get("score", 50)
        for domain in tier.get("domains", []):
            cleaned = domain.strip().lower().removeprefix("www.")
            table[cleaned] = score
    return table or DEFAULT_TRUST


DEFAULT_TRUST: dict[str, int] = {
    "ustr.gov": 100, "economy.gob.mx": 100, "international.gc.ca": 100,
    "federalregister.gov": 100, "congress.gov": 100, "whitehouse.gov": 100,
    "state.gov": 100, "dof.gob.mx": 100, "pm.gc.ca": 100,
    "bloomberg.com": 90, "reuters.com": 90, "ft.com": 90,
    "wsj.com": 90, "nytimes.com": 90, "washingtonpost.com": 90,
    "economist.com": 90,
    "insidetrade.com": 85, "politico.com": 85, "law360.com": 85,
    "csis.org": 75, "brookings.edu": 75, "atlanticcouncil.org": 75,
    "americasquarterly.org": 75, "bakerinstitute.org": 75, "cfr.org": 75,
    "piie.com": 75, "wilsoncenter.org": 75, "as-coa.org": 75,
    "apnews.com": 65, "usatoday.com": 65, "thestar.com": 65,
    "eluniversal.com.mx": 65, "elfinanciero.com.mx": 65,
    "cbc.ca": 65, "theglobeandmail.com": 65, "aljazeera.com": 65,
    "bbc.com": 65, "newsweek.com": 65, "thehill.com": 65,
    "dallasnews.com": 65, "chron.com": 65,
    "nam.org": 60, "businessroundtable.org": 60, "steel.org": 60,
    "aisi.org": 60, "nppc.org": 60, "nmfp.org": 60,
    "farmprogress.com": 60, "brownfieldagnews.com": 60,
    "agweb.com": 60, "farms.com": 60, "rfdtv.com": 60,
    "yahoo.com": 35, "msn.com": 35, "google.com": 35,
    "news.google.com": 35, "substack.com": 35, "medium.com": 35,
    "opportimes.com": 35,
}


def get_trust(url_or_source: str, config: dict[str, Any] | None = None) -> int:
    """Return trust score 0-100 for a URL or source name. Default 50 for unknown."""
    trust_table = _load_trust_table(config)
    host = ""
    parsed = urlparse(url_or_source)
    if parsed.netloc:
        host = parsed.netloc.lower().removeprefix("www.")
    else:
        clean = url_or_source.lower().strip().removeprefix("www.")
        parsed2 = urlparse(f"https://{clean}")
        host = parsed2.netloc or clean

    host = host.rstrip(".")
    return trust_table.get(host, _match_partial(host, trust_table))


def _match_partial(host: str, table: dict[str, int]) -> int:
    for domain, score in table.items():
        if host.endswith("." + domain) or domain.endswith("." + host):
            return score
    return 50


def get_trust_tier(score: int) -> str:
    if score >= 90:
        return "official"
    if score >= 80:
        return "elite"
    if score >= 70:
        return "trusted"
    if score >= 55:
        return "standard"
    return "low"
