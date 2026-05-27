"""Upsert orchestration shared by the import commands."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import frontmatter

from .notes import (
    BookNote,
    NoteIndex,
    find_match,
    merge_fields,
    new_note_path,
    write_note,
)


@dataclass
class UpsertResult:
    action: str  # "create" | "update" | "noop"
    path: Path
    changed: list[str]


def upsert(
    idx: NoteIndex,
    books_path: Path,
    *,
    fields: dict,
    create_only: dict | None = None,
    body: str | None = None,
    union_keys: tuple[str, ...] = (),
    threshold: int = 88,
    match_title: bool = True,
    dry_run: bool = False,
) -> UpsertResult:
    """Match an existing note and fill blanks, or create a new one.

    ``create_only`` fields are applied only when a new note is created (e.g. a
    default status), never to an existing note.
    """
    match = find_match(
        idx,
        goodreads_id=fields.get("goodreads_id"),
        isbn=fields.get("isbn"),
        title=fields.get("title"),
        author=fields.get("author"),
        threshold=threshold,
        match_title=match_title,
    )

    if match is not None:
        changed = merge_fields(match.meta, fields, union_keys=union_keys)
        if body and not match.post.content.strip():
            match.post.content = body
            changed.append("body")
        if changed and not dry_run:
            write_note(match.path, match.post)
            idx.add(match)  # refresh lookup keys (e.g. newly filled goodreads_id/isbn)
        action = "update" if changed else "noop"
        return UpsertResult(action=action, path=match.path, changed=changed)

    path = new_note_path(books_path, fields["title"], fields.get("author", ""), idx.paths)
    post = frontmatter.Post(content=body or "")
    merged = {**fields, **(create_only or {})}
    changed = merge_fields(post.metadata, merged, union_keys=union_keys)
    if body:
        changed.append("body")
    note = BookNote(path=path, post=post)
    idx.add(note)
    if not dry_run:
        write_note(path, post)
    return UpsertResult(action="create", path=path, changed=changed)
