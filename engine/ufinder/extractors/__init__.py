"""Extractor plugins. A new file type is one class and one register call.

Each extractor is a pure function of file content. It returns text pieces, images
to embed, typed properties and raw references. It knows nothing about other
files, so results can be cached by content hash and run in parallel. Bumping
`version` re-extracts only that file type.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

KINDS = {"text": "document", "image": "photo", "audio": "recording", "video": "video"}


@dataclass
class Piece:
    kind: str                # text | ocr | transcript | image | frame
    text: str = ""
    locator: str = ""        # page 3, 01:12, frame 4
    image: bytes | None = None


@dataclass
class Extracted:
    pieces: list[Piece] = field(default_factory=list)
    properties: dict = field(default_factory=dict)
    refs: list[tuple[str, str]] = field(default_factory=list)  # (kind, target)
    thumbnail: bytes | None = None


@dataclass
class Plugin:
    name: str
    version: int
    kind: str
    extensions: tuple[str, ...]
    run: Callable[[Path], Extracted]


_REGISTRY: dict[str, Plugin] = {}


def register(plugin: Plugin) -> None:
    for ext in plugin.extensions:
        _REGISTRY[ext] = plugin


def plugin_for(ext: str) -> Plugin | None:
    return _REGISTRY.get(ext.lower())


def all_plugins() -> list[Plugin]:
    return list({p.name: p for p in _REGISTRY.values()}.values())


def load_builtin() -> None:
    from . import documents, media  # noqa: F401


load_builtin()
