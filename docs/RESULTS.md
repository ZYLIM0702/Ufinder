# Measured results

Generated from `engine/eval/results` by `submission/build_story.py`. Do not edit by hand.

Machine: Apple M2 Max, 64 GB. Docker runs through OrbStack (Linux, 12 CPUs, 16.8 GB). No UGREEN hardware was used.

## How the evaluation was run

1. The corpus and 56 queries were written before any search ran, with published default settings.
2. The first run failed: blending the graph into the ranking lowered recall from 0.88 to 0.62.
3. The 56 queries became the development set. Before any fix, 49 new queries were written and locked by hash (`engine/eval/results/holdout.sha256`).
4. The design was fixed using the development set only, then frozen.
5. The held-out set ran once.
6. Two bug fixes came after that run: clearing stale vectors on re-extraction, and a file name parser fix. Development recall and the 20-file result did not change. The held-out set was not rerun.

The corpus is synthetic and small. The connected queries were written to need the graph. Treat these as a demonstration, not a benchmark.

## Held-out set, 49 queries

464 files. Recall@10:

| Query type | Queries | Keyword | Vector | Keyword + vector |
|---|---|---|---|---|
| File name | 4 | 1.00 | 0.75 | 1.00 |
| Inside documents | 6 | 1.00 | 0.83 | 1.00 |
| Text in images | 4 | 1.00 | 1.00 | 1.00 |
| Spoken | 3 | 1.00 | 1.00 | 1.00 |
| Looks like | 24 | 0.08 | 0.96 | 0.96 |
| Connected | 8 | 0.54 | 0.37 | 0.51 |
| **All** | 49 | 0.47 | 0.84 | 0.90 |

Mean reciprocal rank:

| Query type | Queries | Keyword | Vector | Keyword + vector |
|---|---|---|---|---|
| File name | 4 | 1.00 | 0.15 | 0.83 |
| Inside documents | 6 | 0.81 | 0.22 | 0.81 |
| Text in images | 4 | 0.78 | 1.00 | 0.78 |
| Spoken | 3 | 0.83 | 0.54 | 0.83 |
| Looks like | 24 | 0.08 | 0.45 | 0.35 |
| Connected | 8 | 0.81 | 0.34 | 0.71 |
| **All** | 49 | 0.47 | 0.43 | 0.57 |

Show 20 files either way:

| Queries | Count | 20 direct | 10 direct + 10 connected |
|---|---|---|---|
| Connected | 8 | 0.60 | **0.90** |
| All | 49 | 0.91 | **0.96** |

T-shirt test, averaged over two held-out phrasings. 10 right photos, 10 shirts with another word, 10 photos with the word on a poster:

| Method | Right in top 10 | Wrong word | On a poster |
|---|---|---|---|
| Keyword only | 3 of 10 | 0 | 7 |
| Vector only | 7 of 10 | 0 | 3 |
| Keyword + vector | 6.5 of 10 | 0 | 3.5 |

## Development set, 56 queries, used to fix the design

| Query type | Queries | Keyword | Vector | Keyword + vector |
|---|---|---|---|---|
| File name | 6 | 1.00 | 0.83 | 1.00 |
| Inside documents | 8 | 1.00 | 1.00 | 1.00 |
| Text in images | 6 | 1.00 | 0.92 | 1.00 |
| Spoken | 4 | 0.88 | 1.00 | 0.88 |
| Looks like | 24 | 0.04 | 0.92 | 0.83 |
| Connected | 8 | 0.61 | 0.67 | 0.77 |
| **All** | 56 | 0.52 | 0.89 | 0.89 |

| Queries | Count | 20 direct | 10 direct + 10 connected |
|---|---|---|---|
| Connected | 8 | 0.82 | **0.93** |
| All | 56 | 0.97 | **0.93** |

