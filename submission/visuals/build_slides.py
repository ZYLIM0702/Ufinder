"""Draw the two gallery slides that have no screenshot, then assemble gallery/ in upload order.

Run with a Python that has playwright and Pillow:
  ../../engine/.venv/bin/python build_slides.py
"""
import base64
import json
import re
import shutil
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
R = ROOT / "engine/eval/results"
GALLERY = HERE.parent / "gallery"
scale = json.loads((R / "scale.json").read_text())
run = json.loads((R / "run.json").read_text())
rate = next(r for r in json.loads((R / "model_bench.json").read_text())["rows"] if r["key"] == "docker")["images_per_s"]
logo = "data:image/png;base64," + base64.b64encode((ROOT / "assets/logo.png").read_bytes()).decode()
defs = re.search(r"<defs>.*?</defs>", (HERE / "01-architecture.svg").read_text("utf8"), re.S).group(0)


def icon(name, size=46):
    return f'<svg width="{size}" height="{size}" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><use xlink:href="#i-{name}" width="{size}" height="{size}"/></svg>'


CSS = """
* { box-sizing: border-box; margin: 0; }
html, body { width: 1500px; height: 1000px; overflow: hidden; }
body { position: relative; padding: 56px 64px 48px; display: flex; flex-direction: column; justify-content: space-between;
  font-family: "Avenir Next", "Helvetica Neue", Arial, sans-serif; color: #fff;
  background: radial-gradient(760px 620px at 6% 0%, rgba(43,240,173,.20), transparent 70%),
              radial-gradient(860px 700px at 96% 26%, rgba(61,120,255,.26), transparent 70%),
              radial-gradient(760px 520px at 56% 112%, rgba(181,123,255,.18), transparent 72%),
              linear-gradient(135deg, #090f22, #141a3c); }
header { display: flex; align-items: center; gap: 28px; }
header img { width: 112px; height: 112px; border-radius: 26px; }
h1 { font-size: 53px; font-weight: 800; line-height: 1.08; letter-spacing: -.5px; }
.sub { margin-top: 10px; font-size: 28px; font-weight: 500; color: #b9c9e6; }
.row { display: grid; gap: 22px; }
.card { border: 2px solid rgba(255,255,255,.14); border-radius: 26px; background: rgba(14,24,58,.78); }
.disc { flex: none; width: 76px; height: 76px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #2fd98f, #10cfc4 50%, #0d7cf2); }
.type { display: flex; align-items: center; gap: 16px; padding: 26px 18px; min-width: 0; }
.type b { display: block; font-size: 33px; font-weight: 800; }
.type span { display: block; margin-top: 2px; font-size: 25px; color: #c6d4ec; font-weight: 600; }
.why { padding: 30px 32px; }
.why b { display: block; font-size: 35px; font-weight: 800; color: #ffc24a; }
.why p { margin-top: 12px; font-size: 27px; line-height: 1.32; color: #dce6f6; font-weight: 500; }
.fix { border-radius: 26px; padding: 34px 40px; font-size: 37px; font-weight: 800; color: #06142c; text-align: center;
  background: linear-gradient(90deg, #2bf0ad, #39d9e6 55%, #62b0ff); }
.step { padding: 36px 28px; position: relative; min-width: 0; }
.step .big { font-size: 66px; font-weight: 800; line-height: 1; color: #2bf0ad; white-space: nowrap; }
.step .lab { margin-top: 16px; font-size: 27px; line-height: 1.26; font-weight: 600; color: #dce6f6; }
.step + .step::before { content: ""; position: absolute; left: -22px; top: 50%; width: 22px; height: 22px; margin: -11px 0 0 -9px;
  border-top: 5px solid #7fe3d6; border-right: 5px solid #7fe3d6; transform: rotate(45deg); }
.mini { padding: 24px 30px; }
.mini b { font-size: 46px; font-weight: 800; color: #62b0ff; }
.mini span { display: block; margin-top: 4px; font-size: 25px; font-weight: 600; color: #c6d4ec; }
footer { font-size: 23px; color: #9fb2d2; font-weight: 500; }
"""


