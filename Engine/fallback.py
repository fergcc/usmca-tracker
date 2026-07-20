"""Fallback keyword-based scoring — safeguard when DeepSeek fails or is unavailable.

Uses the same 5 dimensions as the AI impact score so unscored items stay consistent.
"""

from __future__ import annotations

import re
import json
from pathlib import Path
from typing import Any


def _load_config() -> dict[str, Any]:
    config_path = Path(__file__).resolve().parent / "config.yaml"
    try:
        import yaml
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return {}


def _count_keywords(text: str, keywords: list[str]) -> int:
    t = text.lower()
    return sum(1 for kw in keywords if kw.lower() in t)


def score_relevance(title: str, summary: str) -> int:
    core = [r"usmca", r"t-mec", r"cusma", r"united states[- ]mexico[- ]canada"]
    text = f"{title} {summary}".lower()
    hits = sum(1 for kw in core if re.search(kw, text))
    if not hits:
        return 0
    if any(re.search(kw, title.lower()) for kw in core):
        return min(30, hits * 12)
    return max(10, hits * 8)


def score_urgency(title: str, summary: str) -> int:
    keywords = [
        r"deadline", r"expir", r"venci", r"before\s+\w+\s+\d+",
        r"round\s+[1-6]", r"próxim", r"next\s+round",
        r"imminent", r"imminente", r"ultimátum", r"ultimatum",
        r"july\s+\d+", r"sunset", r"clock", r"countdown",
    ]
    text = f"{title} {summary}".lower()
    hits = _count_keywords(text, keywords)
    return min(20, hits * 5)


def score_actors(title: str, summary: str, config: dict[str, Any] | None = None) -> int:
    cfg = config or _load_config()
    actors_cfg = cfg.get("scoring", {}).get("actors", {})
    text = f"{title} {summary}"

    total = 0
    tier_max = {1: 15, 2: 10, 3: 6, 4: 3}
    for tier_num in (1, 2, 3, 4):
        tier = actors_cfg.get(f"tier_{tier_num}", {})
        for name, _weight in tier.items():
            name_clean = name.replace("_", " ")
            if re.search(re.escape(name_clean), text, re.IGNORECASE):
                total += tier_max.get(tier_num, 3)
    return min(15, total)


def score_sectoral(title: str, summary: str, config: dict[str, Any] | None = None) -> int:
    cfg = config or _load_config()
    scoring = cfg.get("scoring", {})
    current_round = scoring.get("current_round", 3)
    weights = scoring.get("round_weights", {}).get(current_round, {})

    text = f"{title} {summary}".lower()
    sector_keywords = {
        "automotive": ["auto", "automotriz", "automaker", "toyota", "ford", "gm", "stellantis", "roo", "rules of origin", "vehicle"],
        "steel": ["steel", "acero", "section 232"],
        "aluminum": ["aluminum", "aluminio"],
        "china": ["china", "chinese", "byd", "ev", "circumvention", "circunvención", "beijing"],
        "agriculture": ["agricult", "farm", "crop", "corn", "maíz", "wheat", "trigo", "soy", "canola", "grain"],
        "dairy": ["dairy", "lacteo", "milk", "leche", "cheese", "queso", "butter", "trq"],
        "energy": ["energy", "energía", "oil", "petroleo", "gas", "pemex", "electricity"],
        "labor": ["labor", "labour", "trabajo", "union", "sindicato", "rrm", "rapid response", "worker"],
        "nearshoring": ["nearshor", "relocaliz", "fdi", "investment", "inversión", "supply chain"],
        "digital": ["digital", "ip", "intellectual property", "e-commerce", "tech"],
        "pharma": ["pharma", "farmaceutic", "drug", "medic", "patent"],
        "environment": ["environment", "ambiente", "climate", "clima", "carbon", "emission"],
        "critical_minerals": ["mineral", "litio", "lithium", "rare earth", "graphite", "cobalt", "nickel"],
        "aerospace": ["aerospace", "aeroespacial", "boeing", "bombardier"],
        "financial": ["financ", "bank", "currency", "peso", "dollar", "exchange rate"],
        "textile": ["textil", "textile", "apparel", "maquila"],
        "forestry": ["forest", "forestal", "madera", "lumber", "softwood", "timber"],
    }

    total = 0
    for sector, keywords in sector_keywords.items():
        if _count_keywords(text, keywords):
            weight = weights.get(sector, 5)
            total += weight // 3
    return min(15, total)


def score_disruption(title: str, summary: str) -> int:
    keywords = [
        r"tariff", r"sancion", r"sanction", r"rupture", r"ruptura",
        r"collapse", r"colapso", r"withdraw", r"retirar", r"terminate",
        r"terminar", r"ultimátum", r"ultimatum", r"arancel",
        r"block", r"bloquear", r"threaten", r"amenaz",
        r"catastroph", r"catastróf", r"crisis", r"emergency",
        r"national security", r"seguridad nacional",
        r"retaliat", r"represalia",
    ]
    text = f"{title} {summary}".lower()
    hits = _count_keywords(text, keywords)
    return min(20, hits * 5 + 5)


def calculate_fallback(title: str, summary: str, config: dict[str, Any] | None = None) -> tuple[int, str]:
    """Returns (score 0-100, reason string)."""
    r = score_relevance(title, summary)
    u = score_urgency(title, summary)
    a = score_actors(title, summary, config)
    s = score_sectoral(title, summary, config)
    d = score_disruption(title, summary)
    total = min(100, r + u + a + s + d)
    reason = f"fallback: relevance={r} urgency={u} actors={a} sectoral={s} disruption={d}"
    return (total, reason)


def apply_fallback(items: list[dict[str, Any]], config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Apply fallback scores to any item missing AI impact data."""
    cfg = config or _load_config()
    fixed = 0
    for item in items:
        if not item.get("impactScore") or item.get("impactScore", 0) == 0:
            title = item.get("title", "")
            summary = item.get("summary", "")
            score, reason = calculate_fallback(title, summary, cfg)
            item["impactScore"] = score
            item["impactReason"] = reason
            fixed += 1
    if fixed:
        print(f"[fallback] Applied keyword-based scores to {fixed} items without AI analysis.")
    return items


def calculate_fallback_score(item: dict[str, Any], config: dict[str, Any] | None = None) -> tuple[int, str]:
    """Convenience wrapper — takes an item dict, returns score+reason. Used by enrich.py."""
    title = item.get("title", "")
    summary = item.get("summary", "")
    return calculate_fallback(title, summary, config)
