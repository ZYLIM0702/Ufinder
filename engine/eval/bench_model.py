"""Measure embedding speed and memory on this machine. Prints one JSON line."""
import argparse
import json
import os
import time

import numpy as np
import psutil
import torch
from PIL import Image
from sentence_transformers import SentenceTransformer

ap = argparse.ArgumentParser()
ap.add_argument("--device", default="cpu")
ap.add_argument("--dtype", default="bfloat16")
ap.add_argument("--side", type=int, default=512)
ap.add_argument("--n", type=int, default=6)
ap.add_argument("--threads", type=int, default=0)
args = ap.parse_args()

if args.threads:
    torch.set_num_threads(args.threads)
proc = psutil.Process(os.getpid())
t0 = time.time()
model = SentenceTransformer(
    os.environ.get("MODEL_DIR", "models/qwen3-vl-embedding-2b"),
    device=args.device,
    model_kwargs={"dtype": getattr(torch, args.dtype)},
    local_files_only=True,
)
load_s = time.time() - t0

rng = np.random.default_rng(0)
imgs = []
for i in range(args.n):
    base = np.zeros((args.side, args.side, 3), dtype=np.uint8) + rng.integers(0, 255, 3, dtype=np.uint8)
    noise = rng.integers(0, 60, (args.side, args.side, 3), dtype=np.uint8)
    imgs.append(Image.fromarray(base + noise))

t0 = time.time()
vec = model.encode(imgs[:1], batch_size=1, show_progress_bar=False)
first = time.time() - t0
t0 = time.time()
model.encode(imgs[1:], batch_size=1, show_progress_bar=False)
per_image = (time.time() - t0) / max(len(imgs) - 1, 1)

t0 = time.time()
model.encode(["Quarterly lease review for the Riverbend bakery."] * 8, batch_size=4, show_progress_bar=False)
per_text = (time.time() - t0) / 8

print(json.dumps({
    "device": args.device, "dtype": args.dtype, "side": args.side, "threads": torch.get_num_threads(),
    "dim": int(vec.shape[1]), "load_s": round(load_s, 1), "first_s": round(first, 2),
    "s_per_image": round(per_image, 3), "images_per_s": round(1 / per_image, 3),
    "s_per_text": round(per_text, 3), "rss_gb": round(proc.memory_info().rss / 1e9, 2),
}))