| Method | Right in top 10 | Wrong word | On a poster |
|---|---|---|---|
| Keyword only | 3 of 10 | 0 | 7 |
| Vector only | 8 of 10 | 0 | 2 |
| Keyword + vector | 8 of 10 | 0 | 2 |

## Public benchmark

COCO val2017, first 1000 images by ID, first caption as the query, exact cosine, on GPU.

| Dimensions | Recall@1 | Recall@10 | 1-bit then rescore, recall@10 |
|---|---|---|---|
| 2048 | 63.9% | 95.8% | 95.7% |
| 1024 | 63.7% | 95.3% | 95.1% |
| 512 | 63.2% | 95.1% | 94.8% |
| 256 | 59.9% | 93.8% | 91.7% |
| 128 | 55.4% | 92.0% | 86.5% |

## Scale

Generated records through the real engines. Word frequency follows a Zipf curve over 50,000 words. No model and no real files. Query vectors are random.

| Measure | Result |
|---|---|
| Keyword search, median | 6.6 ms |
| Keyword search, slowest 5% | 10.5 ms |
| Keyword, vectors and graph, median | 20.8 ms, before query embedding |
| Keyword, vectors and graph, slowest 5% | 27.8 ms, before query embedding |
| Worst case, only very common words | 115 ms |
| Graph walk | 73 ms, touching 140 nodes of 200,000 |
| One exact ID found among 200,000 | Yes |
| Another user's file stayed hidden | Yes |
| SQLite on disk | 795 MB |
| Vector database | 867.9 MB in memory, 938MB on disk |

## Model cost

- The model card's default, `bfloat16`, ran 7× slower than `float32` on this CPU, which has to emulate it.
- `float32` reaches 0.94 images per second, but needs 9.5 GB of RAM.
- 8-bit quantization looked like the fix. It was slower, used more memory, and damaged the vectors: they matched the originals at only 0.62 cosine. Rejected.
- The real pipeline in Linux Docker, with OCR, took 4.7 seconds per image on 6 cores. For 100,000 photos, that is about 5.5 days in the background.

| Setup | Images per second | RAM |
|---|---|---|
| Apple GPU, bfloat16 | 2.42 | 0.8 GB |
| CPU, float32 | 0.94 | 9.5 GB |
| CPU, int8 | 0.42 | 13.7 GB |
| CPU, bfloat16 | 0.14 | 4.5 GB |
| Docker pipeline, with OCR | 0.21 | 8.3 GB |

## Live stack

| Measure | Result |
|---|---|
| Full search, median | 669.1 ms, mostly query embedding on CPU |
| Full search, slowest 5% | 713.8 ms |
| Keyword only, median | 0.6 ms |
| Full index, 464 files | 34 minutes, with other benchmarks running |
| New file searchable | 2.1 s |
| Rename seen, no re-embedding | 0.7 s |
| Delete purged | 0.7 s |
| Index size | 26 MB for 464 files |
| Idle memory, all but the model | 295 MB |
| Model process memory | 8.3 GB |

## System checks

85 of 85 pass, against the live Docker stack.

| Group | Passed |
|---|---|
| no internet | 10 of 10 |
| least privilege | 5 of 5 |
| read only | 3 of 3 |
| user segregation | 19 of 19 |
| exclusions | 4 of 4 |
| content tiers | 3 of 3 |
| key limits | 7 of 7 |
| audit | 2 of 2 |
| prompt injection | 3 of 3 |
| change tracking | 8 of 8 |
| missing files | 2 of 2 |
| skill bridge | 5 of 5 |
| languages | 1 of 1 |
| multimodal query | 1 of 1 |
| operators | 1 of 1 |
| models | 1 of 1 |
| model endpoint | 10 of 10 |

MCP tested with the official Python SDK: protocol 2025-11-25, 6 tools, bad keys rejected.

Not done: a full packet capture. The check that would have pulled a third-party capture image was blocked, so egress is covered by connection tests and connection-table sampling.
