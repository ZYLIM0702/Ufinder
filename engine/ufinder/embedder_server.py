"""Local embedding service. Runs on an internal network with no route out.

Refuses to start if the model did not load its real weights. A silently random
model still returns vectors, so search would look fine and be useless.
"""
from __future__ import annotations

import base64
import io
import os
import threading

import numpy as np
import torch
from fastapi import FastAPI
from PIL import Image
from pydantic import BaseModel
from safetensors import safe_open
from sentence_transformers import SentenceTransformer

MODEL_DIR = os.environ.get("MODEL_DIR", "/models/qwen3-vl-embedding-2b")
DIM = int(os.environ.get("UFINDER_VECTOR_DIM", "1024"))
THREADS = int(os.environ.get("UFINDER_EMBED_THREADS", "6"))
MAX_SIDE = int(os.environ.get("UFINDER_EMBED_SIDE", "512"))

torch.set_num_threads(THREADS)
# float32 on purpose. bfloat16 is 7x slower on CPU, and dynamic int8 damaged the
# vectors in our benchmark.
model = SentenceTransformer(MODEL_DIR, device="cpu", model_kwargs={"dtype": torch.float32}, local_files_only=True)
lock = threading.Lock()


def verify_weights() -> None:
    probe = "model.visual.patch_embed.proj.weight"
    with safe_open(os.path.join(MODEL_DIR, "model.safetensors"), "pt") as f:
        expected = f.get_tensor(probe).float()
    params = dict(model[0].model.named_parameters())
    name = next(k for k in params if k.endswith("visual.patch_embed.proj.weight"))
    if not torch.allclose(params[name].float().cpu(), expected, atol=1e-3):
        raise SystemExit("model weights did not load: refusing to start")


verify_weights()
app = FastAPI(title="ufinder-embedder", docs_url=None, redoc_url=None)


class Req(BaseModel):
    texts: list[str] = []
    images_b64: list[str] = []


def finish(v: np.ndarray) -> list[list[float]]:
    v = v[:, :DIM]  # the model supports truncating dimensions
    v = v / np.clip(np.linalg.norm(v, axis=1, keepdims=True), 1e-9, None)
    return v.astype("float32").tolist()


@app.get("/health")
def health():
    return {"ok": True, "model": os.path.basename(MODEL_DIR), "dim": DIM, "threads": THREADS}


@app.post("/embed")
def embed(req: Req):
    out = {}
    if req.texts:
        # Text never waits for the image queue, so a search stays quick while
        # the background indexer is busy.
        out["texts"] = finish(np.array(model.encode(req.texts, batch_size=4, show_progress_bar=False)))
    if req.images_b64:
        imgs = []
        for b in req.images_b64:
            im = Image.open(io.BytesIO(base64.b64decode(b))).convert("RGB")
            im.thumbnail((MAX_SIDE, MAX_SIDE))
            imgs.append(im)
        with lock:
            out["images"] = finish(np.array(model.encode(imgs, batch_size=1, show_progress_bar=False)))
    return out
