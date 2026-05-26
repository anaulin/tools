from pathlib import Path

import frontmatter

from book_sync.coalesce import (
    best_match,
    build_merged_post,
    build_standalone_post,
    extract_title_author,
    freeform_notes,
)
from book_sync.notes import BookNote, NoteIndex, load_index


def test_extract_title_author_variants(tmp_path):
    assert extract_title_author(Path("daring-greatly.md"), "# Daring Greatly\n\nnotes") == \
        ("Daring Greatly", "")
    assert extract_title_author(Path("x.md"), "# The Middle Passage (James Hollis)\n") == \
        ("The Middle Passage", "James Hollis")
    assert extract_title_author(Path("x.md"), "# No More Feedback - Carol Sanford\n") == \
        ("No More Feedback", "Carol Sanford")
    assert extract_title_author(Path("x.md"), "# Book: Living Your Unlived Life\n") == \
        ("Living Your Unlived Life", "")
    # no H1 -> de-slug filename
    assert extract_title_author(Path("the-first-90-days.md"), "no heading here") == \
        ("The First 90 Days", "")


def test_freeform_notes_skips_frontmatter(tmp_path):
    (tmp_path / "free.md").write_text("# Free Book\n\nnotes", encoding="utf-8")
    (tmp_path / "imported.md").write_text("---\ntitle: X\n---\nbody", encoding="utf-8")
    titles = [f.title for f in freeform_notes(tmp_path)]
    assert titles == ["Free Book"]


def _note(meta):
    return BookNote(path=Path("Daring Greatly - Brené Brown.md"),
                    post=frontmatter.Post(content="A Goodreads review.", **meta))


def test_best_match_title_only():
    idx = NoteIndex()
    idx.add(_note({"title": "Daring Greatly: How the Courage to Be Vulnerable...",
                   "author": "Brené Brown", "gr_id": "9"}))
    match, score = best_match(idx, "Daring Greatly")
    assert match is not None and score >= 85


def test_build_merged_post_keeps_body_adds_frontmatter_and_review(tmp_path):
    free = tmp_path / "daring-greatly.md"
    free.write_text("# Daring Greatly\n\nmy handwritten notes", encoding="utf-8")
    match = _note({"title": "Daring Greatly", "author": "Brené Brown", "gr_id": "9", "status": "read"})
    post = build_merged_post(free, match)
    assert post.metadata["gr_id"] == "9"  # authoritative frontmatter from import
    assert "my handwritten notes" in post.content  # human prose preserved
    assert "## Goodreads review" in post.content and "A Goodreads review." in post.content


def test_build_standalone_post(tmp_path):
    free = tmp_path / "x.md"
    free.write_text("# Some Book\n\nnotes", encoding="utf-8")
    from book_sync.coalesce import FreeformNote
    f = FreeformNote(path=free, title="Some Book", author="An Author")
    post = build_standalone_post(free, f, "read")
    assert post.metadata == {"title": "Some Book", "status": "read", "author": "An Author"}
    assert "notes" in post.content
