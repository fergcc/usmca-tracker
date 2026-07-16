#!/usr/bin/env python3
"""Builds dashboard.html from data/items.jsonl. Run from the project folder."""
import json
import re
import html
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
ITEMS_PATH = PROJECT / "data" / "items.jsonl"
OUT_PATH = PROJECT / "dashboard.html"


def clean(s: str) -> str:
    s = html.unescape(s or "")
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def strip_outlet(s: str) -> str:
    return re.sub(r"\s*[-|–]\s*[A-Za-z0-9&.,' ]{2,60}$", "", s).strip()


def parse_published(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return None, ""
    try:
        d = parsedate_to_datetime(raw)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return int(d.timestamp()), d.strftime("%b %-d, %Y")
    except Exception:
        pass
    for fmt in ("%Y-%m-%d",):
        try:
            d = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
            return int(d.timestamp()), d.strftime("%b %-d, %Y")
        except Exception:
            continue
    return None, raw


def group_label(source: str, origin: str) -> str:
    if origin == "federal_register":
        return "Federal Register"
    if source.startswith("Inside U.S. Trade"):
        return "Inside U.S. Trade"
    return source


def prep(it: dict) -> dict:
    title = clean(it["title"])
    summary = clean(it.get("summary", ""))
    title_core = strip_outlet(title).lower()
    summary_l = summary.lower()
    redundant = bool(title_core) and summary_l.startswith(title_core) and (
        len(summary_l) - len(title_core) < 40
    )
    ts, disp = parse_published(it.get("published", ""))
    is_paywalled = it["source"].startswith("Inside U.S. Trade")
    return {
        "title": title,
        "url": it["url"],
        "source": it["source"],
        "group": group_label(it["source"], it["origin"]),
        "origin": it["origin"],
        "publishedTs": ts,
        "publishedDisplay": disp,
        "summary": "" if redundant else summary,
        "score": it["score"],
        "tags": it.get("tags", []),
        "paywalled": is_paywalled,
        "image": it.get("image_url", ""),
    }


def main():
    raw_items = []
    with ITEMS_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                raw_items.append(json.loads(line))

    items = [prep(it) for it in raw_items]
    items.sort(key=lambda i: (-i["score"], -(i["publishedTs"] or 0)))

    generated_display = datetime.now().strftime("%B %-d, %Y") + " &middot; " + datetime.now().strftime("%-I:%M %p")
    today_label = datetime.now().strftime("%b %-d")
    data_json = json.dumps(items, ensure_ascii=False, separators=(",", ":"))

    html_out = (
        TEMPLATE.replace("__DATA_JSON__", data_json)
        .replace("__GENERATED__", generated_display)
        .replace("__TODAY__", today_label)
    )
    OUT_PATH.write_text(html_out, encoding="utf-8")
    print(f"Wrote {OUT_PATH} ({len(html_out):,} bytes, {len(items)} items)")


TEMPLATE = r"""<meta charset="utf-8">
<title>USMCA Signal Desk</title>
<style>
  #dash, #dash * { box-sizing: border-box; }
  #dash {
    --paper:        #f5f1e6;
    --paper-raised: #fffdf7;
    --paper-sunken: #ece5d2;
    --ink:          #1c1f24;
    --ink-soft:     #565c66;
    --ink-muted:    #8f8a7a;
    --hairline:     #ddd4bd;
    --accent:       #1f3f66;
    --accent-soft:  #cddaea;
    --sig-critical: #b23a2e;
    --sig-notable:  #a6701b;
    --sig-routine:  #6b7178;
    --sig-critical-bg: #f3e2dd;
    --sig-notable-bg:  #f2e6d3;
    --sig-routine-bg:  #e6e2d6;
    --comp-fedreg:  #1f3f66;
    --comp-gnews:   #1f7a68;
    --comp-site:    #6a4f8e;
    --comp-congress: #4a6b2e;
    --shadow: 0 1px 2px rgba(28,31,36,0.06), 0 6px 20px -8px rgba(28,31,36,0.18);

    color-scheme: light;
    background: var(--paper);
    color: var(--ink);
    font-family: "Avenir Next", "Century Gothic", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 15px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
    display: block;
    min-height: 100%;
    padding: 0 0 4rem;
  }
  @media (prefers-color-scheme: dark) {
    #dash:not([data-theme-lock]) {
      --paper:        #14181d;
      --paper-raised: #1c222a;
      --paper-sunken: #0f1216;
      --ink:          #ece7d8;
      --ink-soft:     #a7ada8;
      --ink-muted:    #7d8189;
      --hairline:     #2a2f36;
      --accent:       #7fa8d6;
      --accent-soft:  #253550;
      --sig-critical: #e2695a;
      --sig-notable:  #d9a441;
      --sig-routine:  #8b9099;
      --sig-critical-bg: #3a2420;
      --sig-notable-bg:  #392e18;
      --sig-routine-bg:  #262a2e;
      --comp-fedreg:  #5b8fc9;
      --comp-gnews:   #3aa88f;
      --comp-site:    #9483c9;
      --comp-congress: #8bbf5e;
      --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 8px 24px -10px rgba(0,0,0,0.6);
      color-scheme: dark;
    }
  }
  :root[data-theme="dark"] #dash {
    --paper:        #14181d;
    --paper-raised: #1c222a;
    --paper-sunken: #0f1216;
    --ink:          #ece7d8;
    --ink-soft:     #a7ada8;
    --ink-muted:    #7d8189;
    --hairline:     #2a2f36;
    --accent:       #7fa8d6;
    --accent-soft:  #253550;
    --sig-critical: #e2695a;
    --sig-notable:  #d9a441;
    --sig-routine:  #8b9099;
    --sig-critical-bg: #3a2420;
    --sig-notable-bg:  #392e18;
    --sig-routine-bg:  #262a2e;
    --comp-fedreg:  #5b8fc9;
    --comp-gnews:   #3aa88f;
    --comp-site:    #9483c9;
    --comp-congress: #8bbf5e;
    --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 8px 24px -10px rgba(0,0,0,0.6);
    color-scheme: dark;
  }
  :root[data-theme="light"] #dash {
    --paper:        #f5f1e6;
    --paper-raised: #fffdf7;
    --paper-sunken: #ece5d2;
    --ink:          #1c1f24;
    --ink-soft:     #565c66;
    --ink-muted:    #8f8a7a;
    --hairline:     #ddd4bd;
    --accent:       #1f3f66;
    --accent-soft:  #cddaea;
    --sig-critical: #b23a2e;
    --sig-notable:  #a6701b;
    --sig-routine:  #6b7178;
    --sig-critical-bg: #f3e2dd;
    --sig-notable-bg:  #f2e6d3;
    --sig-routine-bg:  #e6e2d6;
    --comp-fedreg:  #1f3f66;
    --comp-gnews:   #1f7a68;
    --comp-site:    #6a4f8e;
    --comp-congress: #4a6b2e;
    --shadow: 0 1px 2px rgba(28,31,36,0.06), 0 6px 20px -8px rgba(28,31,36,0.18);
    color-scheme: light;
  }

  #dash a { color: var(--accent); }
  #dash .skip-link {
    position: absolute; left: -999px; top: 0;
  }
  #dash .skip-link:focus {
    left: 1rem; top: 1rem; z-index: 50;
    background: var(--paper-raised); padding: 0.5rem 1rem; border-radius: 4px;
  }

  #dash .dash-header {
    position: sticky; top: 0; z-index: 20;
    background: var(--paper);
    border-bottom: 1px solid var(--hairline);
    padding: 1.75rem 1.5rem 1.25rem;
  }
  #dash .dash-header-inner { max-width: 920px; margin: 0 auto; }
  #dash .eyebrow {
    margin: 0 0 0.5rem;
    font-family: "American Typewriter", "Courier New", ui-monospace, monospace;
    font-size: 0.68rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase;
    color: var(--ink-muted);
  }
  #dash h1 {
    margin: 0 0 0.4rem;
    font-family: "Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif;
    font-size: clamp(1.5rem, 2.6vw, 2.05rem);
    font-weight: 600;
    letter-spacing: 0.002em;
    text-wrap: balance;
    color: var(--ink);
  }
  #dash .run-meta {
    margin: 0; font-size: 0.86rem; color: var(--ink-soft);
    font-variant-numeric: tabular-nums;
  }
  #dash .refresh-row {
    margin-top: 0.6rem; display: flex; align-items: center; gap: 0.65rem; flex-wrap: wrap;
  }
  #dash .refresh-btn {
    font: inherit; font-size: 0.82rem; font-weight: 600; cursor: pointer;
    padding: 0.4rem 0.8rem; border-radius: 7px;
    border: 1px solid var(--hairline); background: var(--paper-raised); color: var(--accent);
  }
  #dash .refresh-btn:hover:not(:disabled) { background: var(--accent-soft); }
  #dash .refresh-btn:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  #dash .refresh-btn:disabled { cursor: default; opacity: 0.55; }
  #dash .refresh-status { font-size: 0.8rem; color: var(--ink-muted); }

  #dash .review-clock {
    max-width: 920px; margin: 1.35rem auto 0; padding: 0 1.5rem;
  }
  #dash .clock-caption {
    margin: 0 0 0.55rem;
    font-family: "American Typewriter", "Courier New", ui-monospace, monospace;
    font-size: 0.64rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;
    color: var(--ink-muted);
  }
  #dash .clock-line {
    position: relative;
    display: flex; justify-content: space-between; align-items: flex-start;
    padding-top: 7px;
  }
  #dash .clock-line::before {
    content: ""; position: absolute; left: 5px; right: 5px; top: 7px;
    height: 1px; background: var(--hairline);
  }
  #dash .clock-point {
    position: relative; z-index: 1;
    display: flex; flex-direction: column; align-items: center; gap: 0.4rem;
    flex: 1;
  }
  #dash .clock-dot {
    width: 10px; height: 10px; border-radius: 50%;
    background: var(--paper); border: 2px solid var(--ink-muted);
  }
  #dash .clock-point.is-done .clock-dot { background: var(--accent); border-color: var(--accent); }
  #dash .clock-point.is-today .clock-dot {
    background: var(--sig-critical); border-color: var(--sig-critical);
    box-shadow: 0 0 0 4px var(--sig-critical-bg);
  }
  #dash .clock-point.is-next .clock-dot {
    background: var(--paper); border-color: var(--sig-notable);
    box-shadow: 0 0 0 3px var(--sig-notable-bg);
  }
  #dash .clock-label {
    font-family: "American Typewriter", "Courier New", ui-monospace, monospace;
    font-size: 0.66rem; text-align: center; color: var(--ink-soft); line-height: 1.4;
  }
  #dash .clock-label time { display: block; color: var(--ink-muted); font-variant-numeric: tabular-nums; }
  #dash .clock-point.is-today .clock-label { color: var(--sig-critical); font-weight: 700; }
  #dash .clock-point.is-today .clock-label time { color: var(--sig-critical); }

  #dash .stat-strip {
    max-width: 920px; margin: 1.1rem auto 0; padding: 0 1.5rem;
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.85rem;
  }
  #dash .stat-tile {
    background: var(--paper-raised);
    border: 1px solid var(--hairline);
    border-radius: 10px;
    padding: 0.95rem 1.05rem;
    box-shadow: var(--shadow);
    min-width: 0;
  }
  #dash .stat-label {
    margin: 0 0 0.35rem; font-size: 0.68rem; font-weight: 700;
    letter-spacing: 0.09em; text-transform: uppercase; color: var(--ink-muted);
  }
  #dash .stat-value {
    margin: 0; font-size: 1.65rem; font-weight: 700; line-height: 1.1;
    font-variant-numeric: tabular-nums; color: var(--ink);
  }
  #dash .stat-value--text { font-size: 1.15rem; font-family: "Iowan Old Style", Palatino, Georgia, serif; }
  #dash .stat-sub {
    margin: 0.3rem 0 0; font-size: 0.76rem; color: var(--ink-muted);
    font-variant-numeric: tabular-nums;
  }
  #dash .stat-tile--critical .stat-value { color: var(--sig-critical); }
  #dash .comp-bar {
    display: flex; height: 8px; border-radius: 4px; overflow: hidden;
    background: var(--paper-sunken); margin-top: 0.5rem;
  }
  #dash .comp-seg { height: 100%; }
  #dash .comp-seg + .comp-seg { margin-left: 2px; }
  #dash .comp-legend {
    margin-top: 0.55rem; display: flex; flex-direction: column; gap: 0.2rem;
    font-size: 0.72rem; color: var(--ink-soft);
  }
  #dash .comp-legend-row { display: flex; align-items: center; gap: 0.4rem; }
  #dash .comp-swatch { width: 8px; height: 8px; border-radius: 2px; flex: none; }
  #dash .comp-legend-count { margin-left: auto; font-variant-numeric: tabular-nums; color: var(--ink-muted); }

  #dash .controls {
    position: sticky; top: 92px; z-index: 15;
    max-width: 920px; margin: 1.35rem auto 0; padding: 0.9rem 1.5rem 1.1rem;
    background: var(--paper);
    border-bottom: 1px solid var(--hairline);
    display: flex; flex-direction: column; gap: 0.7rem;
  }
  #dash .control-row { display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; }
  #dash #searchInput {
    flex: 1 1 260px; min-width: 0;
    background: var(--paper-sunken); color: var(--ink);
    border: 1px solid var(--hairline); border-radius: 7px;
    padding: 0.55rem 0.8rem; font-size: 0.88rem; font-family: inherit;
  }
  #dash #searchInput:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
  #dash .sort-toggle { display: flex; border: 1px solid var(--hairline); border-radius: 7px; overflow: hidden; flex: none; }
  #dash .sort-btn {
    font-family: inherit; font-size: 0.8rem; font-weight: 600; letter-spacing: 0.01em;
    color: var(--ink-soft); background: var(--paper-raised); border: none;
    padding: 0.55rem 0.9rem; cursor: pointer;
  }
  #dash .sort-btn + .sort-btn { border-left: 1px solid var(--hairline); }
  #dash .sort-btn.is-active { background: var(--accent); color: var(--paper-raised); }
  #dash .sort-btn:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }

  #dash .chip {
    font-family: inherit; font-size: 0.78rem; font-weight: 600;
    color: var(--ink-soft); background: var(--paper-raised);
    border: 1px solid var(--hairline); border-radius: 999px;
    padding: 0.36rem 0.75rem 0.36rem 0.6rem; cursor: pointer; white-space: nowrap;
    display: inline-flex; align-items: center; gap: 0.4rem;
  }
  #dash .chip-dot { width: 7px; height: 7px; border-radius: 50%; flex: none; background: var(--chip-color, var(--ink-muted)); }
  #dash .chip .chip-count { color: var(--ink-muted); font-variant-numeric: tabular-nums; }
  #dash .chip.is-active { background: var(--accent-soft); border-color: var(--accent); color: var(--ink); }
  #dash .chip:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }

  #dash .control-row--slider { gap: 0.75rem; }
  #dash .control-row--slider label {
    font-size: 0.8rem; color: var(--ink-soft); white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
  #dash #scoreSlider {
    flex: 1 1 160px; height: 6px; border-radius: 3px;
    -webkit-appearance: none; appearance: none; background: var(--paper-sunken); cursor: pointer;
  }
  #dash #scoreSlider::-webkit-slider-thumb {
    -webkit-appearance: none; appearance: none;
    width: 16px; height: 16px; border-radius: 50%; margin-top: 0;
    background: var(--accent); border: 2px solid var(--paper-raised);
    box-shadow: 0 0 0 1px var(--hairline);
    cursor: pointer;
  }
  #dash #scoreSlider::-moz-range-thumb {
    width: 16px; height: 16px; border-radius: 50%;
    background: var(--accent); border: 2px solid var(--paper-raised);
    box-shadow: 0 0 0 1px var(--hairline); cursor: pointer;
  }
  #dash #scoreSlider::-moz-range-track { height: 6px; border-radius: 3px; background: transparent; }

  #dash .result-count {
    max-width: 920px; margin: 1.1rem auto 0.6rem; padding: 0 1.5rem;
    font-size: 0.78rem; color: var(--ink-muted);
    font-variant-numeric: tabular-nums;
  }

  #dash .feed {
    max-width: 920px; margin: 0 auto; padding: 0 1.5rem;
    display: flex; flex-direction: column; gap: 0.7rem;
  }
  #dash .empty-state {
    max-width: 920px; margin: 2rem auto; padding: 0 1.5rem;
    color: var(--ink-muted); font-size: 0.9rem; text-align: center;
  }

  #dash .card {
    display: flex; background: var(--paper-raised);
    border: 1px solid var(--hairline); border-radius: 10px;
    box-shadow: var(--shadow); overflow: hidden;
  }
  #dash .card-stripe { width: 4px; flex: none; background: var(--sig-routine); }
  #dash .card--critical .card-stripe { background: var(--sig-critical); }
  #dash .card--notable .card-stripe { background: var(--sig-notable); }
  #dash .card-thumb {
    width: 96px; height: 96px; flex: none; object-fit: cover;
    background: var(--paper-sunken);
  }
  @media (max-width: 560px) { #dash .card-thumb { width: 72px; height: 72px; } }
  #dash .card-body { padding: 0.95rem 1.1rem 1rem; min-width: 0; flex: 1; }
  #dash .card-top { display: flex; gap: 0.85rem; align-items: flex-start; }
  #dash .score-badge {
    position: relative;
    flex: none; width: 2.6rem; height: 2.6rem;
    display: flex; align-items: center; justify-content: center;
    border-radius: 50%; font-weight: 700; font-size: 1.05rem;
    font-variant-numeric: tabular-nums; font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace;
    background: var(--sig-routine-bg); color: var(--sig-routine);
    border: 1.5px solid currentColor;
    box-shadow: 0 0 0 3px var(--paper-raised), 0 0 0 4px currentColor;
    transform: rotate(var(--stamp-rot, -3deg));
    transition: transform 0.3s cubic-bezier(.2,.8,.3,1.1);
  }
  #dash .card:hover .score-badge { transform: rotate(0deg) scale(1.05); }
  #dash .score-badge::before {
    content: ""; position: absolute; inset: -1px; border-radius: 50%;
    background:
      radial-gradient(circle at 32% 28%, currentColor 0%, transparent 42%),
      radial-gradient(circle at 68% 74%, currentColor 0%, transparent 38%);
    opacity: 0.12; pointer-events: none;
  }
  #dash .card--critical .score-badge { background: var(--sig-critical-bg); color: var(--sig-critical); }
  #dash .card--notable .score-badge { background: var(--sig-notable-bg); color: var(--sig-notable); }
  #dash .card-heading { min-width: 0; flex: 1; }
  #dash .card-title {
    font-size: 0.98rem; font-weight: 600; text-decoration: none; color: var(--ink);
    display: block;
  }
  #dash .card-title:hover { color: var(--accent); text-decoration: underline; }
  #dash .card-title:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  #dash .card-meta {
    margin: 0.3rem 0 0; font-size: 0.78rem; color: var(--ink-muted);
    display: flex; align-items: center; gap: 0.45rem; flex-wrap: wrap;
  }
  #dash .source-pill { font-weight: 600; color: var(--ink-soft); }
  #dash .card-meta time { font-variant-numeric: tabular-nums; }
  #dash .card-meta .dot { opacity: 0.6; }
  #dash .lock-badge {
    font-size: 0.68rem; font-weight: 700; letter-spacing: 0.02em;
    color: var(--sig-notable); background: var(--sig-notable-bg);
    border-radius: 4px; padding: 0.1rem 0.4rem;
  }

  #dash .tag-row { margin: 0.55rem 0 0; display: flex; flex-wrap: wrap; gap: 0.35rem; }
  #dash .tag {
    font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace;
    font-size: 0.68rem; padding: 0.14rem 0.42rem; border-radius: 4px;
    background: var(--paper-sunken); color: var(--ink-soft);
  }
  #dash .tag--critical { color: var(--sig-critical); background: var(--sig-critical-bg); }
  #dash .tag--player { color: var(--accent); background: var(--accent-soft); }
  #dash .tag--sector { color: var(--ink-soft); background: var(--paper-sunken); }

  #dash .card-summary {
    margin: 0.6rem 0 0; font-size: 0.86rem; color: var(--ink-soft); line-height: 1.5;
    display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
  }
  #dash .card-link {
    display: inline-block; margin-top: 0.6rem; font-size: 0.78rem; font-weight: 600;
    text-decoration: none;
  }
  #dash .card-link:hover { text-decoration: underline; }

  #dash .dash-footer {
    max-width: 920px; margin: 2.25rem auto 0; padding: 1.1rem 1.5rem 0;
    border-top: 1px solid var(--hairline);
    font-size: 0.76rem; color: var(--ink-muted); line-height: 1.6;
  }
  #dash .dash-footer p { margin: 0 0 0.4rem; }
  #dash .dash-footer code { font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace; }

  @media (max-width: 720px) {
    #dash .stat-strip { grid-template-columns: repeat(2, 1fr); }
    #dash .controls { top: 0; }
    #dash .clock-label { font-size: 0.58rem; }
  }
  @media (prefers-reduced-motion: no-preference) {
    #dash .dash-header-inner, #dash .review-clock, #dash .stat-tile {
      animation: dashRiseIn 0.5s cubic-bezier(.2,.7,.3,1) both;
    }
    #dash .stat-tile:nth-child(1) { animation-delay: 0.03s; }
    #dash .stat-tile:nth-child(2) { animation-delay: 0.08s; }
    #dash .stat-tile:nth-child(3) { animation-delay: 0.13s; }
    #dash .stat-tile:nth-child(4) { animation-delay: 0.18s; }
  }
  @keyframes dashRiseIn {
    from { opacity: 0; transform: translateY(5px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @media (prefers-reduced-motion: reduce) {
    #dash * { transition: none !important; animation: none !important; scroll-behavior: auto !important; }
  }
</style>

<div class="dash" id="dash">
  <a class="skip-link" href="#feed">Skip to dispatches</a>
  <header class="dash-header">
    <div class="dash-header-inner">
      <p class="eyebrow">Scientika &middot; Trade Intelligence</p>
      <h1>USMCA Joint Review &mdash; Signal Desk</h1>
      <p class="run-meta">Generated __GENERATED__ &middot; <span id="itemCount">0</span> dispatches &middot; <span id="rangeText">&mdash;</span></p>
      <div class="refresh-row">
        <button type="button" id="refreshBtn" class="refresh-btn">&#8635; Refresh now</button>
        <span id="refreshStatus" class="refresh-status" role="status" aria-live="polite"></span>
      </div>
    </div>
  </header>

  <section class="review-clock" aria-label="Joint review timeline">
    <p class="clock-caption">Article 34.7.4 &middot; annual joint review &middot; through Jul 2036</p>
    <div class="clock-line">
      <div class="clock-point is-done">
        <span class="clock-dot"></span>
        <span class="clock-label">Round 1<time>May 28</time></span>
      </div>
      <div class="clock-point is-done">
        <span class="clock-dot"></span>
        <span class="clock-label">Round 2<time>Jun 16</time></span>
      </div>
      <div class="clock-point is-today">
        <span class="clock-dot"></span>
        <span class="clock-label">Today<time>__TODAY__</time></span>
      </div>
      <div class="clock-point is-next">
        <span class="clock-dot"></span>
        <span class="clock-label">Round 3<time>wk of Jul 20</time></span>
      </div>
      <div class="clock-point is-horizon">
        <span class="clock-dot"></span>
        <span class="clock-label">Sunset horizon<time>Jul 2036</time></span>
      </div>
    </div>
  </section>

  <section class="stat-strip" aria-label="Summary">
    <div class="stat-tile">
      <p class="stat-label">Dispatches</p>
      <p class="stat-value" id="statTotal">0</p>
      <p class="stat-sub" id="statRange">&nbsp;</p>
    </div>
    <div class="stat-tile stat-tile--critical">
      <p class="stat-label">Critical signal</p>
      <p class="stat-value" id="statCritical">0</p>
      <p class="stat-sub">score &ge; 10</p>
    </div>
    <div class="stat-tile">
      <p class="stat-label">Most active principal</p>
      <p class="stat-value stat-value--text" id="statPlayer">&mdash;</p>
      <p class="stat-sub" id="statPlayerCount">&nbsp;</p>
    </div>
    <div class="stat-tile stat-tile--composition">
      <p class="stat-label">Source mix</p>
      <div class="comp-bar" id="compBar" role="img" aria-label="Source composition"></div>
      <div class="comp-legend" id="compLegend"></div>
    </div>
  </section>

  <section class="controls" aria-label="Filters">
    <div class="control-row">
      <input type="search" id="searchInput" placeholder="Search dispatches by title or summary&hellip;" aria-label="Search dispatches">
      <div class="sort-toggle" role="group" aria-label="Sort order">
        <button type="button" class="sort-btn is-active" data-sort="score">Signal</button>
        <button type="button" class="sort-btn" data-sort="date">Newest</button>
      </div>
    </div>
    <div class="control-row control-row--chips" id="sourceChips"></div>
    <div class="control-row control-row--slider">
      <label for="scoreSlider">Minimum signal: <output id="scoreSliderVal">0</output></label>
      <input type="range" id="scoreSlider" min="0" max="14" step="1" value="0">
    </div>
  </section>

  <p class="result-count" id="resultCount"></p>
  <section class="feed" id="feed" aria-live="polite"></section>
  <p class="empty-state" id="emptyState" hidden>No dispatches match these filters.</p>

  <footer class="dash-footer">
    <p>Sources: Federal Register API &middot; Google News (Boolean queries + <code>site:</code> feeds) &middot; USTR &middot; Global Affairs Canada &middot; Diario Oficial de la Federaci&oacute;n &middot; CSIS &middot; Rethink Trade &middot; Inside U.S. Trade (headlines).</p>
    <p>This is a monitoring aid, not a source of truth &mdash; open the linked primary document before acting on anything here.</p>
  </footer>
</div>

<script>
(function () {
  const DATA = __DATA_JSON__;

  const fmtRange = (a, b) => {
    if (!a || !b) return "";
    const da = new Date(a * 1000), db = new Date(b * 1000);
    const opts = { month: "short", day: "numeric" };
    const sameYear = da.getFullYear() === db.getFullYear();
    const left = da.toLocaleDateString("en-US", opts);
    const right = db.toLocaleDateString("en-US", { ...opts, year: "numeric" });
    return sameYear ? `${left} - ${right}` : `${left}, ${da.getFullYear()} - ${right}`;
  };

  function groupLabel(item) { return item.group; }

  function computeStats() {
    document.getElementById("itemCount").textContent = DATA.length;
    document.getElementById("statTotal").textContent = DATA.length;

    const tsList = DATA.map(d => d.publishedTs).filter(Boolean).sort((a, b) => a - b);
    const rangeStr = tsList.length ? fmtRange(tsList[0], tsList[tsList.length - 1]) : "";
    document.getElementById("statRange").textContent = rangeStr ? `covering ${rangeStr}` : "";
    document.getElementById("rangeText").textContent = rangeStr || "";

    const critical = DATA.filter(d => d.score >= 10).length;
    document.getElementById("statCritical").textContent = critical;

    const playerTally = {};
    DATA.forEach(d => (d.tags || []).forEach(t => {
      if (t.startsWith("@")) playerTally[t.slice(1)] = (playerTally[t.slice(1)] || 0) + 1;
    }));
    const topPlayer = Object.entries(playerTally).sort((a, b) => b[1] - a[1])[0];
    if (topPlayer) {
      document.getElementById("statPlayer").textContent = topPlayer[0];
      document.getElementById("statPlayerCount").textContent = `${topPlayer[1]} mention${topPlayer[1] === 1 ? "" : "s"}`;
    }

    const compColors = { federal_register: "var(--comp-fedreg)", google_news: "var(--comp-gnews)", site_feed: "var(--comp-site)", congress: "var(--comp-congress)" };
    const compNames = { federal_register: "Federal Register", google_news: "Google News queries", site_feed: "Site feeds", congress: "Congress.gov bills" };
    const compCounts = { federal_register: 0, google_news: 0, site_feed: 0, congress: 0 };
    DATA.forEach(d => { compCounts[d.origin] = (compCounts[d.origin] || 0) + 1; });
    const total = DATA.length || 1;
    const bar = document.getElementById("compBar");
    const legend = document.getElementById("compLegend");
    bar.innerHTML = ""; legend.innerHTML = "";
    ["federal_register", "congress", "google_news", "site_feed"].forEach(key => {
      const n = compCounts[key] || 0;
      if (!n) return;
      const seg = document.createElement("div");
      seg.className = "comp-seg";
      seg.style.width = `${(n / total) * 100}%`;
      seg.style.background = compColors[key];
      seg.title = `${compNames[key]}: ${n}`;
      bar.appendChild(seg);
      const row = document.createElement("div");
      row.className = "comp-legend-row";
      row.innerHTML = `<span class="comp-swatch" style="background:${compColors[key]}"></span><span>${compNames[key]}</span><span class="comp-legend-count">${n}</span>`;
      legend.appendChild(row);
    });
  }

  function buildChips() {
    const counts = {};
    const originOf = {};
    DATA.forEach(d => {
      const g = groupLabel(d);
      counts[g] = (counts[g] || 0) + 1;
      originOf[g] = d.origin;
    });
    const originColor = { federal_register: "var(--comp-fedreg)", google_news: "var(--comp-gnews)", site_feed: "var(--comp-site)", congress: "var(--comp-congress)" };
    const groups = Object.keys(counts).sort((a, b) => counts[b] - counts[a]);
    const wrap = document.getElementById("sourceChips");
    groups.forEach(g => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "chip is-active";
      btn.dataset.group = g;
      btn.style.setProperty("--chip-color", originColor[originOf[g]] || "var(--ink-muted)");
      btn.innerHTML = `<span class="chip-dot"></span>${escapeHtml(g)} <span class="chip-count">${counts[g]}</span>`;
      btn.addEventListener("click", () => {
        btn.classList.toggle("is-active");
        render();
      });
      wrap.appendChild(btn);
    });
    return groups;
  }

  function escapeHtml(s) {
    return (s || "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function tagClass(tag) {
    if (tag.startsWith("!")) return "tag tag--critical";
    if (tag.startsWith("@")) return "tag tag--player";
    return "tag tag--sector";
  }

  function band(score) {
    if (score >= 10) return "critical";
    if (score >= 5) return "notable";
    return "routine";
  }

  function renderCard(item) {
    const tagsHtml = (item.tags || []).length
      ? `<div class="tag-row">${item.tags.map(t => `<span class="${tagClass(t)}">${escapeHtml(t)}</span>`).join("")}</div>`
      : "";
    const summaryHtml = item.summary ? `<p class="card-summary">${escapeHtml(item.summary)}</p>` : "";
    const lockBadge = item.paywalled ? `<span class="lock-badge">headlines only</span>` : "";
    const dateHtml = item.publishedDisplay ? `<span class="dot">&middot;</span><time>${escapeHtml(item.publishedDisplay)}</time>` : "";
    const imgHtml = item.image
      ? `<img class="card-thumb" src="${escapeHtml(item.image)}" alt="" loading="lazy" onerror="this.remove()">`
      : "";
    const rot = ((item.score * 53) % 7) - 3;
    return `
      <article class="card card--${band(item.score)}">
        <div class="card-stripe"></div>
        ${imgHtml}
        <div class="card-body">
          <div class="card-top">
            <span class="score-badge" style="--stamp-rot:${rot}deg">${item.score}</span>
            <div class="card-heading">
              <a class="card-title" href="${escapeHtml(item.url)}" target="_blank" rel="noopener">${escapeHtml(item.title)}</a>
              <p class="card-meta"><span class="source-pill">${escapeHtml(item.group)}</span>${lockBadge}${dateHtml}</p>
            </div>
          </div>
          ${tagsHtml}
          ${summaryHtml}
          <a class="card-link" href="${escapeHtml(item.url)}" target="_blank" rel="noopener">Open source &#8599;</a>
        </div>
      </article>`;
  }

  let state = { query: "", minScore: 0, sort: "score" };

  function render() {
    const activeGroups = new Set(
      Array.from(document.querySelectorAll("#sourceChips .chip.is-active")).map(b => b.dataset.group)
    );
    const q = state.query.trim().toLowerCase();
    let filtered = DATA.filter(d => {
      if (!activeGroups.has(groupLabel(d))) return false;
      if (d.score < state.minScore) return false;
      if (q && !(`${d.title} ${d.summary}`.toLowerCase().includes(q))) return false;
      return true;
    });
    filtered.sort((a, b) => {
      if (state.sort === "date") return (b.publishedTs || 0) - (a.publishedTs || 0);
      return b.score - a.score || (b.publishedTs || 0) - (a.publishedTs || 0);
    });

    const feed = document.getElementById("feed");
    const empty = document.getElementById("emptyState");
    document.getElementById("resultCount").textContent =
      `Showing ${filtered.length} of ${DATA.length} dispatches`;
    if (!filtered.length) {
      feed.innerHTML = "";
      empty.hidden = false;
    } else {
      empty.hidden = true;
      feed.innerHTML = filtered.map(renderCard).join("");
    }
  }

  function init() {
    computeStats();
    buildChips();

    const maxScore = Math.max(0, ...DATA.map(d => d.score));
    const slider = document.getElementById("scoreSlider");
    slider.max = String(maxScore);
    slider.addEventListener("input", () => {
      state.minScore = Number(slider.value);
      document.getElementById("scoreSliderVal").textContent = slider.value;
      render();
    });

    let debounce;
    document.getElementById("searchInput").addEventListener("input", e => {
      clearTimeout(debounce);
      const val = e.target.value;
      debounce = setTimeout(() => { state.query = val; render(); }, 120);
    });

    document.querySelectorAll(".sort-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".sort-btn").forEach(b => b.classList.remove("is-active"));
        btn.classList.add("is-active");
        state.sort = btn.dataset.sort;
        render();
      });
    });

    const refreshBtn = document.getElementById("refreshBtn");
    const refreshStatus = document.getElementById("refreshStatus");
    refreshBtn.addEventListener("click", () => {
      refreshBtn.disabled = true;
      refreshStatus.textContent = "Solicitando actualización…";
      fetch("/api/refresh", { method: "POST" })
        .then(async res => {
          const body = await res.json().catch(() => ({}));
          if (res.status === 202) {
            refreshStatus.textContent = "Actualización en marcha — la página se recargará en ~90s.";
            setTimeout(() => location.reload(), 90000);
          } else if (res.status === 429) {
            const wait = body.retryAfterSeconds || 60;
            refreshStatus.textContent = `Ya se actualizó hace poco. Intenta de nuevo en ${wait}s.`;
            setTimeout(() => { refreshBtn.disabled = false; refreshStatus.textContent = ""; }, wait * 1000);
          } else {
            refreshStatus.textContent = "No se pudo iniciar la actualización, intenta más tarde.";
            refreshBtn.disabled = false;
          }
        })
        .catch(() => {
          refreshStatus.textContent = "No se pudo iniciar la actualización, intenta más tarde.";
          refreshBtn.disabled = false;
        });
    });

    render();
  }

  init();
})();
</script>
"""

if __name__ == "__main__":
    main()
