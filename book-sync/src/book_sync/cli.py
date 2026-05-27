"""book-sync CLI: import reading data into the Obsidian vault."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Annotated

import typer

from . import awards as awards_mod
from . import clippings as clippings_mod
from . import goodreads as goodreads_mod
from . import coalesce as coalesce_mod
from .config import Config, load_config
from .notes import load_index, new_note_path, plan_renames, write_note
from .sync import upsert

app = typer.Typer(
    add_completion=False,
    help="Import Goodreads history, Readwise clippings, and SF award lists into the vault.",
)

ConfigOpt = Annotated[Path, typer.Option("--config", "-c", help="Path to config.toml.")]
DryRunOpt = Annotated[bool, typer.Option("--dry-run", help="Show what would change without writing.")]


def _load(config_path: Path) -> Config:
    if not config_path.exists():
        raise typer.BadParameter(
            f"{config_path} not found. Copy config.example.toml to config.toml."
        )
    return load_config(config_path)


def _report(results, dry_run: bool) -> None:
    counts = Counter(r.action for r in results)
    for r in results:
        if r.action == "noop":
            continue
        mark = "+" if r.action == "create" else "~"
        typer.echo(f"  {mark} {r.path.name}  ({', '.join(r.changed)})")
    prefix = "[dry-run] would " if dry_run else ""
    typer.echo(
        f"{prefix}create {counts['create']}, update {counts['update']}, "
        f"unchanged {counts['noop']}"
    )


@app.command("import-goodreads")
def import_goodreads(
    csv_path: Annotated[Path, typer.Argument(help="Goodreads CSV export.")],
    config: ConfigOpt = Path("config.toml"),
    dry_run: DryRunOpt = False,
) -> None:
    """Backfill book notes from a Goodreads library export."""
    cfg = _load(config)
    idx = load_index(cfg.books_path)
    results = [
        upsert(
            idx,
            cfg.books_path,
            fields=book.fields,
            body=book.body or None,
            threshold=cfg.fuzzy_threshold,
            match_title=False,  # each Goodreads row is a distinct book (goodreads_id)
            dry_run=dry_run,
        )
        for book in goodreads_mod.parse_goodreads_csv(csv_path)
    ]
    _report(results, dry_run)


@app.command("seed-clippings")
def seed_clippings(
    config: ConfigOpt = Path("config.toml"),
    dry_run: DryRunOpt = False,
) -> None:
    """Link/create book notes from Readwise #books clippings."""
    cfg = _load(config)
    idx = load_index(cfg.books_path)
    results = [
        upsert(
            idx,
            cfg.books_path,
            fields={"title": c.title, "author": c.author, "clipping": c.link},
            create_only={"status": cfg.clipping_default_status},
            threshold=cfg.fuzzy_threshold,
            dry_run=dry_run,
        )
        for c in clippings_mod.book_clippings(cfg.clippings_path)
    ]
    _report(results, dry_run)


@app.command("awards")
def awards(
    config: ConfigOpt = Path("config.toml"),
    dry_run: DryRunOpt = False,
) -> None:
    """Tag notes with Hugo/Nebula awards; seed notes for ones not yet logged."""
    cfg = _load(config)
    entries = awards_mod.load_awards(cfg.awards_data)
    if not entries:
        raise typer.BadParameter(
            f"No awards data at {cfg.awards_data}. Generate it first (see README)."
        )
    idx = load_index(cfg.books_path)
    results = [
        upsert(
            idx,
            cfg.books_path,
            fields={"title": b.title, "author": b.author, "awards": b.slugs},
            create_only={"status": cfg.awards_default_status},
            union_keys=("awards",),
            threshold=cfg.fuzzy_threshold,
            dry_run=dry_run,
        )
        for b in awards_mod.group_by_book(entries)
    ]
    _report(results, dry_run)


@app.command("rename")
def rename(
    config: ConfigOpt = Path("config.toml"),
    dry_run: DryRunOpt = False,
) -> None:
    """Rename book notes to 'Title (Series N) - Author'. Skips freeform notes."""
    cfg = _load(config)
    idx = load_index(cfg.books_path)
    plans = plan_renames(idx.notes, cfg.books_path)
    for old, new in plans:
        typer.echo(f"  {old.name}  ->  {new.name}")
        if not dry_run:
            old.rename(new)
    prefix = "[dry-run] would rename" if dry_run else "renamed"
    typer.echo(f"{prefix} {len(plans)} of {len(idx.notes)} notes")


@app.command("coalesce")
def coalesce(
    config: ConfigOpt = Path("config.toml"),
    dry_run: DryRunOpt = False,
    threshold: Annotated[float, typer.Option(help="Min match score to merge (0-100).")] = coalesce_mod.MERGE_THRESHOLD,
) -> None:
    """Fold freeform (no-frontmatter) notes into imported notes, formatting and de-duping."""
    cfg = _load(config)
    idx = load_index(cfg.books_path)
    merges = standalones = 0

    for free in coalesce_mod.freeform_notes(cfg.books_path):
        match, score = coalesce_mod.best_match(idx, free.title)

        if match is not None and score >= threshold:
            merges += 1
            title, author = match.get("title"), match.get("author") or ""
            typer.echo(f"  MERGE  {free.path.name}  ->  {match.path.name}  (score {score:.0f})")
            if dry_run:
                continue
            post = coalesce_mod.build_merged_post(free.path, match)
            write_note(free.path, post)
            match.path.unlink()
            target = new_note_path(cfg.books_path, title, author, {free.path})
            free.path.rename(target)
        else:
            standalones += 1
            cand = f"  (best: {match.get('title')!r} {score:.0f})" if match else ""
            typer.echo(f"  STAND  {free.path.name}{cand}")
            if dry_run:
                continue
            post = coalesce_mod.build_standalone_post(free.path, free, cfg.clipping_default_status)
            write_note(free.path, post)
            target = new_note_path(cfg.books_path, free.title, free.author, {free.path})
            free.path.rename(target)

    prefix = "[dry-run] would " if dry_run else ""
    typer.echo(f"{prefix}merge {merges}, format-only {standalones}")


@app.command("status")
def status(config: ConfigOpt = Path("config.toml")) -> None:
    """Report library stats, unread award winners, and notes missing metadata."""
    cfg = _load(config)
    idx = load_index(cfg.books_path)

    by_status = Counter(n.get("status") or "(none)" for n in idx.notes)
    typer.echo(f"{len(idx.notes)} book notes")
    for st, n in sorted(by_status.items()):
        typer.echo(f"  {st}: {n}")

    unread_winners = [
        n
        for n in idx.notes
        if any("winner" in a for a in (n.get("awards") or []))
        and n.get("status") != "read"
    ]
    typer.echo(f"\nUnread award winners: {len(unread_winners)}")
    for n in unread_winners:
        typer.echo(f"  - {n.get('title')} ({n.get('author')})")

    missing = [n for n in idx.notes if not n.get("status")]
    if missing:
        typer.echo(f"\nNotes missing status: {len(missing)}")
        for n in missing:
            typer.echo(f"  - {n.path.name}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
