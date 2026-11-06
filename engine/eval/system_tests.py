"""End-to-end checks against the running Docker stack. Writes eval/results/system.json.

Each check prints PASS or FAIL with what it observed. Nothing is mocked: requests
go through the published port, and container checks run inside the containers.
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx

BASE = os.environ.get("UFINDER_URL", "http://localhost:8787")
ROOT = Path(__file__).parent.parent
SOURCES = ROOT / "data/sources"
EXCHANGE = ROOT / "data/exchange"
ENV = {**os.environ, "DOCKER_CONTEXT": os.environ.get("DOCKER_CONTEXT", "orbstack")}
truth = json.loads((ROOT / "eval/queries.json").read_text())
results: list[dict] = []


def check(group: str, name: str, ok: bool, detail="") -> bool:
    results.append({"group": group, "name": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(("PASS" if ok else "FAIL"), f"[{group}] {name}", "" if ok else f"-> {detail}", flush=True)
    return ok


def dc(*args, stdin=None, timeout=120):
    return subprocess.run(["docker", "compose", *args], cwd=ROOT, env=ENV, capture_output=True, text=True, input=stdin, timeout=timeout)


def sh(service: str, code: str):
    return dc("exec", "-T", service, "python", "-c", code)


def client(user: str) -> httpx.Client:
    c = httpx.Client(base_url=BASE, timeout=120)
    r = c.post("/api/login", json={"user": user, "password": f"{user}-demo-pass"})
    r.raise_for_status()
    return c


def key_client(token: str) -> httpx.Client:
    return httpx.Client(base_url=BASE, timeout=120, headers={"Authorization": f"Bearer {token}"})


def search(c, q, limit=20):
    r = c.post("/v1/search", json={"q": q, "limit": limit})
    r.raise_for_status()
    return r.json()


def wait_for(fn, seconds=120, step=0.5):
    t0 = time.time()
    while time.time() - t0 < seconds:
        v = fn()
        if v:
            return v, time.time() - t0
        time.sleep(step)
    return None, seconds


# ---- containment -----------------------------------------------------------


def containment():
    services = ["gateway", "indexer", "embedder"]
    probe = (
        "import socket\n"
        "out=[]\n"
        "for h,p in (('1.1.1.1',443),('8.8.8.8',53)):\n"
        "    try:\n"
        "        socket.create_connection((h,p),3); out.append('open')\n"
        "    except Exception as e: out.append(type(e).__name__)\n"
        "try:\n"
        "    socket.getaddrinfo('example.com',443); out.append('dns-ok')\n"
        "except Exception as e: out.append('dns-fail')\n"
        "print(out)\n"
    )
    for s in services:
        r = sh(s, probe)
        out = r.stdout.strip()
        check("no internet", f"{s} cannot reach the internet", "open" not in out and "dns-ok" not in out and out != "", out or r.stderr[-200:])
    r = dc("exec", "-T", "qdrant", "bash", "-c", "timeout 3 bash -c '</dev/tcp/1.1.1.1/443' && echo open || echo closed")
    check("no internet", "qdrant cannot reach the internet", "closed" in r.stdout, r.stdout + r.stderr[-120:])

    for s in services + ["edge"]:
        r = sh(s, "import os;s=open('/proc/self/status').read();c=[l for l in s.splitlines() if l.startswith('CapEff')][0].split()[1];print(os.getuid(),c)")
        uid, caps = (r.stdout.split() + ["?", "?"])[:2]
        check("least privilege", f"{s} is non-root with zero capabilities", uid != "0" and int(caps, 16) == 0 if caps != "?" else False, r.stdout + r.stderr[-120:])
    r = dc("exec", "-T", "qdrant", "bash", "-c", "id -u; grep CapEff /proc/self/status")
    check("least privilege", "qdrant is non-root with zero capabilities", r.stdout.split()[0] != "0" and int(r.stdout.split()[-1], 16) == 0, r.stdout)

    r = sh("indexer", "open('/sources/shared/write-test.txt','w').write('x')")
    check("read only", "indexer cannot write to source files", "Read-only file system" in r.stderr, r.stderr[-120:])
    r = sh("indexer", "open('/app/ufinder/evil.py','w').write('x')")
    check("read only", "container filesystem is read-only", r.returncode != 0, r.stderr[-120:])
    r = sh("gateway", "import os;print(os.path.exists('/sources'))")
    check("read only", "gateway has no mount of user files", "False" in r.stdout, r.stdout)

    with httpx.Client(timeout=5) as c:
        ok = False
        try:
            c.get("http://localhost:6333/collections")
            ok = False
        except httpx.HTTPError:
            ok = True
        check("no internet", "vector database has no published port", ok)
    ports = dc("ps", "--format", "{{.Service}}={{.Ports}}").stdout
    published = [l.split("=")[0] for l in ports.splitlines() if "->" in l]
    check("no internet", "only the edge forwarder publishes a port", published == ["edge"], ports)
    r = sh("edge", "import os;print(os.listdir('/data'), os.path.ismount('/data'), os.path.exists('/config'), os.path.exists('/sources'))")
    check("no internet", "edge forwarder holds no data, config or files", r.stdout.strip() == "[] False False False", r.stdout)


# ---- access -----------------------------------------------------------------


def access():
    alice, bob = client("alice"), client("bob")
    trap_a, trap_b = truth["meta"]["trap_alice"], truth["meta"]["trap_bob"]
    a = search(alice, trap_a)
    paths = [r["path"] for r in a["results"]]
    check("user segregation", "alice finds her private marker", any("blood-test" in p for p in paths), paths[:3])
    for q in (trap_a, "ZEBRA ORCHID passport renewal", "salary review confidential 118,000", "blood test cholesterol"):
        r = search(bob, q)
        leaked = [x["path"] for x in r["results"] if any(w in x["path"] for w in ("blood-test", "salary-review", "passport-note"))]
        check("user segregation", f"bob gets no alice file for '{q[:28]}'", not leaked, leaked)
    r = search(alice, trap_b)
    check("user segregation", "alice gets no bob file", not [x for x in r["results"] if "divorce" in x["path"]])

    target = next(x for x in a["results"] if "blood-test" in x["path"])
    fid = target["file_id"]
    for path in (f"/v1/files/{fid}", f"/v1/files/{fid}/related", f"/v1/files/{fid}/thumb", f"/v1/graph?center={fid}", f"/v1/snippet/{fid}"):
        code = bob.get(path).status_code
        check("user segregation", f"bob gets 404 on {path.replace(str(fid), 'ID')}", code == 404, code)
    nodes = bob.get("/v1/graph?limit=2000").json()["nodes"]
    check("user segregation", "alice private file is not in bob's graph", f"f{fid}" not in {n["id"] for n in nodes} and not any("blood" in n["label"] for n in nodes))
    labels = " ".join(n["label"] for n in nodes).lower()
    check("user segregation", "shared topics from alice's files are not in bob's graph", "zebra" not in labels and "orchid" not in labels, labels[:120])
    alice_labels = " ".join(n["label"] for n in alice.get("/v1/graph?limit=2000").json()["nodes"]).lower()
    check("user segregation", "alice does see her own topic in her graph", "zebra" in alice_labels or "orchid" in alice_labels, alice_labels[:80])
    feed = bob.get("/v1/changes?since=0&limit=500").json()["events"]
    check("user segregation", "bob's change feed has no alice paths", not [e for e in feed if "blood-test" in str(e.get("path")) or "salary" in str(e.get("path"))], len(feed))
    st = bob.get("/v1/status").json()
    check("user segregation", "status shows bob no global index counts", not st["graph"] and not st["indexer"], list(st))
    spoof = httpx.get(f"{BASE}/api/me", headers={"Ugreen-User-Name": "alice"})
    check("user segregation", "a forged identity header is ignored in login mode", spoof.status_code == 401, spoof.status_code)
    bob_key = bob.post("/v1/keys", json={"name": "bob-tool", "max_tier": 2, "external": False, "roots": [1, 2]}).json()
    check("user segregation", "bob cannot create a key for alice's folder", 2 not in bob_key["roots"], bob_key["roots"])
    r = search(key_client(bob_key["token"]), trap_a)
    check("user segregation", "bob's key sees nothing of alice", not [x for x in r["results"] if "blood" in x.get("path", "")])

    canaries = truth["meta"]["canaries"]
    for c in canaries:
        r = search(alice, c)
        bad = [x for x in r["results"] if x["name"] in (".env", "deploy.pem", "config")]
        check("exclusions", f"credential file not indexed ({c})", not bad, bad[:1])
    r = sh("gateway", "import sqlite3;c=sqlite3.connect('/data/ufinder.db');print(c.execute(\"select count(*) from files where name in ('.env','deploy.pem') or rel_path like '%.git/%'\").fetchone()[0])")
    check("exclusions", "file table has zero credential files", r.stdout.strip() == "0", r.stdout)


# ---- keys and agents --------------------------------------------------------


def keys():
    alice = client("alice")
    mk = lambda **kw: alice.post("/v1/keys", json={"name": "t", **kw}).json()
    l1 = mk(max_tier=1, external=True)
    l2 = mk(max_tier=2, external=True)
    r = search(key_client(l1["token"]), "Harbor Mills flour payment")
    check("content tiers", "L1 key gets paths, no text", r["results"] and not any("snippet" in s for x in r["results"] for s in x["reasons"]), r["results"][:1])
    r = search(key_client(l2["token"]), "vendor terms attacker@example.com")
    text = json.dumps(r["results"])  # the query echo is the caller's own text
    check("content tiers", "L2 key gets snippets with the email redacted", "[email]" in text and "attacker@example.com" not in text, text[:200])
    high = mk(max_tier=3, external=True)
    check("content tiers", "external key cannot reach full text", high["max_tier"] == 2, high["max_tier"])

    narrow = mk(max_tier=1, tools=["get_file"])
    code = key_client(narrow["token"]).post("/v1/search", json={"q": "flour"}).status_code
    check("key limits", "key cannot use a tool it was not given", code == 403, code)
    budget = mk(max_tier=1, daily_results=20)  # direct and connected results both count
    c = key_client(budget["token"])
    first = c.post("/v1/search", json={"q": "flour", "limit": 5}).status_code
    second = c.post("/v1/search", json={"q": "flour", "limit": 5}).status_code
    check("key limits", "daily budget stops bulk reads", (first, second) == (200, 429), (first, second))
    gone = mk(max_tier=1)
    alice.delete(f"/v1/keys/{gone['key_id']}")
    check("key limits", "revoked key is refused", key_client(gone["token"]).post("/v1/search", json={"q": "flour"}).status_code == 401)
    check("key limits", "made-up key is refused", key_client("ufd_00000000_nope").post("/v1/search", json={"q": "x"}).status_code == 401)
    check("key limits", "keys cannot mint keys", key_client(l2["token"]).post("/v1/keys", json={"name": "x"}).status_code == 403)
    check("key limits", "no login means no access", httpx.post(f"{BASE}/v1/search", json={"q": "x"}).status_code == 401)
    stored = sh("gateway", "import sqlite3;c=sqlite3.connect('/data/ufinder.db');print(c.execute('select secret_hash from keys limit 1').fetchone()[0])").stdout.strip()
    check("key limits", "key secret is stored only as a hash", len(stored) == 64 and stored not in l2["token"], stored[:12])

    r = sh("gateway", "import sqlite3,hashlib;c=sqlite3.connect('/data/ufinder.db');print(c.execute('select count(*) from audit').fetchone()[0])")
    chain = alice.get("/v1/audit?limit=1").json()["chain"]
    check("audit", "audit chain verifies", chain["ok"] and chain["rows"] > 5, chain)
    tamper = (
        "import sys;sys.path.insert(0,'/app')\n"
        "import sqlite3,os\n"
        "from ufinder import security as s\n"
        "c=sqlite3.connect('/data/ufinder.db',isolation_level=None);c.row_factory=sqlite3.Row\n"
        "old=c.execute('select seq,actor from audit order by seq limit 1 offset 2').fetchone()\n"
        "c.execute('update audit set actor=? where seq=?',('nobody',old['seq']))\n"
        "print(s.verify_audit(c)['ok'])\n"
        "c.execute('update audit set actor=? where seq=?',(old['actor'],old['seq']))\n"
        "print(s.verify_audit(c)['ok'])\n"
    )
    out = sh("gateway", tamper).stdout.split()
    check("audit", "editing a past row breaks the chain", out == ["False", "True"], out)

    r = key_client(l2["token"]).post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).json()
    names = {t["name"] for t in r["result"]["tools"]}
    risky = {n for n in names if any(w in n for w in ("delete", "send", "write", "move", "upload", "exec"))}
    check("prompt injection", "MCP exposes no send, delete or write tool", not risky, sorted(names))
    fid = next(x["file_id"] for x in search(alice, "vendor terms update")["results"] if "vendor-terms" in x["path"])
    r = key_client(l2["token"]).get(f"/v1/snippet/{fid}?q=instructions").json()
    check("prompt injection", "hostile file text comes back flagged as untrusted", r.get("untrusted_content") is True and "attacker@example.com" not in json.dumps(r), r.get("notice"))
    plan = key_client(l2["token"]).post("/v1/proposals", json={"kind": "duplicates"}).json()
    check("prompt injection", "organizing returns a plan and changes nothing", plan["applied"] is False and len(plan["plan"]) >= 1, plan["note"])


# ---- change tracking --------------------------------------------------------


def changes():
    alice = client("alice")
    folder = SOURCES / "shared/Test"
    folder.mkdir(exist_ok=True)
    new = folder / "field-report-a.txt"  # no search word in the name: only content can match
    new.write_text("The quokka survey on Rottnest counted 4128 animals during the marigold census.")
    found, t_add = wait_for(lambda: [r for r in search(alice, "marigold census quokka")["results"] if "field-report-a" in r["path"]])
    check("change tracking", f"new file's content searchable in {t_add:.1f}s", found and t_add < 60, t_add)
    fid = found[0]["file_id"] if found else 0
    done_sql = "import sqlite3;c=sqlite3.connect('/data/ufinder.db');print(c.execute('select b.status from files f join blobs b on b.blob_id=f.blob_id where f.file_id=%d').fetchone()[0])" % fid
    wait_for(lambda: sh("gateway", done_sql).stdout.strip() == "done", 60)

    sql = "import sqlite3;c=sqlite3.connect('/data/ufinder.db');print(c.execute('select b.blob_id,b.done_at,(select count(*) from chunks k where k.blob_id=b.blob_id) from files f join blobs b on b.blob_id=f.blob_id where f.file_id=%d').fetchone())" % fid
    before = sh("gateway", sql).stdout.strip()
    moved = folder / "moved-renamed-report.txt"
    new.rename(moved)
    got, t_ren = wait_for(lambda: [r for r in search(alice, "marigold census quokka")["results"] if "moved-renamed" in r["path"]])
    after = sh("gateway", sql).stdout.strip()
    check("change tracking", f"rename seen in {t_ren:.1f}s with no re-embedding", got and before == after and got[0]["file_id"] == fid, (before, after))

    moved.write_text("The wombat survey replaced the old text and counted lanterns in the orchard.")
    fresh, t_edit = wait_for(lambda: [r for r in search(alice, "wombat lanterns orchard")["results"] if "moved-renamed" in r["path"]])
    stale = [r for r in search(alice, "marigold census quokka")["results"] if "moved-renamed" in r["path"] and "Text" in json.dumps(r["reasons"])]
    check("change tracking", f"edit reindexed in {t_edit:.1f}s", fresh and t_edit < 60, t_edit)
    check("change tracking", "old text is gone after edit", not stale, stale[:1])
    wait_for(lambda: sh("gateway", "import sqlite3;c=sqlite3.connect('/data/ufinder.db');print(c.execute(\"select count(*) from chunks where text like '%marigold%'\").fetchone()[0])").stdout.strip() == "0", 30)
    r = sh("gateway", "import sqlite3;c=sqlite3.connect('/data/ufinder.db');print(c.execute(\"select count(*) from chunks where text like '%marigold%'\").fetchone()[0], c.execute(\"select count(*) from chunks_fts where chunks_fts match 'marigold'\").fetchone()[0])")
    check("change tracking", "edited-out text is purged from the index, not just hidden", r.stdout.split() == ["0", "0"], r.stdout)

    r = sh("gateway", (
        "import sys;sys.path.insert(0,'/app')\n"
        "from ufinder.vectors import VectorStore,name_for\n"
        "from ufinder import config,db\n"
        "s=VectorStore();c=db.connect();n=name_for(config.MODEL_ID,'chunks')\n"
        "ids=[p.id for p in s.client.scroll(n,limit=20000,with_payload=False,with_vectors=False)[0]]\n"
        "known={r[0] for r in c.execute('select chunk_id from chunks')}\n"
        "print(len(ids),len(set(ids)-known))\n"))
    parts = r.stdout.split()
    check("change tracking", "no stale vectors remain after re-indexing", len(parts) == 2 and parts[1] == "0", r.stdout + r.stderr[-120:])

    moved.unlink()
    gone, t_del = wait_for(lambda: not [r for r in search(alice, "wombat lanterns orchard")["results"] if "moved-renamed" in r["path"]])
    check("change tracking", f"delete purged in {t_del:.1f}s", gone and t_del < 60, t_del)
    r = sh("gateway", "import sqlite3;c=sqlite3.connect('/data/ufinder.db');print(c.execute(\"select count(*) from chunks where text like '%wombat%'\").fetchone()[0], c.execute(\"select count(*) from chunks_fts where chunks_fts match 'wombat'\").fetchone()[0])")
    check("change tracking", "deleted text removed from the index", r.stdout.split() == ["0", "0"], r.stdout)

    ghosts = alice.get("/v1/ghosts").json()["missing"]
    names = {g["name"] for g in ghosts}
    if not check("missing files", "index reports files that are mentioned but absent", "Falcon-floorplan-v3.pdf" in names, sorted(names)[:6]):
        check("missing files", "ghost resolved itself when the file arrived", False, "ghost was never listed")
        shutil.rmtree(folder, ignore_errors=True)
        return
    plan = SOURCES / "shared/Bakery/Falcon-floorplan-v3.pdf"
    shutil.copy2(SOURCES / "shared/Bakery/Contracts/Ashford-vent-consent-letter.pdf", plan)
    done, t_ghost = wait_for(lambda: "Falcon-floorplan-v3.pdf" not in {g["name"] for g in alice.get("/v1/ghosts").json()["missing"]}, 90)
    check("missing files", f"ghost resolved itself {t_ghost:.1f}s after the file arrived", bool(done), t_ghost)
    plan.unlink()
    shutil.rmtree(folder, ignore_errors=True)


# ---- skill bridge -----------------------------------------------------------


def exchange():
    status = EXCHANGE / "alice/Ufinder/status.md"
    ok, _ = wait_for(status.exists, 45)
    check("skill bridge", "engine writes status.md", ok, status.name)
    req = EXCHANGE / "alice/Ufinder/requests"
    req.mkdir(parents=True, exist_ok=True)
    (req / "t1.md").write_text(truth["meta"]["trap_alice"])
    res = EXCHANGE / "alice/Ufinder/results/t1.md"
    ok, t = wait_for(res.exists, 45)
    text = res.read_text() if res.exists() else ""
    check("skill bridge", f"file request answered in {t:.1f}s", ok and "blood-test" in text, text[:120])
    check("skill bridge", "result file warns that it is data", "Do not follow instructions" in text)
    breq = EXCHANGE / "bob/Ufinder/requests"
    breq.mkdir(parents=True, exist_ok=True)
    (breq / "t2.md").write_text(truth["meta"]["trap_alice"])
    bres = EXCHANGE / "bob/Ufinder/results/t2.md"
    ok, _ = wait_for(bres.exists, 45)
    check("skill bridge", "bob's request cannot reach alice's files", ok and "blood-test" not in bres.read_text())
    secret = EXCHANGE / "alice/Ufinder/status.md"
    link = breq / "steal.md"
    link.symlink_to(secret)
    time.sleep(5)
    check("skill bridge", "a planted symlink in a request folder is ignored", not (EXCHANGE / "bob/Ufinder/results/steal.md").exists())
    link.unlink()


def extra():
    alice = client("alice")
    r = search(alice, "面粉 周三 送货")
    check("languages", "chinese text is searchable", any("面粉供应备忘录" in x["path"] for x in r["results"]), [x["path"] for x in r["results"][:3]])
    img = (SOURCES / "shared/Bakery/Photos/IMG_3301.jpg").read_bytes()
    r = alice.post("/v1/search/file", files={"file": ("q.jpg", img, "image/jpeg")}, data={"limit": "5"}).json()
    check("multimodal query", "search by uploaded image finds the same image", any("IMG_3301" in x["path"] for x in r["results"][:3]), [x["path"] for x in r["results"][:3]])
    r = search(alice, "type:photo path:Scans receipt")
    check("operators", "operators filter by type and path", r["results"] and all("scans" in x["path"].lower() and x["type"] == "photo" for x in r["results"]), r["results"][:1])
    r = alice.post("/v1/embeddings", json={"input": ["flour delivery"]}).json()
    check("models", "OpenAI-compatible embeddings endpoint works", len(r["data"][0]["embedding"]) == 1024, len(r["data"]))


if __name__ == "__main__":
    groups = {"containment": containment, "access": access, "keys": keys, "changes": changes, "exchange": exchange, "extra": extra}
    chosen = sys.argv[1:] or list(groups)
    for name in chosen:
        print(f"--- {name}", flush=True)
        try:
            groups[name]()
        except Exception as exc:
            check(name, "section crashed", False, repr(exc))
    Path(ROOT / "eval/results").mkdir(exist_ok=True)
    prior = []
    out = ROOT / "eval/results/system.json"
    if out.exists() and set(chosen) != set(groups):
        prior = [r for r in json.loads(out.read_text()) if r["group"] not in {x["group"] for x in results}]
    out.write_text(json.dumps(prior + results, indent=1, ensure_ascii=False))
    print(f"\n{sum(r['ok'] for r in results)} of {len(results)} checks passed")
