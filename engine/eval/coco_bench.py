"""Public benchmark: can the model find a COCO image from one of its captions?

Vector search only, exact cosine, on the first N val2017 images in id order. Each
image is used once as a target and its first caption as the query. Reports recall
at several truncated dimensions, which is how much we can shrink the index.
"""
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from sentence_transformers import SentenceTransformer

N = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
SIDE = 512
CACHE = Path("eval/data/coco/images")
CACHE.mkdir(parents=True, exist_ok=True)
cap = json.load(open("eval/data/coco/annotations/captions_val2017.json"))
first = {}
for a in cap["annotations"]:
    first.setdefault(a["image_id"], a["caption"].strip())
urls = {i["id"]: i["coco_url"] for i in cap["images"]}
ids = sorted(first)[:N]


def get(i):
    p = CACHE / f"{i}.jpg"
    if not p.exists():
        urllib.request.urlretrieve(urls[i], p)


with ThreadPoolExecutor(12) as ex:
    list(ex.map(get, ids))

model = SentenceTransformer("models/qwen3-vl-embedding-2b", device="mps", model_kwargs={"dtype": torch.bfloat16}, local_files_only=True)
t0 = time.time()
vecs = []
for k in range(0, len(ids), 8):
    imgs = []
    for i in ids[k : k + 8]:
        im = Image.open(CACHE / f"{i}.jpg").convert("RGB")
        im.thumbnail((SIDE, SIDE))
        imgs.append(im)
    vecs.append(np.array(model.encode(imgs, batch_size=4, show_progress_bar=False)))
    if k % 160 == 0:
        print("images", k, round(time.time() - t0), "s", flush=True)
images = np.concatenate(vecs)
image_rate = len(ids) / (time.time() - t0)
texts = np.array(model.encode([first[i] for i in ids], batch_size=16, show_progress_bar=False))

out = {"n": len(ids), "images_per_s_gpu": round(image_rate, 2), "dims": {}}
for dim in (2048, 1024, 512, 256, 128):
    a = images[:, :dim] / np.linalg.norm(images[:, :dim], axis=1, keepdims=True)
    b = texts[:, :dim] / np.linalg.norm(texts[:, :dim], axis=1, keepdims=True)
    order = np.argsort(-(b @ a.T), axis=1)
    rank = (order == np.arange(len(ids))[:, None]).argmax(1)
    row = {f"recall@{k}": round(float((rank < k).mean()), 4) for k in (1, 5, 10)}
    row["mrr"] = round(float((1 / (rank + 1)).mean()), 4)
    # binary quantization estimate: sign bits find candidates, full vectors rescore
    bits_a, bits_b = (a > 0), (b > 0)
    ham = (bits_b[:, None, :] != bits_a[None, :, :]).sum(2) if len(ids) <= 1200 else None
    if ham is not None:
        cand = np.argsort(ham, axis=1)[:, :30]
        hits = 0
        for q in range(len(ids)):
            c = cand[q]
            top = c[np.argsort(-(a[c] @ b[q]))[:10]]
            hits += int(q in top)
        row["recall@10_binary_rescore"] = round(hits / len(ids), 4)
    out["dims"][dim] = row
    print(dim, row, flush=True)
Path("eval/results").mkdir(exist_ok=True)
Path("eval/results/coco_bench.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out))
