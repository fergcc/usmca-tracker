#!/usr/bin/env python3
"""
USMCA / T-MEC / CUSMA Negotiation Tracker
=========================================

A dependency-light, config-driven intelligence monitor for the 2026-2036
USMCA annual joint-review cycle. It polls machine-readable sources
(Google News RSS, the Federal Register JSON API, and per-outlet site feeds),
filters against your Boolean intelligence queries, de-duplicates against a
local SQLite store, scores each item for signal, and pushes only *new* items
to you (macOS desktop notification + a dated Markdown briefing + a JSONL log,
optionally email).

Run it once (default) or on a schedule (launchd / cron) for near-real-time
monitoring. See README.md for setup and honest limitations.

Author: built for Scientika / STRATORB.  Public data only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import textwrap
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# --- Third-party (see requirements.txt): feedparser is strongly recommended;
#     we degrade gracefully to stdlib XML parsing if it is missing. ---
try:
    import feedparser  # type: ignore
    HAVE_FEEDPARSER = True
except Exception:  # pragma: no cover
    HAVE_FEEDPARSER = False
    import xml.etree.ElementTree as ET

try:
    import yaml  # type: ignore
    HAVE_YAML = True
except Exception:  # pragma: no cover
    HAVE_YAML = False


HERE = Path(__file__).resolve().parent
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "USMCA-Tracker/1.0 (+scientika.mx research monitor)"
)
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
FEDREG_API = "https://www.federalregister.gov/api/v1/documents.json"
CONGRESS_API = "https://api.congress.gov/v3/bill"
CONGRESS_BILL_SLUGS = {
    "hr": "house-bill",
    "s": "senate-bill",
    "hres": "house-resolution",
    "sres": "senate-resolution",
    "hjres": "house-joint-resolution",
    "sjres": "senate-joint-resolution",
    "hconres": "house-concurrent-resolution",
    "sconres": "senate-concurrent-resolution",
}


# --------------------------------------------------------------------------- #
#  Data model
# --------------------------------------------------------------------------- #
@dataclass
class Item:
    uid: str
    title: str
    url: str
    source: str          # human label of the query/feed that surfaced it
    origin: str          # "google_news" | "federal_register" | "site_feed"
    published: str       # ISO string (best-effort)
    summary: str = ""
    score: int = 0
    tags: list[str] = field(default_factory=list)
    image_url: str = ""


# --------------------------------------------------------------------------- #
#  Config
# --------------------------------------------------------------------------- #
DEFAULT_CONFIG: dict[str, Any] = {
    "notifications": {
        "desktop": True,          # macOS osascript banner
        "log_markdown": True,     # dated brief in ./briefings/
        "log_jsonl": True,        # append-only machine log ./data/items.jsonl
        "email": {
            "enabled": False,
            "smtp_host": "",
            "smtp_port": 587,
            "username": "",
            "password_env": "USMCA_SMTP_PASSWORD",  # NEVER hardcode a password
            "from": "",
            "to": ["jj@scientika.mx"],
            # Only email items at/above this score (keeps your inbox clean):
            "min_score": 3,
        },
    },
    # Words that raise an item's signal score. Tune freely.
    "scoring": {
        "critical": [
            "joint review", "annual review", "sunset", "concludes", "concluded",
            "third round", "fourth round", "public comment", "comment period",
            "signed", "notice", "tariff", "rules of origin", "termination",
            "withdraw", "renewal", "text-based", "legal text",
        ],
        "players": [
            "Greer", "Ebrard", "Carney", "Sidhu", "Goettman", "Sheinbaum",
        ],
        "sectors": [
            "EV", "BYD", "battery", "automotive", "steel", "aluminum",
            "dairy", "biotech corn", "energy", "circumvention", "nearshoring",
            "china", "chinese",
        ],
    },
    # Boolean intelligence queries. `google_news` uses Google News search
    # syntax (space = AND, OR = OR, "..." = phrase). The `boolean` field is the
    # canonical Feedly/Inoreader form, kept for reference & re-use.
    "queries": {
        "macro": {
            "label": "Macro & Geopolitical Review",
            "google_news": '("USMCA" OR "CUSMA" OR "T-MEC") ("joint review" OR sunset OR "annual review" OR Greer OR Ebrard OR Carney)',
            "boolean": '("USMCA" OR "CUSMA" OR "T-MEC") AND ("joint review" OR "sunset" OR "annual review" OR "Greer" OR "Ebrard" OR "Carney")',
        },
        "roundtables": {
            "label": "Bilateral Roundtables (Sectoral Friction)",
            "google_news": '("USMCA" OR "T-MEC" OR "CUSMA") ("rules of origin" OR "rapid response" OR "biotech corn" OR dairy OR steel OR aluminum)',
            "boolean": '("USMCA" OR "T-MEC" OR "CUSMA") AND ("rules of origin" OR "rapid response labor" OR "biotech corn" OR "dairy tariffs" OR "steel" OR "aluminum")',
        },
        "china": {
            "label": "China Circumvention & Nearshoring",
            "google_news": '("USMCA" OR "T-MEC") (China OR EV OR BYD OR circumvention OR nearshoring)',
            "boolean": '("USMCA" OR "T-MEC") AND ("China" OR "EV" OR "byd" OR "circumvention" OR "nearshoring")',
        },
    },
    # Per-outlet feeds: same Google News pipe, restricted to one domain.
    # Headlines/snippets are public; full text of paywalled outlets
    # (e.g. Inside U.S. Trade) still requires YOUR subscription to open.
    "site_feeds": [
        {"label": "Inside U.S. Trade (headlines only – full text = your login)",
         "query": 'USMCA OR "T-MEC" site:insidetrade.com'},
        {"label": "CSIS", "query": 'USMCA OR "joint review" site:csis.org'},
        {"label": "Rethink Trade", "query": 'USMCA OR "T-MEC" site:rethinktrade.org'},
        {"label": "USTR (official)", "query": 'USMCA site:ustr.gov'},
        {"label": "Diario Oficial de la Federación (MX)", "query": 'T-MEC OR USMCA site:dof.gob.mx'},
        {"label": "Global Affairs Canada", "query": 'CUSMA OR USMCA site:international.gc.ca'},
    ],
    # Federal Register: free JSON API, no key. Terms searched via conditions[term].
    "federal_register": {
        "enabled": True,
        "per_page": 20,
        "terms": [
            "USMCA",
            "United States-Mexico-Canada Agreement",
            "rules of origin automotive",
        ],
    },
    # Congress.gov: free JSON API, requires a key (https://api.congress.gov/sign-up/).
    # NEVER put the key here. Export it in your shell / launchd instead:
    #   export CONGRESS_API_KEY="your-key"
    # The API has no full-text search, so this pulls the most recently
    # updated bills and filters locally by title match against `terms`.
    "congress": {
        "enabled": True,
        "per_page": 250,
        "max_pages": 80,
        "api_key_env": "CONGRESS_API_KEY",
        "terms": [
            "USMCA",
            "United States-Mexico-Canada Agreement",
            "CUSMA",
            "T-MEC",
        ],
    },
    # Local safety-net filter applied to Federal Register + raw feeds so a
    # broad term doesn't drag in unrelated notices.
    "match": {
        "require_any": [
            "USMCA", "CUSMA", "T-MEC", "United States-Mexico-Canada",
            "United States-Mexico-Canada Agreement",
        ],
    },
    "limits": {
        "max_items_per_source": 40,
        "http_timeout_seconds": 25,
    },
    # Article thumbnails: reads the og:image (falls back to twitter:image) meta
    # tag off each new item's own page. Skipped for paywalled sources out of
    # respect for their ToS (headlines/snippets only, same policy as elsewhere).
    "images": {
        "enabled": True,
        "timeout_seconds": 10,
        "max_html_bytes": 200_000,
        "skip_sources": [
            "Inside U.S. Trade",
        ],
    },
}


def load_config(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return DEFAULT_CONFIG
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        if not HAVE_YAML:
            sys.exit("config is YAML but PyYAML is not installed. `pip install pyyaml` or use JSON config.")
        user_cfg = yaml.safe_load(text) or {}
    else:
        user_cfg = json.loads(text)
    return _deep_merge(DEFAULT_CONFIG, user_cfg)


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


# --------------------------------------------------------------------------- #
#  HTTP
# --------------------------------------------------------------------------- #
def http_get(url: str, timeout: int) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


_OG_IMAGE_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_OG_IMAGE_RE_SWAPPED = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\']',
    re.IGNORECASE,
)


def fetch_og_image(url: str, timeout: int, max_bytes: int) -> str:
    """Best-effort og:image (falling back to twitter:image) off an article's
    own <head>. Only reads the first `max_bytes` of the response since the
    tag is always near the top — avoids downloading full article pages."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(max_bytes)
    html = raw.decode("utf-8", errors="ignore")
    m = _OG_IMAGE_RE.search(html) or _OG_IMAGE_RE_SWAPPED.search(html)
    if not m:
        return ""
    return urllib.parse.urljoin(url, m.group(1).strip())


