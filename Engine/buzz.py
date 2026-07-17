"""Buzz factor calculator — detects trending sectors from recent coverage."""

from __future__ import annotations

import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


SECTOR_KEYWORDS: dict[str, list[str]] = {
    "automotive": ["auto", "automotriz", "automotrice", "automaker", "toyota", "ford", "gm", "stellantis", "tacoma", "supply chain", "cadena de suministro", "roo", "rules of origin", "reglas de origen", "vsm", "vehicle", "vehiculo"],
    "steel": ["steel", "acero", "232", "section 232", "aisi", "metal"],
    "aluminum": ["aluminum", "aluminio", "aluminium"],
    "china": ["china", "chinese", "beijing", "byd", "ev", "circumvention", "circunvención", "back door", "puerta trasera", "infiltrat"],
    "agriculture": ["agricult", "farm", "crop", "harvest", "grain", "granos", "corn", "maíz", "wheat", "trigo", "soy", "soja", "canola", "produce", "fruit", "vegetable"],
    "dairy": ["dairy", "lacteo", "leche", "milk", "cheese", "queso", "butter", "mantequilla", "supply management", "trq", "tariff-rate quota"],
    "energy": ["energy", "energía", "energetic", "oil", "petroleo", "gas", "pemex", "electricity", "electricidad", "reform"],
    "labor": ["labor", "labour", "trabajo", "sindicato", "union", "rrm", "rapid response", "worker", "trabajador", "wage", "salario"],
    "nearshoring": ["nearshor", "relocaliz", "relocation", "fdi", "investment", "inversión", "planta", "factory", "fabrica"],
    "digital": ["digital", "ip", "intellectual property", "propiedad intelectual", "e-commerce", "data", "datos", "tech", "tecnología"],
    "pharma": ["pharma", "farmaceutic", "drug", "medic", "patent", "patente"],
    "environment": ["environment", "ambiente", "climate", "clima", "carbon", "carbono", "emission", "emision", "green"],
    "critical_minerals": ["mineral", "litio", "lithium", "rare earth", "tierras raras", "graphite", "grafito", "cobalt", "cobalto", "nickel", "niquel"],
    "aerospace": ["aerospace", "aeroespacial", "boeing", "bombardier", "aviation", "aviación"],
    "financial": ["financ", "bank", "banco", "currency", "moneda", "peso", "dollar", "exchange rate", "tipo de cambio"],
    "textile": ["textil", "textile", "apparel", "ropa", "garment", "maquila"],
    "forestry": ["forest", "forestal", "madera", "lumber", "softwood", "timber"],
}


def _load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    items: list[dict[str, Any]] = []
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def _count_sector_mentions(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {s: 0 for s in SECTOR_KEYWORDS}
    if not items:
        return counts
    for item in items:
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        for sector, keywords in SECTOR_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    counts[sector] += 1
                    break
    return counts


def calculate_buzz(
    items_path: str | Path,
    config: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Calculate buzz factor (0.0-2.0) per sector by comparing recent vs baseline coverage.

    Returns a dict mapping sector names to multipliers.
    """
    cfg = config or {}
    buzz_cfg = cfg.get("scoring", {}).get("buzz", {})
    if not buzz_cfg.get("enabled", True):
        return {s: 1.0 for s in SECTOR_KEYWORDS}

    window_hours = buzz_cfg.get("window_hours", 48)
    baseline_days = buzz_cfg.get("baseline_days", 7)
    max_mult = buzz_cfg.get("max_multiplier", 2.0)
    items = _load_jsonl(items_path)
    if len(items) < 10:
        return {s: 1.0 for s in SECTOR_KEYWORDS}

    now = dt.datetime.now(dt.timezone.utc)
    recent: list[dict[str, Any]] = []
    baseline: list[dict[str, Any]] = []
    window_cutoff = now - dt.timedelta(hours=window_hours)
    baseline_cutoff = now - dt.timedelta(days=baseline_days)

    for item in items:
        pub_str = item.get("published", "")
        pub_dt = None
        try:
            for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%a, %d %b %Y %H:%M:%S %z"):
                try:
                    pub_dt = dt.datetime.strptime(pub_str, fmt)
                    if pub_dt.tzinfo is None:
                        pub_dt = pub_dt.replace(tzinfo=dt.timezone.utc)
                    break
                except ValueError:
                    continue
        except Exception:
            pass
        if pub_dt is None:
            continue
        if pub_dt >= window_cutoff:
            recent.append(item)
        if pub_dt >= baseline_cutoff:
            baseline.append(item)

    recent_counts = _count_sector_mentions(recent)
    baseline_counts = _count_sector_mentions(baseline)

    factors: dict[str, float] = {}
    for sector in SECTOR_KEYWORDS:
        recent_n = recent_counts.get(sector, 0)
        baseline_n = baseline_counts.get(sector, 1)
        if baseline_n == 0:
            baseline_n = 1
        ratio = recent_n / max(baseline_n / (baseline_days * 24 / window_hours), 1)
        ratio = max(0.5, min(max_mult, ratio))
        factors[sector] = round(ratio, 2)

    return factors


def detect_early_warnings(
    items_path: str | Path,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Detect sectors with abnormally high buzz (>2 std dev above baseline)."""
    cfg = config or {}
    ew_cfg = cfg.get("scoring", {}).get("early_warning", {})
    if not ew_cfg.get("enabled", True):
        return []

    threshold = ew_cfg.get("std_dev_threshold", 2.0)
    min_items = ew_cfg.get("min_items_for_alert", 5)

    buzz_factors = calculate_buzz(items_path, config)
    alerts: list[dict[str, Any]] = []

    values = list(buzz_factors.values())
    if len(values) < 3:
        return []

    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std_dev = variance ** 0.5

    for sector, factor in buzz_factors.items():
        if factor > mean + threshold * std_dev and factor > 1.3:
            alerts.append({
                "sector": sector,
                "buzz": factor,
                "threshold": round(mean + threshold * std_dev, 2),
                "mean": round(mean, 2),
            })

    return alerts
