"""Sample each container's TCP table while it works. Any public address is a failure."""
import ipaddress, json, os, subprocess, threading, time
from pathlib import Path
import httpx
ENV = {**os.environ, "DOCKER_CONTEXT": "orbstack"}
PROBE = r"""
import ipaddress,socket,struct,time
seen=set()
end=time.time()+25
while time.time()<end:
    for f in ('/proc/net/tcp','/proc/net/udp'):
        for ln in open(f).readlines()[1:]:
            ip=int(ln.split()[2].split(':')[0],16)
            seen.add(socket.inet_ntoa(struct.pack('<I',ip)))
    time.sleep(0.2)
print(' '.join(sorted(seen)))
"""
out = {}
def sample(c):
    r = subprocess.run(["docker", "exec", c, "python", "-c", PROBE], env=ENV, capture_output=True, text=True, timeout=60)
    out[c] = r.stdout.split()
ts = [threading.Thread(target=sample, args=(c,)) for c in ("ufinder-gateway-1", "ufinder-indexer-1", "ufinder-embedder-1")]
[t.start() for t in ts]
time.sleep(2)
note = Path("data/sources/shared/Admin/sample-note.txt")
note.write_text("Connection sample note about a sapphire kettle.")
c = httpx.Client(base_url="http://localhost:8787", timeout=60)
c.post("/api/login", json={"user": "alice", "password": "alice-demo-pass"})
for q in ["sapphire kettle", "Project Falcon", "a dog on a beach", "late fee flour"]:
    time.sleep(3)
    c.post("/v1/search", json={"q": q})
[t.join() for t in ts]
note.unlink()
public = {k: [a for a in v if a != "0.0.0.0" and ipaddress.ip_address(a).is_global] for k, v in out.items()}
res = [{"group": "no internet", "name": f"{k.split('-')[1]} made no public connection while working", "ok": not v and bool(out[k]), "detail": f"{len(out[k])} addresses seen, public: {v}"} for k, v in public.items()]
Path("eval/results/connections.json").write_text(json.dumps(res, indent=1))
for r in res: print("PASS" if r["ok"] else "FAIL", r["name"], r["detail"])
