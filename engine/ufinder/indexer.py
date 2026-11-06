"""The background indexer.

  scan      walk folders, update the file table. Fast, no content read if
            size, mtime and inode match.
  extract   per-content work: text, OCR, speech, vectors. Pure and resumable.
  resolve   graph work across files. Runs when extraction goes quiet.

Search works from the first pass and improves as each stage finishes. A crash
loses nothing: job state lives in SQLite, and a half-done blob just runs again.
"""
from __future__ import annotations

import json
import logging
import os
import re
import signal
import threading
import time
from pathlib import Path

import httpx

from . import config, db, models
from .extractors import all_plugins, plugin_for
from .graph import Resolver
from .storage import PosixAdapter
from .textutil import fts_text
from .vectors import VectorStore, name_for

log = logging.getLogger("ufinder.indexer")
STOP = threading.Event()
ORDER = "CASE kind WHEN 'text' THEN 0 WHEN 'image' THEN 1 WHEN 'audio' THEN 2 ELSE 3 END"


def thumb_path(blob_hash: str) -> Path:
    return config.THUMB_DIR / blob_hash[:2] / f"{blob_hash}.jpg"


class Indexer:
    def __init__(self, settings: config.Settings):
        self.settings = settings
        db.init(settings)
        self.adapters = {r.root_id: PosixAdapter(r.path) for r in settings.roots}
        self.local = models.Local()
        self.store = VectorStore()
        self.chunks_c = name_for(self.local.id, "chunks")
        self.blobs_c = name_for(self.local.id, "blobs")
        self.store.ensure(self.chunks_c, self.local.dim)
        self.store.ensure(self.blobs_c, self.local.dim)
        self.dirty = threading.Event()
        self.conn.execute("UPDATE blobs SET status='pending' WHERE status='working'")
        self.conn.execute("UPDATE blobs SET status='pending', attempts=0 WHERE status='failed' AND error LIKE '%Connection%'")
        self.requeue_outdated()
        for row in self.conn.execute(
            "SELECT blob_id FROM blobs b WHERE NOT EXISTS(SELECT 1 FROM files f WHERE f.blob_id=b.blob_id AND f.state='live')"
        ).fetchall():
            self._purge_blob(row["blob_id"])

    def requeue_outdated(self) -> None:
        """A newer extractor version re-runs only that file type."""
        for row in self.conn.execute("SELECT DISTINCT extractor, extractor_ver FROM blobs WHERE status='done'").fetchall():
            plugin = next((p for p in all_plugins() if p.name == row["extractor"]), None)
            if plugin and plugin.version != row["extractor_ver"]:
                self.conn.execute("UPDATE blobs SET status='pending', attempts=0 WHERE extractor=? AND extractor_ver=?", (row["extractor"], row["extractor_ver"]))

    @property
    def conn(self):
        return db.connect()  # one connection per thread

    # ---- scan -------------------------------------------------------------

    def scan_root(self, root: config.Root) -> dict:
        adapter = self.adapters[root.root_id]
        seen, stats = set(), {"same": 0, "new": 0, "changed": 0, "moved": 0, "deleted": 0}
        known = {
            r["rel_path"]: r
            for r in self.conn.execute("SELECT * FROM files WHERE root_id=? AND state='live'", (root.root_id,))
        }
        by_inode = {r["inode"]: r for r in known.values()}
        now = time.time()
        fresh = []
        for e in adapter.walk():
            seen.add(e.rel_path)
            row = known.get(e.rel_path)
            if row and row["size"] == e.size and row["mtime"] == e.mtime and row["inode"] == e.inode:
                stats["same"] += 1
                continue
            fresh.append((e, row))

        gone = {p: r for p, r in known.items() if p not in seen}
        for e, row in fresh:
            if row is None:
                prior = by_inode.get(e.inode)
                if prior is not None and prior["rel_path"] in gone and prior["size"] == e.size:
                    self._move(root, prior, e.rel_path, now)
                    del gone[prior["rel_path"]]
                    stats["moved"] += 1
                    continue
            self._upsert(root, adapter, e, row, now)
            stats["changed" if row else "new"] += 1

        # Same content under a new path, when the inode changed (copy, then delete).
        for path, row in list(gone.items()):
            twin = self.conn.execute(
                "SELECT file_id FROM files WHERE root_id=? AND blob_id=? AND state='live' AND rel_path!=?",
                (root.root_id, row["blob_id"], path),
            ).fetchone()
            self._delete(root, row, now, moved_to=twin[0] if twin else None)
            stats["deleted"] += 1
        return stats

    def _kind(self, ext: str) -> str:
        p = plugin_for(ext)
        return p.kind if p else "other"

    def _upsert(self, root, adapter, e, row, now) -> None:
        path = Path(e.rel_path)
        kind = self._kind(path.suffix)
        blob_hash = adapter.hash(e.rel_path)
        blob = self.conn.execute("SELECT blob_id FROM blobs WHERE hash=?", (blob_hash,)).fetchone()
        if blob is None:
            status = "pending" if kind != "other" else "skipped"
            cur = self.conn.execute(
                "INSERT INTO blobs(hash,size,kind,status,created_at) VALUES(?,?,?,?,?)",
                (blob_hash, e.size, kind, status, now),
            )
            blob_id = cur.lastrowid
        else:
            blob_id = blob["blob_id"]
        event_time = e.mtime if kind in ("audio", "video") else None
        taken = self.conn.execute("SELECT properties FROM blobs WHERE blob_id=?", (blob_id,)).fetchone()
        if taken and taken["properties"]:
            event_time = json.loads(taken["properties"]).get("taken", event_time)
        if row:
            self.conn.execute(
                "UPDATE files SET size=?,mtime=?,inode=?,blob_id=?,kind=?,last_seen=?,event_time=? WHERE file_id=?",
                (e.size, e.mtime, e.inode, blob_id, kind, now, event_time, row["file_id"]),
            )
            file_id = row["file_id"]
            db.emit(self.conn, "modify", root.root_id, file_id, e.rel_path)
            if row["blob_id"] != blob_id:
                self._drop_if_orphan(row["blob_id"])  # old text must not outlive the edit
        else:
            cur = self.conn.execute(
                "INSERT INTO files(root_id,rel_path,name,stem,ext,size,mtime,inode,blob_id,kind,first_seen,last_seen,event_time) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(root_id,rel_path) DO UPDATE SET state='live',size=excluded.size,"
                "mtime=excluded.mtime,inode=excluded.inode,blob_id=excluded.blob_id,kind=excluded.kind,last_seen=excluded.last_seen,"
                "event_time=excluded.event_time",
                (root.root_id, e.rel_path, path.name, path.stem, path.suffix.lower(), e.size, e.mtime, e.inode, blob_id, kind, now, now, event_time),
            )
            file_id = self.conn.execute(
                "SELECT file_id FROM files WHERE root_id=? AND rel_path=?", (root.root_id, e.rel_path)
            ).fetchone()[0]
            self.conn.execute("INSERT OR REPLACE INTO names_fts(rowid,name) VALUES(?,?)", (file_id, e.rel_path))
            db.emit(self.conn, "create", root.root_id, file_id, e.rel_path)
        self._sync_roots(blob_id)
        self.dirty.set()

    def _move(self, root, row, new_path, now) -> None:
        """A rename costs one row update. Nothing is read or embedded."""
        path = Path(new_path)
        self.conn.execute("DELETE FROM files WHERE root_id=? AND rel_path=? AND state!='live'", (root.root_id, new_path))
        self.conn.execute(
            "UPDATE files SET rel_path=?,name=?,stem=?,ext=?,last_seen=? WHERE file_id=?",
            (new_path, path.name, path.stem, path.suffix.lower(), now, row["file_id"]),
        )
        self.conn.execute("INSERT OR REPLACE INTO names_fts(rowid,name) VALUES(?,?)", (row["file_id"], new_path))
        db.emit(self.conn, "rename", root.root_id, row["file_id"], new_path, row["rel_path"])
        self.dirty.set()

    def _delete(self, root, row, now, moved_to=None) -> None:
        fid = row["file_id"]
        self.conn.execute("UPDATE files SET state='deleted',last_seen=? WHERE file_id=?", (now, fid))
        self.conn.execute("DELETE FROM names_fts WHERE rowid=?", (fid,))
        node = f"f{fid}"
        self.conn.execute("DELETE FROM edges WHERE src=? OR dst=?", (node, node))
        db.emit(self.conn, "delete", root.root_id, fid, row["rel_path"])
        self._drop_if_orphan(row["blob_id"])
        self.dirty.set()

    def _drop_if_orphan(self, blob_id) -> None:
        if not blob_id:
            return
        others = self.conn.execute("SELECT count(*) FROM files WHERE blob_id=? AND state='live'", (blob_id,)).fetchone()[0]
        if others == 0:
            self._purge_blob(blob_id)
        else:
            self._sync_roots(blob_id)

    def _purge_blob(self, blob_id: int) -> None:
        """Deleted means gone: text, vectors, references and thumbnail."""
        row = self.conn.execute("SELECT hash FROM blobs WHERE blob_id=?", (blob_id,)).fetchone()
        ids = [r[0] for r in self.conn.execute("SELECT chunk_id FROM chunks WHERE blob_id=?", (blob_id,))]
        self.conn.execute("BEGIN IMMEDIATE")
        self.conn.executemany("DELETE FROM chunks_fts WHERE rowid=?", [(i,) for i in ids])
        self.conn.execute("DELETE FROM chunks WHERE blob_id=?", (blob_id,))
        self.conn.execute("DELETE FROM refs WHERE blob_id=?", (blob_id,))
        self.conn.execute("DELETE FROM blobs WHERE blob_id=?", (blob_id,))
        self.conn.execute("COMMIT")
        self.store.delete_blob(self.chunks_c, blob_id)
        self.store.delete_blob(self.blobs_c, blob_id)
        if row:
            thumb_path(row["hash"]).unlink(missing_ok=True)

    def _roots_of(self, blob_id) -> list[int]:
        rows = self.conn.execute("SELECT DISTINCT root_id FROM files WHERE blob_id=? AND state='live'", (blob_id,))
        return sorted(r[0] for r in rows)

    def _sync_roots(self, blob_id) -> None:
        row = self.conn.execute("SELECT status FROM blobs WHERE blob_id=?", (blob_id,)).fetchone()
        if row and row["status"] == "done":
            roots = self._roots_of(blob_id)
            self.store.set_roots(self.chunks_c, blob_id, roots)
            self.store.set_roots(self.blobs_c, blob_id, roots)

    # ---- extract ----------------------------------------------------------

    def next_blob(self):
        return self.conn.execute(
            f"SELECT * FROM blobs WHERE status='pending' ORDER BY {ORDER}, created_at DESC LIMIT 1"
        ).fetchone()

    def extract_blob(self, blob) -> None:
        blob_id = blob["blob_id"]
        f = self.conn.execute(
            "SELECT * FROM files WHERE blob_id=? AND state='live' ORDER BY mtime DESC LIMIT 1", (blob_id,)
        ).fetchone()
        if f is None:
            self.conn.execute("UPDATE blobs SET status='skipped' WHERE blob_id=?", (blob_id,))
            return
        self.conn.execute("UPDATE blobs SET status='working', attempts=attempts+1 WHERE blob_id=?", (blob_id,))
        plugin = plugin_for(f["ext"])
        adapter = self.adapters[f["root_id"]]
        try:
            result = plugin.run(adapter.abspath(f["rel_path"]))
            self._store_result(blob, f, plugin, result)
        except httpx.TransportError:
            # The service is down, not the file. Wait, and do not count it against the file.
            self.conn.execute("UPDATE blobs SET status='pending', attempts=attempts-1 WHERE blob_id=?", (blob_id,))
            while not self.local.healthy() and not STOP.is_set():
                log.info("embedder unavailable, waiting")
                STOP.wait(3)
        except Exception as exc:  # one bad file must never stop the queue
            log.exception("extract failed for blob %s", blob_id)
            status = "failed" if blob["attempts"] >= 2 else "pending"
            self.conn.execute("UPDATE blobs SET status=?, error=? WHERE blob_id=?", (status, str(exc)[:300], blob_id))

    def _store_result(self, blob, f, plugin, result) -> None:
        blob_id = blob["blob_id"]
        old = [r[0] for r in self.conn.execute("SELECT chunk_id FROM chunks WHERE blob_id=?", (blob_id,))]
        self.conn.execute("BEGIN IMMEDIATE")
        self.conn.executemany("DELETE FROM chunks_fts WHERE rowid=?", [(i,) for i in old])
        self.conn.execute("DELETE FROM chunks WHERE blob_id=?", (blob_id,))
        self.conn.execute("DELETE FROM refs WHERE blob_id=?", (blob_id,))
        ids, texts, images, text_ids, image_ids = [], [], [], [], []
        for ord_, piece in enumerate(result.pieces):
            cur = self.conn.execute(
                "INSERT INTO chunks(blob_id,ord,kind,locator,text) VALUES(?,?,?,?,?)",
                (blob_id, ord_, piece.kind, piece.locator, piece.text),
            )
            cid = cur.lastrowid
            ids.append(cid)
            if piece.text:
                self.conn.execute("INSERT INTO chunks_fts(rowid,text) VALUES(?,?)", (cid, fts_text(piece.text)))
            if piece.image is not None:
                images.append(piece.image)
                image_ids.append(cid)
            elif piece.text:
                texts.append(piece.text)
                text_ids.append(cid)
        self.conn.executemany(
            "INSERT INTO refs(blob_id,ref_kind,target) VALUES(?,?,?)",
            [(blob_id, k, t) for k, t in dict.fromkeys(result.refs)],
        )
        self.conn.execute("COMMIT")

        vectors = self.local.images(images) + self.local.texts(texts)
        vector_ids = image_ids + text_ids
        roots = self._roots_of(blob_id)
        # Re-extraction makes new chunk IDs, so clear the old vectors first. Left
        # behind, they keep voting in search with no text attached.
        self.store.delete_blob(self.chunks_c, blob_id)
        self.store.delete_blob(self.blobs_c, blob_id)
        self.store.upsert(
            self.chunks_c, vector_ids, vectors,
            [{"blob_id": blob_id, "roots": roots} for _ in vector_ids],
        )
        if vectors:
            import numpy as np

            mean = np.mean(np.array(vectors), axis=0)
            mean = mean / max(float(np.linalg.norm(mean)), 1e-9)
            self.store.upsert(self.blobs_c, [blob_id], [mean.tolist()], [{"blob_id": blob_id, "roots": roots}])

        if result.thumbnail:
            path = thumb_path(blob["hash"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(result.thumbnail)

        self._external_embed(blob_id, f, text_ids, texts, roots)
        props = json.dumps(result.properties)
        self.conn.execute(
            "UPDATE blobs SET status='done', extractor=?, extractor_ver=?, properties=?, model_id=?, done_at=? WHERE blob_id=?",
            (plugin.name, plugin.version, props, self.local.id, time.time(), blob_id),
        )
        if result.properties.get("taken"):
            self.conn.execute("UPDATE files SET event_time=? WHERE blob_id=?", (result.properties["taken"], blob_id))
        db.emit(self.conn, "changed", f["root_id"], f["file_id"], f["rel_path"])

    def _external_embed(self, blob_id, f, ids, texts, roots) -> None:
        """Only for folders the owner opted in. Everything else never leaves."""
        ext = models.get_external(self.conn)
        if ext is None or not texts:
            return
        allowed = {r.root_id for r in self.settings.roots if r.external_embedding}
        if not set(roots) <= allowed:
            return
        try:
            name = name_for(ext.id, "chunks")
            self.store.ensure(name, ext.dim)
            self.store.upsert(name, ids, ext.texts(texts), [{"blob_id": blob_id, "roots": roots} for _ in ids])
        except Exception as exc:
            log.warning("external model unavailable: %s", exc)

    # ---- loop -------------------------------------------------------------

    def status(self) -> None:
        rows = dict(self.conn.execute("SELECT status, count(*) FROM blobs GROUP BY status").fetchall())
        db.set_meta(self.conn, "indexer_status", json.dumps({"blobs": rows, "ts": time.time()}))

    def resolve(self) -> None:
        self.dirty.clear()
        log.info("resolve: %s", Resolver(self.store, self.local.id).run())
        self.status()

    def run(self) -> None:
        while not self.local.healthy() and not STOP.is_set():
            log.info("waiting for embedder")
            STOP.wait(3)
        watcher = threading.Thread(target=watch, args=(self,), daemon=True)
        watcher.start()
        for root in self.settings.roots:
            with LOCK:
                log.info("scan %s: %s", root.name, self.scan_root(root))
        db.set_meta(self.conn, "scan_done_at", time.time())
        self.dirty.set()
        last_scan = last_resolve = time.time()
        while not STOP.is_set():
            blob = self.next_blob()
            if blob is not None:
                self.extract_blob(blob)
                self.status()
                # A first index can run for days. The graph has to grow during
                # that time, not appear at the end.
                if time.time() - last_resolve >= config.RESOLVE_INTERVAL_SECONDS:
                    self.resolve()
                    last_resolve = time.time()
                continue
            if self.dirty.is_set():
                self.resolve()
                last_resolve = time.time()
                db.set_meta(self.conn, "index_ready_at", time.time())
            if time.time() - last_scan >= config.RECONCILE_SECONDS:
                with LOCK:
                    for root in self.settings.roots:
                        self.scan_root(root)
                last_scan = time.time()
            STOP.wait(config.RESOLVE_IDLE_SECONDS)


LOCK = threading.Lock()


def watch(ix: Indexer) -> None:
    """Live changes via inotify. The reconcile walk catches anything missed."""
    from watchfiles import watch as fs_watch

    paths = [r.path for r in ix.settings.roots]
    for _changes in fs_watch(*paths, stop_event=STOP, debounce=int(config.DEBOUNCE_SECONDS * 1000), rust_timeout=2000):
        with LOCK:
            for root in ix.settings.roots:
                try:
                    ix.scan_root(root)
                except Exception:  # one bad event must not end live tracking
                    log.exception("scan failed for %s", root.name)
        ix.dirty.set()


def main() -> None:
    logging.basicConfig(level=os.environ.get("UFINDER_LOG", "INFO"), format="%(asctime)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    signal.signal(signal.SIGTERM, lambda *_: STOP.set())
    signal.signal(signal.SIGINT, lambda *_: STOP.set())
    settings = config.load_settings()
    Indexer(settings).run()


if __name__ == "__main__":
    main()
