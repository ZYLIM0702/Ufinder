"""Hybrid search. No LLM anywhere on this path.

  1. parse operators by rule
  2. keyword search on content (BM25)
  3. keyword search on names and paths
  4. vector search, in the same space for text and images
  5. fuse with reciprocal rank fusion
  6. walk the graph from the top hits with personalized PageRank
  7. fuse again, so a file can win on its connections alone

Access filters apply before every step, so counts and scores never reflect a
file the user cannot read.
"""
from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from . import config, db, models
from .graph import GraphView, explain_path, personalized_pagerank
from .textutil import match_expr, query_terms
from .vectors import VectorStore, name_for

OP = re.compile(r'(?P<neg>-)?(?P<key>type|path|file|after|before):(?:"(?P<q>[^"]+)"|(?P<v>\S+))')
TYPE_ALIASES = {
    "photo": "image", "image": "image", "picture": "image", "doc": "text", "document": "text", "text": "text",
    "audio": "audio", "recording": "audio", "video": "video",
}
COMMON_TERM_DOCS = 20000
KIND_LABEL = {"text": "document", "image": "photo", "audio": "recording", "video": "video", "other": "file"}


@dataclass
class Query:
    text: str = ""
    types: set[str] = field(default_factory=set)
    path: list[str] = field(default_factory=list)
    not_path: list[str] = field(default_factory=list)
    after: float | None = None
    before: float | None = None


def parse(raw: str) -> Query:
    q = Query()

    def take(m: re.Match) -> str:
        key, value = m["key"], m["q"] or m["v"]
        if key == "type":
            q.types.add(TYPE_ALIASES.get(value.lower(), value.lower()))
        elif key in ("path", "file"):
            (q.not_path if m["neg"] else q.path).append(value)
        else:
            try:
                ts = datetime.fromisoformat(value).timestamp()
            except ValueError:
                return m[0]
            setattr(q, key, ts)
        return " "

    q.text = re.sub(r"\s+", " ", OP.sub(take, raw)).strip()
    return q


