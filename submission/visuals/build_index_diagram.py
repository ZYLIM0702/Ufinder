"""Draw 03-index-design: how one file becomes two indexes."""
import base64
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
defs = re.search(r"<defs>.*?</defs>", (HERE / "01-architecture.svg").read_text("utf8"), re.S).group(0)
FONT = "Avenir Next, Helvetica Neue, Helvetica, Arial, sans-serif"
LOGO = base64.b64encode((HERE.parent.parent / "assets/logo.png").read_bytes()).decode()


def text(x, y, s, size=20, weight=500, fill="#e8eefb", anchor="start"):
    s = s.replace("&", "&amp;")
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{s}</text>'


def icon(name, x, y, size, stroke="#0b1020", width=2.3):
    return f'<use xlink:href="#i-{name}" x="{x}" y="{y}" width="{size}" height="{size}" fill="none" stroke="{stroke}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>'


def disc(cx, cy, r, grad, name):
    s = int(r * 1.3)
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#{grad})" filter="url(#glow)"/>' + icon(name, cx - s // 2, cy - s // 2, s)


def arrow(d, color="#e8eefb", dash=False):
    extra = ' stroke-dasharray="8 7"' if dash else ""
    m = "ah" if color == "#e8eefb" else "ahA"
    return f'<path d="{d}" stroke="{color}" stroke-width="4" fill="none" stroke-linecap="round" marker-end="url(#{m})"{extra}/>'


o = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1500" height="1000" viewBox="0 0 1500 1000" font-family="{FONT}">', defs]
o.append('<rect width="1500" height="1000" fill="url(#bg)"/><rect width="1500" height="1000" fill="url(#dots)"/>')
o.append('<ellipse cx="300" cy="280" rx="480" ry="330" fill="url(#glowT)"/><ellipse cx="1180" cy="760" rx="560" ry="360" fill="url(#glowV)"/>')
o.append(f'<image x="1378" y="26" width="74" height="74" xlink:href="data:image/png;base64,{LOGO}"/>')
o.append(text(48, 82, "Read a file once. Know it forever.", 50, 800))
o.append(text(50, 122, "Meaning is stored by content, not by path. Renames, copies and restarts cost nothing.", 24, 500, "#d6dff0"))

# level one and two
o.append('<rect x="48" y="150" width="640" height="288" rx="22" fill="#14224a" stroke="url(#gBlue)" stroke-width="3" filter="url(#shadow)"/>')
o.append(disc(92, 192, 26, "gBlue", "folder"))
o.append(text(132, 190, "File table", 28, 800) + text(132, 216, "Who has what, and where", 18, 600, "#a9c3ff"))
rows = [("Contracts/Riverbend-Lease-2025_v2.docx", 262), ("Archive/lease-signed-copy.docx", 322), ("Photos/IMG_3301.jpg", 382)]
for label, y in rows:
    o.append(f'<rect x="72" y="{y - 32}" width="592" height="48" rx="11" fill="#ffffff" fill-opacity=".07" stroke="#ffffff" stroke-opacity=".15"/>')
    o.append(text(90, y - 1, label, 20, 600))
o.append(text(646, 261, "hash a41f", 17, 700, "#ffc24a", "end") + text(646, 321, "hash a41f", 17, 700, "#ffc24a", "end") + text(646, 381, "hash 9c07", 17, 700, "#5ff5c6", "end"))

o.append('<rect x="812" y="150" width="640" height="288" rx="22" fill="#102d33" stroke="url(#gTeal)" stroke-width="3" filter="url(#shadow)"/>')
o.append(disc(856, 192, 26, "gTeal", "db"))
o.append(text(896, 190, "Content cache", 28, 800) + text(896, 216, "What the content means", 18, 600, "#5ff5c6"))
o.append('<rect x="836" y="232" width="592" height="88" rx="11" fill="#ffffff" fill-opacity=".07" stroke="#ffc24a" stroke-opacity=".6"/>')
o.append(text(854, 264, "a41f", 21, 800, "#ffc24a") + text(922, 264, "lease text, vectors, topics", 20, 600) + text(922, 296, "One record for both paths", 18, 500, "#c3cfe6"))
o.append('<rect x="836" y="332" width="592" height="82" rx="11" fill="#ffffff" fill-opacity=".07" stroke="#5ff5c6" stroke-opacity=".6"/>')
o.append(text(854, 364, "9c07", 21, 800, "#5ff5c6") + text(922, 364, "image vector, text read from the photo", 20, 600) + text(922, 394, "Taken 4 March, 11:05", 18, 500, "#c3cfe6"))
o.append(arrow("M690 252 C 740 252, 760 268, 830 268", "#ffc24a") + arrow("M690 312 C 740 312, 760 288, 830 288", "#ffc24a"))
o.append(arrow("M690 372 H 830"))

