from __future__ import annotations

import argparse
import sys
from pathlib import Path

from send2trash import send2trash
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Footer, Header, ListItem, ListView, Static


def list_notes(notes_dir: Path) -> list[Path]:
    return sorted(p for p in notes_dir.iterdir() if p.is_file() and p.suffix.lower() == ".md")


class NoteItem(ListItem):
    def __init__(self, path: Path) -> None:
        super().__init__(Static(path.name))
        self.path = path


class NoteTriageApp(App):
    CSS = """
    Horizontal { height: 1fr; }
    #list { width: 40%; border: solid $accent; }
    #preview { width: 60%; padding: 1 2; border: solid $accent; }
    """

    BINDINGS = [
        Binding("d", "trash", "Trash"),
        Binding("k,space,enter", "keep", "Keep / next"),
        Binding("j,down", "next", "Next"),
        Binding("up", "prev", "Prev"),
        Binding("q", "quit", "Quit"),
    ]

    notes: reactive[list[Path]] = reactive(list)

    def __init__(self, notes_dir: Path) -> None:
        super().__init__()
        self.notes_dir = notes_dir
        self.notes = list_notes(notes_dir)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield ListView(*(NoteItem(p) for p in self.notes), id="list")
            yield Static("", id="preview", expand=True)
        yield Footer()

    def on_mount(self) -> None:
        self.title = "note-triage"
        self.sub_title = str(self.notes_dir)
        if self.notes:
            self.query_one("#list", ListView).index = 0
            self._render_preview(self.notes[0])
        else:
            self._render_preview(None)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        item = event.item
        if isinstance(item, NoteItem):
            self._render_preview(item.path)

    def _render_preview(self, path: Path | None) -> None:
        preview = self.query_one("#preview", Static)
        if path is None:
            preview.update("[dim]No notes left.[/dim]")
            return
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            preview.update(f"[red]Error reading {path.name}: {e}[/red]")
            return
        preview.update(text)

    def _current(self) -> tuple[ListView, NoteItem | None]:
        lv = self.query_one("#list", ListView)
        item = lv.highlighted_child
        return lv, item if isinstance(item, NoteItem) else None

    def action_next(self) -> None:
        lv, _ = self._current()
        lv.action_cursor_down()

    def action_prev(self) -> None:
        lv, _ = self._current()
        lv.action_cursor_up()

    def action_keep(self) -> None:
        self.action_next()

    def action_trash(self) -> None:
        lv, item = self._current()
        if item is None:
            return
        path = item.path
        try:
            send2trash(str(path))
        except OSError as e:
            self.notify(f"Failed to trash {path.name}: {e}", severity="error")
            return
        idx = lv.index or 0
        item.remove()
        self.notes = [p for p in self.notes if p != path]
        if self.notes:
            lv.index = min(idx, len(self.notes) - 1)
        else:
            self._render_preview(None)
        self.notify(f"Trashed {path.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Triage markdown notes in a directory.")
    parser.add_argument("notes_dir", type=Path, help="Directory containing .md files")
    args = parser.parse_args()

    notes_dir: Path = args.notes_dir.expanduser().resolve()
    if not notes_dir.is_dir():
        print(f"error: {notes_dir} is not a directory", file=sys.stderr)
        return 2

    NoteTriageApp(notes_dir).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
