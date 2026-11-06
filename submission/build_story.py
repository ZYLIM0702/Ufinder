"""Fill about-the-project.md and docs/RESULTS.md from engine/eval/results.

No number in the story is typed by hand. If a test is rerun, run this again.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
R = ROOT / "engine/eval/results"
IMG_BASE = sys.argv[1] if len(sys.argv) > 1 else "visuals/"

ev = json.loads((R / "eval_holdout.json").read_text())
dev = json.loads((R / "eval_dev.json").read_text())
first = json.loads((R / "eval_first_run.json").read_text())
coco = json.loads((R / "coco_bench.json").read_text())
scale = json.loads((R / "scale.json").read_text())
system = json.loads((R / "system.json").read_text()) + json.loads((R / "frontier.json").read_text()) + json.loads((R / "connections.json").read_text())
model = json.loads((R / "model_bench.json").read_text())
run = json.loads((R / "run.json").read_text())
truth = json.loads((ROOT / "engine/eval/queries.json").read_text())

CATS = [("name", "File name"), ("content", "Inside documents"), ("ocr", "Text in images"), ("spoken", "Spoken"),
        ("visual", "Looks like"), ("graph", "Connected"), ("all", "All")]
MODES = ["keyword", "vector", "hybrid"]
LABEL = {"keyword": "Keyword only", "vector": "Vector only", "hybrid": "Keyword + vector"}


def recall_table(d=ev, field="recall@10"):
    rows = []
    for key, name in CATS:
        s = d["summary"][key]
        cells = " | ".join(f"{s[m][field]:.2f}" for m in MODES)
        rows.append(f"| {'**All**' if key == 'all' else name} | {s['n']} | {cells} |")
    return "\n".join(rows)


def budget_table(d=ev):
    rows = []
    for key, name in (("graph", "Connected"), ("all", "All")):
        s = d["summary"][key]
        rows.append(f"| {name} | {s['n']} | {s['budget20']['direct_only']:.2f} | **{s['budget20']['direct_plus_connected']:.2f}** |")
    return "\n".join(rows)


def shirt_table(d=ev):
    return "\n".join(
        f"| {LABEL[m]} | {d['tshirt'][m]['correct_in_top10']:g} of 10 | {d['tshirt'][m]['wrong_word_shirts']:g} | {d['tshirt'][m]['word_on_poster']:g} |"
        for m in MODES
    )


def coco_table():
    rows = []
    for dim in ("2048", "1024", "512", "256"):
        d = coco["dims"][dim]
        rows.append(f"| {dim} | {d['recall@10'] * 100:.1f}% | {d['recall@10_binary_rescore'] * 100:.1f}% |")
    return "\n".join(rows)


def scale_table():
    lat = scale["latency_ms"]
    rows = [
        ("Keyword search, median", f"{lat['keyword_only']['p50']:.1f} ms"),
        ("Keyword search, slowest 5%", f"{lat['keyword_only']['p95']:.1f} ms"),
        ("Keyword, vectors and graph, median", f"{lat['full']['p50']:.1f} ms, before query embedding"),
        ("Keyword, vectors and graph, slowest 5%", f"{lat['full']['p95']:.1f} ms, before query embedding"),
        ("Worst case, only very common words", f"{lat['common_words']['p50']:.0f} ms"),
        ("Graph walk", f"{scale['ppr_ms']:.0f} ms, touching {scale['ppr_nodes_touched']} nodes of 200,000"),
        ("One exact ID found among 200,000", "Yes" if scale["exact_id_found"] else "No"),
        ("Another user's file stayed hidden", "Yes" if scale["other_root_hidden"] else "No"),
        ("SQLite on disk", f"{scale['sqlite_mb']} MB"),
        ("Vector database", f"{scale['qdrant_mem']} in memory, {scale['qdrant_disk']}B on disk"),
    ]
    return "\n".join(f"| {a} | {b} |" for a, b in rows)


def model_notes():
    rows = {r["key"]: r for r in model["rows"]}
    bf, fl, i8, dk = rows["bf16"], rows["float32"], rows["int8"], rows["docker"]
    return "\n".join([
        f"- The model card's default, `bfloat16`, ran {fl['images_per_s'] / bf['images_per_s']:.0f}× slower than `float32` on this CPU, which has to emulate it.",
        f"- `float32` reaches {fl['images_per_s']:.2f} images per second, but needs {fl['ram_gb']:.1f} GB of RAM.",
        f"- 8-bit quantization looked like the fix. It was slower, used more memory, and damaged the vectors: they matched the originals at only {model['int8_cosine']:.2f} cosine. Rejected.",
        f"- The real pipeline in Linux Docker, with OCR, took {1 / dk['images_per_s']:.1f} seconds per image on 6 cores. For 100,000 photos, that is about {100000 / dk['images_per_s'] / 86400:.1f} days in the background.",
    ])


def groups():
    out = {}
    for r in system:
        g = out.setdefault(r["group"], [0, 0])
        g[1] += 1
        g[0] += int(r["ok"])
    return out


passed = sum(r["ok"] for r in system)
tokens = {
    "SHIRT_DECOYS": str(len(truth["tshirt"]["decoys_other_word"]) + len(truth["tshirt"]["decoys_word_on_poster"])),
    "SHIRT_TABLE": shirt_table(),
    "RESTART_SKIPPED": str(run["restart_skipped"]),
    "GHOST_SECONDS": f"{run['ghost_seconds']:.1f}",
    "RENAME_SECONDS": f"{run['rename_seconds']:.1f}",
    "NEW_FILE_SECONDS": f"{run['new_file_seconds']:.1f}",
    "DELETE_SECONDS": f"{run['delete_seconds']:.1f}",
    "N_FILES": str(run["files"]),
    "N_PHOTOS": str(truth["meta"]["photos_noise"]),
    "HELD_N": str(ev["summary"]["all"]["n"]),
    "RECALL_TABLE": recall_table(),
    "BUDGET_TABLE": budget_table(),
    "FIRST_HYBRID": f"{first['summary']['all']['hybrid']['recall@10']:.2f}",
    "FIRST_GRAPH": f"{first['summary']['all']['hybrid+graph']['recall@10']:.2f}",
    "COCO_TABLE": coco_table(),
    "SCALE_FILES": f"{scale['files']:,}",
    "SCALE_EDGES": f"{scale['edges']:,}",
    "SCALE_TABLE": scale_table(),
    "SCALE_KEYWORD": f"{scale['latency_ms']['keyword_only']['p50']:.1f}",
    "FULL_P50": f"{ev['latency']['full']['p50_ms']:.0f}",
    "KEYWORD_P50": f"{ev['latency']['keyword']['p50_ms']:.1f}",
    "MODEL_NOTES": model_notes(),
    "SECONDS_PER_IMAGE": f"{1 / {r['key']: r for r in model['rows']}['docker']['images_per_s']:.1f}",
    "TESTS_PASSED": str(passed),
    "TESTS_TOTAL": str(len(system)),
}
story = (HERE / "about-the-project.template.md").read_text("utf8")
for k, v in tokens.items():
    story = story.replace("{{" + k + "}}", v)
story = story.replace("IMG:", IMG_BASE)
left = re.findall(r"\{\{\w+\}\}", story)
if left:
    raise SystemExit(f"unfilled tokens: {left}")
(HERE / "about-the-project.md").write_text(story, "utf8")

g = groups()
checks = "\n".join(f"| {name} | {a} of {b} |" for name, (a, b) in g.items())
failing = [r for r in system if not r["ok"]]
d_sum, h_sum = dev["summary"], ev["summary"]
results = f"""# Measured results

