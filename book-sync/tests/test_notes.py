import frontmatter

from book_sync.notes import (
    BookNote,
    NoteIndex,
    author_surname,
    find_match,
    match_key,
    merge_fields,
    new_note_path,
    normalize_title,
    slugify,
)


def test_normalize_title_drops_subtitle_articles_punctuation():
    assert normalize_title("The Fifth Season: A Novel!") == "fifth season"
    assert normalize_title("Ancillary Justice (Imperial Radch #1)") == "ancillary justice"


def test_author_surname_handles_both_orders():
    assert author_surname("Ann Leckie") == "leckie"
    assert author_surname("Leckie, Ann") == "leckie"
    assert author_surname("") == ""


def test_match_key_combines_title_and_surname():
    assert match_key("Ancillary Justice", "Ann Leckie") == "ancillary justice|leckie"


def test_slugify():
    assert slugify("The Fifth Season: A Novel") == "fifth-season"


def _note(meta):
    return BookNote(path=None, post=frontmatter.Post(content="", **meta))


def test_find_match_priority_and_fuzzy():
    idx = NoteIndex()
    idx.add(_note({"title": "2312", "author": "Kim Stanley Robinson", "gr_id": "111", "isbn": "999"}))
    idx.add(_note({"title": "Ancillary Justice", "author": "Ann Leckie"}))

    assert find_match(idx, gr_id="111").get("title") == "2312"
    assert find_match(idx, isbn="999").get("title") == "2312"
    # fuzzy: slight title variation, same author still matches
    m = find_match(idx, title="Ancillary Justice: Imperial Radch", author="Leckie", threshold=80)
    assert m is not None and m.get("title") == "Ancillary Justice"
    # below threshold -> no match
    assert find_match(idx, title="Totally Different Book", author="Nobody", threshold=88) is None


def test_find_match_title_disabled_keeps_series_volumes_distinct():
    # Two series volumes share a normalized title key after subtitle stripping.
    idx = NoteIndex()
    idx.add(_note({"title": "The Mongoliad: Book One", "author": "Neal Stephenson", "gr_id": "1"}))
    # A different volume, no shared identifier: must NOT match when title is off.
    assert find_match(idx, title="The Mongoliad: Book Two", author="Neal Stephenson",
                      match_title=False) is None
    # gr_id still matches regardless.
    assert find_match(idx, gr_id="1", match_title=False).get("gr_id") == "1"
    # With title matching on, they collapse (the behavior we avoid for imports).
    assert find_match(idx, title="The Mongoliad: Book Two", author="Neal Stephenson") is not None


def test_merge_fields_is_fill_only():
    meta = {"status": "read", "rating": 5}
    changed = merge_fields(meta, {"status": "want", "rating": None, "isbn": "123"})
    assert meta["status"] == "read"  # not overwritten
    assert meta["rating"] == 5
    assert meta["isbn"] == "123"  # filled blank
    assert changed == ["isbn"]


def test_merge_fields_union_for_lists():
    meta = {"awards": ["hugo-winner-2014"]}
    changed = merge_fields(meta, {"awards": ["hugo-winner-2014", "nebula-winner-2013"]}, union_keys=("awards",))
    assert meta["awards"] == ["hugo-winner-2014", "nebula-winner-2013"]
    assert changed == ["awards"]


def test_new_note_path_disambiguates(tmp_path):
    p1 = new_note_path(tmp_path, "Ancillary Justice", "Ann Leckie", set())
    assert p1.name == "ancillary-justice.md"
    taken = {p1}
    p2 = new_note_path(tmp_path, "Ancillary Justice", "Someone Else", taken)
    assert p2.name == "ancillary-justice-else.md"
