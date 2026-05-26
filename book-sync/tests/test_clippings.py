from textwrap import dedent

from book_sync.clippings import book_clippings, parse_clipping

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
