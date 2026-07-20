"""Bias score calculator — combines source classification with DeepSeek content analysis."""

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


def get_source_bias(url_or_source: str, config: dict[str, Any] | None = None) -> int:
    """Return pre-classified source bias 0-100 for a domain. Default 50 for unknown."""
    cfg = config or _load_config()
    bias_table = cfg.get("scoring", {}).get("source_bias", {})
    if not bias_table:
        return 50

    host = ""
    parsed = urlparse(url_or_source)
    if parsed.netloc:
        host = parsed.netloc.lower().removeprefix("www.").rstrip(".")
    else:
        clean = url_or_source.lower().strip().removeprefix("www.")
        parsed2 = urlparse(f"https://{clean}")
        host = parsed2.netloc or clean
        host = host.rstrip(".")

    if host in bias_table:
        return bias_table[host].get("bias", 50)

    for domain, data in bias_table.items():
        if host.endswith("." + domain) or domain.endswith("." + host):
            return data.get("bias", 50)
    return 50


def get_source_country(url_or_source: str, config: dict[str, Any] | None = None) -> str:
    """Return US/MX/CA/MULTI for a domain's country alignment."""
    cfg = config or _load_config()
    bias_table = cfg.get("scoring", {}).get("source_bias", {})
    if not bias_table:
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

    if host in bias_table:
        return bias_table[host].get("country", "MULTI")

    for domain, data in bias_table.items():
        if host.endswith("." + domain) or domain.endswith("." + host):
            return data.get("country", "MULTI")
    return "MULTI"


def compute_final_bias(source_bias: int, content_bias: int | None) -> dict[str, Any]:
    """Combine source bias (40%) and AI content bias (60%)."""
    if content_bias is None:
        return {"biasScore": source_bias, "biasReason": "source-based only"}

    final = round(source_bias * 0.4 + content_bias * 0.6)
    final = max(0, min(100, final))
    return {"biasScore": final, "biasReason": f"source={source_bias} content={content_bias}"}


def compute_bias(source_bias: int, content_bias: int | None) -> int:
    """Return final bias score 0-100 combining source (40%) and content (60%)."""
    if content_bias is None:
        return source_bias
    return max(0, min(100, round(source_bias * 0.4 + content_bias * 0.6)))


def bias_label(score: int) -> str:
    if score <= 20:
        return "Balanced"
    if score <= 40:
        return "Mild bias"
    if score <= 60:
        return "Moderate"
    if score <= 80:
        return "Strong bias"
    return "Heavy"