Generated from `engine/eval/results` by `submission/build_story.py`. Do not edit by hand.

Machine: Apple M2 Max, 64 GB. Docker runs through OrbStack (Linux, 12 CPUs, 16.8 GB). No UGREEN hardware was used.

## How the evaluation was run

1. The corpus and 56 queries were written before any search ran, with published default settings.
2. The first run failed: blending the graph into the ranking lowered recall from {first['summary']['all']['hybrid']['recall@10']:.2f} to {first['summary']['all']['hybrid+graph']['recall@10']:.2f}.
3. The 56 queries became the development set. Before any fix, 49 new queries were written and locked by hash (`engine/eval/results/holdout.sha256`).
4. The design was fixed using the development set only, then frozen.
5. The held-out set ran once.
6. Two bug fixes came after that run: clearing stale vectors on re-extraction, and a file name parser fix. Development recall and the 20-file result did not change. The held-out set was not rerun.

The corpus is synthetic and small. The connected queries were written to need the graph. Treat these as a demonstration, not a benchmark.

## Held-out set, {h_sum['all']['n']} queries

{run['files']} files. Recall@10:

| Query type | Queries | Keyword | Vector | Keyword + vector |
|---|---|---|---|---|
{recall_table()}

Mean reciprocal rank:

| Query type | Queries | Keyword | Vector | Keyword + vector |
|---|---|---|---|---|
{recall_table(ev, "mrr")}

