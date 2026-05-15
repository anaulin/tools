# note-triage

A small Textual TUI for triaging markdown notes in a directory. For each note you can **keep** it (skip) or send it to the **Trash**.

## Setup

```sh
cd note-triage
mise install     # python + uv
uv sync
```

## Usage

```sh
uv run note-triage ~/path/to/notes
```

### Keys

- `j` / `↓` — next
- `↑` — previous
- `k` / `space` / `enter` — keep, advance
- `d` — move current note to Trash, advance
- `q` — quit
