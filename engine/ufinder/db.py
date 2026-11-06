"""SQLite schema: the file table, the content cache, the graph, and the audit log.

Two levels, on purpose:

  files  path -> (size, mtime, inode) -> blob      who has what, and where
  blobs  blob -> extracted text, vectors, entities  what the content means

Renames, copies and duplicates touch only `files`. Nothing is read or embedded
again, because the meaning is keyed by content, not by path.
"""
from __future__ import annotations

import sqlite3
import threading
import time

from . import config

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS roots(
  root_id INTEGER PRIMARY KEY, name TEXT UNIQUE, path TEXT, allow TEXT,
  external_embedding INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS blobs(
  blob_id INTEGER PRIMARY KEY, hash TEXT UNIQUE, size INTEGER, kind TEXT,
  status TEXT DEFAULT 'pending', extractor TEXT, extractor_ver INTEGER,
  error TEXT, properties TEXT DEFAULT '{}', attempts INTEGER DEFAULT 0,
  model_id TEXT, created_at REAL, done_at REAL
);
CREATE INDEX IF NOT EXISTS blobs_status ON blobs(status, kind);

CREATE TABLE IF NOT EXISTS files(
  file_id INTEGER PRIMARY KEY AUTOINCREMENT, root_id INTEGER, rel_path TEXT,
  name TEXT, stem TEXT, ext TEXT, size INTEGER, mtime REAL, inode INTEGER,
  blob_id INTEGER, kind TEXT, state TEXT DEFAULT 'live',
  first_seen REAL, last_seen REAL, event_time REAL,
  UNIQUE(root_id, rel_path)
);
CREATE INDEX IF NOT EXISTS files_blob ON files(blob_id);
CREATE INDEX IF NOT EXISTS files_state ON files(state, root_id);
CREATE INDEX IF NOT EXISTS files_inode ON files(inode);
CREATE INDEX IF NOT EXISTS files_stem ON files(stem);

CREATE TABLE IF NOT EXISTS chunks(
  chunk_id INTEGER PRIMARY KEY AUTOINCREMENT, blob_id INTEGER, ord INTEGER,
  kind TEXT, locator TEXT, text TEXT
);
CREATE INDEX IF NOT EXISTS chunks_blob ON chunks(blob_id);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  text, tokenize='porter unicode61 remove_diacritics 2'
);
CREATE VIRTUAL TABLE IF NOT EXISTS names_fts USING fts5(
  name, tokenize='trigram'
);

-- References found inside one blob. Pure output of parsing, like a per-file
-- metadata record. Turning them into edges needs the whole index, so that
-- happens later, in the resolve phase.
CREATE TABLE IF NOT EXISTS refs(
  blob_id INTEGER, ref_kind TEXT, target TEXT, chunk_id INTEGER, ctx TEXT
);
CREATE INDEX IF NOT EXISTS refs_blob ON refs(blob_id);
CREATE INDEX IF NOT EXISTS refs_target ON refs(target);

CREATE TABLE IF NOT EXISTS entities(
  entity_id INTEGER PRIMARY KEY, norm TEXT UNIQUE, display TEXT, kind TEXT
);

-- Nodes are strings: f12 (file), e7 (entity hub), g3 (ghost, a missing file).
CREATE TABLE IF NOT EXISTS edges(
  src TEXT, dst TEXT, type TEXT, weight REAL, evidence TEXT, updated_at REAL,
  PRIMARY KEY(src, dst, type)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS edges_dst ON edges(dst);

-- References that point at nothing yet. Each resolves on its own when the
-- target file shows up.
CREATE TABLE IF NOT EXISTS ghosts(
  ghost_id INTEGER PRIMARY KEY, norm TEXT UNIQUE, display TEXT, first_seen REAL,
  resolved_file INTEGER
);

CREATE TABLE IF NOT EXISTS events(
  seq INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, type TEXT, root_id INTEGER,
  file_id INTEGER, path TEXT, detail TEXT
);

CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user TEXT, expires REAL);

CREATE TABLE IF NOT EXISTS keys(
  key_id TEXT PRIMARY KEY, secret_hash TEXT, owner TEXT, name TEXT, roots TEXT,
  tools TEXT, max_tier INTEGER, external INTEGER, daily_results INTEGER,
  expires REAL, revoked INTEGER DEFAULT 0, created_at REAL
);
CREATE TABLE IF NOT EXISTS key_usage(key_id TEXT, day TEXT, results INTEGER,
  PRIMARY KEY(key_id, day));

CREATE TABLE IF NOT EXISTS audit(
  seq INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, actor TEXT, key_id TEXT,
  tool TEXT, n_results INTEGER, tier INTEGER, outcome TEXT, prev_hash TEXT, hash TEXT
);

CREATE TABLE IF NOT EXISTS exchange_done(user TEXT, name TEXT, ts REAL, PRIMARY KEY(user, name));
"""

_local = threading.local()


def connect() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(config.DB_PATH, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA foreign_keys=OFF")
        _local.conn = conn
    return conn


def init(settings: config.Settings | None = None) -> sqlite3.Connection:
    conn = connect()
    conn.executescript(SCHEMA)
    if settings:
        for r in settings.roots:
            conn.execute(
                "INSERT INTO roots(root_id,name,path,allow,external_embedding) VALUES(?,?,?,?,?) "
                "ON CONFLICT(root_id) DO UPDATE SET name=excluded.name, path=excluded.path, "
                "allow=excluded.allow, external_embedding=excluded.external_embedding",
                (r.root_id, r.name, r.path, ",".join(r.allow), int(r.external_embedding)),
            )
    return conn


def emit(conn: sqlite3.Connection, type_: str, root_id=None, file_id=None, path=None, detail=None):
    """Append to the change feed. Webhooks and the UI read this table."""
    conn.execute(
        "INSERT INTO events(ts,type,root_id,file_id,path,detail) VALUES(?,?,?,?,?,?)",
        (time.time(), type_, root_id, file_id, path, detail),
    )


def get_meta(conn, key, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(conn, key, value):
    conn.execute(
        "INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )
