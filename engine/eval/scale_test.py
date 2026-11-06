"""One million real files: Ufinder against find, grep and ripgrep, on the same data.

Runs in a throwaway stack. Every file is written to disk, and the same text goes
into the index. Word frequency follows a Zipf curve over a 50,000-word vocabulary,
like real text. The model is skipped, because this measures storage and retrieval,
so query vectors are random.

Baselines run with a warm file cache on fast storage. That is their best case.
"""
import json
import os
import random
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, "/app")
os.environ["UFINDER_DATA"] = "/data"
import numpy as np  # noqa: E402

from ufinder import config, db  # noqa: E402
from ufinder.graph import GraphView, personalized_pagerank  # noqa: E402
from ufinder.search import Searcher  # noqa: E402
from ufinder.storage import PosixAdapter  # noqa: E402
from ufinder.vectors import VectorStore, name_for  # noqa: E402

N = int(os.environ.get("SCALE_N", "1000000"))
BATCH = 20000
DIM = config.VECTOR_DIM
MODEL = config.MODEL_ID
FILES = Path(os.environ.get("SCALE_FILES", "/files"))
rng = np.random.default_rng(7)
r = random.Random(7)
WORDS = np.array([f"w{i:05d}" for i in range(50000)])
_p = 1.0 / np.arange(1, 50001)
_p /= _p.sum()
COMMON, MIDDLE = [str(w) for w in WORDS[:20]], [str(w) for w in WORDS[500:8000]]


class FakeLocal:
    id = MODEL
    dim = DIM

    def texts(self, t):
        v = rng.standard_normal((len(t), DIM))
        return (v / np.linalg.norm(v, axis=1, keepdims=True)).tolist()

    def images(self, t):
        return self.texts(t)


def timed(cmd: list[str], runs: int = 3) -> float:
    """Median of the warm runs, in milliseconds. The first run warms the cache."""
    laps = []
    for _ in range(runs + 1):
        t = time.perf_counter()
        subprocess.run(cmd, capture_output=True)
        laps.append((time.perf_counter() - t) * 1000)
    return round(statistics.median(laps[1:]), 1)


conn = db.init()
conn.execute("PRAGMA synchronous=OFF")
store = VectorStore()
chunks = name_for(MODEL, "chunks")
store.ensure(chunks, DIM)
conn.execute("INSERT OR IGNORE INTO roots(root_id,name,path,allow) VALUES(1,'a','/files','u1'),(2,'b','/y','u2')")

t0 = time.time()
for start in range(1, N + 1, BATCH):
    ids = list(range(start, min(start + BATCH, N + 1)))
    draw = WORDS[rng.choice(50000, 150 * len(ids), p=_p)].reshape(len(ids), 150)
    files, cs, fts, names, blobs, edges = [], [], [], [], [], []
    for row, i in zip(draw, ids):
        root = 1 if i % 10 else 2
        rel = f"d{i % 1000}/file-{i}.txt"
        text = " ".join(row) + f" zqx{i:07d}"
        path = FILES / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        blobs.append((i, f"h{i}", 1000, "text", "done"))
        files.append((i, root, rel, f"file-{i}.txt", f"file-{i}", ".txt", 1000, 1.0, i, i, "text"))
        cs.append((i, i, 0, "text", "page 1", text))
        fts.append((i, text))
        names.append((i, rel))
        for _ in range(5):
            j = r.randint(1, N)
            if j != i:
                edges.append((f"f{i}", f"f{j}", "has_entity", 0.7, "x", 0.0))
    conn.execute("BEGIN")
    conn.executemany("INSERT INTO blobs(blob_id,hash,size,kind,status) VALUES(?,?,?,?,?)", blobs)
    conn.executemany("INSERT INTO files(file_id,root_id,rel_path,name,stem,ext,size,mtime,inode,blob_id,kind) VALUES(?,?,?,?,?,?,?,?,?,?,?)", files)
    conn.executemany("INSERT INTO chunks(chunk_id,blob_id,ord,kind,locator,text) VALUES(?,?,?,?,?,?)", cs)
    conn.executemany("INSERT INTO chunks_fts(rowid,text) VALUES(?,?)", fts)
    conn.executemany("INSERT INTO names_fts(rowid,name) VALUES(?,?)", names)
    conn.executemany("INSERT OR IGNORE INTO edges VALUES(?,?,?,?,?,?)", edges)
    conn.execute("COMMIT")
    v = rng.standard_normal((len(ids), DIM)).astype("float32")
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    for k in range(0, len(ids), 800):
        part = ids[k : k + 800]
        store.upsert(chunks, part, v[k : k + 800].tolist(), [{"blob_id": i, "roots": [1 if i % 10 else 2]} for i in part])
    print("loaded", ids[-1], round(time.time() - t0), "s", flush=True)
