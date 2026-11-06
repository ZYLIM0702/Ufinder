"""Held-out queries, written after the first run failed and before any fix ran.

They are used once, on the frozen design. The original 56 queries became the
development set, so tuning on them proves nothing by itself.
"""
import json
import random
from pathlib import Path

ROOT = Path(__file__).parent
truth = json.loads((ROOT / "queries.json").read_text("utf8"))
cap = json.load(open(ROOT / "data/coco/annotations/captions_val2017.json"))
B = "Bakery"
F = "Family/2025-06-holiday"
supply = f"{B}/Contracts/Harbor-Mills-Supply-Agreement-2025.pdf"
leases = [f"{B}/Contracts/Riverbend-Lease-2025_v1.docx", f"{B}/Contracts/Riverbend-Lease-2025_v2.docx", f"{B}/Archive/lease-signed-copy.docx"]
notes, budget = f"{B}/Meetings/2025-03-04 kickoff notes.md", f"{B}/Meetings/Falcon budget.md"
board, memo, call = f"{B}/Photos/IMG_3301.jpg", f"{B}/Recordings/voice-memo-0305.m4a", f"{B}/Recordings/supplier-call-0318.m4a"
consent, video = f"{B}/Contracts/Ashford-vent-consent-letter.pdf", f"{B}/Videos/oven-walkthrough.mp4"
oven = f"{B}/Invoices/INV-2025-0507.pdf"
site = [f"{B}/Photos/IMG_33{10 + n}.jpg" for n in range(3)]
trip_photos = [f"{F}/DSC0{4100 + n}.jpg" for n in range(9)]
trip_memo, hotel, itinerary = f"{F}/voice-note-day2.m4a", f"{F}/scan_0001.jpg", f"{F}/itinerary.md"
invoices = [f"{B}/Invoices/INV-2025-{400 + i * 3:04d}.pdf" for i in range(12)]

q = [
    ("name", "vendor terms update", [f"{B}/Contracts/vendor-terms-update.pdf"]),
    ("name", "invoice INV-2025-0418", [f"{B}/Invoices/INV-2025-0418.pdf"]),
    ("name", "supplier call recording", [call]),
    ("name", "Falcon budget", [budget]),
    ("content", "which city handles disputes in the flour contract", [supply]),
    ("content", "who attended the first project meeting", [notes]),
    ("content", "how much flour does Harbor deliver each week", [supply]),
    ("content", "what can the tenant not change without consent", leases),
    ("content", "which bank funds the oven", [budget]),
    ("content", "hydration of the rye dough", [f"{B}/Recipes/sourdough-rye.txt"]),
    ("ocr", "window flowers florist receipt", [f"{B}/Scans/scan_003.jpg"]),
    ("ocr", "bread bags packaging receipt", [f"{B}/Scans/scan_005.jpg"]),
    ("ocr", "city hardware receipt", [f"{B}/Scans/scan_002.jpg"]),
    ("ocr", "note on the board saying the vent needs the landlord", [board]),
    ("spoken", "price stays at three dollars a kilo", [call]),
    ("spoken", "work outside trading hours and I still need the signed letter", [memo, consent]),
    ("spoken", "vent goes up the north wall", [video]),
    ("graph", "files for the second oven line", [notes, budget, board, video, oven, consent]),
    ("graph", "photos and recordings from the June holiday", trip_photos[:6] + [trip_memo]),
    ("graph", "pictures from the day we ate at Gurney Drive", trip_photos[5:] + [trip_memo]),
    ("graph", "our stay at Hotel Kenanga Bay", [itinerary, hotel]),
    ("graph", "photos taken right after the whiteboard session", site),
    ("graph", "paperwork behind the extraction vent", [consent, memo, notes, budget]),
    ("graph", "everything under purchase order PO-2025-118", [supply] + invoices),
    ("graph", "files connected to the Westpac loan", [budget, oven, notes]),
]
held = [{"cat": c, "query": t, "targets": x} for c, t, x in q]

used = {p for r in truth["queries"] for p in r["targets"]}
ids = {}
for a in cap["annotations"]:
    ids.setdefault(a["image_id"], []).append(a["caption"].strip())
dev_captions = {r["query"] for r in truth["queries"] if r["cat"] == "visual"}
photos = sorted((ROOT.parent / "data/sources/shared/Photos").rglob("*.jpg"))
noise_ids = json.loads((ROOT / "noise_ids.json").read_text())
rng = random.Random(4417)
rows = []
seen = {}
for cid in noise_ids.values():
    seen[cid] = seen.get(cid, 0) + 1
for name, cid in noise_ids.items():
    rel = f"Photos/{name}"
    if seen[cid] > 1 or rel in used or any(c in dev_captions for c in ids[cid]):  # an ambiguous match is not ground truth
        continue
    rows.append((rel, rng.choice(ids[cid])))
rng.shuffle(rows)
held += [{"cat": "visual", "query": c, "targets": [p]} for p, c in rows[:24]]
truth["holdout"] = held
truth["tshirt_holdout"] = ["man in a shirt with UGREEN printed on it", "UGREEN logo on a person's chest"]
(ROOT / "queries.json").write_text(json.dumps(truth, indent=1, ensure_ascii=False), "utf8")
print(len(held), "held-out queries")