class Searcher:
    def __init__(self, store: VectorStore | None = None, local: models.Local | None = None):
        self.store = store or VectorStore()
        self.local = local or models.Local()

    # ---- candidates ---------------------------------------------------------

    @staticmethod
    def _where(roots: list[int], q: Query) -> tuple[str, list]:
        """The same access and operator filter for every retriever."""
        marks = ",".join(str(int(r)) for r in roots) or "0"
        # The unary plus keeps SQLite off the (state, root) index. Every query here
        # already has a precise key, and using that index scans each visible file.
        sql = f"+f.state='live' AND +f.root_id IN ({marks})"
        args: list = []
        if q.types:
            sql += f" AND f.kind IN ({','.join('?' * len(q.types))})"
            args += list(q.types)
        for p in q.path:
            sql += " AND f.rel_path LIKE ?"
            args.append(f"%{p}%")
        for p in q.not_path:
            sql += " AND f.rel_path NOT LIKE ?"
            args.append(f"%{p}%")
        if q.after:
            sql += " AND coalesce(f.event_time, f.mtime) >= ?"
            args.append(q.after)
        if q.before:
            sql += " AND coalesce(f.event_time, f.mtime) <= ?"
            args.append(q.before)
        return sql, args

    @staticmethod
    def _focus(conn, text: str) -> str:
        """Drop terms that match nearly everything when rarer terms are present.

        Scoring a word found in most documents is the one slow case in FTS5, and
        such a word adds little to the ranking.
        """
        terms = query_terms(text)
        common, rare = [], []
        for t in terms:
            n = conn.execute(
                "SELECT count(*) FROM (SELECT 1 FROM chunks_fts WHERE chunks_fts MATCH ? LIMIT ?)", (f'"{t}"', COMMON_TERM_DOCS)
            ).fetchone()[0]
            (common if n >= COMMON_TERM_DOCS else rare).append(t)
        if rare:
            return " OR ".join(f'"{t}"' for t in rare)
        return " AND ".join(f'"{t}"' for t in common)

    def _bm25(self, conn, text: str, where: str, args: list) -> list[tuple[int, dict]]:
        expr = self._focus(conn, text)
        if not expr:
            return []
        # Rank inside the full-text index first, then join. Letting the planner
        # start from `chunks` is a full scan, and only shows up at scale.
        limit = config.CANDIDATES * 4
        while True:
            hits = conn.execute(
                "SELECT rowid AS id, rank AS s FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?", (expr, limit)
            ).fetchall()
            ids = ",".join(str(h["id"]) for h in hits) or "0"
            order = {h["id"]: i for i, h in enumerate(hits)}
            rows = conn.execute(
                f"SELECT c.chunk_id, c.blob_id, c.kind, c.locator, c.text FROM chunks c WHERE c.chunk_id IN ({ids}) "
                f"AND EXISTS(SELECT 1 FROM files f WHERE f.blob_id=c.blob_id AND {where})",
                args,
            ).fetchall()
            best: dict[int, dict] = {}
            for r in sorted(rows, key=lambda r: order[r["chunk_id"]]):
                if r["blob_id"] not in best:
                    best[r["blob_id"]] = {"kind": r["kind"], "locator": r["locator"], "text": r["text"]}
            # A strict filter can hide most top hits, so widen until full or exhausted.
            if len(best) >= config.CANDIDATES or len(hits) < limit or limit >= config.CANDIDATES * 64:
                return list(best.items())[: config.CANDIDATES]
            limit *= 4

    def _names(self, conn, text: str, where: str, args: list) -> list[tuple[int, dict]]:
        expr = " OR ".join(t for t in match_expr(text).split(" OR ") if len(t.strip('"')) >= 3)
        if not expr:
            return []
        hits = conn.execute(
            "SELECT rowid AS id FROM names_fts WHERE names_fts MATCH ? ORDER BY rank LIMIT ?", (expr, config.CANDIDATES * 4)
        ).fetchall()
        ids = ",".join(str(h["id"]) for h in hits) or "0"
        order = {h["id"]: i for i, h in enumerate(hits)}
        rows = conn.execute(f"SELECT f.file_id, f.blob_id, f.rel_path FROM files f WHERE f.file_id IN ({ids}) AND {where}", args).fetchall()
        out: dict[int, dict] = {}
        for r in sorted(rows, key=lambda r: order[r["file_id"]]):
            out.setdefault(r["blob_id"], {"kind": "name", "locator": "", "text": r["rel_path"]})
        return list(out.items())[: config.CANDIDATES]

    def _dense(self, conn, vector, roots, where: str, args: list, model_id=None) -> dict[str, list[tuple[int, dict]]]:
        """Pictures and text vote separately.

        A photo holds an image vector and a vector for the text read from it. If
        one best chunk spoke for the file, a poster with the right word would tie a
        photo that matches both the word and the scene.
        """
        name = name_for(model_id or self.local.id, "chunks")
        points = self.store.search(name, vector, roots, config.CANDIDATES * 2)
        if not points:
            return {}
        ids = ",".join(str(int(p.id)) for p in points)
        info = {r["chunk_id"]: r for r in conn.execute(f"SELECT chunk_id,kind,locator,text FROM chunks WHERE chunk_id IN ({ids})")}
        blobs = ",".join(str(int(p.payload["blob_id"])) for p in points)
        allowed = {r[0] for r in conn.execute(f"SELECT blob_id FROM files f WHERE f.blob_id IN ({blobs}) AND {where}", args)}
        best: dict[str, dict[int, dict]] = {"visual": {}, "meaning": {}}
        for p in points:
            blob = p.payload["blob_id"]
            c = info.get(p.id)
            if c is None:  # a vector with no record in the file table is not evidence
                continue
            side = best["visual" if c["kind"] in ("image", "frame") else "meaning"]
            if blob in allowed and blob not in side:
                side[blob] = {"kind": c["kind"], "locator": c["locator"], "text": c["text"], "score": float(p.score)}
        return {k: list(v.items())[: config.CANDIDATES] for k, v in best.items() if v}

    def _rows(self, conn, blobs, where: str, args: list) -> dict[int, list]:
        if not blobs:
            return {}
        marks = ",".join(str(int(b)) for b in blobs)
        out: dict[int, list] = defaultdict(list)
        for r in conn.execute(f"SELECT f.* FROM files f WHERE f.blob_id IN ({marks}) AND {where}", args):
            out[r["blob_id"]].append(r)
        return out

    # ---- pipeline -----------------------------------------------------------

    def run(self, conn, user_roots: list[int], raw: str = "", image: bytes | None = None, limit: int = 20,
            modes: tuple[str, ...] = ("bm25", "names", "dense", "graph"), use_external: bool = False) -> dict:
        t0 = time.perf_counter()
        q = parse(raw)
        where, args = self._where(user_roots, q)
        lists: dict[str, list[tuple[int, dict]]] = {}
        if q.text and "bm25" in modes:
            lists["bm25"] = self._bm25(conn, q.text, where, args)
        if q.text and "names" in modes:
            lists["names"] = self._names(conn, q.text, where, args)
        if "dense" in modes and (q.text or image):
            vector = self.local.images([image])[0] if image else self.local.texts([q.text])[0]
            lists.update(self._dense(conn, vector, user_roots, where, args))
            # A query can be as private as a file, so it leaves only when the caller
            # asks for it, once per search. Connecting a model does not turn this on.
            ext = models.get_external(conn) if use_external else None
            if ext is not None and q.text and not image:
                allowed = [r["root_id"] for r in conn.execute("SELECT root_id FROM roots WHERE external_embedding=1")]
                shared = [r for r in user_roots if r in allowed]
                if shared:
                    try:
                        got = self._dense(conn, ext.texts([q.text])[0], shared, where, args, ext.id)
                        lists["external"] = got.get("meaning", [])
                    except Exception:
                        pass

        fused: dict[int, float] = defaultdict(float)
        evidence: dict[int, dict[str, dict]] = defaultdict(dict)
        for name, items in lists.items():
            for rank, (blob, info) in enumerate(items[: config.FUSION_WINDOW]):
                fused[blob] += 1.0 / (config.RRF_K + rank + 1)
                evidence[blob].setdefault(name, info)

        ranked = sorted(fused, key=fused.get, reverse=True)
        by_blob = self._rows(conn, ranked, where, args)
        results = [self._result(conn, blob, by_blob[blob], fused[blob], evidence.get(blob, {}), None)
                   for blob in [b for b in ranked if b in by_blob][:limit]]

        connected = []
        if "graph" in modes and results:
            view = GraphView(conn, user_roots, config.WALK_WEIGHTS)
            seeds_blobs = [b for b in ranked if b in by_blob][: config.PPR_SEEDS]
            seeds = {f"f{by_blob[b][0]['file_id']}": 1.0 / (i + 1) for i, b in enumerate(seeds_blobs)}
            scores = personalized_pagerank(view, seeds)
            shown = {r["file_id"] for r in results}
            walked = sorted(
                ((n, s) for n, s in scores.items() if n[0] == "f" and n not in seeds and int(n[1:]) not in shown),
                key=lambda x: x[1], reverse=True,
            )
            ids = ",".join(n[1:] for n, _ in walked[: config.CANDIDATES]) or "0"
            rows = {f"f{r['file_id']}": r for r in conn.execute(f"SELECT f.* FROM files f WHERE f.file_id IN ({ids}) AND {where}", args)}
            labels = self._labeller(conn)
            seen_blobs = {b for b in ranked[:limit]}
            for node, score in walked:
                row = rows.get(node)
                if row is None or row["blob_id"] in seen_blobs:
                    continue
                seen_blobs.add(row["blob_id"])
                connected.append(self._result(conn, row["blob_id"], [row], score, {}, explain_path(view, node, set(seeds), labels)))
                if len(connected) >= config.CONNECTED_LIMIT:
                    break

        return {
            "query": raw, "took_ms": round((time.perf_counter() - t0) * 1000, 1), "count": len(results),
            "results": results, "connected": connected, "stages": {k: len(v) for k, v in lists.items()},
        }

    def _result(self, conn, blob: int, rows: list, score: float, found: dict, graph: str | None) -> dict:
        f = rows[0]
        props = conn.execute("SELECT properties FROM blobs WHERE blob_id=?", (blob,)).fetchone()
        return {
            "file_id": f["file_id"], "root_id": f["root_id"], "path": f["rel_path"], "name": f["name"],
            "type": KIND_LABEL.get(f["kind"], "file"), "size": f["size"], "mtime": f["mtime"],
            "score": round(score, 5), "reasons": self._reasons(found, graph),
            "properties": json.loads(props["properties"] or "{}") if props else {},
            "copies": len(rows), "has_thumb": f["kind"] in ("image", "video"),
            "all_paths": [r["rel_path"] for r in rows],
        }

    @staticmethod
    def _labeller(conn):
        def label(node: str) -> str:
            if node[0] == "e":
                row = conn.execute("SELECT display FROM entities WHERE entity_id=?", (int(node[1:]),)).fetchone()
                return row["display"] if row else node
            return node
        return label

    @staticmethod
    def _reasons(found: dict[str, dict], graph: str | None) -> list[dict]:
        out = []
        for name, info in found.items():
            kind, text = info.get("kind", ""), (info.get("text") or "")
            if name == "names":
                out.append({"signal": "name", "label": "File name", "snippet": text[:120], "locator": ""})
            elif name in ("visual", "meaning", "external"):
                is_visual = name == "visual"
                out.append({
                    "signal": "visual" if is_visual else "meaning", "label": "Looks like" if is_visual else "Means",
                    "snippet": "" if is_visual else text[:220], "locator": info.get("locator", ""),
                    "similarity": round(info.get("score", 0.0), 3),
                })
            else:
                label = {"ocr": "Text in image", "transcript": "Said aloud", "text": "Text"}.get(kind, "Text")
                out.append({"signal": kind or "text", "label": label, "snippet": text[:220], "locator": info.get("locator", "")})
        if graph:
            out.append({"signal": "graph", "label": "Connected", "snippet": graph, "locator": ""})
        return out
