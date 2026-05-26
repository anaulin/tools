"""Configuration loading from config.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    vault_path: Path
    books_dir: str
    clippings_dir: str
    clipping_default_status: str
    awards_default_status: str
    awards_data: Path
    fuzzy_threshold: int

    @property
    def books_path(self) -> Path:
        return self.vault_path / self.books_dir

    @property
    def clippings_path(self) -> Path:
        return self.vault_path / self.clippings_dir


def load_config(path: Path) -> Config:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    vault = data["vault"]
    clippings = data.get("clippings", {})
    awards = data.get("awards", {})
    matching = data.get("matching", {})

    awards_data = awards.get("data_file", "data/awards.json")
    awards_path = Path(awards_data)
    if not awards_path.is_absolute():
        awards_path = path.parent / awards_path

    return Config(
        vault_path=Path(vault["path"]).expanduser(),
        books_dir=vault.get("books_dir", "Reference/books"),
        clippings_dir=vault.get("clippings_dir", "Reference/Clippings"),
        clipping_default_status=clippings.get("default_status", "read"),
        awards_default_status=awards.get("default_status", "want"),
        awards_data=awards_path,
        fuzzy_threshold=int(matching.get("fuzzy_threshold", 88)),
    )