# phases
y = 474
o.append(text(48, y, "THREE PASSES", 16, 800, "#ff9ab0"))
cards = [
    (48, 450, "gBlue", "eye", "1. Scan", ["Size, time and inode match?", "Skip it. Nothing is read."], "Fast, whole NAS"),
    (525, 450, "gViolet", "chip", "2. Parse", ["One file at a time.", "Text, OCR, speech, vectors."], "Pure, resumable, cached"),
    (1002, 450, "gTeal", "graph", "3. Resolve", ["Across all files.", "Links, topics, events, gaps."], "Runs while indexing"),
]
for x, w, grad, ic, title, lines, tag in cards:
    o.append(f'<rect x="{x}" y="{y + 14}" width="{w}" height="166" rx="18" fill="#17214a" stroke="#ffffff" stroke-opacity=".14" stroke-width="2" filter="url(#shadow)"/>')
    o.append(disc(x + 50, y + 66, 28, grad, ic))
    o.append(text(x + 92, y + 76, title, 27, 800))
    o.append(text(x + 24, y + 124, lines[0], 20, 600) + text(x + 24, y + 152, lines[1], 20, 600))
    o.append(text(x + w - 24, y + 72, tag, 16, 700, "#a9c3ff", "end"))
o.append(arrow("M500 572 H 522") + arrow("M977 572 H 999"))

# outcomes
y = 668
o.append('<rect x="48" y="678" width="690" height="290" rx="22" fill="#14224a" stroke="url(#gBlue)" stroke-width="3" filter="url(#shadow)"/>')
o.append(disc(92, 722, 26, "gBlue", "photo"))
o.append(text(132, 716, "Vector index", 29, 800) + text(132, 744, "What a file means", 19, 600, "#a9c3ff"))
import random
r = random.Random(4)
clusters = [(190, 860, "#ff6fa8"), (365, 835, "#62b0ff"), (540, 875, "#ffc24a")]
for cx, cy, c in clusters:
    for _ in range(26):
        px, py = r.gauss(cx, 44), min(max(r.gauss(cy, 24), 776), 916)
        o.append(f'<circle cx="{px:.0f}" cy="{py:.0f}" r="4.5" fill="{c}" opacity=".85"/>')
o.append(text(190, 948, "photos", 18, 700, "#ff9ab0", "middle") + text(365, 948, "documents", 18, 700, "#a9c3ff", "middle") + text(540, 948, "recordings", 18, 700, "#ffc24a", "middle"))
o.append(text(714, 722, "One space for every format", 18, 600, "#c3cfe6", "end"))

o.append('<rect x="762" y="678" width="690" height="290" rx="22" fill="#102d33" stroke="url(#gTeal)" stroke-width="3" filter="url(#shadow)"/>')
o.append(disc(806, 722, 26, "gTeal", "graph"))
o.append(text(846, 716, "Graph index", 29, 800) + text(846, 744, "How files connect", 19, 600, "#5ff5c6"))
nodes = {
    "memo": (850, 830, "#ffc24a", 10, "voice memo"), "note": (960, 900, "#62b0ff", 10, "kickoff notes"),
    "hub": (1040, 815, "#2bf0ad", 19, "Project Falcon"), "board": (1185, 800, "#ff6fa8", 10, "whiteboard"),
    "site": (1320, 760, "#ff6fa8", 10, "site photo"), "inv": (1180, 866, "#62b0ff", 10, "oven invoice"),
}
links = [("memo", "hub", "#2bf0ad"), ("note", "hub", "#2bf0ad"), ("board", "hub", "#2bf0ad"), ("inv", "hub", "#2bf0ad"), ("board", "site", "#ff6fa8")]
for a, b, c in links:
    o.append(f'<line x1="{nodes[a][0]}" y1="{nodes[a][1]}" x2="{nodes[b][0]}" y2="{nodes[b][1]}" stroke="{c}" stroke-width="3" opacity=".7"/>')
o.append('<line x1="960" y1="900" x2="1330" y2="900" stroke="#ff8a5c" stroke-width="3" stroke-dasharray="8 7" opacity=".85"/>')
for k, (x, yy, c, rad, label) in nodes.items():
    o.append(f'<circle cx="{x}" cy="{yy}" r="{rad}" fill="{c}" filter="url(#led)"/>')
    dy = -24 if k == "hub" else 6 if k == "inv" else 30
    o.append(text(x + (66 if k == "inv" else 0), yy + dy, label, 17, 700 if k == "hub" else 600, "#ffffff", "middle"))
o.append('<circle cx="1330" cy="900" r="11" fill="#0e1530" stroke="#ff8a5c" stroke-width="3" stroke-dasharray="5 4"/>')
o.append(text(1330, 932, "missing floor plan", 17, 700, "#ffb38a", "middle"))
o.append(text(1236, 762, "same time", 15, 600, "#ff9ab0", "middle"))
o.append("</svg>")
(HERE / "03-index-design.svg").write_text("\n".join(o), "utf8")
subprocess.run(["rsvg-convert", "-w", "1500", "-h", "1000", str(HERE / "03-index-design.svg"), "-o", str(HERE / "03-index-design.png")], check=True)
