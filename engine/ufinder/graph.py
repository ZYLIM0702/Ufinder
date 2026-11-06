"""The graph index: the resolve phase, and graph retrieval.

Parsing looks at one file. Resolving looks at all of them, so it runs as a
separate pass over what changed.

Links people never wrote are found from evidence:
  same_hash    identical content
  version_of   report_v1 and report_v2
  links_to     a real link in a document
  mentions     a document names another file in plain text
  has_entity   a file shares a project, place, person or ID with others
  same_event   media taken close together in time
  similar_to   nearest neighbours in vector space

References to files that do not exist become ghost nodes. A ghost resolves by
itself when the file arrives, and until then it tells the user what is missing.
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict

from . import config, db
from .vectors import VectorStore, name_for

VERSION = re.compile(r"[\s_-]*(?:v\d+|ver\d+|rev\d+|final|draft|copy|old|new|\(\d+\))(?=$|[\s_-])", re.I)
PROJECT = re.compile(r"\bProject\s+[A-Z][a-z]+\b")
CODE = re.compile(r"\b[A-Z]{2,6}-\d{2,6}(?:-\d{1,6})*\b")
TITLE = re.compile(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){1,3}\b")
CAPS = re.compile(r"\b[A-Z]{4,}\b")
STOP_TITLE = {
    "dear sir", "thank you", "best regards", "kind regards", "total due", "payment terms", "action items",
    "next steps", "meeting notes", "due date", "good morning", "the meeting", "this agreement", "the following",
}
STOP_CAPS = {"THE", "THIS", "THAT", "WITH", "FROM", "TOTAL", "DATE", "NOTE", "NOTES", "PAID", "DUE", "TAX", "CASH", "ITEM", "ITEMS", "PAGE"}
GENERIC_STEMS = {"untitled", "document", "new document", "image", "photo", "scan", "notes", "readme"}


def normalize(text: str) -> str:
    return re.sub(r"[^\w]+", " ", text.lower(), flags=re.UNICODE).strip()


def fts_phrase(text: str) -> str:
    return '"' + " ".join(t for t in normalize(text).split()) + '"'


def find_entities(text: str) -> Counter:
    found: Counter = Counter()
    for pat, kind in ((PROJECT, "project"), (CODE, "id")):
        for m in pat.findall(text):
            found[(m, kind)] += 1
    for m in TITLE.findall(text):
        if m.lower() not in STOP_TITLE:
            found[(m, "name")] += 1
    for m in CAPS.findall(text):
        if m not in STOP_CAPS:
            found[(m, "name")] += 1
    return found


class Resolver:
    def __init__(self, store: VectorStore, model_id: str = config.MODEL_ID):
        self.store = store
        self.model_id = model_id
        self.conn = db.connect()

    def _set_edges(self, types: tuple[str, ...], rows: list[tuple[str, str, str, float, str]]) -> None:
        marks = ",".join("?" * len(types))
        now = time.time()
        with_ts = [(a, b, t, w, e, now) for a, b, t, w, e in rows]
        self.conn.execute("BEGIN IMMEDIATE")
        self.conn.execute(f"DELETE FROM edges WHERE type IN ({marks})", types)
        self.conn.executemany("INSERT OR REPLACE INTO edges VALUES(?,?,?,?,?,?)", with_ts)
        self.conn.execute("COMMIT")

    def _live(self):
        return self.conn.execute("SELECT * FROM files WHERE state='live'").fetchall()

    def run(self) -> dict:
        t0 = time.time()
        files = self._live()
        self._blob_edges(files)
        self._reference_edges(files)
        self._entity_edges(files)
        self._event_edges(files)
        self._similarity_edges(files)
        stats = dict(self.conn.execute("SELECT type, count(*) FROM edges GROUP BY type").fetchall())
        ghosts = self.conn.execute("SELECT count(*) FROM ghosts WHERE resolved_file IS NULL").fetchone()[0]
        db.set_meta(self.conn, "graph_stats", json.dumps({"edges": stats, "ghosts": ghosts, "seconds": round(time.time() - t0, 2)}))
        db.emit(self.conn, "resolved", detail=json.dumps({"edges": sum(stats.values()), "ghosts": ghosts}))
        self.conn.execute("PRAGMA optimize")
        return stats

    def _blob_edges(self, files) -> None:
        rows = []
        by_blob = defaultdict(list)
        for f in files:
            if f["blob_id"]:
                by_blob[f["blob_id"]].append(f)
        for group in by_blob.values():
            group.sort(key=lambda f: f["file_id"])
            for a, b in zip(group, group[1:]):
                rows.append((f"f{a['file_id']}", f"f{b['file_id']}", "same_hash", 1.0, "identical content"))
        versions = defaultdict(list)
        for f in files:
            key = VERSION.sub("", f["stem"]).strip(" _-").lower()
            if key and key not in GENERIC_STEMS and len(key) > 3:
                versions[(f["root_id"], key)].append(f)
        for group in versions.values():
            if len({f["blob_id"] for f in group}) < 2:
                continue
            group.sort(key=lambda f: f["mtime"])
            for a, b in zip(group, group[1:]):
                rows.append((f"f{a['file_id']}", f"f{b['file_id']}", "version_of", 1.0, f"{a['name']} then {b['name']}"))
        self._set_edges(("same_hash", "version_of"), rows)

    def _resolve_name(self, target: str, source, by_name: dict) -> dict | None:
        """Best match: same folder first, then the shortest path."""
        base = target.replace("\\", "/").rsplit("/", 1)[-1].strip().lower()
        options = by_name.get(base) or by_name.get(base + ".md") or []
        options = [o for o in options if o["file_id"] != source["file_id"]]
        if not options:
            return None
        folder = source["rel_path"].rsplit("/", 1)[0] if "/" in source["rel_path"] else ""
        same = [o for o in options if o["rel_path"].startswith(folder + "/") and o["root_id"] == source["root_id"]]
        return min(same or options, key=lambda o: (o["root_id"] != source["root_id"], len(o["rel_path"])))

    def _reference_edges(self, files) -> None:
        by_name = defaultdict(list)
        by_blob = defaultdict(list)
        for f in files:
            by_name[f["name"].lower()].append(f)
            by_blob[f["blob_id"]].append(f)
        rows, wanted = [], {}
        refs = self.conn.execute("SELECT blob_id, ref_kind, target FROM refs").fetchall()
        for r in refs:
            for src in by_blob.get(r["blob_id"], []):
                edge = "links_to" if r["ref_kind"] == "link" else "mentions"
                hit = self._resolve_name(r["target"], src, by_name)
                if hit:
                    rows.append((f"f{src['file_id']}", f"f{hit['file_id']}", edge, 1.0, f"names {r['target']}"))
                else:
                    wanted.setdefault(normalize(r["target"]), (r["target"], []))[1].append((src, edge))

        # Plain-text mentions: a file's multi-word name appears in another file.
        for f in files:
            words = normalize(f["stem"]).split()
            if len(words) < 2 or " ".join(words) in GENERIC_STEMS:
                continue
            for hit in self.conn.execute(
                "SELECT DISTINCT c.blob_id FROM chunks_fts CROSS JOIN chunks c ON c.chunk_id=chunks_fts.rowid "
                "WHERE chunks_fts MATCH ? LIMIT 50",
                (fts_phrase(f["stem"]),),
            ):
                for src in by_blob.get(hit["blob_id"], []):
                    if src["file_id"] != f["file_id"]:
                        rows.append((f"f{src['file_id']}", f"f{f['file_id']}", "mentions", 0.8, f"text names {f['stem']}"))
        self._set_edges(("links_to", "mentions"), rows)

        # Ghosts: anything still unresolved.
        now = time.time()
        ghost_rows = []
        was_open = {r[0]: r[1] for r in self.conn.execute("SELECT norm, display FROM ghosts WHERE resolved_file IS NULL")}
        self.conn.execute("UPDATE ghosts SET resolved_file=1")  # cleared below for those still missing
        for norm, (display, sources) in wanted.items():
            self.conn.execute(
                "INSERT INTO ghosts(norm,display,first_seen,resolved_file) VALUES(?,?,?,NULL) "
                "ON CONFLICT(norm) DO UPDATE SET resolved_file=NULL",
                (norm, display, now),
            )
            gid = self.conn.execute("SELECT ghost_id FROM ghosts WHERE norm=?", (norm,)).fetchone()[0]
            for src, edge in sources:
                ghost_rows.append((f"f{src['file_id']}", f"g{gid}", "wants", 1.0, f"refers to {display}, not found"))
        self._set_edges(("wants",), ghost_rows)
        for norm, display in was_open.items():
            if norm not in wanted:
                db.emit(self.conn, "ghost_resolved", detail=display)

    def _entity_edges(self, files) -> None:
        # Candidates come from the patterns above. The inverted index then finds
        # every other place each one appears: OCR, transcripts, any letter case.
        counts: Counter = Counter()
        kinds: dict[str, tuple[str, str]] = {}
        sources = self.conn.execute("SELECT text FROM chunks WHERE text != ''").fetchall()
        for row in sources:
            for (name, kind), n in find_entities(row["text"]).items():
                key = normalize(name)
                if len(key) < 4:
                    continue
                counts[key] += n
                if key not in kinds or kind in ("project", "id"):
                    kinds[key] = (name, kind)
        by_blob = defaultdict(list)
        for f in files:
            by_blob[f["blob_id"]].append(f)
        total = max(len(files), 1)
        max_df = max(int(total * 0.25), 6)
        rows = []
        self.conn.execute("BEGIN IMMEDIATE")
        for key, (display, kind) in kinds.items():
            hits = self.conn.execute(
                "SELECT c.blob_id, count(*) n FROM chunks_fts CROSS JOIN chunks c ON c.chunk_id=chunks_fts.rowid "
                "WHERE chunks_fts MATCH ? GROUP BY c.blob_id LIMIT ?",
                (fts_phrase(key), max_df + 2),
            ).fetchall()
            members = [f for h in hits for f in by_blob.get(h["blob_id"], [])]
            if not 2 <= len(members) <= max_df:
                continue
            self.conn.execute(
                "INSERT INTO entities(norm,display,kind) VALUES(?,?,?) ON CONFLICT(norm) DO UPDATE SET display=excluded.display",
                (key, display, kind),
            )
            eid = self.conn.execute("SELECT entity_id FROM entities WHERE norm=?", (key,)).fetchone()[0]
            rows += [(f"f{f['file_id']}", f"e{eid}", "has_entity", 1.0, display) for f in members]
        self.conn.execute("COMMIT")
        self._set_edges(("has_entity",), rows)

    def _event_edges(self, files) -> None:
        # Chain neighbours in time, per root. Only real capture times count:
        # EXIF for photos, file time for recordings. Copy dates would invent events.
        rows = []
        groups = defaultdict(list)
        for f in files:
            if f["event_time"] and f["kind"] in ("image", "audio", "video"):
                groups[f["root_id"]].append(f)
        for group in groups.values():
            group.sort(key=lambda f: f["event_time"])
            for a, b in zip(group, group[1:]):
                gap = b["event_time"] - a["event_time"]
                if 0 <= gap <= 3 * 3600:
                    rows.append((f"f{a['file_id']}", f"f{b['file_id']}", "same_event", 1.0, f"{int(gap // 60)} minutes apart"))
        self._set_edges(("same_event",), rows)

    def _similarity_edges(self, files) -> None:
        name = name_for(self.model_id, "blobs")
        if not self.store.client.collection_exists(name):
            return
        by_blob = defaultdict(list)
        for f in files:
            by_blob[f["blob_id"]].append(f)
        blobs = [b for b in by_blob if b]
        all_roots = sorted({f["root_id"] for f in files}) or [0]
        rows = []
        for start in range(0, len(blobs), 200):
            batch = blobs[start : start + 200]
            for rec in self.store.retrieve(name, batch):
                for hit in self.store.search(name, rec.vector, all_roots, config.KNN_EDGES + 1, exclude_blob=rec.id):
                    if hit.score < config.KNN_MIN_SCORE:
                        continue
                    a = by_blob[rec.id][0]
                    for b in by_blob.get(hit.id, [])[:1]:
                        if a["root_id"] == b["root_id"] and a["file_id"] != b["file_id"]:
                            lo, hi = sorted((a["file_id"], b["file_id"]))
                            rows.append((f"f{lo}", f"f{hi}", "similar_to", float(hit.score), f"similarity {hit.score:.2f}"))
        self._set_edges(("similar_to",), rows)


# ---- retrieval ------------------------------------------------------------


class GraphView:
    """Edges limited to what one user may see. Hidden files are never walked."""

    def __init__(self, conn, roots: list[int], weights: dict | None = None):
        self.conn = conn
        self.roots = set(roots)
        self.weights = weights or config.EDGE_WEIGHTS
        self.cache: dict[str, list[tuple[str, float, str, str]]] = {}
        self.seen: dict[str, bool] = {}

    def can_see(self, node: str) -> bool:
        """A file by its folder. A hub or ghost only through a file the user can read."""
        hit = self.seen.get(node)
        if hit is not None:
            return hit
        if node[0] == "f":
            row = self.conn.execute("SELECT root_id, state FROM files WHERE file_id=?", (int(node[1:]),)).fetchone()
            ok = bool(row) and row["state"] == "live" and row["root_id"] in self.roots
        else:
            ok = False
            for r in self.conn.execute("SELECT src FROM edges WHERE dst=? AND src LIKE 'f%'", (node,)):
                if self.can_see(r["src"]):
                    ok = True
                    break
        self.seen[node] = ok
        return ok

    def neighbours(self, node: str) -> list[tuple[str, float, str, str]]:
        hit = self.cache.get(node)
        if hit is not None:
            return hit
        out = []
        rows = self.conn.execute(
            "SELECT dst AS other, type, weight, evidence FROM edges WHERE src=? "
            "UNION ALL SELECT src AS other, type, weight, evidence FROM edges WHERE dst=?",
            (node, node),
        ).fetchall()
        for r in rows:
            other = r["other"]
            if other[0] == "f" and not self.can_see(other):
                continue
            base = self.weights.get(r["type"], 0.0)
            if base:
                out.append((other, base * float(r["weight"] or 1.0), r["type"], r["evidence"] or ""))
        self.cache[node] = out
        return out


def personalized_pagerank(view: GraphView, seeds: dict[str, float], alpha=config.PPR_ALPHA, eps=config.PPR_EPSILON) -> dict[str, float]:
    """Forward push. Work depends on eps and alpha, not on the size of the graph."""
    total = sum(seeds.values()) or 1.0
    residual = {k: v / total for k, v in seeds.items()}
    rank: dict[str, float] = defaultdict(float)
    queue = list(residual)
    while queue:
        u = queue.pop()
        r_u = residual.get(u, 0.0)
        nbrs = view.neighbours(u)
        degree = sum(w for _, w, _, _ in nbrs)
        if degree == 0:
            rank[u] += r_u
            residual[u] = 0.0
            continue
        if r_u < eps * max(degree, 1.0):
            continue
        rank[u] += alpha * r_u
        residual[u] = 0.0
        share = (1 - alpha) * r_u / degree
        for v, w, _, _ in nbrs:
            before = residual.get(v, 0.0)
            residual[v] = before + share * w
            if before < eps * max(sum(x[1] for x in view.neighbours(v)), 1.0) <= residual[v]:
                queue.append(v)
    return dict(rank)


def explain_path(view: GraphView, target: str, seeds: set[str], labels) -> str:
    """Shortest evidence path back to a direct hit, up to two hops."""
    for node, _w, etype, evidence in view.neighbours(target):
        if node in seeds:
            return f"{etype}: {evidence}"
    for node, _w, etype, evidence in view.neighbours(target):
        for second, _w2, _t2, _e2 in view.neighbours(node):
            if second in seeds:
                return f"via {labels(node)}" if node[0] == "e" else f"{etype}: {evidence}"
    return "connected"
