"""Classify the book clippings that `seed-clippings` left unmatched.

`seed-clippings --no-create` links every clipping whose title+author resolves
to a book note, and skips the rest. Those leftovers are a mix of:

- **duplicates** of an existing note that the author-surname key missed
  (Readwise reorders/expands authors, e.g. "Cixin Liu and Ken Liu"),
- **junk**: sample/preview editions, Readwise parse artifacts, travel guides,
- **genuinely new** books with no note yet.

This module sorts a clipping into one of those buckets by matching on the
normalized title alone (author ignored), which is what catches the dupes.
"""

from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz

from .clippings import Clipping
from .notes import BookNote, NoteIndex, normalize_title

# A title-only score this high means the same book, even when authors differ.
LINK_THRESHOLD = 92


def junk_reason(title: str) -> str | None:
    """Why this clipping isn't a real book note, or None if it looks legit."""
    t = title.lower()
    if "free preview" in t or "(free preview" in t:
        return "sample/preview"
    if title.startswith("UC_"):
        return "parse artifact"
    if "lonely planet" in t:
        return "travel guide"
    return None


def best_title_match(idx: NoteIndex, title: str) -> tuple[BookNote | None, float]:
    """Highest title-only fuzzy match in the index (author ignored)."""
    nt = normalize_title(title)
    best: BookNote | None = None
    best_score = 0.0
    for note in idx.notes:
        score = fuzz.token_sort_ratio(nt, normalize_title(note.get("title") or ""))
        if score > best_score:
            best, best_score = note, score
    return best, best_score


@dataclass
class Verdict:
    action: str  # "link" | "skip" | "new"
    clipping: Clipping
    note: BookNote | None = None  # set when action == "link"
    score: float = 0.0  # title score for "link"
    reason: str = ""  # junk reason for "skip"


def classify(
    idx: NoteIndex, clipping: Clipping, *, link_threshold: float = LINK_THRESHOLD
) -> Verdict:
    """Bucket an unmatched clipping. Link-strong dupes win over the junk filter."""
    note, score = best_title_match(idx, clipping.title)
    if note is not None and score >= link_threshold:
        return Verdict("link", clipping, note=note, score=score)
    if reason := junk_reason(clipping.title):
        return Verdict("skip", clipping, reason=reason)
    return Verdict("new", clipping, note=note, score=score)
