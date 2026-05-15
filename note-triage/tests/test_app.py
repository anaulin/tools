from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from note_triage.app import NoteTriageApp, list_notes


def test_list_notes_returns_only_md_files_sorted(tmp_path: Path) -> None:
    (tmp_path / "b.md").write_text("b")
    (tmp_path / "a.md").write_text("a")
    (tmp_path / "ignore.txt").write_text("nope")
    (tmp_path / "sub").mkdir()

    result = list_notes(tmp_path)

    assert [p.name for p in result] == ["a.md", "b.md"]


def test_list_notes_empty_dir(tmp_path: Path) -> None:
    assert list_notes(tmp_path) == []


@pytest.mark.asyncio
async def test_trash_action_removes_note_and_advances(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("alpha")
    (tmp_path / "b.md").write_text("beta")

    trashed: list[str] = []

    with patch("note_triage.app.send2trash", side_effect=trashed.append):
        app = NoteTriageApp(tmp_path)
        async with app.run_test() as pilot:
            await pilot.press("d")
            await pilot.pause()

    assert len(trashed) == 1
    assert trashed[0].endswith("a.md")
    assert [p.name for p in app.notes] == ["b.md"]
