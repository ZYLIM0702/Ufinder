"""Draw 02-search-pipeline and 05-privacy-tests. The worked example and the test
counts come from the real system, not from this file."""
import base64
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
R = HERE.parent.parent / "engine/eval/results"
defs = re.search(r"<defs>.*?</defs>", (HERE / "01-architecture.svg").read_text("utf8"), re.S).group(0)
FONT = "Avenir Next, Helvetica Neue, Helvetica, Arial, sans-serif"


def text(x, y, s, size=20, weight=500, fill="#e8eefb", anchor="start"):
    s = s.replace("&", "&amp;")
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{s}</text>'


def icon(name, x, y, size, stroke="#0b1020", width=2.3):
    return f'<use xlink:href="#i-{name}" x="{x}" y="{y}" width="{size}" height="{size}" fill="none" stroke="{stroke}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>'


def disc(cx, cy, r, grad, name):
    s = int(r * 1.3)
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#{grad})" filter="url(#glow)"/>' + icon(name, cx - s // 2, cy - s // 2, s)


def arrow(d, color="#e8eefb"):
    m = "ah" if color == "#e8eefb" else "ahA"
    return f'<path d="{d}" stroke="{color}" stroke-width="4" fill="none" stroke-linecap="round" marker-end="url(#{m})"/>'


def card(x, y, w, h, fill="#17214a", stroke='stroke="#ffffff" stroke-opacity=".14"', r=18):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" {stroke} stroke-width="2" filter="url(#shadow)"/>'


def start():
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1500" height="1000" viewBox="0 0 1500 1000" font-family="{FONT}">',
        defs,
        '<rect width="1500" height="1000" fill="url(#bg)"/><rect width="1500" height="1000" fill="url(#dots)"/>',
    ]


def logo(x, y, w):
    data = base64.b64encode((HERE.parent.parent / "assets/logo.png").read_bytes()).decode()
    return f'<image x="{x}" y="{y}" width="{w}" height="{w}" xlink:href="data:image/png;base64,{data}"/>'


def finish(o, name):
    o.append("</svg>")
    (HERE / f"{name}.svg").write_text("\n".join(o), "utf8")
    subprocess.run(["rsvg-convert", "-w", "1500", "-h", "1000", str(HERE / f"{name}.svg"), "-o", str(HERE / f"{name}.png")], check=True)


