"""Fold hand-written freeform book notes into the imported, formatted ones.

A freeform note has no frontmatter (just prose, usually under an H1). For each,
we guess title/author, find the best title match among imported notes, and
either merge (freeform note survives, gains the import's frontmatter, dup import
deleted) or, if there's no confident match, just add minimal frontmatter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import frontmatter
from rapidfuzz import fuzz

from .notes import BookNote, NoteIndex, book_filename, normalize_title

# token_sort_ratio above this -> treat as the same book and merge.
MERGE_THRESHOLD = 85

_HEADING_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def _deslug(stem: str) -> str:
    s = re.sub(r"^book-", "", stem)
    return s.replace("-", " ").title() if "-" in s and " " not in s else s


def extract_title_author(path: Path, content: str) -> tuple[str, str]:
    """Best-effort (title, author) from the H1 heading or the filename."""
    m = _HEADING_RE.search(content)
    raw = (m.group(1) if m else _deslug(path.stem)).strip()
    raw = re.sub(r"^book:\s*", "", raw, flags=re.IGNORECASE).strip()
    author = ""
    if pm := re.search(r"\(([^)]+)\)\s*$", raw):  # "Title (Author)"
        author, raw = pm.group(1).strip(), raw[: pm.start()].strip()
    elif dm := re.search(r"\s[-–]\s(.+)$", raw):  # "Title - Author"
        author, raw = dm.group(1).strip(), raw[: dm.start()].strip()
    return raw, author


@dataclass
class FreeformNote:
    path: Path
    title: str
    author: str


def freeform_notes(books_path: Path) -> list[FreeformNote]:
    """Notes in the books dir that lack frontmatter (i.e. not yet formatted)."""
    out = []
    for p in sorted(books_path.glob("*.md")):
        post = frontmatter.loads(p.read_text(encoding="utf-8"))
        if post.metadata:
            continue
        title, author = extract_title_author(p, post.content)
        out.append(FreeformNote(path=p, title=title, author=author))
    return out


def best_match(idx: NoteIndex, title: str) -> tuple[BookNote | None, float]:
    """Highest title-only fuzzy match among imported notes (author is unreliable
    on freeform notes, so it's not required)."""
    nt = normalize_title(title)
    best, score = None, 0.0
    for note in idx.notes:
        s = fuzz.token_sort_ratio(nt, normalize_title(note.get("title") or ""))
        if s > score:
            best, score = note, float(s)
    return best, score


def build_merged_post(free_path: Path, match: BookNote) -> frontmatter.Post:
    """Freeform body + the import's authoritative frontmatter; append any review."""
    post = frontmatter.loads(free_path.read_text(encoding="utf-8"))
    post.metadata = dict(match.meta)
    if review := match.post.content.strip():
        post.content = f"{post.content.rstrip()}\n\n## Goodreads review\n\n{review}"
    return post


def build_standalone_post(free_path: Path, free: FreeformNote, status: str) -> frontmatter.Post:
    """Freeform body + minimal frontmatter for a book with no Goodreads match."""
    post = frontmatter.loads(free_path.read_text(encoding="utf-8"))
    meta = {"title": free.title, "status": status}
    if free.author:
        meta["author"] = free.author
    post.metadata = meta
    return post