# --------------------------------------------------------------------------- #
#  Parsing helpers
# --------------------------------------------------------------------------- #
def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def _uid(url: str, title: str) -> str:
    key = (url or "") + "|" + (title or "")
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def parse_rss(raw: bytes, source_label: str, origin: str, limit: int) -> list[Item]:
    items: list[Item] = []
    if HAVE_FEEDPARSER:
        feed = feedparser.parse(raw)
        entries = feed.entries[:limit]
        for e in entries:
            url = getattr(e, "link", "") or ""
            title = _clean(getattr(e, "title", ""))
            summary = _clean(getattr(e, "summary", ""))
            published = getattr(e, "published", "") or getattr(e, "updated", "")
            items.append(Item(_uid(url, title), title, url, source_label, origin, published, summary))
    else:  # stdlib fallback
        root = ET.fromstring(raw)
        for node in root.iter("item"):
            title = _clean((node.findtext("title") or ""))
            url = (node.findtext("link") or "").strip()
            summary = _clean(node.findtext("description") or "")
            published = (node.findtext("pubDate") or "").strip()
            items.append(Item(_uid(url, title), title, url, source_label, origin, published, summary))
            if len(items) >= limit:
                break
    return items


def fetch_google_news(query: str, label: str, origin: str, timeout: int, limit: int) -> list[Item]:
    url = GOOGLE_NEWS_RSS.format(q=urllib.parse.quote(query))
    raw = http_get(url, timeout)
    return parse_rss(raw, label, origin, limit)


