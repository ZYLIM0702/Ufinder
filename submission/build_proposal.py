"""Build proposal.pdf from proposal.md, with figures drawn from the measured results.

Run with a Python that has playwright and Pillow:
  ../engine/.venv/bin/python build_proposal.py
"""
import base64
import html
import json
import re
import subprocess
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
ROOT = HERE.parent
R = ROOT / "engine/eval/results"
OUT = HERE / "proposal_figures"
OUT.mkdir(exist_ok=True)
defs = re.search(r"<defs>.*?</defs>", (HERE / "visuals/01-architecture.svg").read_text("utf8"), re.S).group(0)
FONT = "Avenir Next, Helvetica Neue, Helvetica, Arial, sans-serif"
INK, MUTE, LINE, TINT = "#10264a", "#51627c", "#d5e0ee", "#f2f7fd"
GREEN, TEAL, BLUE, DEEP = "#2fd98f", "#10cfc4", "#0d7cf2", "#0a56d6"
ev = json.loads((R / "eval_holdout.json").read_text())
scale = json.loads((R / "scale.json").read_text())
coco = json.loads((R / "coco_bench.json").read_text())
sys_checks = json.loads((R / "system.json").read_text()) + json.loads((R / "frontier.json").read_text()) + json.loads((R / "connections.json").read_text())


def t(x, y, s, size=26, weight=600, fill=INK, anchor="start"):
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{html.escape(s)}</text>'


def icon(name, x, y, size, stroke="#fff", width=2.3):
    return f'<use xlink:href="#i-{name}" x="{x}" y="{y}" width="{size}" height="{size}" fill="none" stroke="{stroke}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>'


def disc(cx, cy, r, name, grad="brand"):
    s = int(r * 1.25)
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#{grad})"/>' + icon(name, cx - s // 2, cy - s // 2, s)


def box(x, y, w, h, fill="#fff", stroke=LINE, r=20, sw=2):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def arrow(d, color=BLUE, w=5):
    return f'<path d="{d}" stroke="{color}" stroke-width="{w}" fill="none" stroke-linecap="round" marker-end="url(#tip)"/>'


EXTRA = f"""
<linearGradient id="brand" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{GREEN}"/><stop offset=".5" stop-color="{TEAL}"/><stop offset="1" stop-color="{BLUE}"/></linearGradient>
<linearGradient id="deep" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{BLUE}"/><stop offset="1" stop-color="{DEEP}"/></linearGradient>
<marker id="tip" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4.5" markerHeight="4.5" orient="auto"><path d="M0 0 L10 5 L0 10 z" fill="{BLUE}"/></marker>
"""


