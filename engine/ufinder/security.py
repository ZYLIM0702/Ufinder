"""Identity, keys, content tiers, budgets and the audit chain.

Everything an agent or a person sees passes through here. Tiers are enforced in
code, not by asking a model to behave.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import time
from dataclasses import dataclass, field

from . import db

L0, L1, L2, L3 = 0, 1, 2, 3
SESSION_SECONDS = 12 * 3600
ALL_TOOLS = ["search_files", "get_file", "get_related", "list_changes", "read_snippet", "propose_organization"]

EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PHONE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d\b")
CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
ID_LIKE = re.compile(r"\b(?:\d{6}-\d{2}-\d{4}|\d{3}-\d{2}-\d{4}|[A-Z]\d{7}[A-Z]?)\b")


def redact(text: str) -> str:
    """Pattern-based only. It misses things, which is why external keys default to L1."""
    for pat, tag in ((EMAIL, "[email]"), (CARD, "[number]"), (ID_LIKE, "[id]"), (PHONE, "[phone]")):
        text = pat.sub(tag, text)
    return text


@dataclass
class Actor:
    user: str
    role: str = "user"
    roots: list[int] = field(default_factory=list)
    key_id: str | None = None
    tools: list[str] = field(default_factory=lambda: list(ALL_TOOLS))
    max_tier: int = L2
    external: bool = False
    daily_results: int = 0


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return salt.hex() + "$" + digest.hex()


def check_password(password: str, stored: str) -> bool:
    salt, digest = stored.split("$")
    return hmac.compare_digest(hash_password(password, bytes.fromhex(salt)), stored)


def _digest(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def new_session(conn, user: str) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute("INSERT INTO sessions VALUES(?,?,?)", (_digest(token), user, time.time() + SESSION_SECONDS))
    return token


def session_user(conn, token: str) -> str | None:
    row = conn.execute("SELECT user, expires FROM sessions WHERE token_hash=?", (_digest(token),)).fetchone()
    return row["user"] if row and row["expires"] > time.time() else None


def roots_for(conn, user: str) -> list[int]:
    out = []
    for r in conn.execute("SELECT root_id, allow FROM roots"):
        if user in (r["allow"] or "").split(","):
            out.append(r["root_id"])
    return out


def create_key(conn, owner: str, name: str, roots: list[int], tools: list[str], max_tier: int, external: bool,
               daily_results: int, days: int) -> tuple[str, dict]:
    """A key never exceeds its owner. External keys stop at L2 and start at L1."""
    allowed = set(roots_for(conn, owner))
    roots = [r for r in roots if r in allowed] or sorted(allowed)
    tools = [t for t in tools if t in ALL_TOOLS]
    max_tier = min(max_tier, L2 if external else L3)
    key_id = secrets.token_hex(4)
    secret = secrets.token_urlsafe(32)
    expires = time.time() + days * 86400
    conn.execute(
        "INSERT INTO keys(key_id,secret_hash,owner,name,roots,tools,max_tier,external,daily_results,expires,created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (key_id, _digest(secret), owner, name, json.dumps(roots), json.dumps(tools), max_tier, int(external), daily_results, expires, time.time()),
    )
    return f"ufd_{key_id}_{secret}", {
        "key_id": key_id, "roots": roots, "tools": tools, "max_tier": max_tier, "external": external,
        "daily_results": daily_results, "expires": expires,
    }


def actor_from_key(conn, token: str) -> Actor | None:
    parts = token.split("_", 2)
    if len(parts) != 3 or parts[0] != "ufd":
        return None
    row = conn.execute("SELECT * FROM keys WHERE key_id=?", (parts[1],)).fetchone()
    if row is None or row["revoked"] or row["expires"] < time.time():
        return None
    if not hmac.compare_digest(row["secret_hash"], _digest(parts[2])):
        return None
    owner_roots = set(roots_for(conn, row["owner"]))  # losing folder access also limits the key
    return Actor(
        user=row["owner"], roots=[r for r in json.loads(row["roots"]) if r in owner_roots], key_id=row["key_id"],
        tools=json.loads(row["tools"]), max_tier=row["max_tier"], external=bool(row["external"]),
        daily_results=row["daily_results"],
    )


def spend(conn, actor: Actor, results: int) -> bool:
    """Daily result budget limits bulk theft if a key leaks."""
    if not actor.key_id or not actor.daily_results:
        return True
    day = time.strftime("%Y-%m-%d")
    row = conn.execute("SELECT results FROM key_usage WHERE key_id=? AND day=?", (actor.key_id, day)).fetchone()
    used = row["results"] if row else 0
    if used + results > actor.daily_results:
        return False
    conn.execute(
        "INSERT INTO key_usage VALUES(?,?,?) ON CONFLICT(key_id,day) DO UPDATE SET results=results+excluded.results",
        (actor.key_id, day, results),
    )
    return True


def audit(conn, actor: str, key_id: str | None, tool: str, n_results: int, tier: int, outcome: str) -> None:
    """Each row hashes the one before it, so editing history breaks the chain."""
    conn.execute("BEGIN IMMEDIATE")
    prev = conn.execute("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
    prev_hash = prev["hash"] if prev else "genesis"
    ts = time.time()
    body = json.dumps([ts, actor, key_id, tool, n_results, tier, outcome, prev_hash])
    conn.execute(
        "INSERT INTO audit(ts,actor,key_id,tool,n_results,tier,outcome,prev_hash,hash) VALUES(?,?,?,?,?,?,?,?,?)",
        (ts, actor, key_id, tool, n_results, tier, outcome, prev_hash, hashlib.sha256(body.encode()).hexdigest()),
    )
    conn.execute("COMMIT")


def verify_audit(conn) -> dict:
    prev, n = "genesis", 0
    for r in conn.execute("SELECT * FROM audit ORDER BY seq"):
        body = json.dumps([r["ts"], r["actor"], r["key_id"], r["tool"], r["n_results"], r["tier"], r["outcome"], prev])
        if r["prev_hash"] != prev or r["hash"] != hashlib.sha256(body.encode()).hexdigest():
            return {"ok": False, "broken_at": r["seq"], "rows": n}
        prev, n = r["hash"], n + 1
    return {"ok": True, "rows": n}


def shape(result: dict, tier: int, external: bool) -> dict:
    """Cut one search result down to what this tier may see."""
    if tier <= L0:
        return {"file_id": result["file_id"], "score": result["score"]}
    out = {k: result[k] for k in ("file_id", "score", "path", "name", "type", "size", "mtime") if k in result}
    signals = []
    for r in result.get("reasons", []):
        entry = {"signal": r["signal"], "label": r["label"], "locator": r.get("locator", "")}
        if tier >= L2 and r.get("snippet"):
            entry["snippet"] = redact(r["snippet"]) if (external or tier == L2) else r["snippet"]
        signals.append(entry)
    out["reasons"] = signals
    if tier >= L3:
        out["properties"] = result.get("properties", {})
    return out
