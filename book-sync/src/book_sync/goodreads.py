"""Parse a Goodreads CSV export into book-note field dicts."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

# Goodreads "Exclusive Shelf" -> our status vocabulary.
SHELF_STATUS = {
    "read": "read",
    "currently-reading": "reading",
    "to-read": "want",
}


def _clean_isbn(value: str) -> str | None:
    # Goodreads exports ISBNs as ="9780316098120" to defeat spreadsheet coercion.
    m = re.search(r"\d[\dXx]{8,}", value or "")
    return m.group(0) if m else None


def _date(value: str) -> str | None:
    # Goodreads dates look like 2016/12/09.
    m = re.match(r"\s*(\d{4})/(\d{1,2})/(\d{1,2})", value or "")
    if not m:
        return None
    y, mo, d = m.groups()
    return f"{y}-{int(mo):02d}-{int(d):02d}"


@dataclass
class GoodreadsBook:
    fields: dict
    body: str


def parse_goodreads_csv(path: Path) -> list[GoodreadsBook]:
    books: list[GoodreadsBook] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            title = (row.get("Title") or "").strip()
            if not title:
                continue
            shelf = (row.get("Exclusive Shelf") or "").strip()
            rating = int(row.get("My Rating") or 0)
            isbn = _clean_isbn(row.get("ISBN13") or "") or _clean_isbn(row.get("ISBN") or "")
            shelves = [
                s.strip()
                for s in (row.get("Bookshelves") or "").split(",")
                if s.strip() and s.strip() not in SHELF_STATUS
            ]
            fields = {
                "title": title,
                "author": (row.get("Author") or "").strip(),
                "status": SHELF_STATUS.get(shelf, shelf or None),
                "rating": rating or None,
                "finished": _date(row.get("Date Read")),
                "isbn": isbn,
                "gr_id": (row.get("Book Id") or "").strip() or None,
                "shelves": shelves or None,
            }
            books.append(GoodreadsBook(fields=fields, body=(row.get("My Review") or "").strip()))
    return books