Show 20 files either way:

| Queries | Count | 20 direct | 10 direct + 10 connected |
|---|---|---|---|
{budget_table()}

T-shirt test, averaged over two held-out phrasings. 10 right photos, 10 shirts with another word, 10 photos with the word on a poster:

| Method | Right in top 10 | Wrong word | On a poster |
|---|---|---|---|
{shirt_table()}

## Development set, {d_sum['all']['n']} queries, used to fix the design

| Query type | Queries | Keyword | Vector | Keyword + vector |
|---|---|---|---|---|
{recall_table(dev)}

| Queries | Count | 20 direct | 10 direct + 10 connected |
|---|---|---|---|
{budget_table(dev)}

| Method | Right in top 10 | Wrong word | On a poster |
|---|---|---|---|
{shirt_table(dev)}

## Public benchmark

COCO val2017, first {coco['n']} images by ID, first caption as the query, exact cosine, on GPU.

| Dimensions | Recall@1 | Recall@10 | 1-bit then rescore, recall@10 |
|---|---|---|---|
""" + "\n".join(
    f"| {d} | {coco['dims'][d]['recall@1'] * 100:.1f}% | {coco['dims'][d]['recall@10'] * 100:.1f}% | {coco['dims'][d]['recall@10_binary_rescore'] * 100:.1f}% |"
    for d in ("2048", "1024", "512", "256", "128")
) + f"""

## Scale

Generated records through the real engines. Word frequency follows a Zipf curve over 50,000 words. No model and no real files. Query vectors are random.

| Measure | Result |
|---|---|
{scale_table()}

## Model cost

{model_notes()}

| Setup | Images per second | RAM |
|---|---|---|
""" + "\n".join(f"| {r['label'].replace(chr(10), ', ')} | {r['images_per_s']:.2f} | {r['ram_gb']:.1f} GB |" for r in model["rows"]) + f"""

## Live stack

| Measure | Result |
|---|---|
| Full search, median | {ev['latency']['full']['p50_ms']} ms, mostly query embedding on CPU |
| Full search, slowest 5% | {ev['latency']['full']['p95_ms']} ms |
| Keyword only, median | {ev['latency']['keyword']['p50_ms']} ms |
| Full index, {run['files']} files | {run['index_minutes']:.0f} minutes, with other benchmarks running |
| New file searchable | {run['new_file_seconds']:.1f} s |
| Rename seen, no re-embedding | {run['rename_seconds']:.1f} s |
| Delete purged | {run['delete_seconds']:.1f} s |
| Index size | {run['index_mb']} MB for {run['files']} files |
| Idle memory, all but the model | {run['idle_mb']} MB |
| Model process memory | {run['embedder_gb']:.1f} GB |

## System checks

{passed} of {len(system)} pass, against the live Docker stack.

| Group | Passed |
|---|---|
{checks}

MCP tested with the official Python SDK: protocol 2025-11-25, 6 tools, bad keys rejected.

Not done: a full packet capture. The check that would have pulled a third-party capture image was blocked, so egress is covered by connection tests and connection-table sampling.
"""
if failing:
    results += "\nFailing:\n\n" + "\n".join(f"- {r['group']}: {r['name']}: {r['detail']}" for r in failing) + "\n"
(ROOT / "docs/RESULTS.md").write_text(results, "utf8")
print("tests", passed, "of", len(system), "| words in story:", len(story.split()), "| images:", story.count("!["))
