# Ufinder

## 1. What it does

Ufinder finds any file on a UGREEN NAS by what is inside it, across photos, documents, recordings and video, and shows why each file matched.

## 2. User and problem

NAS owners with scattered terabytes. They remember content, not file names. UGOS has good AI, but each app keeps its own, and nothing records how files relate. Agents have no shared index, so they spend one LLM turn per file: slow locally, risky in the cloud.

## 3. Solution

The Skill turns one question into searches across every UGOS AI service and merges results with evidence. An optional local engine, installed by the owner, builds one permission-aware vector and graph index, so search needs no LLM.

## 4. User flow

The user asks Uliya: "find the photo of a man in a UGREEN T-shirt." The Skill searches each domain, verifies top photos with vision, and returns paths, reasons and evidence. Next: album, tags or graph notes. Every write needs approval.

## 5. Difference

Existing tools search one silo. We rank OCR, passage, transcript and vision evidence together, then walk a file graph to find files no word or picture matches, such as photos taken after a whiteboard session. Privacy sits below the LLM: read-only mounts, no internet route, per-user filtering.

## 6. NAS capabilities

Search: ug-photo search-picture and search-screen, ug-document qa, ug-knowledge collect-evidence, ug-video search, ug-filesystem find. Verify: vision-ocr, vision-vlm. Act: create-album, tag-add-file, save-text, file-workflow start and run.

## 7. Technical approach

The parent Skill only delegates, to photo-, document-, knowledge-, media- and file-agent. Inputs: request and scope. UGOS permissions and approvals apply. Rules forbid daemons and local API calls, so the owner installs the engine in Docker, and the Skill reads its files from the user's folder. Engine: SQLite file table, BM25 and graph; Qdrant vectors; rank fusion; personalized PageRank; local Qwen3-VL-Embedding-2B, Uliya's model family. Frontier models connect per folder, off by default. If Uliya uses a cloud model, content follows that setting, and the Skill warns first.

## 8. Status

Implemented: Skill package passing the static checker. Engine prototype, tested in Docker on a laptop: 85 of 85 system checks, recall@10 0.90 on 49 locked held-out queries, 95.1% on 1,000 COCO images. Not implemented: UGOS app packaging. Pending NAS validation: expert behaviour, approval prompts, exchange folder, iDX6011 Pro speed.

## 9. Validation

Core 1: find UGREEN T-shirt photos among poster and wrong-word decoys, native versus engine. Core 2: labelled content queries across documents and recordings, measuring recall@10. Edge: user B searches for user A's private file; expect zero leaks in results, snippets or graph.

## 10. Limits

Skill-only mode depends on Uliya's model speed. The engine's model needs about 9 GB of RAM, and a first index takes days on CPU. Test data is synthetic. We have no OS-level access: Docker gives no system change feed or UGOS identity, so we plan official UGOS Docker and Native app packages, with UGREEN's guidance. Running the engine on the judging NAS needs organizer confirmation. The Skill works without it.

## Third-party components, sources and licenses

| Component | Use | Source | License |
|---|---|---|---|
| UGOS Skill Creation Tool, Uliya | Skill platform | UGREEN | Per UGREEN terms |
| Qdrant 1.20.0 | Vector index | github.com/qdrant/qdrant | Apache-2.0 |
| SQLite with FTS5 | File table, keyword search, graph | sqlite.org | Public domain |
| Qwen3-VL-Embedding-2B | Embeddings | github.com/QwenLM/Qwen3-VL-Embedding | Apache-2.0 |
| faster-whisper, Systran base | Speech to text | github.com/SYSTRAN/faster-whisper | MIT |
| RapidOCR | Text in images | github.com/RapidAI/RapidOCR | Apache-2.0 |
| PyTorch, Transformers, Sentence Transformers | Model runtime | pytorch.org, huggingface.co | BSD-3-Clause, Apache-2.0 |
| FastAPI, Uvicorn, httpx | Service layer | github.com/fastapi, github.com/encode | MIT, BSD-3-Clause |
| pypdfium2, python-docx, Pillow, NumPy | File parsing | pypi.org | Apache-2.0 or BSD-3-Clause, MIT, HPND, BSD-3-Clause |
| FFmpeg | Video frames, audio | ffmpeg.org | LGPL or GPL |

External services and data flows: the Skill calls no external service. Expert results go to the AI model Uliya is set to use, which may be a cloud model under the user's setting. The engine runs with no internet route. An owner may connect a model endpoint for chosen folders, through one allowed host, off by default.

Test data, not distributed: COCO val2017 photos, faces blurred.

AI tools: Claude Code (Claude Opus 5.5) for research, Skill drafting, engine code and tests, proposal drafting, diagrams and static checks.