def fetch_federal_register(term: str, per_page: int, timeout: int) -> list[Item]:
    params = {
        "per_page": per_page,
        "order": "newest",
        "conditions[term]": term,
    }
    url = FEDREG_API + "?" + urllib.parse.urlencode(params)
    raw = http_get(url, timeout)
    data = json.loads(raw.decode("utf-8"))
    out: list[Item] = []
    for r in data.get("results", []):
        title = _clean(r.get("title", ""))
        link = r.get("html_url", "")
        summary = _clean(r.get("abstract", "") or "")
        published = r.get("publication_date", "")
        doc_type = r.get("type", "")
        agencies = ", ".join(a.get("name", "") for a in r.get("agencies", []) if isinstance(a, dict))
        label = f"Federal Register [{term}]"
        it = Item(_uid(link, title), title, link, label, "federal_register", published, summary)
        it.tags = [t for t in (doc_type, agencies) if t]
        out.append(it)
    return out


def fetch_congress_bills(api_key: str, terms: list[str], per_page: int, timeout: int, max_pages: int = 80) -> list[Item]:
    """Congress.gov has no full-text search, so a "recently updated" pull is
    close to random with respect to subject (most touches are routine
    procedural actions). Instead this pages through every bill in the
    current congress and filters locally by title match against `terms`.
    """
    if not api_key:
        raise RuntimeError("CONGRESS_API_KEY is not set (export it in your shell / launchd)")
    congress_num = (dt.datetime.now().year - 1789) // 2 + 1
    terms_l = [t.lower() for t in terms]
    out: list[Item] = []
    offset = 0
    for _ in range(max_pages):
        params = {"api_key": api_key, "format": "json", "limit": per_page, "offset": offset}
        url = f"{CONGRESS_API}/{congress_num}?" + urllib.parse.urlencode(params)
        try:
            raw = http_get(url, timeout)
            data = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            print(f"[warn] Congress.gov page at offset {offset} failed: {exc}", file=sys.stderr)
            break
        bills = data.get("bills", [])
        if not bills:
            break
        for b in bills:
            title = _clean(b.get("title", ""))
            if not any(t in title.lower() for t in terms_l):
                continue
            bill_type = (b.get("type") or "").lower()
            number = b.get("number")
            slug = CONGRESS_BILL_SLUGS.get(bill_type, bill_type)
            link = f"https://www.congress.gov/bill/{congress_num}th-congress/{slug}/{number}"
            latest = b.get("latestAction", {}) or {}
            published = latest.get("actionDate", "")
            summary = _clean(latest.get("text", ""))
            display_title = f"{bill_type.upper()} {number}: {title}"
            it = Item(_uid(link, display_title), display_title, link, "Congress.gov", "congress", published, summary)
            chamber = b.get("originChamber", "")
            if chamber:
                it.tags = [chamber]
            out.append(it)
        if len(bills) < per_page:
            break
        offset += per_page
    return out


