"""Parse Readwise clipping notes (the `## Metadata` block, not YAML frontmatter)."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Clipping:
    path: Path
    title: str
    author: str
    category: str  # "books", "articles", ...

    @property
    def link(self) -> str:
        """Obsidian wikilink to this clipping (filename without extension)."""
        return f"[[{self.path.stem}]]"


def _meta_value(text: str, label: str) -> str:
    m = re.search(rf"^- {re.escape(label)}:\s*(.+)$", text, re.MULTILINE)
    if not m:
        return ""
    val = m.group(1).strip()
    val = re.sub(r"\[\[(.*?)\]\]", r"\1", val)  # unwrap wikilinks
    return val.lstrip("#").strip()


def parse_clipping(path: Path) -> Clipping | None:
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
    )


def book_clippings(clippings_path: Path) -> Iterator[Clipping]:
    for p in sorted(clippings_path.glob("*.md")):
        c = parse_clipping(p)
        if c and c.category == "books":
            yield c
