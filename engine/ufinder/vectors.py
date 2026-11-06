"""Qdrant wrapper. Original vectors stay on disk, binary-quantized copies in RAM."""
from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client import models as qm

from . import config


def name_for(model_id: str, level: str) -> str:
    return f"{level}__{model_id}".replace(".", "_")


class VectorStore:
    def __init__(self, url: str | None = None):
        self.client = QdrantClient(url=url or config.QDRANT_URL, timeout=120, check_compatibility=False)
        self._ready: set[str] = set()

    def ensure(self, name: str, dim: int) -> None:
        if name in self._ready:
            return
        if not self.client.collection_exists(name):
            self.client.create_collection(
                name,
                vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE, on_disk=True),
                quantization_config=qm.BinaryQuantization(binary=qm.BinaryQuantizationConfig(always_ram=True)),
            )
            for field in ("blob_id", "roots"):
                self.client.create_payload_index(name, field, qm.PayloadSchemaType.INTEGER)
        self._ready.add(name)

    def upsert(self, name: str, ids: list[int], vectors: list[list[float]], payloads: list[dict]) -> None:
        if ids:
            self.client.upsert(name, qm.Batch(ids=ids, vectors=vectors, payloads=payloads), wait=True)

    def search(self, name: str, vector: list[float], roots: list[int], limit: int, exclude_blob: int | None = None):
        must = [qm.FieldCondition(key="roots", match=qm.MatchAny(any=roots))]
        must_not = [qm.FieldCondition(key="blob_id", match=qm.MatchValue(value=exclude_blob))] if exclude_blob else []
        res = self.client.query_points(
            name, query=vector, limit=limit, with_payload=True,
            query_filter=qm.Filter(must=must, must_not=must_not),
            search_params=qm.SearchParams(
                quantization=qm.QuantizationSearchParams(rescore=True, oversampling=3.0)
            ),
        )
        return res.points

    def retrieve(self, name: str, ids: list[int]):
        return self.client.retrieve(name, ids=ids, with_vectors=True, with_payload=False)

    def set_roots(self, name: str, blob_id: int, roots: list[int]) -> None:
        self.client.set_payload(
            name, payload={"roots": roots}, wait=True,
            points=qm.Filter(must=[qm.FieldCondition(key="blob_id", match=qm.MatchValue(value=blob_id))]),
        )

    def delete_blob(self, name: str, blob_id: int) -> None:
        self.client.delete(
            name, wait=True,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(must=[qm.FieldCondition(key="blob_id", match=qm.MatchValue(value=blob_id))])
            ),
        )