# --------------------------------------------------------------------------- #
#  Filtering & scoring
# --------------------------------------------------------------------------- #
def passes_local_filter(item: Item, require_any: list[str]) -> bool:
    if item.origin == "google_news":
        return True  # Google already applied the Boolean query server-side
    hay = (item.title + " " + item.summary).lower()
    return any(term.lower() in hay for term in require_any)


def score_item(item: Item, scoring: dict[str, list[str]]) -> None:
    hay = (item.title + " " + item.summary).lower()
    score = 0
    tags = list(item.tags)
    for kw in scoring.get("critical", []):
        if kw.lower() in hay:
            score += 3
            tags.append(f"!{kw}")
    for kw in scoring.get("players", []):
        if kw.lower() in hay:
            score += 2
            tags.append(f"@{kw}")
    for kw in scoring.get("sectors", []):
        if kw.lower() in hay:
            score += 1
            tags.append(f"#{kw}")
    if item.origin == "federal_register":
        score += 3  # primary/legal source — always high signal
    elif item.origin == "congress":
        score += 2  # primary legislative source — real but not yet binding
    item.score = score
    # de-dupe tags, keep order
    seen: set[str] = set()
    item.tags = [t for t in tags if not (t in seen or seen.add(t))]


# --------------------------------------------------------------------------- #
#  State (SQLite dedupe)
# --------------------------------------------------------------------------- #
def open_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.execute(
        """CREATE TABLE IF NOT EXISTS seen (
               uid TEXT PRIMARY KEY,
               title TEXT, url TEXT, source TEXT, origin TEXT,
               published TEXT, summary TEXT, score INTEGER,
               tags TEXT, first_seen TEXT
           )"""
    )
    con.commit()
    return con


def is_new(con: sqlite3.Connection, uid: str) -> bool:
    cur = con.execute("SELECT 1 FROM seen WHERE uid = ?", (uid,))
    return cur.fetchone() is None


def remember(con: sqlite3.Connection, item: Item) -> None:
    con.execute(
        "INSERT OR IGNORE INTO seen VALUES (?,?,?,?,?,?,?,?,?,?)",
        (item.uid, item.title, item.url, item.source, item.origin,
         item.published, item.summary, item.score, ",".join(item.tags),
         dt.datetime.now().isoformat(timespec="seconds")),
    )


# --------------------------------------------------------------------------- #
#  Notifications
# --------------------------------------------------------------------------- #
def notify_desktop(new_items: list[Item]) -> None:
    if sys.platform != "darwin" or not new_items:
        return
    top = max(new_items, key=lambda i: i.score)
    n = len(new_items)
    title = f"USMCA Tracker: {n} new item{'s' if n != 1 else ''}"
    body = top.title[:180].replace('"', "'")
    script = f'display notification "{body}" with title "{title}" sound name "Ping"'
    try:
        subprocess.run(["osascript", "-e", script], check=False, timeout=10)
    except Exception as exc:  # pragma: no cover
        print(f"[desktop notify failed] {exc}", file=sys.stderr)


