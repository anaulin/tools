"""Book-note model, index, fuzzy matching, and fill-only merge/write.

A "book note" is a markdown file in the vault's books dir with YAML frontmatter.
The vault is the source of truth: this module never overwrites a field a human
has set (fill-only-if-empty), except list fields explicitly merged by union.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import frontmatter
from rapidfuzz import fuzz

ARTICLES = {"the", "a", "an"}

_EMPTY = (None, "", [], {})


def normalize_title(title: str) -> str:
    """Lowercase, drop subtitle after ':', parentheticals, punctuation, articles."""
    t = (title or "").split(":")[0].lower()
    t = re.sub(r"\(.*?\)", " ", t)
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    words = [w for w in t.split() if w not in ARTICLES]
    return " ".join(words).strip()


def author_surname(author: str) -> str:
    """Best-effort surname from 'First Last' or 'Last, First'."""
    if not author:
        return ""
    a = author.split(",")[0] if "," in author else author
    parts = re.sub(r"[^A-Za-z ]", " ", a).split()
    return parts[-1].lower() if parts else ""


def match_key(title: str, author: str) -> str:
    return f"{normalize_title(title)}|{author_surname(author)}"


# Goodreads series tag, e.g. "(Imperial Radch, #1)" at the end of a title.
_SERIES_RE = re.compile(r"\s*\(([^()]+?),\s*#(\d+)\)\s*$")
# Characters Obsidian disallows in filenames or that break wikilinks.
_ILLEGAL_RE = re.compile(r"[\\/:*?\"<>|#^\[\]]")


def _parse_series(title: str) -> tuple[str | None, int | None, str]:
    """Split a trailing '(Series, #N)' tag off a title -> (series, number, base)."""
    m = _SERIES_RE.search(title)
    if not m:
        return None, None, title
    return m.group(1).strip(), int(m.group(2)), title[: m.start()].rstrip()


def _sanitize_filename(text: str) -> str:
    text = _ILLEGAL_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.rstrip(". ")


def book_filename(title: str, author: str = "", *, drop_subtitle: bool = True) -> str:
    """Human-readable note filename: 'Title (Series N) - Author'.

    A Goodreads series tag becomes '(Series N)' so same-titled volumes stay
    distinct; author is appended. With ``drop_subtitle`` the part after the
    first ':' is dropped for a cleaner name; without it the full title is kept
    (':' -> ' -'), used to disambiguate books that collide once trimmed.
    """
    series, number, base = _parse_series(title)
    base = base.split(":")[0] if drop_subtitle else base.replace(":", " -")
    name = _sanitize_filename(base)
    if series and number is not None:
        name = f"{name} ({_sanitize_filename(series)} {number})"
    if author and (clean_author := _sanitize_filename(author)):
        name = f"{name} - {clean_author}"
    return name or "book"


@dataclass
class BookNote:
    path: Path
    post: frontmatter.Post

    @property
    def meta(self) -> dict:
        return self.post.metadata

    def get(self, key: str):
        return self.post.metadata.get(key)


@dataclass
class NoteIndex:
    notes: list[BookNote] = field(default_factory=list)
    by_gr_id: dict[str, BookNote] = field(default_factory=dict)
    by_isbn: dict[str, BookNote] = field(default_factory=dict)
    by_key: dict[str, BookNote] = field(default_factory=dict)
    paths: set[Path] = field(default_factory=set)

    def add(self, note: BookNote) -> None:
        self.notes.append(note)
        self.paths.add(note.path)
        if gid := note.get("gr_id"):
            self.by_gr_id[str(gid)] = note
        if isbn := note.get("isbn"):
            self.by_isbn[str(isbn)] = note
        if title := note.get("title"):
            self.by_key.setdefault(match_key(title, note.get("author") or ""), note)


def load_index(books_path: Path) -> NoteIndex:
    """Load notes that have frontmatter. Freeform notes (no frontmatter) are ignored."""
    idx = NoteIndex()
    if not books_path.exists():
        return idx
    for p in sorted(books_path.glob("*.md")):
        post = frontmatter.loads(p.read_text(encoding="utf-8"))
        if not post.metadata:
            continue
        idx.add(BookNote(path=p, post=post))
    return idx


def find_match(
    idx: NoteIndex,
    *,
    gr_id: str | None = None,
    isbn: str | None = None,
    title: str | None = None,
    author: str | None = None,
    threshold: int = 88,
    match_title: bool = True,
) -> BookNote | None:
    """Match priority: gr_id -> isbn -> exact title+author key -> fuzzy fallback.

    ``match_title=False`` restricts matching to the exact identifiers (gr_id,
    isbn). Use it when the source is already deduplicated per book (a Goodreads
    export): title matching would wrongly collapse same-titled series volumes.
    """
    if gr_id and str(gr_id) in idx.by_gr_id:
        return idx.by_gr_id[str(gr_id)]
    if isbn and str(isbn) in idx.by_isbn:
        return idx.by_isbn[str(isbn)]
    if not title or not match_title:
        return None
    key = match_key(title, author or "")
    if key in idx.by_key:
        return idx.by_key[key]
    best, best_score = None, 0.0
    for k, note in idx.by_key.items():
        score = fuzz.token_sort_ratio(key, k)
        if score > best_score:
            best, best_score = note, score
    return best if best and best_score >= threshold else None


def merge_fields(meta: dict, new: dict, *, union_keys: tuple[str, ...] = ()) -> list[str]:
    """Fill only empty/missing fields (vault wins). union_keys merge lists instead.

    Mutates ``meta``. Returns the list of keys that changed.
    """
    changed: list[str] = []
    for k, v in new.items():
        if v in _EMPTY:
            continue
        if k in union_keys and isinstance(v, list):
            existing = meta.get(k) or []
            merged = list(dict.fromkeys([*existing, *v]))
            if merged != existing:
                meta[k] = merged
                changed.append(k)
            continue
        if meta.get(k) in _EMPTY:
            meta[k] = v
            changed.append(k)
    return changed


def _unique_path(books_path: Path, stem: str, taken: set[Path]) -> Path:
    path = books_path / f"{stem}.md"
    if path not in taken and not path.exists():
        return path
    n = 2
    while True:
        path = books_path / f"{stem} ({n}).md"
        if path not in taken and not path.exists():
            return path
        n += 1


def new_note_path(books_path: Path, title: str, author: str, taken: set[Path]) -> Path:
    """Unique path for a new note, numbering '(2)' on collision."""
    return _unique_path(books_path, book_filename(title, author), taken)


def plan_renames(notes: list[BookNote], books_path: Path) -> list[tuple[Path, Path]]:
    """Compute (old, new) paths to bring notes in line with book_filename().

    Subtitles are dropped for cleaner names, but restored for a book whose
    trimmed name would collide with another while its full title is unique.
    Notes already correctly named are skipped (and reserved) so they aren't
    displaced; genuine duplicate titles fall back to a numbered suffix.
    """
    titled = [n for n in notes if n.get("title")]
    clean = {n.path: book_filename(n.get("title"), n.get("author") or "") for n in titled}
    full = {n.path: book_filename(n.get("title"), n.get("author") or "", drop_subtitle=False) for n in titled}
    clean_counts = Counter(clean.values())
    full_counts = Counter(full.values())

    desired = {}
    for n in titled:
        name = clean[n.path]
        if clean_counts[name] > 1 and full_counts[full[n.path]] == 1:
            name = full[n.path]  # the subtitle resolves the collision
        desired[n.path] = name

    taken = {n.path for n in titled if n.path.stem == desired[n.path]}
    plans: list[tuple[Path, Path]] = []
    for n in titled:
        if n.path.stem == desired[n.path]:
            continue
        target = _unique_path(books_path, desired[n.path], taken)
        taken.add(target)
        plans.append((n.path, target))
    return plans


def write_note(path: Path, post: frontmatter.Post) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = frontmatter.dumps(post, sort_keys=False, allow_unicode=True, default_flow_style=False)
    path.write_text(text + "\n", encoding="utf-8")