def pipeline():
    ev = json.loads((R / "eval_holdout.json").read_text())
    g = ev["summary"]["graph"]["budget20"]
    o = start()
    o.append('<ellipse cx="260" cy="330" rx="470" ry="320" fill="url(#glowT)"/><ellipse cx="1140" cy="690" rx="620" ry="380" fill="url(#glowV)"/>')
    o.append(logo(1378, 26, 74))
    o.append(text(48, 82, "One search. No LLM.", 54, 800))
    o.append(text(50, 122, "Direct evidence first. Then the graph finds what no word or picture could.", 24, 500, "#d6dff0"))

    # query
    o.append('<circle cx="86" cy="196" r="34" fill="url(#gCoral)" filter="url(#glow)"/>' + icon("user", 62, 172, 48, "#fff", 2.1))
    o.append(card(136, 160, 640, 72, "#ffffff", 'stroke="none"', 16))
    o.append(text(456, 206, "“Pictures from the day we ate at Gurney Drive”", 25, 700, "#141a3c", "middle"))

    # retrievers
    rows = [("gTeal", "doc", "Keyword", "Text, OCR, speech, names", 262), ("gViolet", "photo", "Picture vectors", "How it looks", 372), ("gBlue", "chip", "Text vectors", "What it means", 482)]
    for grad, ic, title, sub, y in rows:
        o.append(card(48, y, 380, 96))
        o.append(disc(102, y + 48, 30, grad, ic))
        o.append(text(150, y + 42, title, 25, 800) + text(150, y + 72, sub, 18, 500, "#c3cfe6"))
    o.append(arrow("M432 310 C 470 310, 470 410, 512 410") + arrow("M432 420 H 512") + arrow("M432 530 C 470 530, 470 430, 512 430"))

    # fusion
    o.append(card(516, 330, 214, 180, "#1f2a5e", 'stroke="url(#gGate)"', 18))
    o.append(text(623, 386, "Rank", 26, 800, anchor="middle") + text(623, 418, "fusion", 26, 800, anchor="middle"))
    o.append(text(623, 460, "Only the top of", 16, 600, "#c3cfe6", "middle") + text(623, 482, "each list votes", 16, 600, "#c3cfe6", "middle"))
    o.append(arrow("M734 420 H 790"))

    # direct results
    o.append(card(794, 150, 658, 428, "#102d33", 'stroke="url(#gTeal)"', 22))
    o.append(disc(842, 196, 26, "gTeal", "check"))
    o.append(text(884, 194, "Direct results", 28, 800) + text(884, 220, "Files that match the words or the picture", 18, 600, "#5ff5c6"))
    direct = [("voice-note-day2.m4a", "Said aloud", "“...we had char kway teow at Gurney Drive...”", "#ffc24a", "mic"), ("itinerary.md", "Text", "“Hawker lunch at Gurney Drive”", "#62b0ff", "doc")]
    y = 248
    for name, label, quote, color, ic in direct:
        o.append(f'<rect x="818" y="{y}" width="610" height="104" rx="12" fill="#ffffff" fill-opacity=".07" stroke="{color}" stroke-opacity=".6"/>')
        o.append(icon(ic, 836, y + 18, 32, color))
        o.append(text(882, y + 42, name, 22, 700))
        o.append(f'<rect x="1270" y="{y + 18}" width="140" height="34" rx="17" fill="{color}" fill-opacity=".2"/>' + text(1340, y + 41, label, 16, 700, color, "middle"))
        o.append(text(836, y + 84, quote, 18, 500, "#c3cfe6"))
        y += 116
    o.append(text(836, 508, "Keyword and vectors alone stop here.", 21, 700, "#ffffff"))
    o.append(text(836, 540, "They cannot see the photos: no words, nothing to match.", 19, 500, "#c3cfe6"))

    # graph walk
    o.append(arrow("M1118 582 V 628", "#ffc24a"))
    o.append(text(1134, 612, "graph walk from those hits", 18, 700, "#ffc24a"))
    o.append(card(48, 632, 1404, 330, "#1b1c52", 'stroke="url(#gGate)"', 22))
    o.append(disc(96, 682, 28, "gViolet", "graph"))
    o.append(text(140, 680, "Connected files", 29, 800) + text(140, 708, "Each one shown with the evidence that links it", 18, 600, "#d9c7ff"))

    # example graph
    seed = (250, 836)
    o.append(f'<circle cx="{seed[0]}" cy="{seed[1]}" r="17" fill="#ffc24a" filter="url(#led)"/>')
    o.append(text(seed[0], seed[1] + 44, "voice note", 19, 700, "#ffffff", "middle"))
    book = (250, 742)
    o.append(f'<circle cx="{book[0]}" cy="{book[1]}" r="15" fill="#62b0ff" filter="url(#led)"/>')
    o.append(text(book[0] - 28, book[1] + 6, "itinerary", 19, 700, "#ffffff", "end"))
    photos = [(560, 782), (620, 836), (560, 890)]
    o.append(f'<line x1="{seed[0]}" y1="{seed[1]}" x2="540" y2="836" stroke="#ff6fa8" stroke-width="4" opacity=".85"/>')
    o.append(text(395, 826, "same time", 18, 700, "#ff9ab0", "middle"))
    for x, y2 in photos:
        o.append(f'<line x1="540" y1="836" x2="{x}" y2="{y2}" stroke="#ff6fa8" stroke-width="3" opacity=".7"/>')
        o.append(f'<circle cx="{x}" cy="{y2}" r="13" fill="#ff6fa8" filter="url(#led)"/>')
    o.append(text(650, 842, "3 holiday photos", 20, 700))
    o.append(text(650, 870, "no text in them at all", 17, 500, "#d9c7ff"))
    o.append(f'<line x1="{book[0]}" y1="{book[1]}" x2="620" y2="742" stroke="#2bf0ad" stroke-width="4" opacity=".85"/>')
    o.append(text(430, 730, "booking KBH-77120", 18, 700, "#5ff5c6", "middle"))
    o.append('<circle cx="620" cy="742" r="13" fill="#2bf0ad" filter="url(#led)"/>')
    o.append(text(650, 736, "hotel receipt", 20, 700) + text(650, 762, "same booking ID, read by OCR", 17, 500, "#d9c7ff"))

    # measured
    o.append(f'<rect x="940" y="668" width="486" height="268" rx="16" fill="#0b1020" fill-opacity=".55" stroke="#ffffff" stroke-opacity=".12"/>')
    o.append(text(964, 708, "HELD-OUT TEST, 20 FILES SHOWN", 15, 800, "#ffc24a"))
    o.append(text(964, 772, f"{g['direct_only']:.2f}", 56, 800, "#a4b1cc") + text(1118, 770, "→", 40, 700, "#ffc24a") + text(1176, 772, f"{g['direct_plus_connected']:.2f}", 56, 800, "#2bf0ad"))
    o.append(text(964, 812, "Share of right files found", 19, 600, "#e8eefb"))
    o.append(text(964, 840, "on queries that need connections", 19, 600, "#e8eefb"))
    o.append(text(964, 896, "Queries were locked before the run.", 17, 500, "#a4b1cc"))
    o.append(text(964, 920, "Test corpus is synthetic.", 17, 500, "#a4b1cc"))
    finish(o, "02-search-pipeline")


