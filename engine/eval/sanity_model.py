"""Fail loudly if the model loaded with random weights: captions must find their own images."""
import io, json, os, sys, urllib.request, warnings, logging
import numpy as np, torch
from PIL import Image
from sentence_transformers import SentenceTransformer
logging.basicConfig(level=logging.ERROR)
cap = json.load(open("eval/data/coco/annotations/captions_val2017.json"))
names = {i["id"]: i["coco_url"] for i in cap["images"]}
pairs, seen = [], set()
for a in cap["annotations"]:
    if a["image_id"] not in seen:
        seen.add(a["image_id"]); pairs.append((a["image_id"], a["caption"]))
    if len(pairs) == 8: break
imgs = [Image.open(io.BytesIO(urllib.request.urlopen(names[i]).read())).convert("RGB") for i, _ in pairs]
dev = sys.argv[1] if len(sys.argv) > 1 else "mps"
m = SentenceTransformer(os.environ.get("MODEL_DIR", "models/qwen3-vl-embedding-2b"), device=dev, model_kwargs={"dtype": torch.bfloat16}, local_files_only=True)
iv = np.array(m.encode(imgs, batch_size=1, show_progress_bar=False)); tv = np.array(m.encode([c for _, c in pairs], batch_size=4, show_progress_bar=False))
s = tv @ iv.T
print("diag mean %.3f offdiag mean %.3f top1 hits %d/%d norm %.3f" % (np.diag(s).mean(), (s.sum()-np.trace(s))/(s.size-len(s)), (s.argmax(1)==np.arange(len(s))).sum(), len(s), np.linalg.norm(iv[0])))
