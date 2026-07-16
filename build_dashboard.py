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
    --ink:          #14171c;
    --ink-soft:     #454b56;
    --ink-muted:    #767d89;
    --hairline:     rgba(20,23,30,0.12);
    --accent:       #2451a3;
    --accent-2:     #17306b;
    --accent-soft:  rgba(36,81,163,0.14);
    --sig-critical: #c23a2e;
    --sig-notable:  #b5791b;
    --sig-routine:  #5f6672;
    --sig-critical-bg: rgba(194,58,46,0.13);
    --sig-notable-bg:  rgba(181,121,27,0.13);
    --sig-routine-bg:  rgba(95,102,114,0.11);
    --comp-fedreg:  #2451a3;
    --comp-gnews:   #1f7a68;
    --comp-site:    #6a4f8e;
    --comp-congress: #046a38;
    --wash-blue:    #3c3b6e;
    --wash-red:     #ce1126;
    --wash-green:   #046a38;
    --wash-opacity: 0.5;
    --page-base: linear-gradient(180deg, #fbfbfa, #eef0ee);

    --glass-fill:        rgba(255,255,255,0.55);
    --glass-fill-strong: rgba(255,255,255,0.74);
    --glass-border:      rgba(255,255,255,0.75);
    --glass-shadow:      0 10px 34px rgba(28,38,66,0.16), inset 0 1px 0 rgba(255,255,255,0.65);
    --card-fill:   linear-gradient(160deg, rgba(255,255,255,0.84), rgba(255,255,255,0.6));
    --card-border: rgba(255,255,255,0.75);
    --card-shadow: 0 6px 20px -6px rgba(28,38,66,0.18), inset 0 1px 0 rgba(255,255,255,0.6);

    color-scheme: light;
    color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 15px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
    display: block;
    position: relative;
    min-height: 100%;
    padding: 0 0 4rem;
    background: var(--page-base);
  }
  @media (prefers-color-scheme: dark) {
    #dash:not([data-theme-lock]) {
      --ink:          #eef0f2;
      --ink-soft:     #b9bec6;
      --ink-muted:    #87909b;
      --hairline:     rgba(255,255,255,0.12);
      --accent:       #7ea6e8;
      --accent-2:     #4f7ecb;
      --accent-soft:  rgba(126,166,232,0.16);
      --sig-critical: #e2695a;
      --sig-notable:  #d9a441;
      --sig-routine:  #9aa0aa;
      --sig-critical-bg: rgba(226,105,90,0.16);
      --sig-notable-bg:  rgba(217,164,65,0.16);
      --sig-routine-bg:  rgba(154,160,170,0.14);
      --comp-fedreg:  #7ea6e8;
      --comp-gnews:   #3aa88f;
      --comp-site:    #ab9adf;
      --comp-congress: #5fbf8c;
      --wash-opacity: 0.32;
      --page-base: linear-gradient(180deg, #0c0e11, #111418);
      --glass-fill:        rgba(255,255,255,0.08);
      --glass-fill-strong: rgba(255,255,255,0.14);
      --glass-border:      rgba(255,255,255,0.16);
      --glass-shadow:      0 12px 36px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.08);
      --card-fill:   linear-gradient(160deg, rgba(255,255,255,0.09), rgba(255,255,255,0.035));
      --card-border: rgba(255,255,255,0.14);
      --card-shadow: 0 8px 22px -6px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.07);
      color-scheme: dark;
    }
  }
  :root[data-theme="dark"] #dash {
    --ink: #eef0f2; --ink-soft: #b9bec6; --ink-muted: #87909b;
    --hairline: rgba(255,255,255,0.12);
    --accent: #7ea6e8; --accent-2: #4f7ecb; --accent-soft: rgba(126,166,232,0.16);
    --sig-critical: #e2695a; --sig-notable: #d9a441; --sig-routine: #9aa0aa;
    --sig-critical-bg: rgba(226,105,90,0.16); --sig-notable-bg: rgba(217,164,65,0.16); --sig-routine-bg: rgba(154,160,170,0.14);
    --comp-fedreg: #7ea6e8; --comp-gnews: #3aa88f; --comp-site: #ab9adf; --comp-congress: #5fbf8c;
    --wash-opacity: 0.32;
    --page-base: linear-gradient(180deg, #0c0e11, #111418);
    --glass-fill: rgba(255,255,255,0.08); --glass-fill-strong: rgba(255,255,255,0.14);
    --glass-border: rgba(255,255,255,0.16);
    --glass-shadow: 0 12px 36px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.08);
    --card-fill: linear-gradient(160deg, rgba(255,255,255,0.09), rgba(255,255,255,0.035));
    --card-border: rgba(255,255,255,0.14);
    --card-shadow: 0 8px 22px -6px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.07);
    color-scheme: dark;
  }
  :root[data-theme="light"] #dash {
    --ink: #14171c; --ink-soft: #454b56; --ink-muted: #767d89;
    --hairline: rgba(20,23,30,0.12);
    --accent: #2451a3; --accent-2: #17306b; --accent-soft: rgba(36,81,163,0.14);
    --sig-critical: #c23a2e; --sig-notable: #b5791b; --sig-routine: #5f6672;
    --sig-critical-bg: rgba(194,58,46,0.13); --sig-notable-bg: rgba(181,121,27,0.13); --sig-routine-bg: rgba(95,102,114,0.11);
    --comp-fedreg: #2451a3; --comp-gnews: #1f7a68; --comp-site: #6a4f8e; --comp-congress: #046a38;
    --wash-opacity: 0.5;
    --page-base: linear-gradient(180deg, #fbfbfa, #eef0ee);
    --glass-fill: rgba(255,255,255,0.55); --glass-fill-strong: rgba(255,255,255,0.74);
    --glass-border: rgba(255,255,255,0.75);
    --glass-shadow: 0 10px 34px rgba(28,38,66,0.16), inset 0 1px 0 rgba(255,255,255,0.65);
    --card-fill: linear-gradient(160deg, rgba(255,255,255,0.84), rgba(255,255,255,0.6));
    --card-border: rgba(255,255,255,0.75);
    --card-shadow: 0 6px 20px -6px rgba(28,38,66,0.18), inset 0 1px 0 rgba(255,255,255,0.6);
    color-scheme: light;
  }

  #dash a { color: var(--accent); }
  #dash .skip-link { position: absolute; left: -999px; top: 0; }
  #dash .skip-link:focus {
    left: 1rem; top: 1rem; z-index: 60;
    background: var(--glass-fill-strong); padding: 0.5rem 1rem; border-radius: 8px;
  }

  /* ambient flag-colored wash, fixed behind everything */
  #dash .bg-wash { position: fixed; inset: 0; z-index: -1; overflow: hidden; pointer-events: none; }
  #dash .bg-wash span { position: absolute; border-radius: 50%; filter: blur(64px); opacity: var(--wash-opacity); }
  #dash .bg-wash span:nth-child(1) { width: 48vw; height: 48vw; top: -14%; left: -10%; background: var(--wash-blue); animation: blobDriftA 34s ease-in-out infinite alternate; }
  #dash .bg-wash span:nth-child(2) { width: 40vw; height: 40vw; top: -8%; right: -12%; background: var(--wash-red); animation: blobDriftB 27s ease-in-out infinite alternate; }
  #dash .bg-wash span:nth-child(3) { width: 52vw; height: 52vw; bottom: -20%; left: 4%; background: var(--wash-green); animation: blobDriftC 38s ease-in-out infinite alternate; }
  #dash .bg-wash span:nth-child(4) { width: 38vw; height: 38vw; bottom: -16%; right: -8%; background: var(--wash-red); animation: blobDriftA 29s ease-in-out infinite alternate-reverse; }
  @keyframes blobDriftA { from { transform: translate(0,0) scale(1); } to { transform: translate(4%,5%) scale(1.08); } }
  @keyframes blobDriftB { from { transform: translate(0,0) scale(1); } to { transform: translate(-5%,4%) scale(1.1); } }
  @keyframes blobDriftC { from { transform: translate(0,0) scale(1); } to { transform: translate(3%,-4%) scale(1.06); } }
  @media (prefers-reduced-motion: reduce) { #dash .bg-wash span { animation: none; } }

  #dash .glass {
    background: linear-gradient(160deg, var(--glass-fill-strong), var(--glass-fill));
    backdrop-filter: blur(26px) saturate(170%);
    -webkit-backdrop-filter: blur(26px) saturate(170%);
    border: 1px solid var(--glass-border);
    box-shadow: var(--glass-shadow);
  }

  /* ---------- tab switcher ---------- */
  #dash .tab-switch {
    position: sticky; top: 12px; z-index: 40;
    width: fit-content; margin: 12px auto 0;
    display: flex; padding: 4px; border-radius: 999px; gap: 2px;
  }
  #dash .tab-indicator {
    position: absolute; top: 4px; bottom: 4px; left: 4px;
    width: calc(50% - 4px); border-radius: 999px;
    background: linear-gradient(135deg, var(--accent), var(--accent-2));
    box-shadow: 0 4px 14px rgba(36,81,163,0.35);
    transition: transform 0.35s cubic-bezier(.2,.8,.2,1);
    z-index: 0;
  }
  #dash .tab-btn {
    position: relative; z-index: 1;
    font: inherit; font-size: 0.86rem; font-weight: 600; letter-spacing: 0.01em;
    padding: 0.5rem 1.15rem; border-radius: 999px; border: none; background: transparent;
    color: var(--ink-soft); cursor: pointer;
  }
  #dash .tab-btn.is-active { color: #fff; }
  #dash .tab-btn:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  @media (prefers-reduced-motion: reduce) { #dash .tab-indicator { transition: none; } }

  #dash .panel { padding: 1.6rem 1.25rem 0; }
  #dash .panel[hidden] { display: none !important; }

  /* ---------- welcome panel ---------- */
  #dash .panel-welcome { display: flex; justify-content: center; padding-top: clamp(1.5rem, 5vw, 4rem); }
  #dash .welcome-card {
    max-width: 700px; width: 100%; border-radius: 28px;
    padding: clamp(1.8rem, 5vw, 3.2rem);
  }
  #dash .eyebrow {
    margin: 0 0 0.6rem;
    font-family: "American Typewriter", "Courier New", ui-monospace, monospace;
    font-size: 0.68rem; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase;
    color: var(--ink-muted);
  }
  #dash .welcome-title {
    margin: 0 0 0.7rem;
    font-family: "Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif;
    font-size: clamp(2.5rem, 6.2vw, 4.1rem);
    font-weight: 600; letter-spacing: -0.01em; line-height: 1.02;
    text-wrap: balance;
    background: linear-gradient(115deg, var(--ink) 30%, var(--accent-2) 100%);
    -webkit-background-clip: text; background-clip: text; color: transparent;
  }
  #dash .welcome-sub {
    margin: 0 0 1.3rem; font-size: clamp(1rem, 1.6vw, 1.18rem); color: var(--ink-soft);
    line-height: 1.5; text-wrap: balance;
  }
  #dash .welcome-body { margin: 0 0 1.6rem; font-size: 0.95rem; color: var(--ink-soft); line-height: 1.65; }
  #dash .how-steps { list-style: none; margin: 0 0 1.8rem; padding: 0; display: flex; flex-direction: column; gap: 1rem; }
  #dash .how-steps li { display: flex; gap: 0.9rem; align-items: flex-start; }
  #dash .step-no {
    flex: none; width: 1.9rem; height: 1.9rem; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace; font-weight: 700; font-size: 0.85rem;
    background: var(--accent-soft); color: var(--accent);
    border: 1px solid var(--glass-border);
  }
  #dash .how-steps strong { color: var(--ink); }
  #dash .how-steps div { color: var(--ink-soft); font-size: 0.93rem; line-height: 1.55; padding-top: 0.15rem; }
  #dash .welcome-meta {
    font-size: 0.82rem; color: var(--ink-muted); font-variant-numeric: tabular-nums;
    padding-top: 1rem; margin-bottom: 1.3rem; border-top: 1px solid var(--hairline);
  }
  #dash .cta-btn {
    font: inherit; font-size: 0.95rem; font-weight: 700; cursor: pointer;
    padding: 0.75rem 1.5rem; border-radius: 999px; border: 1px solid rgba(255,255,255,0.5);
    background: linear-gradient(135deg, var(--accent), var(--accent-2)); color: #fff;
    box-shadow: 0 10px 26px rgba(36,81,163,0.38);
  }
  #dash .cta-btn:hover { filter: brightness(1.07); }
  #dash .cta-btn:focus-visible { outline: 2px solid var(--accent-2); outline-offset: 2px; }

  /* ---------- tracker panel shell ---------- */
  #dash .tracker-inner { max-width: clamp(320px, 94vw, 1360px); margin: 0 auto; padding: 0 clamp(1rem, 4vw, 3.5rem); }
  #dash .tracker-meta {
    margin: 0.2rem 0 1rem; font-size: 0.84rem; color: var(--ink-soft);
    font-variant-numeric: tabular-nums; text-align: center;
  }

  #dash .tracker-topbar {
    position: sticky; top: 66px; z-index: 25;
    display: flex; align-items: center; gap: 0.85rem; flex-wrap: wrap;
    padding: 0.75rem 1rem; border-radius: 18px; margin-bottom: 1.3rem;
  }
  #dash #searchInput {
    flex: 1 1 260px; min-width: 0;
    background: rgba(255,255,255,0.5); color: var(--ink);
    border: 1px solid var(--glass-border); border-radius: 11px;
    padding: 0.6rem 0.9rem; font-size: 0.9rem; font-family: inherit;
  }
  :root[data-theme="dark"] #dash #searchInput, @media (prefers-color-scheme: dark) { }
  #dash #searchInput::placeholder { color: var(--ink-muted); }
  #dash #searchInput:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
  #dash .refresh-row { display: flex; align-items: center; gap: 0.65rem; flex: none; flex-wrap: wrap; }
  #dash .refresh-btn {
    font: inherit; font-size: 0.85rem; font-weight: 700; cursor: pointer;
    padding: 0.55rem 1rem; border-radius: 11px;
    border: 1px solid var(--glass-border); background: linear-gradient(135deg, var(--accent), var(--accent-2));
    color: #fff; white-space: nowrap;
  }
  #dash .refresh-btn:hover:not(:disabled) { filter: brightness(1.08); }
  #dash .refresh-btn:focus-visible { outline: 2px solid var(--accent-2); outline-offset: 2px; }
  #dash .refresh-btn:disabled { cursor: default; opacity: 0.55; filter: none; }
  #dash .refresh-status { font-size: 0.78rem; color: var(--ink-muted); }

  /* ---------- review clock ---------- */
  #dash .review-clock { border-radius: 18px; padding: 1rem 1.2rem 1.15rem; margin-bottom: 1.1rem; }
  #dash .clock-caption {
    margin: 0 0 0.6rem;
    font-family: "American Typewriter", "Courier New", ui-monospace, monospace;
    font-size: 0.64rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;
    color: var(--ink-muted);
  }
  #dash .clock-line { position: relative; display: flex; justify-content: space-between; align-items: flex-start; padding-top: 7px; }
  #dash .clock-line::before { content: ""; position: absolute; left: 5px; right: 5px; top: 7px; height: 1px; background: var(--hairline); }
  #dash .clock-point { position: relative; z-index: 1; display: flex; flex-direction: column; align-items: center; gap: 0.4rem; flex: 1; }
  #dash .clock-dot { width: 10px; height: 10px; border-radius: 50%; background: transparent; border: 2px solid var(--ink-muted); }
  #dash .clock-point.is-done .clock-dot { background: var(--accent); border-color: var(--accent); }
  #dash .clock-point.is-today .clock-dot { background: var(--sig-critical); border-color: var(--sig-critical); box-shadow: 0 0 0 4px var(--sig-critical-bg); }
  #dash .clock-point.is-next .clock-dot { background: transparent; border-color: var(--sig-notable); box-shadow: 0 0 0 3px var(--sig-notable-bg); }
  #dash .clock-label { font-family: "American Typewriter", "Courier New", ui-monospace, monospace; font-size: 0.66rem; text-align: center; color: var(--ink-soft); line-height: 1.4; }
  #dash .clock-label time { display: block; color: var(--ink-muted); font-variant-numeric: tabular-nums; }
  #dash .clock-point.is-today .clock-label { color: var(--sig-critical); font-weight: 700; }
  #dash .clock-point.is-today .clock-label time { color: var(--sig-critical); }

  /* ---------- stat strip ---------- */
  #dash .stat-strip { margin: 0 0 1.1rem; display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.85rem; }
  #dash .stat-tile { border-radius: 16px; padding: 0.95rem 1.05rem; min-width: 0; }
  #dash .stat-label { margin: 0 0 0.35rem; font-size: 0.68rem; font-weight: 700; letter-spacing: 0.09em; text-transform: uppercase; color: var(--ink-muted); }
  #dash .stat-value { margin: 0; font-size: 1.65rem; font-weight: 700; line-height: 1.1; font-variant-numeric: tabular-nums; color: var(--ink); }
  #dash .stat-value--text { font-size: 1.15rem; font-family: "Iowan Old Style", Palatino, Georgia, serif; }
  #dash .stat-sub { margin: 0.3rem 0 0; font-size: 0.76rem; color: var(--ink-muted); font-variant-numeric: tabular-nums; }
  #dash .stat-tile--critical .stat-value { color: var(--sig-critical); }
  #dash .comp-bar { display: flex; height: 8px; border-radius: 4px; overflow: hidden; background: var(--hairline); margin-top: 0.5rem; }
  #dash .comp-seg { height: 100%; }
  #dash .comp-seg + .comp-seg { margin-left: 2px; }
  #dash .comp-legend { margin-top: 0.55rem; display: flex; flex-direction: column; gap: 0.2rem; font-size: 0.72rem; color: var(--ink-soft); }
  #dash .comp-legend-row { display: flex; align-items: center; gap: 0.4rem; }
  #dash .comp-swatch { width: 8px; height: 8px; border-radius: 2px; flex: none; }
  #dash .comp-legend-count { margin-left: auto; font-variant-numeric: tabular-nums; color: var(--ink-muted); }

  /* ---------- chips + sort ---------- */
  #dash .control-row--chipsort { display: flex; align-items: center; gap: 0.8rem; flex-wrap: wrap; margin-bottom: 0.9rem; }
  #dash .control-row--chips { display: flex; flex-wrap: wrap; gap: 0.45rem; flex: 1; }
  #dash .sort-toggle { display: flex; border-radius: 11px; overflow: hidden; flex: none; padding: 2px; }
  #dash .sort-btn {
    font-family: inherit; font-size: 0.8rem; font-weight: 600; letter-spacing: 0.01em;
    color: var(--ink-soft); background: transparent; border: none; border-radius: 9px;
    padding: 0.5rem 0.85rem; cursor: pointer;
  }
  #dash .sort-btn.is-active { background: linear-gradient(135deg, var(--accent), var(--accent-2)); color: #fff; }
  #dash .sort-btn:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }

  #dash .chip {
    font-family: inherit; font-size: 0.78rem; font-weight: 600;
    color: var(--ink-soft); background: var(--card-fill);
    border: 1px solid var(--card-border); border-radius: 999px;
    padding: 0.36rem 0.75rem 0.36rem 0.6rem; cursor: pointer; white-space: nowrap;
    display: inline-flex; align-items: center; gap: 0.4rem;
    box-shadow: var(--card-shadow);
  }
  #dash .chip-dot { width: 7px; height: 7px; border-radius: 50%; flex: none; background: var(--chip-color, var(--ink-muted)); }
  #dash .chip .chip-count { color: var(--ink-muted); font-variant-numeric: tabular-nums; }
  #dash .chip.is-active { background: var(--accent-soft); border-color: var(--accent); color: var(--ink); }
  #dash .chip:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }

  #dash .result-count { margin: 0 0 0.6rem; font-size: 0.78rem; color: var(--ink-muted); font-variant-numeric: tabular-nums; }

  /* ---------- tracker body: main + vertical signal rail ---------- */
  #dash .tracker-body { display: grid; grid-template-columns: 1fr auto; gap: 1.6rem; align-items: start; }
  #dash .tracker-main { min-width: 0; }
  #dash .feed { display: flex; flex-direction: column; gap: 0.7rem; }
  #dash .empty-state { margin: 2rem auto; color: var(--ink-muted); font-size: 0.9rem; text-align: center; }

  #dash .signal-rail {
    position: sticky; top: 140px;
    width: 84px; height: 380px; flex: none;
    display: flex; flex-direction: column; align-items: center; justify-content: space-between;
    padding: 1.1rem 0.5rem; border-radius: 22px; gap: 0.6rem;
  }
  #dash .rail-label {
    font-family: "American Typewriter", ui-monospace, monospace;
    font-size: 0.6rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
    color: var(--ink-muted); text-align: center; line-height: 1.35;
  }
  #dash .slider-wrap { position: relative; width: 40px; height: 260px; display: flex; align-items: center; justify-content: center; }
  #dash #scoreSlider {
    position: absolute; top: 50%; left: 50%;
    width: 260px; height: 40px;
    transform: translate(-50%, -50%) rotate(-90deg);
    -webkit-appearance: none; appearance: none;
    background: transparent; margin: 0; cursor: pointer;
  }
  #dash #scoreSlider::-webkit-slider-runnable-track {
    height: 8px; border-radius: 999px;
    background: linear-gradient(to right, #ffffff 0%, var(--sig-critical) 100%);
    box-shadow: inset 0 0 0 1px rgba(0,0,0,0.08);
  }
  #dash #scoreSlider::-moz-range-track {
    height: 8px; border-radius: 999px;
    background: linear-gradient(to right, #ffffff 0%, var(--sig-critical) 100%);
    box-shadow: inset 0 0 0 1px rgba(0,0,0,0.08);
  }
  #dash #scoreSlider::-webkit-slider-thumb {
    -webkit-appearance: none; appearance: none; margin-top: -7px;
    width: 22px; height: 22px; border-radius: 50%;
    background: var(--thumb-color, #ffffff);
    border: 2px solid rgba(255,255,255,0.95);
    box-shadow: 0 2px 10px rgba(0,0,0,0.28), 0 0 0 1px rgba(0,0,0,0.1);
    cursor: pointer;
  }
  #dash #scoreSlider::-moz-range-thumb {
    width: 22px; height: 22px; border-radius: 50%; border: 2px solid rgba(255,255,255,0.95);
    background: var(--thumb-color, #ffffff);
    box-shadow: 0 2px 10px rgba(0,0,0,0.28), 0 0 0 1px rgba(0,0,0,0.1);
    cursor: pointer;
  }
  #dash .rail-value {
    font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace; font-weight: 700; font-size: 1.05rem;
    color: var(--ink); background: var(--card-fill); border: 1px solid var(--card-border);
    border-radius: 10px; padding: 0.2rem 0.55rem; min-width: 2.1rem; text-align: center;
  }

  @media (max-width: 880px) {
    #dash .tracker-body { grid-template-columns: 1fr; }
    #dash .signal-rail {
      position: static; width: 100%; height: auto; flex-direction: row; justify-content: flex-start;
      padding: 0.85rem 1.1rem; margin-bottom: 1.1rem;
    }
    #dash .rail-label { writing-mode: horizontal-tb; text-align: left; }
    #dash .slider-wrap { flex: 1; width: auto; height: 40px; }
    #dash #scoreSlider { position: static; width: 100%; height: 8px; transform: none; }
  }

  /* ---------- feed cards ---------- */
  #dash .card {
    display: flex; background: var(--card-fill);
    border: 1px solid var(--card-border); border-radius: 16px;
    box-shadow: var(--card-shadow); overflow: hidden;
  }
  #dash .card-stripe { width: 4px; flex: none; background: var(--sig-routine); }
  #dash .card--critical .card-stripe { background: var(--sig-critical); }
  #dash .card--notable .card-stripe { background: var(--sig-notable); }
  #dash .card-thumb { width: 96px; height: 96px; flex: none; object-fit: cover; background: var(--hairline); }
  @media (max-width: 560px) { #dash .card-thumb { width: 72px; height: 72px; } }
  #dash .card-body { padding: 0.95rem 1.1rem 1rem; min-width: 0; flex: 1; }
  #dash .card-top { display: flex; gap: 0.85rem; align-items: flex-start; }
  #dash .score-badge {
    position: relative; flex: none; width: 2.6rem; height: 2.6rem;
    display: flex; align-items: center; justify-content: center;
    border-radius: 50%; font-weight: 700; font-size: 1.05rem;
    font-variant-numeric: tabular-nums; font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace;
    background: var(--sig-routine-bg); color: var(--sig-routine);
    border: 1.5px solid currentColor;
    box-shadow: 0 0 0 3px rgba(255,255,255,0.5), 0 0 0 4px currentColor;
    transform: rotate(var(--stamp-rot, -3deg));
    transition: transform 0.3s cubic-bezier(.2,.8,.3,1.1);
  }
  #dash .card:hover .score-badge { transform: rotate(0deg) scale(1.05); }
  #dash .score-badge::before {
    content: ""; position: absolute; inset: -1px; border-radius: 50%;
    background: radial-gradient(circle at 32% 28%, currentColor 0%, transparent 42%), radial-gradient(circle at 68% 74%, currentColor 0%, transparent 38%);
    opacity: 0.12; pointer-events: none;
  }
  #dash .card--critical .score-badge { background: var(--sig-critical-bg); color: var(--sig-critical); }
  #dash .card--notable .score-badge { background: var(--sig-notable-bg); color: var(--sig-notable); }
  #dash .card-heading { min-width: 0; flex: 1; }
  #dash .card-title { font-size: 0.98rem; font-weight: 600; text-decoration: none; color: var(--ink); display: block; }
  #dash .card-title:hover { color: var(--accent); text-decoration: underline; }
  #dash .card-title:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  #dash .card-meta { margin: 0.3rem 0 0; font-size: 0.78rem; color: var(--ink-muted); display: flex; align-items: center; gap: 0.45rem; flex-wrap: wrap; }
  #dash .source-pill { font-weight: 600; color: var(--ink-soft); }
  #dash .card-meta time { font-variant-numeric: tabular-nums; }
  #dash .card-meta .dot { opacity: 0.6; }
  #dash .lock-badge { font-size: 0.68rem; font-weight: 700; letter-spacing: 0.02em; color: var(--sig-notable); background: var(--sig-notable-bg); border-radius: 4px; padding: 0.1rem 0.4rem; }

  #dash .tag-row { margin: 0.55rem 0 0; display: flex; flex-wrap: wrap; gap: 0.35rem; }
  #dash .tag { font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace; font-size: 0.68rem; padding: 0.14rem 0.42rem; border-radius: 4px; background: var(--hairline); color: var(--ink-soft); }
  #dash .tag--critical { color: var(--sig-critical); background: var(--sig-critical-bg); }
  #dash .tag--player { color: var(--accent); background: var(--accent-soft); }
  #dash .tag--sector { color: var(--ink-soft); background: var(--hairline); }

  #dash .card-summary { margin: 0.6rem 0 0; font-size: 0.86rem; color: var(--ink-soft); line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
  #dash .card-link { display: inline-block; margin-top: 0.6rem; font-size: 0.78rem; font-weight: 600; text-decoration: none; }
  #dash .card-link:hover { text-decoration: underline; }

  #dash .dash-footer { margin: 2.25rem 0 0; padding: 1.1rem 0 0; border-top: 1px solid var(--hairline); font-size: 0.76rem; color: var(--ink-muted); line-height: 1.6; }
  #dash .dash-footer p { margin: 0 0 0.4rem; }
  #dash .dash-footer code { font-family: "SF Mono", ui-monospace, Menlo, Consolas, monospace; }

  @media (max-width: 720px) {
    #dash .stat-strip { grid-template-columns: repeat(2, 1fr); }
    #dash .tracker-topbar { top: 58px; }
    #dash .clock-label { font-size: 0.58rem; }
  }
  @media (prefers-reduced-motion: no-preference) {
    #dash .welcome-card, #dash .stat-tile { animation: dashRiseIn 0.5s cubic-bezier(.2,.7,.3,1) both; }
    #dash .stat-tile:nth-child(1) { animation-delay: 0.03s; }
    #dash .stat-tile:nth-child(2) { animation-delay: 0.08s; }
    #dash .stat-tile:nth-child(3) { animation-delay: 0.13s; }
    #dash .stat-tile:nth-child(4) { animation-delay: 0.18s; }
  }
  @keyframes dashRiseIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
  @media (prefers-reduced-motion: reduce) { #dash * { transition: none !important; animation: none !important; scroll-behavior: auto !important; } }
</style>

<div class="dash" id="dash">
  <div class="bg-wash" aria-hidden="true"><span></span><span></span><span></span><span></span></div>
  <a class="skip-link" href="#feed">Skip to dispatches</a>

  <nav class="tab-switch glass" role="tablist" aria-label="Sections">
    <span class="tab-indicator" aria-hidden="true"></span>
    <button type="button" class="tab-btn is-active" role="tab" aria-selected="true" id="tab-welcome" data-tab="welcome">Welcome</button>
    <button type="button" class="tab-btn" role="tab" aria-selected="false" id="tab-tracker" data-tab="tracker">Tracker</button>
  </nav>

  <section id="panel-welcome" class="panel panel-welcome" role="tabpanel" aria-labelledby="tab-welcome">
    <div class="welcome-card glass">
      <p class="eyebrow">Scientika &middot; Trade Intelligence</p>
      <h1 class="welcome-title">The USMCA Watcher</h1>
      <p class="welcome-sub">A live monitor for the USMCA / T&#8209;MEC / CUSMA joint review &mdash; 2026 through the 2036 sunset horizon.</p>
      <p class="welcome-body">Every six hours, or the moment you ask, it pulls fresh notices from the Federal Register, bills from Congress.gov, and headlines from Google News and official sources across the U.S., Mexico, and Canada. Each dispatch gets scored for signal, checked against everything already seen, and only what's new and relevant reaches the feed.</p>
      <ol class="how-steps">
        <li><span class="step-no">1</span><div><strong>Watch.</strong> Polls the Federal Register, Congress.gov, and news feeds from all three countries, every 6 hours or on demand.</div></li>
        <li><span class="step-no">2</span><div><strong>Score.</strong> Ranks each dispatch by signal &mdash; procedural moves, named principals like Greer, Ebrard, and Carney, and sector keywords like autos, steel, and dairy.</div></li>
        <li><span class="step-no">3</span><div><strong>Filter out noise.</strong> De-duplicates against everything already seen, so the feed only ever shows what's new.</div></li>
        <li><span class="step-no">4</span><div><strong>Deliver.</strong> Rebuilds the dashboard you're about to open, sortable by signal or by date.</div></li>
      </ol>
      <p class="welcome-meta"><span id="welcomeCount">0</span> dispatches tracked so far &middot; refreshed every 6 hours</p>
      <button type="button" class="cta-btn" id="openTrackerBtn">Open the tracker &rarr;</button>
    </div>
  </section>

  <section id="panel-tracker" class="panel panel-tracker" role="tabpanel" aria-labelledby="tab-tracker" hidden>
    <div class="tracker-inner">
      <p class="tracker-meta">Generated __GENERATED__ &middot; <span id="itemCount">0</span> dispatches &middot; <span id="rangeText">&mdash;</span></p>

      <div class="tracker-topbar glass">
        <input type="search" id="searchInput" placeholder="Search dispatches by title or summary&hellip;" aria-label="Search dispatches">
        <div class="refresh-row">
          <button type="button" id="refreshBtn" class="refresh-btn">&#8635; Refresh now</button>
          <span id="refreshStatus" class="refresh-status" role="status" aria-live="polite"></span>
        </div>
      </div>

      <section class="review-clock glass" aria-label="Joint review timeline">
        <p class="clock-caption">Article 34.7.4 &middot; annual joint review &middot; through Jul 2036</p>
        <div class="clock-line">
          <div class="clock-point is-done"><span class="clock-dot"></span><span class="clock-label">Round 1<time>May 28</time></span></div>
          <div class="clock-point is-done"><span class="clock-dot"></span><span class="clock-label">Round 2<time>Jun 16</time></span></div>
          <div class="clock-point is-today"><span class="clock-dot"></span><span class="clock-label">Today<time>__TODAY__</time></span></div>
          <div class="clock-point is-next"><span class="clock-dot"></span><span class="clock-label">Round 3<time>wk of Jul 20</time></span></div>
          <div class="clock-point is-horizon"><span class="clock-dot"></span><span class="clock-label">Sunset horizon<time>Jul 2036</time></span></div>
        </div>
      </section>

      <section class="stat-strip glass-group" aria-label="Summary">
        <div class="stat-tile glass"><p class="stat-label">Dispatches</p><p class="stat-value" id="statTotal">0</p><p class="stat-sub" id="statRange">&nbsp;</p></div>
        <div class="stat-tile glass stat-tile--critical"><p class="stat-label">Critical signal</p><p class="stat-value" id="statCritical">0</p><p class="stat-sub">score &ge; 10</p></div>
        <div class="stat-tile glass"><p class="stat-label">Most active principal</p><p class="stat-value stat-value--text" id="statPlayer">&mdash;</p><p class="stat-sub" id="statPlayerCount">&nbsp;</p></div>
        <div class="stat-tile glass stat-tile--composition"><p class="stat-label">Source mix</p><div class="comp-bar" id="compBar" role="img" aria-label="Source composition"></div><div class="comp-legend" id="compLegend"></div></div>
      </section>

      <div class="control-row--chipsort">
        <div class="control-row--chips" id="sourceChips"></div>
        <div class="sort-toggle glass" role="group" aria-label="Sort order">
          <button type="button" class="sort-btn is-active" data-sort="score">Signal</button>
          <button type="button" class="sort-btn" data-sort="date">Newest</button>
        </div>
      </div>

      <div class="tracker-body">
        <div class="tracker-main">
          <p class="result-count" id="resultCount"></p>
          <section class="feed" id="feed" aria-live="polite"></section>
          <p class="empty-state" id="emptyState" hidden>No dispatches match these filters.</p>
          <footer class="dash-footer">
            <p>Sources: Federal Register API &middot; Google News (Boolean queries + <code>site:</code> feeds) &middot; USTR &middot; Global Affairs Canada &middot; Diario Oficial de la Federaci&oacute;n &middot; CSIS &middot; Rethink Trade &middot; Inside U.S. Trade (headlines).</p>
            <p>This is a monitoring aid, not a source of truth &mdash; open the linked primary document before acting on anything here.</p>
          </footer>
        </div>

        <aside class="signal-rail glass" aria-label="Minimum signal filter">
          <span class="rail-label">Min<br>Signal</span>
          <div class="slider-wrap">
            <input type="range" id="scoreSlider" min="0" max="14" step="1" value="0" aria-label="Minimum signal">
          </div>
          <output id="scoreSliderVal" class="rail-value" for="scoreSlider">0</output>
        </aside>
      </div>
    </div>
  </section>
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
    document.getElementById("welcomeCount").textContent = DATA.length;

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

  function setTab(name) {
    const isWelcome = name === "welcome";
    document.getElementById("panel-welcome").hidden = !isWelcome;
    document.getElementById("panel-tracker").hidden = isWelcome;
    document.querySelectorAll(".tab-btn").forEach(b => {
      const active = b.dataset.tab === name;
      b.classList.toggle("is-active", active);
      b.setAttribute("aria-selected", String(active));
    });
    const indicator = document.querySelector(".tab-indicator");
    if (indicator) indicator.style.transform = isWelcome ? "translateX(0%)" : "translateX(100%)";
    try { localStorage.setItem("usmca-tab", name); } catch (e) {}
  }

  function updateThumbColor(slider) {
    const min = Number(slider.min) || 0, max = Number(slider.max) || 1;
    const ratio = Math.min(1, Math.max(0, (Number(slider.value) - min) / (max - min)));
    const r = Math.round(255 + (194 - 255) * ratio);
    const g = Math.round(255 + (58 - 255) * ratio);
    const b = Math.round(255 + (46 - 255) * ratio);
    slider.style.setProperty("--thumb-color", `rgb(${r},${g},${b})`);
  }

  function init() {
    computeStats();
    buildChips();

    const maxScore = Math.max(0, ...DATA.map(d => d.score));
    const slider = document.getElementById("scoreSlider");
    slider.max = String(maxScore);
    updateThumbColor(slider);
    slider.addEventListener("input", () => {
      state.minScore = Number(slider.value);
      document.getElementById("scoreSliderVal").textContent = slider.value;
      updateThumbColor(slider);
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

    document.querySelectorAll(".tab-btn").forEach(b => b.addEventListener("click", () => setTab(b.dataset.tab)));
    document.getElementById("openTrackerBtn").addEventListener("click", () => setTab("tracker"));
    let initialTab = "welcome";
    try { initialTab = localStorage.getItem("usmca-tab") || "welcome"; } catch (e) {}
    setTab(initialTab);

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
