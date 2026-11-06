"""Does 8-bit dynamic quantization keep quality while cutting memory on CPU?

Compares float32 and int8 on the same real COCO images. Reports speed, memory,
and agreement between the two sets of vectors.
"""
import io
import json
import os
import psutil
import sys
import time
import urllib.request

import numpy as np
import torch
from PIL import Image
from sentence_transformers import SentenceTransformer

MODE = sys.argv[1]  # float32 | int8 | bfloat16
N = int(sys.argv[2]) if len(sys.argv) > 2 else 12
SIDE = int(sys.argv[3]) if len(sys.argv) > 3 else 512
CACHE = "eval/data/quant_cache"
os.makedirs(CACHE, exist_ok=True)

cap = json.load(open("eval/data/coco/annotations/captions_val2017.json"))
urls = {i["id"]: i["coco_url"] for i in cap["images"]}
pairs, seen = [], set()
for a in cap["annotations"]:
    if a["image_id"] not in seen:
        seen.add(a["image_id"])
        pairs.append((a["image_id"], a["caption"]))
    if len(pairs) == N:
        break


def load(i):
    path = f"{CACHE}/{i}.jpg"
    if not os.path.exists(path):
        urllib.request.urlretrieve(urls[i], path)
    img = Image.open(path).convert("RGB")
    img.thumbnail((SIDE, SIDE))
    return img


imgs = [load(i) for i, _ in pairs]
caps = [c for _, c in pairs]

model = SentenceTransformer(
    os.environ.get("MODEL_DIR", "models/qwen3-vl-embedding-2b"),
    device="cpu", model_kwargs={"dtype": torch.bfloat16 if MODE == "bfloat16" else torch.float32}, local_files_only=True,
)
if MODE == "int8":
    torch.backends.quantized.engine = "qnnpack" if "qnnpack" in torch.backends.quantized.supported_engines else "fbgemm"
    t0 = time.time()
    model[0].model = torch.ao.quantization.quantize_dynamic(model[0].model, {torch.nn.Linear}, dtype=torch.qint8)
    print("quantized in", round(time.time() - t0, 1), "s", file=sys.stderr)

t0 = time.time()
iv = np.array(model.encode(imgs, batch_size=1, show_progress_bar=False))
img_s = (time.time() - t0) / len(imgs)
t0 = time.time()
tv = np.array(model.encode(caps, batch_size=4, show_progress_bar=False))
txt_s = (time.time() - t0) / len(caps)
s = tv @ iv.T
rss = psutil.Process(os.getpid()).memory_info().rss / 1e9  # steady, after inference
np.save(f"{CACHE}/iv_{MODE}_{SIDE}.npy", iv)
print(json.dumps({
    "mode": MODE, "side": SIDE, "n": len(imgs), "s_per_image": round(img_s, 3), "images_per_s": round(1 / img_s, 3),
    "s_per_text": round(txt_s, 3), "ram_gb": round(rss, 2), "top1": int((s.argmax(1) == np.arange(len(s))).sum()),
    "diag": round(float(np.diag(s).mean()), 3), "offdiag": round(float((s.sum() - np.trace(s)) / (s.size - len(s))), 3),
}))
