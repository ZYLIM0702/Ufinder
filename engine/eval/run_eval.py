"""Compare retrieval methods on one query set.

  python run_eval.py dev       the 56 queries used to fix the design
  python run_eval.py holdout   49 queries locked by hash, run once on the frozen design

Runs inside the gateway container, against the real index, with alice's access.
Two measures. Recall@10 scores the direct list. The budget test shows 20 files
either way: 20 direct results, or 10 direct plus 10 connected through the graph.
"""
import json
import statistics
import sys
import time

sys.path.insert(0, "/app")
from ufinder import db  # noqa: E402
from ufinder.search import Searcher  # noqa: E402

truth = json.load(open("/tmp/queries.json"))
SET = sys.argv[1] if len(sys.argv) > 1 else "dev"
QUERIES = truth["queries"] if SET == "dev" else truth["holdout"]
MODES = {
    "keyword": ("bm25", "names"),
    "vector": ("dense",),
    "hybrid": ("bm25", "names", "dense"),
}
conn = db.connect()
roots = [1]
searcher = Searcher()


def paths(raw):
    # A duplicate is one result with two paths, so each path counts as found.
    return [p for r in raw["results"] for p in r["all_paths"]]


def score(found, targets, k=10):
    targets = set(targets)
    top = found[:k]
    hits = len(targets & set(top))
    recall = hits / min(len(targets), k)
    rr = next((1 / (i + 1) for i, p in enumerate(found) if p in targets), 0.0)
    return recall, rr


rows = []
latency = {m: [] for m in MODES}
full_ms = []
for q in QUERIES:
    row = {"cat": q["cat"], "query": q["query"], "n_targets": len(q["targets"])}
    for mode, parts in MODES.items():
        t0 = time.perf_counter()
        raw = searcher.run(conn, roots, q["query"], limit=30, modes=parts)
        latency[mode].append((time.perf_counter() - t0) * 1000)
        r, rr = score(paths(raw), q["targets"])
        row[mode] = {"recall": round(r, 4), "rr": round(rr, 4)}
    wide = searcher.run(conn, roots, q["query"], limit=20, modes=MODES["hybrid"])
    r20, _ = score(paths(wide), q["targets"], 20)
    t0 = time.perf_counter()
    full = searcher.run(conn, roots, q["query"], limit=10)
    full_ms.append((time.perf_counter() - t0) * 1000)
    linked = [p for c in full["connected"] for p in c["all_paths"]]
    r_full, _ = score(paths(full) + linked, q["targets"], 20)
    row["budget20"] = {"direct_only": round(r20, 4), "direct_plus_connected": round(r_full, 4)}
    rows.append(row)

cats = sorted({r["cat"] for r in rows})
summary = {}
for cat in cats + ["all"]:
    sel = [r for r in rows if cat == "all" or r["cat"] == cat]
    summary[cat] = {"n": len(sel)}
    for mode in MODES:
        summary[cat][mode] = {
            "recall@10": round(statistics.mean(r[mode]["recall"] for r in sel), 3),
            "mrr": round(statistics.mean(r[mode]["rr"] for r in sel), 3),
        }
    summary[cat]["budget20"] = {k: round(statistics.mean(r["budget20"][k] for r in sel), 3) for k in ("direct_only", "direct_plus_connected")}

ts = truth["tshirt"]
shirt = {}
pos, deco, post = set(ts["positives"]), set(ts["decoys_other_word"]), set(ts["decoys_word_on_poster"])
texts = [ts["query"]] if SET == "dev" else truth["tshirt_holdout"]
for mode, parts in MODES.items():
    tally = {"correct_in_top10": 0, "wrong_word_shirts": 0, "word_on_poster": 0}
    for text in texts:
        found = paths(searcher.run(conn, roots, text, limit=30, modes=parts))[:10]
        tally["correct_in_top10"] += len(pos & set(found))
        tally["wrong_word_shirts"] += len(deco & set(found))
        tally["word_on_poster"] += len(post & set(found))
    shirt[mode] = {k: round(v / len(texts), 1) for k, v in tally.items()}

stats = {m: {"p50_ms": round(statistics.median(v), 1), "p95_ms": round(sorted(v)[int(len(v) * 0.95) - 1], 1)} for m, v in latency.items()}
latency["full"] = full_ms
stats = {m: {"p50_ms": round(statistics.median(v), 1), "p95_ms": round(sorted(v)[int(len(v) * 0.95) - 1], 1)} for m, v in latency.items()}
print(json.dumps({"summary": summary, "tshirt": shirt, "latency": stats, "rows": rows}, ensure_ascii=False))
