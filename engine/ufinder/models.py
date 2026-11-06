"""Model endpoints. The local model is the default. A frontier model is one setting.

The owner can register any OpenAI-compatible embedding endpoint and choose which
folders may use it. Content from every other folder stays with the local model.
Calls leave only through the egress proxy, which does not run unless the owner
turns it on, and which allows exactly one host.
"""
from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass

import httpx

from . import config, db


class Local:
    id = config.MODEL_ID
    dim = config.VECTOR_DIM
    external = False

    def __init__(self, url: str | None = None):
        self.client = httpx.Client(base_url=url or config.EMBEDDER_URL, timeout=600)

    def texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        r = self.client.post("/embed", json={"texts": [t[:6000] for t in texts]})
        r.raise_for_status()
        return r.json()["texts"]

    def images(self, images: list[bytes]) -> list[list[float]]:
        if not images:
            return []
        r = self.client.post("/embed", json={"images_b64": [base64.b64encode(i).decode() for i in images]})
        r.raise_for_status()
        return r.json()["images"]

    def healthy(self) -> bool:
        try:
            return self.client.get("/health", timeout=3).status_code == 200
        except httpx.HTTPError:
            return False


@dataclass
class External:
    base_url: str
    model: str
    api_key: str
    dim: int
    external = True

    @property
    def id(self) -> str:
        return "ext-" + re.sub(r"[^a-z0-9]+", "-", self.model.lower()).strip("-")

    def _client(self) -> httpx.Client:
        proxy = os.environ.get("UFINDER_EGRESS_PROXY") or None
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        return httpx.Client(timeout=120, proxy=proxy, headers=headers)

    def texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        with self._client() as c:
            r = c.post(f"{self.base_url.rstrip('/')}/embeddings", json={"model": self.model, "input": texts})
            r.raise_for_status()
            return [d["embedding"] for d in sorted(r.json()["data"], key=lambda x: x["index"])]

    def images(self, images: list[bytes]) -> list[list[float]]:
        return []  # text only until a provider's image format is configured


def get_external(conn) -> External | None:
    raw = db.get_meta(conn, "external_model")
    if not raw:
        return None
    d = json.loads(raw)
    return External(d["base_url"], d["model"], d.get("api_key", ""), int(d["dim"]))


def set_external(conn, base_url: str, model: str, api_key: str, dim: int) -> External:
    db.set_meta(conn, "external_model", json.dumps({"base_url": base_url, "model": model, "api_key": api_key, "dim": dim}))
    return External(base_url, model, api_key, dim)


def clear_external(conn) -> None:
    conn.execute("DELETE FROM meta WHERE key='external_model'")
