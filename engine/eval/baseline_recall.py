"""What does ordinary file search find on the held-out queries?

  file names            what most file search does
  names + document text the next step up: names plus text stored in documents

Neither can see photos, scanned pages, speech or video. Runs on the same index
and the same locked queries as run_eval.py. These are baselines, so nothing here
tunes Ufinder.
"""
import json
import statistics
import sys

sys.path.insert(0, "/app")
from ufinder import db  # noqa: E402
from ufinder.textutil import match_expr  # noqa: E402

truth = json.load(open("/tmp/queries.json"))
conn = db.connect()
WHERE = "f.state='live' AND f.root_id=1"


def names(q):
    expr = " OR ".join(t for t in match_expr(q).split(" OR ") if len(t.strip('"')) >= 3)
    if not expr:
        return []
    rows = conn.execute(
        f"SELECT f.rel_path FROM names_fts JOIN files f ON f.file_id=names_fts.rowid WHERE names_fts MATCH ? AND {WHERE} ORDER BY bm25(names_fts) LIMIT 40",
        (expr,),
    )
    return [r[0] for r in rows]


def text(q):
    expr = match_expr(q)
    if not expr:
        return []
    hits = conn.execute("SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY rank LIMIT 800", (expr,)).fetchall()
    ids = ",".join(str(h[0]) for h in hits) or "0"
    order = {h[0]: i for i, h in enumerate(hits)}
    rows = conn.execute(
        f"SELECT c.chunk_id, f.rel_path FROM chunks c JOIN files f ON f.blob_id=c.blob_id WHERE c.chunk_id IN ({ids}) AND c.kind='text' AND {WHERE}"
    ).fetchall()
    seen, out = set(), []
    for r in sorted(rows, key=lambda r: order[r[0]]):
        if r[1] not in seen:
            seen.add(r[1])
            out.append(r[1])
    return out


def fuse(a, b):
    score = {}
    for lst in (a, b):
        for rank, p in enumerate(lst):
            score[p] = score.get(p, 0) + 1 / (61 + rank)
    return sorted(score, key=score.get, reverse=True)


def recall(found, targets, k=10):
    t = set(targets)
    return len(t & set(found[:k])) / min(len(t), k)


cats = {}
for q in truth["holdout"]:
    n, t = names(q["query"]), text(q["query"])
    row = cats.setdefault(q["cat"], {"names": [], "names_text": []})
    row["names"].append(recall(n, q["targets"]))
    row["names_text"].append(recall(fuse(n, t), q["targets"]))
out = {c: {"n": len(v["names"]), "names": round(statistics.mean(v["names"]), 3), "names_text": round(statistics.mean(v["names_text"]), 3)} for c, v in cats.items()}
every_n = [x for v in cats.values() for x in v["names"]]
every_t = [x for v in cats.values() for x in v["names_text"]]
out["all"] = {"n": len(every_n), "names": round(statistics.mean(every_n), 3), "names_text": round(statistics.mean(every_t), 3)}

kinds = dict(conn.execute("SELECT kind, count(*) FROM files WHERE state='live' GROUP BY kind").fetchall())
total = sum(kinds.values())
pure_text = conn.execute(
    "SELECT count(DISTINCT f.file_id) FROM files f JOIN chunks c ON c.blob_id=f.blob_id WHERE f.state='live' AND c.kind='text'"
).fetchone()[0]
out["corpus"] = {"files": total, "kinds": kinds, "with_native_text": pure_text, "invisible_share": round(1 - pure_text / total, 3)}
print(json.dumps(out))