conn.execute("PRAGMA optimize")
load_s = time.time() - t0
for _ in range(600):
    st = store.client.get_collection(chunks)
    if str(st.status).endswith("green") and (st.indexed_vectors_count or 0) >= N * 0.9:
        break
    time.sleep(3)
print("hnsw ready", round(time.time() - t0), "s", flush=True)

target = 123456
word = f"zqx{target:07d}"
name = f"file-{target}.txt"
baseline = {
    "find_by_name_ms": timed(["find", str(FILES), "-name", name]),
    "grep_exact_word_ms": timed(["grep", "-rl", word, str(FILES)]),
    "ripgrep_exact_word_ms": timed(["rg", "-l", word, str(FILES)]),
    "grep_three_words_ms": timed(["grep", "-rlE", "w00600|w01500|w03000", str(FILES)], runs=1),
}
print("baselines", baseline, flush=True)

s = Searcher(store=store, local=FakeLocal())
queries = [" ".join(r.choices(MIDDLE, k=3)) for _ in range(40)] + [f"zqx{r.randint(1, N):07d}" for _ in range(40)]
laps = {"full": [], "keyword_only": [], "common_words": [], "exact_id": []}
for q in queries:
    t = time.perf_counter()
    s.run(conn, [1], q, limit=20)
    laps["full"].append((time.perf_counter() - t) * 1000)
    t = time.perf_counter()
    s.run(conn, [1], q, limit=20, modes=("bm25", "names"))
    keyword = (time.perf_counter() - t) * 1000
    laps["keyword_only"].append(keyword)
    if q.startswith("zqx"):
        laps["exact_id"].append(keyword)
for _ in range(15):
    t = time.perf_counter()
    s.run(conn, [1], " ".join(r.choices(COMMON, k=3)), limit=20)
    laps["common_words"].append((time.perf_counter() - t) * 1000)

found = s.run(conn, [1], word, limit=5, modes=("bm25",))
hidden = s.run(conn, [1], f"zqx{20:07d}", limit=5, modes=("bm25",))  # file 20 sits in root 2

t = time.perf_counter()
view = GraphView(conn, [1], config.WALK_WEIGHTS)
scores = personalized_pagerank(view, {"f11": 1.0})
ppr_ms = (time.perf_counter() - t) * 1000

adapter = PosixAdapter(str(FILES))
t = time.perf_counter()
walked = sum(1 for _ in adapter.walk())
scan_s = time.perf_counter() - t

source_bytes = 0
for sub in FILES.iterdir():
    source_bytes += sum(e.stat().st_size for e in os.scandir(sub))


def pct(v, q):
    return round(sorted(v)[int(len(v) * q) - 1], 1)


out = {
    "files": N, "vectors": N, "edges": conn.execute("SELECT count(*) FROM edges").fetchone()[0],
    "latency_ms": {k: {"p50": round(statistics.median(v), 1), "p95": pct(v, 0.95)} for k, v in laps.items()},
    "baseline_ms": baseline,
    "ppr_ms": round(ppr_ms, 1), "ppr_nodes_touched": len(scores),
    "exact_id_found": any(name in x["path"] for x in found["results"]),
    "other_root_hidden": hidden["count"] == 0,
    "rescan_files": walked, "rescan_seconds": round(scan_s, 1),
    "source_mb": round(source_bytes / 1e6),
    "sqlite_mb": round(os.path.getsize(config.DB_PATH) / 1e6),
    "load_seconds": round(load_s),
    "python_peak_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024),
}
print("RESULT " + json.dumps(out), flush=True)
