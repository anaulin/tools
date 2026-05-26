import frontmatter

from book_sync.awards import Award, group_by_book
from book_sync.notes import load_index
from book_sync.sync import upsert


def test_upsert_creates_then_fills_without_clobbering(tmp_path):
    books = tmp_path / "books"
    idx = load_index(books)

    # create from goodreads
    r1 = upsert(idx, books, fields={"title": "2312", "author": "Kim Stanley Robinson",
                                    "status": "read", "rating": 4, "gr_id": "111"})
    assert r1.action == "create"
    assert r1.path.name == "2312 - Kim Stanley Robinson.md"
    note = frontmatter.loads(r1.path.read_text())
    assert note["status"] == "read" and note["rating"] == 4

    # a review becomes the note body and is reported as a change
    r_body = upsert(idx, books, fields={"title": "Reviewed", "author": "A"}, body="great")
    assert "body" in r_body.changed
    assert frontmatter.loads(r_body.path.read_text()).content == "great"

    # re-running with a different status must NOT overwrite, but fills isbn
    idx2 = load_index(books)
    r2 = upsert(idx2, books, fields={"title": "2312", "author": "Kim Stanley Robinson",
                                     "status": "want", "isbn": "9780316098120", "gr_id": "111"})
    assert r2.action == "update"
    note = frontmatter.loads(r1.path.read_text())
    assert note["status"] == "read"  # preserved (vault wins)
    assert note["isbn"] == "9780316098120"  # blank filled


def test_upsert_create_only_status(tmp_path):
    books = tmp_path / "books"
    idx = load_index(books)
    # clipping seeds default status only on creation
    r = upsert(idx, books, fields={"title": "Powers", "author": "Ursula K. Le Guin",
                                   "clipping": "[[Powers - Ursula K. Le Guin]]"},
               create_only={"status": "read"})
    note = frontmatter.loads(r.path.read_text())
    assert note["status"] == "read"
    assert note["clipping"] == "[[Powers - Ursula K. Le Guin]]"


def test_upsert_dry_run_writes_nothing(tmp_path):
    books = tmp_path / "books"
    idx = load_index(books)
    upsert(idx, books, fields={"title": "Ghost", "author": "No One"}, dry_run=True)
    assert not books.exists() or not list(books.glob("*.md"))


def test_group_awards_by_book():
    awards = [
        Award("Ancillary Justice", "Ann Leckie", "hugo", "winner", 2014),
        Award("Ancillary Justice", "Ann Leckie", "nebula", "winner", 2013),
        Award("2312", "Kim Stanley Robinson", "nebula", "winner", 2012),
    ]
    grouped = {b.title: b.slugs for b in group_by_book(awards)}
    assert grouped["Ancillary Justice"] == ["hugo-winner-2014", "nebula-winner-2013"]
    assert grouped["2312"] == ["nebula-winner-2012"]
