# Ufinder

## 1. What it does

Ufinder finds any file on a UGREEN NAS by what is inside it, across photos, documents, recordings and video, and shows the evidence for every match.

## 2. User and problem

NAS owners with terabytes. AI's bottleneck is data, not model intelligence: a smarter LLM reading the wrong file still fails. People remember content, not file names. Each file type needs different AI, each UGOS app keeps its own, and nothing records how files relate. Agents spend one LLM turn per file.

## 3. Solution

The Skill turns one request into searches across UGOS AI services, ranked by evidence. An optional owner-installed engine reads each file once into one permission-aware vector and graph index, so search becomes a lookup, not an inference.

## 4. User flow

Ask Uliya: "find the photo of a man in a UGREEN T-shirt." The Skill searches each domain, verifies top photos with vision, and returns paths and evidence. Next: album, tags or notes. Every write needs approval.

## 5. Difference

Competitors race to fit bigger LLMs. Ufinder builds the memory underneath. One search spans text, speech and vision. A file graph then finds what no word or picture matches, like photos taken after a whiteboard session. Privacy sits below the LLM: read-only mounts, no internet route, per-user filtering.

## 6. NAS features

Search: ug-photo search-picture, search-screen; ug-document qa; ug-knowledge collect-evidence; ug-video search; ug-filesystem find. Verify: vision-ocr, vision-vlm. Understand: extract, reconcile, audio-transcription, scan-dedupe, event-timeline. Act: create-album, tag-add-file, save-text, file-workflow.

## 7. Technical approach

The parent Skill only delegates, to all six expert agents, through 16 functions. Inputs: request and scope. UGOS permissions and approvals apply. Rules forbid daemons and local APIs, so the owner installs the engine in Docker, and the Skill reads results from the user's folder. Engine: SQLite files, BM25 and graph; Qdrant vectors; personalized PageRank; local Qwen3-VL-Embedding-2B, Uliya's model family. Frontier models connect by endpoint, per folder, off by default. If Uliya uses a cloud model, the Skill warns first.

## 8. Built so far

Built: Skill, passing the static checker. Engine, tested in Docker on a laptop: 85 of 85 system checks; recall@10 0.90 on 49 locked queries; 95.1% on 1,000 COCO images; 21 ms lookup at 200,000 generated files, before query embedding. Not built: UGOS app packaging. NAS testing: expert behaviour, approvals, exchange folder, iDX6011 Pro speed.

## 9. Test plan

Core 1: find UGREEN T-shirt photos among poster and wrong-word decoys, native versus engine. Core 2: labelled queries across documents and recordings, measuring recall@10. Edge: user B searches for user A's private file; expect zero leaks in results, snippets or graph.

## 10. Limits

Skill-only speed depends on Uliya's model. The engine's model needs about 9 GB RAM, and a first index takes days on CPU, in the background on a 24/7 machine. Test data is synthetic. We have no OS-level access yet: Docker gives no change feed or UGOS identity, so we plan official UGOS apps. The engine on the judging NAS needs organizer confirmation. The Skill works without it.

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

Ufinder is an independent project, not an official UGREEN product.
