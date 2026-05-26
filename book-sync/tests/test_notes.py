import frontmatter

from pathlib import Path

from book_sync.notes import (
    BookNote,
    NoteIndex,
    author_surname,
    book_filename,
    find_match,
    match_key,
    merge_fields,
    new_note_path,
    normalize_title,
    plan_renames,
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


def test_book_filename_forms():
    # standalone: subtitle dropped, author appended
    assert book_filename("The First 20 Hours: How to Learn Anything . . . Fast!", "Josh Kaufman") == \
        "The First 20 Hours - Josh Kaufman"
    # series tag -> "(Series N)", illegal '#'/':' removed
    assert book_filename("Ancillary Justice (Imperial Radch, #1)", "Ann Leckie") == \
        "Ancillary Justice (Imperial Radch 1) - Ann Leckie"
    # same base title, different volume stays distinct
    assert book_filename("The Mongoliad: Book One (Foreworld, #1)", "Neal Stephenson") == \
        "The Mongoliad (Foreworld 1) - Neal Stephenson"
    assert book_filename("The Mongoliad: Book Three (Foreworld, #3)", "Neal Stephenson") == \
        "The Mongoliad (Foreworld 3) - Neal Stephenson"
    # no author
    assert book_filename("Project Hail Mary") == "Project Hail Mary"


def _note(meta, path=None):
    return BookNote(path=path, post=frontmatter.Post(content="", **meta))


def test_plan_renames_restores_subtitle_on_collision(tmp_path):
    # Two different books sharing a main title before ':' must keep their
    # subtitles; a genuine duplicate (identical title) falls back to numbering.
    notes = [
        _note({"title": "Y: The Last Man, Vol. 1: Unmanned", "author": "Brian K. Vaughan"},
              path=tmp_path / "y.md"),
        _note({"title": "Y: The Last Man Omnibus", "author": "Brian K. Vaughan"},
              path=tmp_path / "y-vaughan.md"),
        _note({"title": "Abolish Silicon Valley: How to Liberate Technology", "author": "Wendy Liu"},
              path=tmp_path / "abolish.md"),
        _note({"title": "Abolish Silicon Valley: How to Liberate Technology", "author": "Wendy Liu"},
              path=tmp_path / "abolish-liu.md"),
    ]
    new_names = {old.name: new.name for old, new in plan_renames(notes, tmp_path)}
    # distinct books -> subtitles restored, both unique
    assert new_names["y.md"] == "Y - The Last Man, Vol. 1 - Unmanned - Brian K. Vaughan.md"
    assert new_names["y-vaughan.md"] == "Y - The Last Man Omnibus - Brian K. Vaughan.md"
    # genuine dup -> full title identical, so stay clean + numbered
    abolish = sorted(v for k, v in new_names.items() if k.startswith("abolish"))
    assert abolish == ["Abolish Silicon Valley - Wendy Liu (2).md",
                       "Abolish Silicon Valley - Wendy Liu.md"]


def test_plan_renames_skips_correct_and_disambiguates(tmp_path):
    notes = [
        _note({"title": "Project Hail Mary", "author": "Andy Weir"},
              path=tmp_path / "project-hail-mary.md"),
        _note({"title": "Project Hail Mary", "author": "Andy Weir"},  # already correct
              path=tmp_path / "Project Hail Mary - Andy Weir.md"),
    ]
    plans = {old.name: new.name for old, new in plan_renames(notes, tmp_path)}
    # the correctly-named note is skipped; the slug one is renamed but must not
    # collide with the reserved correct name -> gets a numbered suffix
    assert "Project Hail Mary - Andy Weir.md" not in [old for old in plans]
    assert plans["project-hail-mary.md"] == "Project Hail Mary - Andy Weir (2).md"


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
    assert p1.name == "Ancillary Justice - Ann Leckie.md"
    p2 = new_note_path(tmp_path, "Ancillary Justice", "Ann Leckie", {p1})
    assert p2.name == "Ancillary Justice - Ann Leckie (2).md"
