from textwrap import dedent

from book_sync.clippings import (
    add_book_link,
    book_clippings,
    parse_clipping,
    with_book_link,
)

BOOK_CLIPPING = dedent(
    """\
    ![rw-book-cover](https://example.com/cover.jpg)
      ## Metadata
    - Author: [[Kim Stanley Robinson]]
    - Full Title: 2312
    - Category: #books
    - Source: kindle

    ## Highlights
    - some highlight
    """
)

ARTICLE_CLIPPING = dedent(
    """\
    ## Metadata
    - Author: [[Some Writer]]
    - Full Title: An Article
    - Category: #articles
    """
)


def test_parse_clipping_extracts_metadata(tmp_path):
    p = tmp_path / "2312 - Kim Stanley Robinson.md"
    p.write_text(BOOK_CLIPPING, encoding="utf-8")
    c = parse_clipping(p)
    assert c.title == "2312"
    assert c.author == "Kim Stanley Robinson"  # wikilink unwrapped
    assert c.category == "books"
    assert c.link == "[[2312 - Kim Stanley Robinson]]"


def test_book_clippings_filters_to_books(tmp_path):
    (tmp_path / "book.md").write_text(BOOK_CLIPPING, encoding="utf-8")
    (tmp_path / "article.md").write_text(ARTICLE_CLIPPING, encoding="utf-8")
    titles = [c.title for c in book_clippings(tmp_path)]
    assert titles == ["2312"]


STEM = "2312 - Kim Stanley Robinson"


def test_with_book_link_inserts_into_metadata_block():
    new, changed = with_book_link(BOOK_CLIPPING, STEM)
    assert changed
    assert f"- Book note: [[{STEM}]]" in new
    # inserted inside Metadata, above the Highlights section
    assert new.index("Book note") < new.index("## Highlights")


def test_with_book_link_is_idempotent():
    once, _ = with_book_link(BOOK_CLIPPING, STEM)
    twice, changed = with_book_link(once, STEM)
    assert not changed
    assert twice == once
    assert once.count("- Book note:") == 1


def test_with_book_link_replaces_stale_link():
    once, _ = with_book_link(BOOK_CLIPPING, "Old Title - Old Author")
    new, changed = with_book_link(once, STEM)
    assert changed
    assert new.count("- Book note:") == 1
    assert f"[[{STEM}]]" in new
    assert "Old Title" not in new


def test_with_book_link_prepends_when_no_metadata():
    new, changed = with_book_link("just some prose\n", STEM)
    assert changed
    assert new.startswith(f"- Book note: [[{STEM}]]\n")


def test_add_book_link_writes_file(tmp_path):
    p = tmp_path / "2312 - Kim Stanley Robinson.md"
    p.write_text(BOOK_CLIPPING, encoding="utf-8")
    assert add_book_link(p, STEM) is True
    assert f"[[{STEM}]]" in p.read_text(encoding="utf-8")
    assert add_book_link(p, STEM) is False  # second run is a no-op
