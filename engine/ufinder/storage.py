"""StorageAdapter: the only code that touches user files, and it only reads.

A later UGOS system feed or Native APP swaps in here. Nothing above this layer
knows it is talking to a POSIX mount.
"""
from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from blake3 import blake3

from . import config


@dataclass
class Entry:
    rel_path: str
    size: int
    mtime: float
    inode: int


class PosixAdapter:
    def __init__(self, root: str):
        self.root = Path(root)
        self.ignore = list(config.DEFAULT_EXCLUDES) + self._read_ignore()

    def _read_ignore(self) -> list[str]:
        f = self.root / ".ufinderignore"
        if not f.is_file():
            return []
        lines = (ln.strip() for ln in f.read_text("utf8", "ignore").splitlines())
        return [ln for ln in lines if ln and not ln.startswith("#")]

    def excluded(self, name: str) -> bool:
        return any(fnmatch.fnmatch(name, pat) for pat in self.ignore)

    def walk(self) -> Iterator[Entry]:
        stack = [self.root]
        while stack:
            base = stack.pop()
            try:
                it = list(os.scandir(base))
            except OSError:
                continue
            for e in it:
                if self.excluded(e.name):
                    continue
                try:
                    if e.is_symlink():
                        continue
                    if e.is_dir(follow_symlinks=False):
                        stack.append(Path(e.path))
                    elif e.is_file(follow_symlinks=False):
                        st = e.stat(follow_symlinks=False)
                        yield Entry(
                            rel_path=os.path.relpath(e.path, self.root),
                            size=st.st_size,
                            mtime=st.st_mtime,
                            inode=st.st_ino,
                        )
                except OSError:
                    continue

    def stat(self, rel_path: str) -> Entry | None:
        try:
            st = os.stat(self.root / rel_path, follow_symlinks=False)
        except OSError:
            return None
        return Entry(rel_path, st.st_size, st.st_mtime, st.st_ino)

    def abspath(self, rel_path: str) -> Path:
        path = (self.root / rel_path).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError("path escapes root")
        return path

    def hash(self, rel_path: str) -> str:
        h = blake3()
        with open(self.abspath(rel_path), "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        return h.hexdigest()
