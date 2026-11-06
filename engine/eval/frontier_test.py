"""Prove the model endpoint rule with a fake frontier API that records what it gets.

  off      no egress container: nothing can reach the API
  on       only folders the owner opted in reach it, other folders stay local
  always   the proxy refuses every host except the one allowed
"""
import json
import os
import subprocess
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).parent.parent
ENV = {**os.environ, "DOCKER_CONTEXT": "orbstack"}
FILES = ["-f", "docker-compose.yml", "-f", "docker-compose.frontier-test.yml"]
OUT = []


def check(name, ok, detail=""):
    OUT.append({"group": "model endpoint", "name": name, "ok": bool(ok), "detail": str(detail)[:200]})
    print("PASS" if ok else "FAIL", name, "" if ok else f"-> {detail}", flush=True)


def dc(*args, env=None):
    return subprocess.run(["docker", "compose", *FILES, *args], cwd=ROOT, env={**ENV, **(env or {})}, capture_output=True, text=True, timeout=300)


def seen() -> str:
    return dc("exec", "-T", "stub-frontier", "sh", "-c", "cat /tmp/seen.jsonl 2>/dev/null || true").stdout


def login():
    c = httpx.Client(base_url="http://localhost:8787", timeout=60)
    for _ in range(40):
        try:
            c.post("/api/login", json={"user": "alice", "password": "alice-demo-pass"}).raise_for_status()
            return c
        except httpx.HTTPError:
            time.sleep(1.5)
    raise SystemExit("gateway not up")


def indexed(c, marker):
    return any(marker in json.dumps(r) for r in c.post("/v1/search", json={"q": marker}).json()["results"])


def wait(fn, seconds=60):
    t0 = time.time()
    while time.time() - t0 < seconds:
        if fn():
            return True
        time.sleep(1)
    return False


lab = ROOT / "data/sources/frontier-lab"
shared = ROOT / "data/sources/shared/Admin"
dc("up", "-d", "stub-frontier")
c = login()
r = c.put("/v1/models/external", json={"base_url": "http://stub-frontier:9000", "model": "frontier-test-1", "api_key": "test", "dim": 64})
check("owner can connect a model endpoint", r.status_code == 200, r.text[:120])
bob = httpx.Client(base_url="http://localhost:8787", timeout=30)
bob.post("/api/login", json={"user": "bob", "password": "bob-demo-pass"})
check("a normal user cannot change the model endpoint", bob.put("/v1/models/external", json={"base_url": "http://x", "model": "y", "dim": 8}).status_code == 403)

(lab / "off-note.txt").write_text("Off phase note with marker AMBERFOX-OFF-11 for the frontier check.")
ok = wait(lambda: indexed(c, "AMBERFOX-OFF-11"))
time.sleep(4)
check("egress off: file still indexes locally", ok)
check("egress off: nothing reaches the frontier API", "AMBERFOX" not in seen(), seen()[:120])

on = {"UFINDER_EGRESS_PROXY": "http://egress:8899", "UFINDER_EGRESS_ALLOW": "stub-frontier"}
dc("--profile", "egress", "up", "-d", "egress", "gateway", "indexer", env=on)
c = login()
time.sleep(6)
(lab / "on-note.txt").write_text("On phase note with marker BLUEHERON-ON-22 for the frontier check.")
(shared / "stay-local.txt").write_text("Shared folder note with marker COPPERWREN-LOCAL-33 that must stay on the NAS.")
ok = wait(lambda: "BLUEHERON" in seen(), 90)
check("egress on: opted-in folder reaches the frontier API", ok, seen()[:160])
wait(lambda: indexed(c, "COPPERWREN-LOCAL-33"), 60)
time.sleep(4)
check("egress on: other folders stay local", "COPPERWREN" not in seen(), seen()[:160])
check("egress on: a normal search sends no query out", "COPPERWREN" not in seen(), seen()[:160])
r = c.post("/v1/search", json={"q": "VIOLETOWL-QUERY-44", "use_external": True})
time.sleep(2)
check("a person can choose to send one query out", r.status_code == 200 and "VIOLETOWL" in seen(), seen()[-120:])
key = c.post("/v1/keys", json={"name": "agent", "max_tier": 1}).json()["token"]
r = httpx.post("http://localhost:8787/v1/search", json={"q": "x", "use_external": True}, headers={"Authorization": f"Bearer {key}"}, timeout=30)
check("an agent key cannot send a query out", r.status_code == 403, r.status_code)

probe = (
    "import httpx\n"
    "for h in ('http://example.com/','http://stub-frontier:9000/'):\n"
    "    try:\n"
    "        print(h, httpx.Client(proxy='http://egress:8899',timeout=5).get(h).status_code)\n"
    "    except Exception as e:\n"
    "        print(h, type(e).__name__)\n"
)
r = dc("exec", "-T", "indexer", "python", "-c", probe)
check("proxy refuses any other host", "example.com/ 403" in r.stdout, r.stdout + r.stderr[-120:])

c.delete("/v1/models/external")
(lab / "on-note.txt").unlink(missing_ok=True)
(lab / "off-note.txt").unlink(missing_ok=True)
(shared / "stay-local.txt").unlink(missing_ok=True)
dc("rm", "-sf", "stub-frontier", "egress")
dc("up", "-d", "gateway", "indexer")
path = ROOT / "eval/results/frontier.json"
path.write_text(json.dumps(OUT, indent=1))
print(sum(x["ok"] for x in OUT), "of", len(OUT))
