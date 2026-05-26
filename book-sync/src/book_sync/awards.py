"""Load the curated SF-awards dataset and group it per book."""

from __future__ import annotations

import json
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

from .notes import match_key


@dataclass
class Award:
    title: str
    author: str
    award: str  # "hugo", "nebula"
    result: str  # "winner", "nominee"
    year: int

    @property
    def slug(self) -> str:
        return f"{self.award}-{self.result}-{self.year}"


@dataclass
class AwardedBook:
    title: str
    author: str
    slugs: list[str] = field(default_factory=list)


def load_awards(path: Path) -> list[Award]:
    if not path.exists():
        return []
    return [Award(**entry) for entry in json.loads(path.read_text(encoding="utf-8"))]


def group_by_book(awards: list[Award]) -> list[AwardedBook]:
    """Collapse awards to one entry per book, accumulating award slugs."""
    grouped: OrderedDict[str, AwardedBook] = OrderedDict()
    for a in awards:
        book = grouped.setdefault(match_key(a.title, a.author), AwardedBook(a.title, a.author))
        if a.slug not in book.slugs:
            book.slugs.append(a.slug)
    return list(grouped.values())