def write_markdown(new_items: list[Item], briefings_dir: Path) -> Path:
    briefings_dir.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now()
    path = briefings_dir / f"usmca-brief-{now:%Y-%m-%d_%H%M}.md"
    lines = [
        f"# USMCA Tracker Brief — {now:%Y-%m-%d %H:%M}",
        "",
        f"**{len(new_items)} new item(s)** since last run. Sorted by signal score.",
        "",
    ]
    for it in sorted(new_items, key=lambda i: (-i.score, i.source)):
        stars = "⭐" * min(it.score, 5) if it.score else ""
        lines.append(f"## {it.title} {stars}".rstrip())
        meta = f"*{it.source}*"
        if it.published:
            meta += f" · {it.published}"
        meta += f" · score {it.score}"
        lines.append(meta)
        if it.tags:
            lines.append(f"`{'` `'.join(it.tags)}`")
        if it.summary:
            lines.append("")
            lines.append(textwrap.shorten(it.summary, width=400, placeholder=" …"))
        lines.append("")
        lines.append(f"[Open source]({it.url})")
        lines.append("")
        lines.append("---")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def append_jsonl(new_items: list[Item], data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "items.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        for it in new_items:
            fh.write(json.dumps(asdict(it), ensure_ascii=False) + "\n")


def send_email(new_items: list[Item], cfg: dict[str, Any]) -> None:
    ecfg = cfg["notifications"]["email"]
    if not ecfg.get("enabled"):
        return
    worthy = [i for i in new_items if i.score >= int(ecfg.get("min_score", 0))]
    if not worthy:
        return
    import smtplib
    from email.mime.text import MIMEText

    password = os.environ.get(ecfg.get("password_env", ""), "")
    if not password:
        print(f"[email skipped] env var {ecfg.get('password_env')} not set", file=sys.stderr)
        return
    body_lines = []
    for it in sorted(worthy, key=lambda i: -i.score):
        body_lines.append(f"[{it.score}] {it.title}\n    {it.source}\n    {it.url}\n")
    msg = MIMEText("\n".join(body_lines), _charset="utf-8")
    msg["Subject"] = f"USMCA Tracker: {len(worthy)} high-signal item(s)"
    msg["From"] = ecfg.get("from") or ecfg.get("username")
    msg["To"] = ", ".join(ecfg["to"])
    try:
        with smtplib.SMTP(ecfg["smtp_host"], int(ecfg["smtp_port"]), timeout=30) as s:
            s.starttls()
            s.login(ecfg["username"], password)
            s.send_message(msg)
    except Exception as exc:  # pragma: no cover
        print(f"[email failed] {exc}", file=sys.stderr)


# --------------------------------------------------------------------------- #
#  Main run
# --------------------------------------------------------------------------- #
def gather(cfg: dict[str, Any]) -> list[Item]:
    timeout = int(cfg["limits"]["http_timeout_seconds"])
    limit = int(cfg["limits"]["max_items_per_source"])
    collected: list[Item] = []

    for _, q in cfg["queries"].items():
        try:
            collected += fetch_google_news(q["google_news"], q["label"], "google_news", timeout, limit)
        except Exception as exc:
            print(f"[warn] query '{q['label']}' failed: {exc}", file=sys.stderr)

    for feed in cfg.get("site_feeds", []):
        try:
            collected += fetch_google_news(feed["query"], feed["label"], "site_feed", timeout, limit)
        except Exception as exc:
            print(f"[warn] site feed '{feed['label']}' failed: {exc}", file=sys.stderr)

    fr = cfg.get("federal_register", {})
    if fr.get("enabled"):
        for term in fr.get("terms", []):
            try:
                collected += fetch_federal_register(term, int(fr.get("per_page", 20)), timeout)
            except Exception as exc:
                print(f"[warn] Federal Register '{term}' failed: {exc}", file=sys.stderr)

    cg = cfg.get("congress", {})
    if cg.get("enabled"):
        try:
            api_key = os.environ.get(cg.get("api_key_env", "CONGRESS_API_KEY"), "")
            collected += fetch_congress_bills(
                api_key, cg.get("terms", []), int(cg.get("per_page", 250)), timeout,
                max_pages=int(cg.get("max_pages", 80)),
            )
        except Exception as exc:
            print(f"[warn] Congress.gov failed: {exc}", file=sys.stderr)

    return collected


def enrich_images(items: list[Item], cfg: dict[str, Any]) -> None:
    """Mutates each item in place, setting .image_url when a thumbnail can be
    found. Skips paywalled/ToS-restricted sources. Never raises — a failed
    fetch just leaves image_url empty, same as any other best-effort source."""
    icfg = cfg["images"]
    if not icfg.get("enabled"):
        return
    skip = tuple(icfg.get("skip_sources", []))
    timeout = int(icfg.get("timeout_seconds", 10))
    max_bytes = int(icfg.get("max_html_bytes", 200_000))
    for it in items:
        if it.source.startswith(skip):
            continue
        try:
            it.image_url = fetch_og_image(it.url, timeout, max_bytes)
        except Exception as exc:
            print(f"[warn] image fetch failed for {it.url}: {exc}", file=sys.stderr)


def run(cfg: dict[str, Any], base: Path, dry_run: bool) -> int:
    db = open_db(base / "data" / "seen.db")
    require_any = cfg["match"]["require_any"]

    raw = gather(cfg)

    # filter + score + de-dupe within this run
    seen_uids: set[str] = set()
    candidates: list[Item] = []
    for it in raw:
        if it.uid in seen_uids:
            continue
        seen_uids.add(it.uid)
        if not passes_local_filter(it, require_any):
            continue
        score_item(it, cfg["scoring"])
        candidates.append(it)

    new_items = [it for it in candidates if is_new(db, it.uid)]

    if not dry_run:
        enrich_images(new_items, cfg)

    print(f"Fetched {len(raw)} raw → {len(candidates)} matched → {len(new_items)} NEW")

    if dry_run:
        for it in sorted(new_items, key=lambda i: -i.score)[:25]:
            print(f"  [{it.score:>2}] {it.title[:90]}  ({it.source})")
        print("(dry-run: nothing saved, nothing notified)")
        return 0

    if not new_items:
        return 0

    notif = cfg["notifications"]
    if notif.get("log_markdown"):
        path = write_markdown(new_items, base / "briefings")
        print(f"Brief written: {path}")
    if notif.get("log_jsonl"):
        append_jsonl(new_items, base / "data")
    if notif.get("desktop"):
        notify_desktop(new_items)
    send_email(new_items, cfg)

    for it in new_items:
        remember(db, it)
    db.commit()
    db.close()
    return 0


def backfill_images(cfg: dict[str, Any], base: Path) -> int:
    """One-off pass over the whole items.jsonl history, filling in image_url
    for any record that doesn't already have one. Rewrites the file in place.
    Meant to be run manually/once — not part of the regular scheduled run."""
    icfg = cfg["images"]
    skip = tuple(icfg.get("skip_sources", []))
    timeout = int(icfg.get("timeout_seconds", 10))
    max_bytes = int(icfg.get("max_html_bytes", 200_000))
    path = base / "data" / "items.jsonl"
    if not path.exists():
        print(f"No items.jsonl at {path}, nothing to backfill.")
        return 0

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    todo = [r for r in rows if not r.get("image_url") and not r.get("source", "").startswith(skip)]
    print(f"{len(rows)} items total, {len(todo)} missing an image.")

    done = 0
    for i, r in enumerate(todo, 1):
        try:
            r["image_url"] = fetch_og_image(r["url"], timeout, max_bytes)
            if r["image_url"]:
                done += 1
        except Exception as exc:
            print(f"[warn] image fetch failed for {r['url']}: {exc}", file=sys.stderr)
        if i % 20 == 0:
            print(f"  ...{i}/{len(todo)} processed")
        time.sleep(0.3)  # be polite to hosts

    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(f"Backfill done: {done}/{len(todo)} got an image. Rewrote {path}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="USMCA/T-MEC/CUSMA negotiation tracker")
    ap.add_argument("--config", type=Path, default=None,
                    help="Path to config.yaml or config.json (defaults to built-in config)")
    ap.add_argument("--base", type=Path, default=HERE,
                    help="Base dir for data/ and briefings/ (default: script dir)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Fetch & show new items but save/notify nothing")
    ap.add_argument("--print-queries", action="store_true",
                    help="Print the Boolean queries (for Feedly/Inoreader/Alerts) and exit")
    ap.add_argument("--backfill-images", action="store_true",
                    help="One-off: fill in image_url for existing items.jsonl rows that lack one, then exit")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)

    if args.print_queries:
        for _, q in cfg["queries"].items():
            print(f"# {q['label']}\n{q['boolean']}\n")
        return 0

    if args.backfill_images:
        return backfill_images(cfg, args.base)

    return run(cfg, args.base, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
