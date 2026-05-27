"""Parse Readwise clipping notes (the `## Metadata` block, not YAML frontmatter)."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path


def wikilink(directory: str, name: str) -> str:
    """Vault-relative Obsidian wikilink, e.g. ``[[Reference/books/Title - Author]]``.

    The directory prefix is what keeps the link unambiguous: a book note and its
    clipping almost always share a basename, so a bare ``[[name]]`` resolves to
    whichever file is in the same folder (i.e. itself).
    """
    return f"[[{directory}/{name}]]"


@dataclass
class Clipping:
    path: Path
    title: str
    author: str
    category: str  # "books", "articles", ...
    rel_dir: str = ""  # clipping's vault-relative folder, for building links

    @property
    def link(self) -> str:
        """Vault-relative wikilink to this clipping."""
        return wikilink(self.rel_dir, self.path.stem)


def _meta_value(text: str, label: str) -> str:
    m = re.search(rf"^- {re.escape(label)}:\s*(.+)$", text, re.MULTILINE)
    if not m:
        return ""
    val = m.group(1).strip()
    val = re.sub(r"\[\[(.*?)\]\]", r"\1", val)  # unwrap wikilinks
    return val.lstrip("#").strip()


def parse_clipping(path: Path, rel_dir: str = "") -> Clipping | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    title = _meta_value(text, "Full Title")
    author = _meta_value(text, "Author")
    if not (title or author):
        return None
    return Clipping(
        path=path,
        title=title,
        author=author,
        category=_meta_value(text, "Category").lower(),
        rel_dir=rel_dir,
    )


def book_clippings(clippings_path: Path, rel_dir: str = "") -> Iterator[Clipping]:
    for p in sorted(clippings_path.glob("*.md")):
        c = parse_clipping(p, rel_dir)
        if c and c.category == "books":
            yield c


_BOOK_NOTE_LINE = re.compile(r"^- Book note: .*$", re.MULTILINE)
_METADATA_HDR = re.compile(r"^\s*## Metadata\s*$", re.MULTILINE)


def with_book_link(text: str, book_dir: str, book_stem: str) -> tuple[str, bool]:
    """Add/update a ``- Book note: [[dir/stem]]`` line in the clipping's Metadata block.

    Idempotent: replaces an existing back-link (e.g. after a note rename, or an
    older bare-stem link) and leaves the file untouched when it already points at
    the same target. Returns the new text and whether anything changed.
    """
    line = f"- Book note: {wikilink(book_dir, book_stem)}"
    if _BOOK_NOTE_LINE.search(text):
        new = _BOOK_NOTE_LINE.sub(line, text, count=1)
        return new, new != text
    if m := _METADATA_HDR.search(text):
        end = m.end()
        return f"{text[:end]}\n{line}{text[end:]}", True
    return f"{line}\n{text}", True  # no Metadata block: prepend


def add_book_link(path: Path, book_dir: str, book_stem: str) -> bool:
    """Write a back-link to ``book_dir/book_stem`` into the clipping file. Returns changed."""
    text = path.read_text(encoding="utf-8", errors="replace")
    new, changed = with_book_link(text, book_dir, book_stem)
    if changed:
        path.write_text(new, encoding="utf-8")
    return changed