def page(title, sub, body):
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<svg width="0" height="0" style="position:absolute" xmlns:xlink="http://www.w3.org/1999/xlink">{defs}</svg>
<header><img src="{logo}" alt=""><div><h1>{title}</h1><div class="sub">{sub}</div></div></header>{body}</body></html>"""


def problem():
    types = (("photo", "Photo", "Needs vision"), ("doc", "Scan", "Needs OCR"), ("mic", "Recording", "Needs speech"), ("video", "Video", "Needs all three"))
    tiles = "".join(f'<div class="card type"><div class="disc">{icon(i)}</div><div><b>{a}</b><span>{b}</span></div></div>' for i, a, b in types)
    why = (("Search is blind", "It sees names and stored text. A photo, a scan and a voice memo have neither."),
           ("Knowledge is split", "Each app keeps its own. Nothing joins them or records how files relate."),
           ("Agents pay per look", "With no shared index, every file costs one LLM turn."))
    cards = "".join(f'<div class="card why"><b>{a}</b><p>{b}</p></div>' for a, b in why)
    return page("The bottleneck in AI is data, not the model", "A smarter LLM reading the wrong file still fails.",
                f'<div class="row" style="grid-template-columns:repeat(4,minmax(0,1fr))">{tiles}</div>'
                f'<div class="row" style="grid-template-columns:repeat(3,1fr)">{cards}</div>'
                '<div class="fix">Ufinder reads each file once into one index.<br>Search becomes a lookup, not an inference.</div>')


def always_on():
    steps = ((f"{1 / rate:.1f} s", "per image<br>on CPU"), (f"{round(rate * 86400, -3):,.0f}", "images a day<br>in the background"),
             (f"{100000 / rate / 86400:.1f} days", "100,000 photos<br>once"), (f"{scale['latency_ms']['full']['p50']:.0f} ms", "each lookup<br>after that"))
    cards = "".join(f'<div class="card step"><div class="big">{a}</div><div class="lab">{b}</div></div>' for a, b in steps)
    minis = ((f"{run['new_file_seconds']:.1f} s", "new text file searchable"), (f"{run['rename_seconds']:.1f} s", "rename, nothing re-read"),
             (str(run["restart_skipped"]), "files skipped after a restart"))
    little = "".join(f'<div class="card mini"><b>{a}</b><span>{b}</span></div>' for a, b in minis)
    return page("A NAS runs 24/7, so a slow first pass is fine", "Read every file once in the background. Only new files cost anything after that.",
                f'<div class="row" style="grid-template-columns:minmax(0,.86fr) minmax(0,1.06fr) minmax(0,1.22fr) minmax(0,.94fr);gap:34px">{cards}</div>'
                f'<div class="row" style="grid-template-columns:repeat(3,1fr)">{little}</div>'
                '<div class="fix">An LLM pays on every question. An index pays once.</div>'
                '<footer>Laptop in Docker, 6 CPU cores. Lookup is before query embedding. iDX6011 Pro speed not yet measured.</footer>')


ORDER = [
    ("../thumbnail.png", "01-cover"), ("14-problem.png", "02-problem"), ("01-architecture.png", "03-architecture"),
    ("02-search-pipeline.png", "04-search-pipeline"), ("07-search-tshirt.png", "05-search-tshirt"), ("11-search-falcon.png", "06-search-falcon"),
    ("08-graph.png", "07-file-graph"), ("12-graph-local.png", "08-connected-files"), ("09-missing.png", "09-missing-files"),
    ("03-index-design.png", "10-index-design"), ("04-results.png", "11-search-results"), ("10-graph-gain.png", "12-graph-gain"),
    ("15-always-on.png", "13-always-on"), ("05-privacy-tests.png", "14-privacy-tests"), ("13-keys.png", "15-agent-keys"),
]

with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    view = b.new_page(viewport={"width": 1500, "height": 1000})
    for name, html in (("14-problem", problem()), ("15-always-on", always_on())):
        view.set_content(html, wait_until="networkidle")
        view.screenshot(path=str(HERE / f"{name}.png"))
    b.close()

GALLERY.mkdir(exist_ok=True)
for old in GALLERY.glob("*.png"):
    old.unlink()
for src, name in ORDER:
    shutil.copyfile(HERE / src, GALLERY / f"{name}.png")
for f in sorted(GALLERY.glob("*.png")):
    w, h = Image.open(f).size
    print(f.name, f"{w}x{h}", f"{f.stat().st_size // 1024} KB", "" if abs(w / h - 1.5) < 1e-6 and f.stat().st_size < 5_000_000 else "BAD")
