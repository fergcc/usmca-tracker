"""Trade-policy lean calculator — combines source classification with DeepSeek content analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _load_config() -> dict[str, Any]:
    config_path = Path(__file__).resolve().parent / "config.yaml"
    try:
        import yaml
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return {}


def get_source_lean(url_or_source: str, config: dict[str, Any] | None = None) -> int:
    """Return pre-classified trade-policy lean -100..+100 for a domain. Default 0 for unknown."""
    cfg = config or _load_config()
    lean_table = cfg.get("scoring", {}).get("source_lean", {})
    if not lean_table:
        return 0

    host = ""
    parsed = urlparse(url_or_source)
    if parsed.netloc:
        host = parsed.netloc.lower().removeprefix("www.").rstrip(".")
    else:
        clean = url_or_source.lower().strip().removeprefix("www.")
        parsed2 = urlparse(f"https://{clean}")
        host = parsed2.netloc or clean
        host = host.rstrip(".")

    if host in lean_table:
        return lean_table[host].get("leanScore", 0)

    for domain, data in lean_table.items():
        if host.endswith("." + domain) or domain.endswith("." + host):
            return data.get("leanScore", 0)
    return 0


def get_source_country(url_or_source: str, config: dict[str, Any] | None = None) -> str:
    """Return US/MX/CA/MULTI for a domain's country alignment."""
    cfg = config or _load_config()
    lean_table = cfg.get("scoring", {}).get("source_lean", {})
    if not lean_table:
        return "MULTI"

    host = ""
    parsed = urlparse(url_or_source)
    if parsed.netloc:
        host = parsed.netloc.lower().removeprefix("www.").rstrip(".")
    else:
        clean = url_or_source.lower().strip().removeprefix("www.")
        parsed2 = urlparse(f"https://{clean}")
        host = parsed2.netloc or clean
        host = host.rstrip(".")

    if host in lean_table:
        return lean_table[host].get("country", "MULTI")

    for domain, data in lean_table.items():
        if host.endswith("." + domain) or domain.endswith("." + host):
            return data.get("country", "MULTI")
    return "MULTI"


def compute_final_lean(source_lean: int, content_lean: int | None) -> dict[str, Any]:
    """Combine source lean (40%) and AI content lean (60%)."""
    if content_lean is None:
        return {"leanScore": source_lean, "leanReason": "source-based only"}

    final = round(source_lean * 0.4 + content_lean * 0.6)
    final = max(-100, min(100, final))
    return {"leanScore": final, "leanReason": f"source={source_lean} content={content_lean}"}


def compute_lean(source_lean: int, content_lean: int | None) -> int:
    """Return final lean score -100..+100 combining source (40%) and content (60%)."""
    if content_lean is None:
        return source_lean
    return max(-100, min(100, round(source_lean * 0.4 + content_lean * 0.6)))


def lean_label(score: int) -> str:
    if score <= -70:
        return "Proteccionista"
    if score <= -30:
        return "Nacionalista"
    if score <= -10:
        return "Leve protecc."
    if score < 10:
        return "Neutral"
    if score < 30:
        return "Leve pro-TLC"
    if score < 70:
        return "Pro-TLC"
    return "Globalista"


def lean_color(score: int) -> tuple[int, int, int]:
    """Return (hue, saturation%, lightness%) for CSS hsl.
    Orange (-100) → Gray (0) → Green (+100)."""
    abs_score = min(abs(score), 100)
    sat = min(90, 20 + int(abs_score * 0.7))

    if score <= 0:
        hue = 25
    else:
        hue = 25 + int((abs_score / 100) * 95)
    return (hue, sat, 42)