def scoreboard():
    rows = json.loads((R / "system.json").read_text()) + json.loads((R / "frontier.json").read_text()) + json.loads((R / "connections.json").read_text())
    groups = {}
    for r in rows:
        g = groups.setdefault(r["group"], [0, 0])
        g[1] += 1
        g[0] += int(r["ok"])
    show = [
        ("user segregation", "User segregation", "user", "One user never sees another's files, topics or counts"),
        ("no internet", "No route out", "nocloud", "Nothing that touches data can reach the internet"),
        ("least privilege", "Least privilege", "lock", "Non-root, zero capabilities, in every container"),
        ("read only", "Read-only files", "folder", "The engine cannot change a user file"),
        ("key limits", "Key limits", "key", "Scope, budget, revocation, hashed storage"),
        ("content tiers", "Content tiers", "shield", "External keys get paths. Snippets are redacted"),
        ("prompt injection", "Prompt injection", "doc", "Hostile files stay data. No send or delete tool"),
        ("exclusions", "Credential files", "lock", "Keys and env files are never indexed"),
        ("audit", "Audit chain", "doc", "Editing history breaks the chain"),
        ("change tracking", "Change tracking", "eye", "Edits and deletes are purged, not hidden"),
        ("missing files", "Missing files", "graph", "Mentioned but absent, and resolves itself"),
        ("skill bridge", "Skill bridge", "folder", "Plain files, per user, with no sockets"),
        ("model endpoint", "Frontier endpoint", "cloud", "Off by default. One host. Opted-in folders only"),
        (("languages", "multimodal query", "operators", "models"), "Search features", "eye", "Chinese text, image query, operators, embeddings"),
    ]
    passed, total = sum(g[0] for g in groups.values()), sum(g[1] for g in groups.values())
    o = start()
    o.append('<ellipse cx="1100" cy="240" rx="560" ry="300" fill="url(#glowT)"/><ellipse cx="300" cy="800" rx="520" ry="340" fill="url(#glowV)"/>')
    o.append(logo(40, 26, 104))
    o.append(text(152, 86, "Enforced below the LLM", 50, 800))
    o.append(text(154, 124, "Every check runs against the live Docker stack. Nothing is mocked.", 22, 500, "#d6dff0"))
    o.append(text(1452, 92, f"{passed} / {total}", 66, 800, "url(#title)", "end"))
    o.append(text(1452, 126, "checks passed", 22, 600, "#d6dff0", "end"))
    y0, cw, ch = 152, 690, 106
    for i, (key, title, ic, sub) in enumerate(show):
        x = 48 + (i % 2) * (cw + 24)
        y = y0 + (i // 2) * (ch + 11)
        keys = key if isinstance(key, tuple) else (key,)
        a, b = sum(groups.get(k, [0, 0])[0] for k in keys), sum(groups.get(k, [0, 0])[1] for k in keys)
        o.append(card(x, y, cw, ch))
        o.append(f'<circle cx="{x + 54}" cy="{y + ch / 2}" r="30" fill="url(#gTeal)" filter="url(#glow)"/>' + icon(ic, x + 34, int(y + ch / 2 - 20), 40))
        o.append(text(x + 100, y + 44, title, 24, 800) + text(x + 100, y + 76, sub, 17, 500, "#c3cfe6"))
        o.append(text(x + cw - 24, y + 62, f"{a}/{b}", 30, 800, "#5ff5c6", "end"))
    finish(o, "05-privacy-tests")
    return groups


if __name__ == "__main__":
    pipeline()
    print(scoreboard())
