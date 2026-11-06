"""Draw the 3:2 project thumbnail from the logo and the measured results.

Run with a Python that has playwright:
  ../engine/.venv/bin/python build_thumbnail.py
"""
import base64
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
ROOT = HERE.parent
R = ROOT / "engine/eval/results"
scale = json.loads((R / "scale.json").read_text())
ev = json.loads((R / "eval_holdout.json").read_text())
LOOKUP = f"{scale['latency_ms']['full']['p50']:.0f} ms"
RECALL = f"{ev['summary']['all']['hybrid']['recall@10']:.2f}"
FILES = f"{scale['files']:,}"
logo = "data:image/png;base64," + base64.b64encode((ROOT / "assets/logo.png").read_bytes()).decode()
defs = re.search(r"<defs>.*?</defs>", (HERE / "visuals/01-architecture.svg").read_text("utf8"), re.S).group(0)

HUB = (1128, 372)
HUB_R = 86
SATELLITES = [("photo", 912, 182), ("doc", 1352, 170), ("video", 884, 556), ("mic", 1372, 548)]
SMALL = [(1012, 96), (1236, 84), (1442, 330), (780, 372), (1040, 624), (1250, 640), (1010, 300), (1262, 292), (1240, 462), (1016, 452)]
LINKS = [(0, 6), (1, 7), (2, 9), (3, 8), (0, 0), (1, 1), (2, 4), (3, 5), (1, 2), (3, 2), (0, 3), (2, 3)]


def graph():
    o = []
    for sat, small in LINKS:
        _, x, y = SATELLITES[sat]
        sx, sy = SMALL[small]
        o.append(f'<line x1="{x}" y1="{y}" x2="{sx}" y2="{sy}" stroke="#62b0ff" stroke-opacity=".28" stroke-width="2.5"/>')
    for sx, sy in SMALL[6:]:
        o.append(f'<line x1="{HUB[0]}" y1="{HUB[1]}" x2="{sx}" y2="{sy}" stroke="#2bf0ad" stroke-opacity=".34" stroke-width="2.5"/>')
    for _, x, y in SATELLITES:
        o.append(f'<line x1="{HUB[0]}" y1="{HUB[1]}" x2="{x}" y2="{y}" stroke="url(#edge)" stroke-width="6" stroke-linecap="round"/>')
    for i, (sx, sy) in enumerate(SMALL):
        o.append(f'<circle cx="{sx}" cy="{sy}" r="{9 if i % 2 else 12}" fill="{"#2bf0ad" if i % 3 == 0 else "#62b0ff"}"/>')
    for name, x, y in SATELLITES:
        o.append(f'<circle cx="{x}" cy="{y}" r="58" fill="#0e1a3e" stroke="url(#edge)" stroke-width="4"/>')
        o.append(f'<use xlink:href="#i-{name}" x="{x - 32}" y="{y - 32}" width="64" height="64" fill="none" stroke="#e9fbff" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/>')
    x, y = HUB
    o.append(f'<circle cx="{x}" cy="{y}" r="{HUB_R + 44}" fill="url(#halo)"/>')
    o.append(f'<circle cx="{x}" cy="{y}" r="{HUB_R}" fill="url(#hub)"/>')
    o.append(f'<circle cx="{x - 9}" cy="{y - 9}" r="35" fill="none" stroke="#fff" stroke-width="11"/>')
    o.append(f'<line x1="{x + 17}" y1="{y + 17}" x2="{x + 45}" y2="{y + 45}" stroke="#fff" stroke-width="13" stroke-linecap="round"/>')
    return "".join(o)


PAGE = f"""<!doctype html><html><head><meta charset="utf-8"><style>
* {{ box-sizing: border-box; margin: 0; }}
html, body {{ width: 1500px; height: 1000px; overflow: hidden; }}
body {{ position: relative; font-family: "Avenir Next", "Helvetica Neue", Arial, sans-serif; color: #fff;
  background: radial-gradient(760px 620px at 8% 2%, rgba(43,240,173,.26), transparent 70%),
              radial-gradient(860px 700px at 88% 30%, rgba(61,120,255,.30), transparent 70%),
              radial-gradient(760px 520px at 62% 112%, rgba(181,123,255,.20), transparent 72%),
              linear-gradient(135deg, #090f22, #141a3c); }}
svg.art {{ position: absolute; inset: 0; }}
.brand {{ position: absolute; left: 88px; top: 92px; width: 700px; }}
.brand img {{ width: 212px; height: 212px; display: block; border-radius: 46px; box-shadow: 0 26px 70px rgba(16,207,196,.30); }}
h1 {{ margin-top: 30px; font-size: 138px; font-weight: 800; line-height: 1; letter-spacing: -2px;
  background: linear-gradient(90deg, #2bf0ad, #39d9e6 50%, #62b0ff); -webkit-background-clip: text; background-clip: text; color: transparent; }}
.line {{ margin-top: 22px; font-size: 45px; font-weight: 700; line-height: 1.16; }}
.sub {{ margin-top: 14px; font-size: 29px; font-weight: 500; color: #b9c9e6; }}
.stats {{ position: absolute; left: 88px; right: 88px; bottom: 58px; height: 168px; display: grid; grid-template-columns: repeat(3, 1fr);
  border: 2px solid rgba(255,255,255,.14); border-radius: 30px; background: rgba(10,18,44,.72); }}
.stat {{ display: flex; flex-direction: column; justify-content: center; padding-left: 46px; }}
.stat + .stat {{ border-left: 2px solid rgba(255,255,255,.12); }}
.big {{ font-size: 72px; font-weight: 800; line-height: 1; color: #2bf0ad; }}
.small {{ margin-top: 10px; font-size: 27px; font-weight: 600; color: #cfdcf2; }}
</style></head><body>
<svg class="art" width="1500" height="1000" viewBox="0 0 1500 1000" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
{defs.replace("</defs>", '''<linearGradient id="edge" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2bf0ad"/><stop offset="1" stop-color="#62b0ff"/></linearGradient>
<linearGradient id="hub" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2fd98f"/><stop offset=".5" stop-color="#10cfc4"/><stop offset="1" stop-color="#0d7cf2"/></linearGradient>
<radialGradient id="halo"><stop offset=".55" stop-color="#10cfc4" stop-opacity=".42"/><stop offset="1" stop-color="#10cfc4" stop-opacity="0"/></radialGradient></defs>''')}
{graph()}
</svg>
<div class="brand">
  <img src="{logo}" alt="">
  <h1>Ufinder</h1>
  <div class="line">Find any file by what is inside it.</div>
  <div class="sub">The memory layer for AI on a NAS</div>
</div>
<div class="stats">
  <div class="stat"><div class="big">{LOOKUP}</div><div class="small">lookup at {FILES} files</div></div>
  <div class="stat"><div class="big">{RECALL}</div><div class="small">recall on locked queries</div></div>
  <div class="stat"><div class="big">0</div><div class="small">LLM calls to search</div></div>
</div>
</body></html>"""

with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    page = b.new_page(viewport={"width": 1500, "height": 1000})
    page.set_content(PAGE, wait_until="networkidle")
    page.screenshot(path=str(HERE / "thumbnail.png"))
    b.close()
