# book-sync

Imports reading data into an Obsidian vault, which is the **source of truth**.
Inbound only (for now): Goodreads history, Readwise `#books` clippings, and
Hugo/Nebula award lists all flow *into* book notes under `Reference/books/`.

The vault always wins: existing field values are never overwritten
(fill-only-if-empty), except `awards`, which is merged by union.

## Setup

```sh
cd book-sync
mise install        # python + uv
uv sync             # install deps + dev tools
cp config.example.toml config.toml   # then edit paths
```

## Commands

All commands take `--config/-c` (default `config.toml`) and `--dry-run`.

```sh
uv run book-sync import-goodreads goodreads_library_export.csv --dry-run
uv run book-sync seed-clippings --dry-run
uv run book-sync awards --dry-run
uv run book-sync status
```

Recommended first run, in order (review each `--dry-run` before writing):

1. **`import-goodreads <export.csv>`** — backfill from a Goodreads library
   export (Goodreads → *My Books* → *Import and export* → *Export Library*).
   Maps shelf→status, rating, date read, ISBN, shelves; review → note body;
   keeps `Book Id` as `gr_id` for stable re-imports.
2. **`seed-clippings`** — for each Readwise `#books` clipping, link an existing
   note or create one. New clipping-only notes get `clippings.default_status`.
3. **`awards`** — tag notes with Hugo/Nebula awards and create stubs (status
   `awards.default_status`) for award books you have not logged yet.

## Matching

Books are matched across sources by, in priority: `gr_id` → `isbn` → exact
normalized `title`+author-surname → fuzzy `title`+author (rapidfuzz, threshold
in `config.toml`). The fuzzy fallback is where mismatches hide — always
`--dry-run` the first pass.

## Awards data

`data/awards.json` is a curated list (`title`, `author`, `award`, `result`,
`year`). The committed file is a small seed — regenerate the full Hugo/Nebula
set from your tracking spreadsheet or public lists and replace it.

## Tests

```sh
uv run pytest
```
