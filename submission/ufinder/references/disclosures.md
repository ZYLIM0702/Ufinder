# Disclosures

## Developed for this Hackathon

All of this Skill: the orchestration workflow, evidence ranking rules, graph note format and engine exchange format. The separate engine was also developed for this Hackathon: file table, graph resolver, hybrid search, gateway, tests and Web UI.

## UGREEN components used

UGOS Skill Creation Tool, Uliya, and the registered experts and CLI capabilities named in `SKILL.md`.

## Third-party components in this package

None. This package is Markdown only and contains no third-party code.

## Optional engine: separate from this package, not installed by this Skill

A working prototype, tested in Docker on a laptop. It has not been tested on a UGREEN NAS.

| Component | Purpose | Source | License |
|---|---|---|---|
| Qdrant 1.20.0 | vector index | github.com/qdrant/qdrant | Apache-2.0 |
| SQLite with FTS5 | file table, keyword search, graph | sqlite.org | Public domain |
| Qwen3-VL-Embedding-2B | text, image and video embeddings | github.com/QwenLM/Qwen3-VL-Embedding | Apache-2.0 |
| faster-whisper with Systran base weights | speech to text | github.com/SYSTRAN/faster-whisper | MIT |
| RapidOCR | text in images | github.com/RapidAI/RapidOCR | Apache-2.0 |
| PyTorch, Transformers, Sentence Transformers | model runtime | pytorch.org, huggingface.co | BSD-3-Clause, Apache-2.0 |
| FastAPI, Uvicorn, httpx | service layer | github.com/fastapi, github.com/encode | MIT, BSD-3-Clause |
| pypdfium2, python-docx, Pillow, NumPy | file parsing | pypi.org | Apache-2.0 or BSD-3-Clause, MIT, HPND, BSD-3-Clause |
| FFmpeg | video frames and audio | ffmpeg.org | LGPL or GPL, Debian package |

Test data only, not distributed: COCO val2017 photos, with faces blurred.

## External services and data flows

- This Skill calls no external service.
- Expert results go to the AI model Uliya is configured to use. If that is a cloud model, content leaves the NAS under that user setting.
- The engine runs with no internet route. An owner may connect their own model endpoint for chosen folders. That route is off by default and allows one host.

## AI tools used

- Claude Code (Anthropic, model Claude Opus 5.5): researched rules and documentation, drafted this Skill package and its references, wrote the engine prototype and tests, ran the static checker, and drafted documents and diagrams.
