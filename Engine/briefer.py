"""Daily briefing generator — produces executive summary markdown from enriched data."""

from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .buzz import calculate_buzz, detect_early_warnings


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


def generate_briefing(
    enriched_path: str | Path,
    output_dir: str | Path,
    config: dict[str, Any] | None = None,
) -> str:
    items = _load_jsonl(enriched_path)
    if not items:
        return ""

    enriched = [it for it in items if "aiSummary" in it]
    if not enriched:
        enriched = items

    today = dt.date.today().isoformat()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"briefing-{today}.md"

    top5 = sorted(enriched, key=lambda i: i.get("impactScore", 0), reverse=True)[:5]

    sentiment_counter: Counter = Counter()
    stance_counter: Counter = Counter()
    tensions: list[dict[str, Any]] = []
    all_sentiment = 0
    for it in enriched:
        s = it.get("sentiment", "")
        st = it.get("stance", "")
        if s:
            sentiment_counter[s] += 1
            all_sentiment += 1
        if st:
            stance_counter[st] += 1
        ts = it.get("tensionScore")
        if ts and isinstance(ts, (int, float)) and ts > 0:
            tensions.append({
                "score": ts,
                "origin": it.get("tensionOrigin", "?"),
                "target": it.get("tensionTarget", "?"),
                "reason": it.get("tensionReason", ""),
                "title": it.get("title", ""),
            })

    tensions.sort(key=lambda t: t["score"], reverse=True)
    top_tensions = tensions[:5]

    buzz = calculate_buzz(enriched_path, config)
    buzz_items = sorted(buzz.items(), key=lambda x: x[1], reverse=True)
    trending = [(s, f) for s, f in buzz_items if f > 1.2][:5]

    warnings = detect_early_warnings(enriched_path, config)

    generated = dt.datetime.now().strftime("%B %-d, %Y — %-I:%M %p")

    lines: list[str] = []
    lines.append(f"# Briefing T-MEC — {today}")
    lines.append(f"*Generado {generated} · {len(enriched)} artículos analizados*")
    lines.append("")

    lines.append("## Top 5 por impacto")
    lines.append("")
    for i, item in enumerate(top5, 1):
        score = item.get("impactScore", 0)
        title = item.get("title", "?")
        source = item.get("source", "?")
        sentiment = item.get("sentiment", "")
        sent_icon = {"positive": "+", "negative": "-", "neutral": "~"}.get(sentiment, "")
        lines.append(f"{i}. [{sent_icon}**{score}**] {title} — *{source}*")
    lines.append("")

    lines.append("## Sentimiento general")
    lines.append("")
    total = sum(sentiment_counter.values()) or 1
    for label in ("positive", "negative", "neutral"):
        count = sentiment_counter.get(label, 0)
        pct = round(count / total * 100)
        icon = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}.get(label, "⚪")
        lines.append(f"- {icon} {label}: {count} artículos ({pct}%)")
    lines.append("")

    if stance_counter:
        lines.append("## Postura por país")
        lines.append("")
        for stance, count in stance_counter.most_common():
            flag = {"US": "🇺🇸", "MX": "🇲🇽", "CA": "🇨🇦", "MULTI": "🌐"}.get(stance, "❓")
            lines.append(f"- {flag} {stance}: {count} artículos")
        lines.append("")

    if trending:
        lines.append("## Buzz del día")
        lines.append("")
        for sector, factor in trending:
            pct = round((factor - 1) * 100)
            sign = "+" if pct > 0 else ""
            lines.append(f"- {sector}: {sign}{pct}% vs promedio 7d")
        lines.append("")

    if top_tensions:
        lines.append("## Tensiones del día")
        lines.append("")
        for t in top_tensions:
            arrow = f"{t['origin']}→{t['target']}"
            lines.append(f"- ⚡ **{t['score']}/100** {arrow}: {t['reason'][:100]}")
        lines.append("")

    if warnings:
        lines.append("## ⚠️ Early Warnings")
        lines.append("")
        for w in warnings:
            lines.append(f"- **{w['sector']}**: buzz {w['buzz']}× (umbral: {w['threshold']}×) — posible anuncio inminente")
        lines.append("")

    lines.append("## Qué vigilar mañana")
    lines.append("")
    if top_tensions:
        lines.append(f"- Seguir la tensión {top_tensions[0]['origin']}→{top_tensions[0]['target']}")
    if trending:
        lines.append(f"- Sector {trending[0][0]} sigue en tendencia alcista")
    lines.append("- Atención a comunicados oficiales post-ronda 3 de negociación")
    lines.append("")

    content = "\n".join(lines)
    out_path.write_text(content, encoding="utf-8")
    print(f"[briefer] Written to {out_path}")
    return content
