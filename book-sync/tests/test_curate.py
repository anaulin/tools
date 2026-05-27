import frontmatter

from book_sync.clippings import Clipping
from book_sync.curate import classify, junk_reason
from book_sync.notes import BookNote, NoteIndex


def _note(meta):
    return BookNote(path=__import__("pathlib").Path(f"{meta['title']}.md"),
                    post=frontmatter.Post("", **meta))


def _idx(*titles):
    idx = NoteIndex()
    for t in titles:
        idx.add(_note({"title": t, "author": "Whoever"}))
    return idx


def _clip(title, author="Some Author"):
    return Clipping(path=__import__("pathlib").Path(f"{title}.md"),
                    title=title, author=author, category="books")


def test_junk_reason_flags_samples_artifacts_guides():
    assert junk_reason("The Drowned Cities - Free Preview") == "sample/preview"
    assert junk_reason("UC_The Drawing of the Three") == "parse artifact"
    assert junk_reason("Lonely Planet Singapore") == "travel guide"
    assert junk_reason("The Three-Body Problem") is None


def test_classify_links_title_dupe_despite_author_mismatch():
    # book stored as "Liu Cixin", clipping author "Cixin Liu and Ken Liu"
    idx = _idx("The Three-Body Problem (Remembrance of Earth's Past, #1)")
    v = classify(idx, _clip("The Three-Body Problem", "Cixin Liu and Ken Liu"))
    assert v.action == "link"
    assert v.score >= 92
    assert "Three-Body" in v.note.get("title")


def test_classify_skips_junk_when_no_strong_match():
    idx = _idx("Some Unrelated Book")
    v = classify(idx, _clip("UC_The Drawing of the Three"))
    assert v.action == "skip"
    assert v.reason == "parse artifact"


def test_classify_reports_genuinely_new_book():
    idx = _idx("Some Unrelated Book")
    v = classify(idx, _clip("The Dark Tower I", "Stephen King"))
    assert v.action == "new"


def test_link_wins_over_junk_filter():
    # a junk-pattern title that is actually a strong dupe should still link
    idx = _idx("Lonely Planet Singapore")
    v = classify(idx, _clip("Lonely Planet Singapore", "Lonely Planet"))
    assert v.action == "link"