def render(name, w, h, body):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="{FONT}">'
           + defs.replace("</defs>", EXTRA + "</defs>") + body + "</svg>")
    src, png = OUT / f"{name}.svg", OUT / f"{name}.png"
    src.write_text(svg, "utf8")
    subprocess.run(["rsvg-convert", "-w", str(w), "-h", str(h), str(src), "-o", str(png)], check=True)
    art = Image.open(png).convert("RGBA")
    flat = Image.new("RGBA", art.size, "white")
    flat.alpha_composite(art)
    small = flat.convert("RGB").quantize(colors=200, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    colors = small.getpalette()[:600]
    rgb = [colors[i:i + 3] for i in range(0, len(colors), 3)]
    brightest = max(range(len(rgb)), key=lambda i: sum(rgb[i]))
    rgb[brightest] = [255, 255, 255]  # keep paper white, so figures sit flush on the page
    small.putpalette([v for row in rgb for v in row])
    small.save(png, optimize=True)
    src.unlink()
    return png


def metrics():
    lat = scale["latency_ms"]["full"]["p50"]
    recall = ev["summary"]["all"]["hybrid"]["recall@10"]
    public = coco["dims"]["1024"]["recall@10_binary_rescore"] * 100
    passed = sum(r["ok"] for r in sys_checks)
    tiles = [
        (f"{lat:.0f} ms", "lookup, 200,000 files"),
        (f"{recall:.2f}", "recall, locked queries"),
        ("0", "LLM calls to search"),
        (f"{public:.1f}%", "public COCO benchmark"),
        (f"{passed}/{len(sys_checks)}", "system checks passed"),
    ]
    o, w = [], 312
    for i, (big, small) in enumerate(tiles):
        x = i * (w + 17)
        o.append(f'<rect x="{x}" y="4" width="{w}" height="172" rx="22" fill="{TINT}" stroke="{LINE}" stroke-width="2"/>')
        o.append(f'<text x="{x + w / 2}" y="98" font-size="62" font-weight="800" fill="url(#brandh)" text-anchor="middle">{big}</text>')
        o.append(t(x + w / 2, 142, small, 23, 600, MUTE, "middle"))
    grad = f'<linearGradient id="brandh" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{TEAL}"/><stop offset="1" stop-color="{DEEP}"/></linearGradient>'
    return render("metrics", 1628, 180, f"<defs>{grad}</defs>" + "".join(o))


def architecture():
    o = [f'<rect width="1640" height="760" rx="26" fill="{TINT}"/>']
    # clients
    for x, w, name, ic in ((36, 500, "Uliya chat", "chat"), (572, 300, "Web UI", "web"), (892, 300, "Agents", "bot"), (1212, 392, "Frontier model", "cloud")):
        dashed = ' stroke-dasharray="10 8"' if name.startswith("Frontier") else ""
        o.append(f'<rect x="{x}" y="28" width="{w}" height="84" rx="18" fill="#fff" stroke="{LINE}" stroke-width="2"{dashed}/>')
        o.append(disc(x + 50, 70, 28, ic))
        o.append(t(x + 92, 80, name, 28, 700))
    o.append(t(1426, 152, "off by default", 21, 700, DEEP))
    # skill
    o.append(box(36, 176, 500, 330, "#fff", GREEN, 22, 3))
    o.append(disc(90, 232, 30, "doc"))
    o.append(t(136, 226, "Skill", 34, 800) + t(136, 256, "Works on a stock NAS", 22, 600, MUTE))
    for i, label in enumerate(("16 functions", "6 UGOS expert agents", "Evidence ranking", "Approval on every write")):
        o.append(icon("check", 64, 288 + i * 50, 28, TEAL, 3.4))
        o.append(t(104, 312 + i * 50, label, 25, 600))
    # engine
    o.append(box(572, 176, 1032, 330, "#fff", BLUE, 22, 3))
    o.append(disc(626, 232, 30, "chip"))
    o.append(t(672, 226, "Engine", 34, 800) + t(672, 256, "Optional, owner-installed, no LLM to search", 22, 600, MUTE))
    o.append('<rect x="600" y="282" width="976" height="60" rx="14" fill="url(#deep)"/>')
    o.append(t(1088, 322, "Gateway: identity, per-user filter, content tiers, audit", 25, 700, "#fff", "middle"))
    for x, ic, title, sub in ((600, "eye", "Indexer", "Parse, then resolve"), (930, "chip", "Local Qwen", "One vector space"), (1260, "graph", "Vector + graph", "Meaning and links")):
        o.append(box(x, 358, 316, 126, TINT, LINE, 14))
        o.append(disc(x + 50, 421, 28, ic))
        o.append(t(x + 92, 412, title, 26, 700) + t(x + 92, 444, sub, 21, 500, MUTE))
    # exchange and files
    o.append('<rect x="372" y="534" width="930" height="64" rx="16" fill="url(#brand)"/>')
    o.append(icon("folder", 402, 548, 36, "#fff", 2.3))
    o.append(t(860, 576, "Private folder per user: plain files, no sockets", 26, 700, "#fff", "middle"))
    o.append(f'<rect x="36" y="630" width="1568" height="100" rx="20" fill="{INK}"/>')
    for x, ic, label in ((360, "photo", "Photos"), (640, "doc", "Documents"), (960, "mic", "Recordings"), (1280, "video", "Video")):
        o.append(icon(ic, x - 66, 662, 38, "#7fe3d6", 2.2))
        o.append(t(x - 16, 690, label, 26, 700, "#fff"))
    o.append(t(92, 690, "NAS files", 28, 800, "#fff"))
    # arrows
    for d in ("M286 114 V172", "M722 114 V172", "M1042 114 V172", "M420 532 V510", "M1088 510 V530", "M150 626 V510", "M1490 626 V510"):
        o.append(arrow(d))
    o.append(f'<path d="M1408 172 V116" stroke="{DEEP}" stroke-width="5" fill="none" stroke-dasharray="9 8"/>')
    o.append(t(168, 574, "UGOS permissions", 20, 700, DEEP))
    o.append(t(1472, 574, "read-only", 20, 700, DEEP, "end"))
    return render("architecture", 1640, 760, "".join(o))


def pipeline():
    o = [f'<rect width="1640" height="620" rx="26" fill="{TINT}"/>']
    o.append(f'<rect x="36" y="30" width="980" height="76" rx="38" fill="{INK}"/>')
    o.append(icon("user", 62, 46, 44, "#7fe3d6", 2.2))
    o.append(t(526, 80, "“Pictures from the day we ate at Gurney Drive”", 30, 700, "#fff", "middle"))
    y = 138
    for ic, name in (("doc", "Keyword"), ("photo", "Picture vectors"), ("chip", "Text vectors")):
        o.append(box(36, y, 320, 62, "#fff", LINE, 14))
        o.append(icon(ic, 54, y + 13, 36, BLUE, 2.2))
        o.append(t(104, y + 41, name, 25, 700))
        o.append(arrow(f"M360 {y + 31} C 396 {y + 31}, 396 214, 432 214"))
        y += 76
    o.append(f'<rect x="438" y="154" width="196" height="120" rx="18" fill="url(#deep)"/>')
    o.append(t(536, 208, "Rank", 28, 800, "#fff", "middle") + t(536, 242, "fusion", 28, 800, "#fff", "middle"))
    o.append(arrow("M640 214 H696"))
    o.append(box(702, 128, 902, 218, "#fff", GREEN, 20, 3))
    o.append(t(730, 174, "Direct results", 28, 800) + t(1578, 174, "evidence for every file", 21, 600, MUTE, "end"))
    o.append(icon("mic", 730, 196, 34, BLUE, 2.2) + t(778, 222, "voice-note-day2.m4a", 25, 700) + t(1578, 222, "said aloud", 22, 600, DEEP, "end"))
    o.append(f'<line x1="730" y1="246" x2="1578" y2="246" stroke="{LINE}" stroke-width="2"/>')
    o.append(icon("doc", 730, 262, 34, BLUE, 2.2) + t(778, 288, "itinerary.md", 25, 700) + t(1578, 288, "text", 22, 600, DEEP, "end"))
    o.append(arrow("M1152 350 V402"))
    o.append(t(1168, 384, "graph walk from those hits", 22, 700, DEEP))
    o.append(box(36, 408, 1568, 184, "#fff", BLUE, 20, 3))
    o.append(t(64, 454, "Connected files", 28, 800) + t(64, 486, "Nothing here matches a word or a picture.", 22, 600, MUTE))
    o.append(f'<circle cx="150" cy="546" r="17" fill="{GREEN}"/>' + t(182, 554, "voice note", 23, 700))
    o.append(f'<line x1="316" y1="546" x2="520" y2="546" stroke="{TEAL}" stroke-width="6"/>' + t(418, 532, "same time", 21, 700, DEEP, "middle"))
    for dx, c in ((0, TEAL), (36, BLUE), (72, DEEP)):
        o.append(f'<circle cx="{544 + dx}" cy="546" r="15" fill="{c}"/>')
    o.append(t(644, 554, "3 holiday photos", 23, 700))
    o.append(f'<circle cx="940" cy="546" r="17" fill="{GREEN}"/>' + t(972, 554, "itinerary", 23, 700))
    o.append(f'<line x1="1078" y1="546" x2="1290" y2="546" stroke="{TEAL}" stroke-width="6"/>' + t(1184, 532, "same booking ID", 21, 700, DEEP, "middle"))
    o.append(f'<circle cx="1314" cy="546" r="15" fill="{BLUE}"/>' + t(1344, 554, "hotel receipt", 23, 700))
    return render("pipeline", 1640, 620, "".join(o))


def proof():
    s = ev["summary"]
    bars = [("Keyword", s["all"]["keyword"]["recall@10"], "#b5c3d6"), ("Vector", s["all"]["vector"]["recall@10"], "#7ea3d6"), ("Both", s["all"]["hybrid"]["recall@10"], "url(#deep)")]
    o = [f'<rect width="800" height="330" rx="24" fill="{TINT}"/>', t(36, 58, "Right files found, top 10", 28, 800), t(36, 90, "49 locked held-out queries", 21, 600, MUTE)]
    for i, (label, v, c) in enumerate(bars):
        y = 122 + i * 66
        o.append(t(36, y + 34, label, 25, 700))
        o.append(f'<rect x="170" y="{y}" width="520" height="46" rx="12" fill="#e4ecf6"/>')
        o.append(f'<rect x="170" y="{y}" width="{520 * v:.0f}" height="46" rx="12" fill="{c}"/>')
        o.append(t(708, y + 34, f"{v:.2f}", 28, 800))
    x = 840
    g = s["graph"]["budget20"]
    o.append(f'<rect x="{x}" width="800" height="330" rx="24" fill="{TINT}"/>')
    o.append(t(x + 36, 58, "Queries that need connections", 28, 800) + t(x + 36, 90, "20 files shown either way", 21, 600, MUTE))
    for i, (label, v, c) in enumerate((("Direct only", g["direct_only"], "#b5c3d6"), ("With graph", g["direct_plus_connected"], "url(#brand)"))):
        y = 128 + i * 92
        o.append(t(x + 36, y + 42, label, 25, 700))
        o.append(f'<rect x="{x + 216}" y="{y}" width="464" height="62" rx="14" fill="#e4ecf6"/>')
        o.append(f'<rect x="{x + 216}" y="{y}" width="{464 * v:.0f}" height="62" rx="14" fill="{c}"/>')
        o.append(t(x + 698, y + 44, f"{v:.2f}", 34, 800))
    return render("proof", 1640, 330, "".join(o))


def hero():
    o = ['<rect width="1240" height="250" fill="#fff"/>']
    o.append('<defs><linearGradient id="tg" x1="0" x2="1"><stop offset="0" stop-color="#2fd98f"/><stop offset=".45" stop-color="#10cfc4"/><stop offset="1" stop-color="#0a56d6"/></linearGradient></defs>')
    o.append('<text x="0" y="132" font-size="150" font-weight="800" fill="url(#tg)">Ufinder</text>')
    o.append(t(4, 208, "The memory layer for AI on a NAS", 52, 600))
    return render("hero", 1240, 250, "".join(o))


def modes():
    tiles = (("photo", "Photo", "needs vision"), ("doc", "Scan", "needs OCR"), ("mic", "Recording", "needs speech"), ("video", "Video", "needs all three"))
    o, w = [], 262
    for i, (ic, name, need) in enumerate(tiles):
        x = i * (w + 16)
        o.append(box(x, 4, w, 122, TINT, LINE, 20))
        o.append(disc(x + 54, 65, 32, ic))
        o.append(t(x + 100, 56, name, 27, 800) + t(x + 100, 90, need, 22, 600, MUTE))
    o.append(arrow("M1124 65 H1176"))
    o.append('<rect x="1186" y="4" width="442" height="122" rx="20" fill="url(#deep)"/>')
    o.append(t(1407, 56, "One index", 34, 800, "#fff", "middle") + t(1407, 94, "every type, same search", 23, 600, "#dceaff", "middle"))
    return render("modes", 1628, 130, "".join(o))


def always_on():
    rate = next(r for r in json.loads((R / "model_bench.json").read_text())["rows"] if r["key"] == "docker")["images_per_s"]
    lookup = scale["latency_ms"]["full"]["p50"]
    tiles = ((f"{1 / rate:.1f} s", "per image, CPU"), (f"{round(rate * 86400, -3):,.0f}", "images a day"),
             (f"{100000 / rate / 86400:.1f} days", "100,000 photos, once"), (f"{lookup:.0f} ms", "lookup after that"))
    o = ['<rect width="1628" height="170" rx="22" fill="#10264a"/>']
    o.append(t(40, 78, "A NAS runs 24/7", 32, 800, "#fff") + t(40, 116, "Laptop test, 6 CPU cores", 22, 600, "#a9c4e6"))
    w = 300
    for i, (big, small) in enumerate(tiles):
        x = 400 + i * w
        if i:
            o.append(f'<path d="M{x - 34} 64 l16 20 l-16 20" stroke="#7fe3d6" stroke-width="5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>')
        o.append(t(x + 8, 88, big, 44, 800, "#7fe3d6") + t(x + 8, 124, small, 21, 600, "#dceaff"))
    return render("always_on", 1628, 170, "".join(o))


def data_uri(p):
    return "data:image/png;base64," + base64.b64encode(Path(p).read_bytes()).decode()


def parse():
    text = (HERE / "proposal.md").read_text("utf8")
    main, rest = text.split("## Third-party components, sources and licenses")
    sections = {}
    for part in re.split(r"^## ", main, flags=re.M)[1:]:
        head, _, body = part.partition("\n")
        num, label = head.split(". ", 1)
        sections[int(num)] = (label, body.strip())
    return sections, rest


def section(sections, n):
    label, body = sections[n]
    return f'<section><div class="n">{n}</div><div><h2>{html.escape(label)}</h2><p>{html.escape(body)}</p></div></section>'


def table(rest):
    rows = [r for r in rest.splitlines() if r.startswith("|") and "---" not in r]
    cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows]
    head = "".join(f"<th>{html.escape(c)}</th>" for c in cells[0])
    body = "".join("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in row) + "</tr>" for row in cells[1:])
    notes = "".join(f"<p class=note>{html.escape(ln)}</p>" for ln in rest.splitlines() if ln.strip() and not ln.startswith("|"))
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>{notes}"


CSS = f"""
@page {{ size: A4; margin: 0; }}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
body {{ font-family: {FONT}; color: {INK}; font-size: 10.6pt; line-height: 1.46; }}
.page {{ width: 210mm; height: 297mm; padding: 13mm 15mm 13mm; position: relative; page-break-after: always; overflow: hidden;
  display: flex; flex-direction: column; justify-content: space-between; }}
.page:last-child {{ page-break-after: auto; }}
.hero {{ display: flex; align-items: center; gap: 6mm; margin-bottom: 4mm; }}
.hero img {{ width: 30mm; height: 30mm; }}
.hero .wordmark {{ width: 100mm; height: auto; }}
.hero .tag {{ font-size: 13.5pt; font-weight: 600; margin-top: 2mm; }}
.fig {{ width: 100%; display: block; margin: 3.4mm 0; }}
section {{ display: grid; grid-template-columns: 8mm 1fr; gap: 3mm; margin: 3.1mm 0; }}
.n {{ width: 7.4mm; height: 7.4mm; border-radius: 50%; color: #fff; font-weight: 800; font-size: 9.5pt; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, {GREEN}, {TEAL} 50%, {BLUE}); }}
h2 {{ margin: 0 0 .6mm; font-size: 11.2pt; font-weight: 800; }}
p {{ margin: 0; }}
.foot {{ position: absolute; left: 15mm; right: 15mm; bottom: 6.5mm; height: 1mm; border-radius: 1mm; background: linear-gradient(90deg, {GREEN}, {TEAL}, {BLUE}); }}
h3 {{ margin: 0 0 1.6mm; font-size: 11.2pt; font-weight: 800; }}
table {{ width: 100%; border-collapse: collapse; font-size: 7.5pt; line-height: 1.22; }}
th {{ text-align: left; color: #fff; background: {INK}; padding: 1mm 1.8mm; font-weight: 700; }}
td {{ padding: .75mm 1.8mm; border-bottom: .25mm solid {LINE}; vertical-align: top; }}
tr:nth-child(even) td {{ background: {TINT}; }}
.note {{ margin-top: 1.1mm; color: {MUTE}; font-size: 7.5pt; line-height: 1.26; }}
"""


def build():
    sec, rest = parse()
    figs = {k: data_uri(fn()) for k, fn in (("m", metrics), ("a", architecture), ("p", pipeline), ("r", proof), ("d", modes), ("n", always_on), ("h", hero))}
    im = Image.open(ROOT / "assets/logo.png").convert("RGBA").resize((340, 340), Image.LANCZOS)
    tmp = OUT / "logo.png"
    im.save(tmp, optimize=True)
    logo = data_uri(tmp)
    s = lambda *ns: "".join(section(sec, n) for n in ns)
    fig = lambda key, alt: f'<img class="fig" src="{figs[key]}" alt="{alt}">'
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Ufinder Project Proposal</title><style>{CSS}</style></head><body>
<div class="page">
  <div class="hero"><img src="{logo}" alt="Ufinder logo"><img class="wordmark" src="{figs['h']}" alt="Ufinder, the memory layer for AI on a NAS"></div>
  {fig("m", "Measured results")}
  {s(1, 2)}
  {fig("d", "Each file type needs different understanding")}
  {s(3)}
  {fig("a", "Architecture")}
  <div class="foot"></div>
</div>
<div class="page">
  {s(4, 5)}
  {fig("p", "How one search runs")}
  {s(6, 7)}
  {fig("n", "Why a slow first pass suits a NAS")}
  <div class="foot"></div>
</div>
<div class="page">
  {s(8)}
  {fig("r", "Measured retrieval quality")}
  {s(9, 10)}
  <div><h3>Third-party components, sources and licenses</h3>
  {table(rest)}</div>
  <div class="foot"></div>
</div>
</body></html>"""
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        pg = b.new_page()
        pg.set_content(page, wait_until="networkidle")
        pg.pdf(path=str(HERE / "proposal.pdf"), format="A4", print_background=True, prefer_css_page_size=True)
        b.close()


if __name__ == "__main__":
    build()
