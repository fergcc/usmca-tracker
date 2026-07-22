# Agent instructions for this repo

This project is worked on by multiple AI coding agents in parallel (Claude Code,
opencode/DeepSeek, etc.). Read this before touching the data pipeline.

## Data pipeline safety rules

- **`data/items_enriched.jsonl` and its `.bak` are read-only on disk (chmod
  0o444) between runs.** This is enforced by the OS, not just convention — a
  script (from any AI, including one editing this repo in parallel) that
  tries `open(path, "w")` on either file gets a `PermissionError`, full stop.
  If you hit that error, **do not `chmod` the file writable yourself** —
  it means you're about to bypass the one safe writer. Run
  `python -m Engine.engine enrich` instead.
- **Never write directly to `data/items_enriched.jsonl`.** Always go through
  `python -m Engine.engine enrich` (or `run`). That function
  (`Engine/enrich.py: Enricher.enrich_items`, via `_save_enriched_output`) is
  the only sanctioned writer — it's the only code that unlocks the file,
  writes it, and locks it read-only again afterward. It preserves every
  existing AI field (`impactScore`, `trustScore`, `aiSummary`, `sentiment`,
  `leanScore`, etc.) while updating only what's missing or stale.
- **Do not create one-off/ad-hoc scripts that reload `data/items.jsonl` and
  overwrite `items_enriched.jsonl`.** `items.jsonl` never has the AI fields —
  a script that loads it and saves straight to `items_enriched.jsonl` silently
  wipes `impactScore`/`trustScore`/`aiSummary` for every item. This already
  happened once (a stray `Engine/run_lean_only.py` script did exactly this on
  2026-07-21, zeroing every score on the dashboard) and has since been deleted.
- If you need to backfill or recompute a specific field (e.g. `leanScore`),
  add it to `enrich_items()` in `Engine/enrich.py` so the built-in
  regression guard (`_check_no_regression`) and automatic `.bak` backup cover
  it — don't write a standalone script for it.
- `data/` is gitignored, so git will never show you a diff proving you broke
  the enrichment data. Before and after any manual edit, sanity-check with:
  ```bash
  python3 -c "import json; d=[json.loads(l) for l in open('data/items_enriched.jsonl')]; print(sum(1 for x in d if x.get('impactScore')), '/', len(d), 'scored')"
  ```
- `build_dashboard.py` has a last-resort guard that falls back to
  `items_enriched.jsonl.bak` if the live file looks badly regressed, but
  don't rely on it — fix the root cause instead of triggering the fallback.
