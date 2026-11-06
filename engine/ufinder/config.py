"""Runtime settings. Everything comes from the environment or config/ufinder.json."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


DATA_DIR = Path(_env("UFINDER_DATA", "/data"))
DB_PATH = DATA_DIR / "ufinder.db"
THUMB_DIR = DATA_DIR / "thumbs"
CONFIG_PATH = Path(_env("UFINDER_CONFIG", "/config/ufinder.json"))
EXCHANGE_DIR = Path(_env("UFINDER_EXCHANGE", "/exchange"))

QDRANT_URL = _env("QDRANT_URL", "http://qdrant:6333")
EMBEDDER_URL = _env("EMBEDDER_URL", "http://embedder:8100")

VECTOR_DIM = int(_env("UFINDER_VECTOR_DIM", "1024"))
MODEL_ID = _env("UFINDER_MODEL_ID", "qwen3-vl-embedding-2b")

RECONCILE_SECONDS = float(_env("UFINDER_RECONCILE_SECONDS", "300"))
DEBOUNCE_SECONDS = float(_env("UFINDER_DEBOUNCE_SECONDS", "2"))
RESOLVE_IDLE_SECONDS = float(_env("UFINDER_RESOLVE_IDLE_SECONDS", "1"))
RESOLVE_INTERVAL_SECONDS = float(_env("UFINDER_RESOLVE_INTERVAL_SECONDS", "120"))

# Retrieval settings are fixed here, before evaluation, from the published
# defaults: k=60 for reciprocal rank fusion, alpha=0.5 for personalized PageRank.
RRF_K = 60
PPR_ALPHA = 0.5
PPR_EPSILON = 1e-4
CANDIDATES = 200
PPR_SEEDS = 10
KNN_EDGES = 5
KNN_MIN_SCORE = float(_env("UFINDER_KNN_MIN_SCORE", "0.62"))

# Weight of each edge type during graph retrieval. Evidence-backed edges count
# more than statistical similarity.
EDGE_WEIGHTS = {
    "same_hash": 1.0,
    "links_to": 1.0,
    "mentions": 0.8,
    "version_of": 0.8,
    "has_entity": 0.7,
    "same_event": 0.5,
    "similar_to": 0.4,
}

# Graph retrieval walks evidence only. similar_to stays out, because the vector
# list already carries that signal and counting it twice floods the results.
WALK_WEIGHTS = {k: v for k, v in EDGE_WEIGHTS.items() if k != "similar_to"}
# The walk starts from the hits, so it is not independent evidence. Blending it into
# the ranking lowered recall in every setting we tried, so connected files are a
# separate list. Direct results are never changed by the graph.
CONNECTED_LIMIT = 10
# Only the top of each list votes. Without this, a file found weakly by two lists
# outranks a file found strongly by one.
FUSION_WINDOW = int(_env("UFINDER_FUSION_WINDOW", "20"))

# Never indexed, whatever the owner grants. Matches SkillHub rule 7.1.
DEFAULT_EXCLUDES = [
    ".env", ".env.*", ".git", ".ssh", "id_rsa", "id_rsa.*", "id_ed25519", "id_ed25519.*",
    "*.pem", "*.key", "*.p12", "*.pfx", "*.kdbx", "credentials.json", "config.json",
    "@*", "#recycle", ".Trash*", ".DS_Store", "Thumbs.db", ".ufinderignore", "Ufinder",
]


@dataclass
class Root:
    root_id: int
    name: str
    path: str
    allow: list[str]
    external_embedding: bool = False


@dataclass
class User:
    name: str
    role: str = "user"
    password: str = ""


@dataclass
class Settings:
    roots: list[Root] = field(default_factory=list)
    users: list[User] = field(default_factory=list)


def load_settings(path: Path | None = None) -> Settings:
    data = json.loads((path or CONFIG_PATH).read_text("utf8"))
    roots = [
        Root(
            root_id=i + 1,
            name=r["name"],
            path=r["path"],
            allow=list(r.get("allow", [])),
            external_embedding=bool(r.get("external_embedding", False)),
        )
        for i, r in enumerate(data.get("roots", []))
    ]
    users = [
        User(name=u["name"], role=u.get("role", "user"), password=u.get("password", ""))
        for u in data.get("users", [])
    ]
    return Settings(roots=roots, users=users)
