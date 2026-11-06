# Market and positioning

Researched on 2026-11-06. Vendor claims are marked as such. Most AI NAS features are new, so independent testing is thin.

## The thesis

**Data handling is the largest problem in AI, not how smart the LLM is.**

A smarter model reading the wrong file gives a smarter wrong answer. A model that cannot find the file gives nothing. Fast, correct retrieval is what makes an LLM useful, and it needs no LLM at all.

## Evidence

| Claim | Source | Note |
|---|---|---|
| Through 2026, organizations will abandon 60% of AI projects unsupported by AI-ready data | [Gartner, Feb 2025](https://www.gartner.com/en/newsroom/press-releases/2025-02-26-lack-of-ai-ready-data-puts-ai-projects-at-risk) | A prediction |
| 63% of organizations lack confidence that they manage data the way AI needs | Same Gartner release, survey from July 2024 | Survey |
| Roughly 80 to 90% of enterprise data is unstructured | [IDC white paper for Box](https://blog.box.com/90-your-data-unstructured-and-its-full-untapped-value) | Vendor-sponsored, figures vary |
| Knowledge workers spend about 19% of their time searching for and gathering information | McKinsey 2012, as [widely cited](https://cottrillresearch.com/various-survey-statistics-workers-spend-too-much-time-searching-for-information/) | Old, secondary source |
| About 2.5 hours a day goes to finding information | IDC 2001, as [widely cited](https://www.m-files.com/blog/how-long-does-it-actually-take-to-find-a-document/) | Old, secondary source |

The search-time figures are old and come through secondary sources, so use them as direction, not precision.

## Market size

| Segment | Estimate | Source |
|---|---|---|
| All NAS, 2026 | USD 39B to 55B, depending on the firm | [MarketsandMarkets](https://www.marketsandmarkets.com/PressReleases/network-attached-storage.asp), [Roots Analysis](https://www.rootsanalysis.com/network-attached-storage-market) |
| Consumer NAS | USD 1.79B in 2024 to 3.81B in 2032, 9.9% a year | [Credence Research](https://www.credenceresearch.com/report/consumer-nas-market) |

Market reports disagree widely. Treat these as order of magnitude. Technavio's consumer estimate is much larger and cannot be reconciled with Credence.

## Competitors

| Product | What it does | Where it stops |
|---|---|---|
| **Synology** | AI Search in Drive, using embeddings | [Semantic indexing covers Synology Drive only and needs a GPU model](https://www.synology.com/en-us/dsm/7.3/software_spec/ai_console). Reports say Photos has no natural-language search |
| **QNAP Qsirch 7.1 AI Mode** | [Cross-media search with local VLM and LLM](https://www.qnap.com/en-us/news/2026/qnap-qsirch-integrates-on-premises-vlm-and-llm-ai-to-enhance-cross-media-semantic-search-on-nas). The closest rival | [Needs an x74 or higher NAS with a discrete GPU, 16 GB VRAM or more](https://www.qnap.com/en-us/software/qsirch) |
| **TerraMaster TOS 7** | [500+ REST APIs for agents](https://www.terra-master.com/blogs/news/f4-425-pro-features-ai-native-tos-7), conversational admin | Aimed at control of the NAS. Entry hardware limits local LLM work |
| **Zettlab** | [Offline OCR, transcription and semantic search](https://fstoppers.com/artificial-intelligence/zettlab-d6-launches-polished-new-nas-ambitions-beyond-storage-721137) | A rival hardware brand. [Early reviews](https://www.neowin.net/reviews/zettlab-d4-nas-review-alpha-software-ambitious-vision/) describe alpha software |
| **Minisforum N5** | [High-end local AI hardware with OpenClaw](https://www.tomshardware.com/pc-components/nas/minisforums-new-flagship-nas-comes-with-openclaw-pre-installed-strix-halo-powered-n5-max-can-run-a-local-ai-llm) | A hardware-first approach. Search claims are vendor-sourced |
| **UGREEN UGOS** | Photos semantic search, OCR, document Q&A, Uliya | Each app keeps its own understanding. The Skill catalog has no shared search |
| **Immich** | [CLIP smart search, self-hosted](https://docs.immich.app/features/search) | Photos and videos only. No documents, speech or graph |
| **Dropbox Dash** | [Cross-format search including video and audio](https://www.businesswire.com/news/home/20250424371851/en) | Cloud, paid. Your files leave home |
| **find, grep, ripgrep** | Fast exact matching | No meaning. Text only. Scans everything each time |

## Positioning

**Everyone else is adding a bigger brain. Ufinder builds the memory.**

| | LLM-first AI NAS | Ufinder |
|---|---|---|
| Core idea | Put a smarter model on the box | Put a better index under any model |
| Search needs | A GPU and an LLM | CPU and an index. No LLM |
| Cost of a search | Inference | About 20 ms of lookup, plus one query embedding |
| Understanding | Per app | One index across every file type |
| Relationships | Not modelled | A graph built from evidence |
| Privacy | Depends on the prompt and model | Enforced below the model |
| Agents | Tied to one assistant | MCP and REST for any agent |
| Model choice | The vendor's | Local Qwen by default, or your own endpoint |

Honest tradeoffs:

- QNAP's VLM route can answer richer questions than an index can, on far more expensive hardware.
- An LLM reads meaning that embeddings miss. Ufinder hands it the right files, and the Skill calls UGOS vision for the last check.
- Ufinder has a slow first index on CPU, which is why it runs in the background on a machine that never sleeps.

## Why this fits UGREEN

- **It makes every other Skill better.** Any agent that can reach the index needs fewer LLM turns.
- **It fits the hardware.** A 24/7 box with idle CPU is the right place for a slow first pass.
- **It uses what UGREEN built.** The Skill orchestrates Photos, documents, knowledge and surveillance experts.
- **It matches the model family.** Uliya runs on Qwen, per reviews, and Ufinder defaults to Qwen embeddings.
- **It has a path into UGOS.** Docker APP, Native APP, then a system service.

## Name check

- No "UFinder" trademark turned up in a [basic search](https://trademarks.justia.com/884/73/ufind-88473193.html). Nearby "UFIND" marks cover other goods, and [UltraFinder](https://www.componentsource.com/product/ultrafinder) is a Windows search product. This is not legal clearance.
- SkillHub 2.3 bans names that imply an official UGREEN product. "Ufinder" sits close to UGOS and Uliya, so state plainly that it is an independent project.
